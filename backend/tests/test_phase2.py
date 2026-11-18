from __future__ import annotations

import base64
import os
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

from app.api.router import _vault
from app.core.config import Settings, get_settings
from app.core.crypto import SecretVault, mask_secret, redact_secrets
from app.core.security import (
    build_totp_uri,
    generate_totp_code,
    generate_totp_secret,
    hash_password,
    verify_password,
    verify_totp_code,
)
from app.db.models import (
    ApiCredential,
    AuditLog,
    Base,
    LiveAuthorization,
    LiveOrder,
    LiveTrade,
    PaperAccount,
    PaperOrder,
    PaperTrade,
)
from app.db.session import build_engine, get_db
from app.main import create_app
from app.services.audit import verify_audit_chain
from app.services.mexc_provider import get_mexc_client, reset_mexc_health_cache
from exchanges.mexc.market_client import MexcMarketDataClient


@pytest.fixture()
def isolated_env(tmp_path: Path):
    """Create an isolated SQLite DB and ephemeral AES-256-GCM key per test."""
    db_path = tmp_path / "test_apex.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    master_key_bytes = os.urandom(32)
    master_key_b64 = base64.urlsafe_b64encode(master_key_bytes).decode("ascii")

    test_settings = Settings(
        database_url=db_url,
        master_encryption_key=master_key_b64,
        session_ttl_hours=24,
    )
    test_engine = build_engine(db_url)
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(
        bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )

    app = create_app()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_settings():
        return test_settings

    def override_vault():
        return SecretVault(master_key_bytes)

    offline_client = MexcMarketDataClient(
        transport=httpx.MockTransport(lambda _req: httpx.Response(503, json={"msg": "offline in phase2 test"}))
    )
    reset_mexc_health_cache()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[_vault] = override_vault
    app.dependency_overrides[get_mexc_client] = lambda: offline_client

    with TestClient(app) as client:
        yield client, TestingSessionLocal, test_engine, master_key_bytes

    offline_client.close()
    reset_mexc_health_cache()
    test_engine.dispose()


def test_secret_vault_aes256_gcm_roundtrip_and_tamper_detection():
    key = os.urandom(32)
    vault = SecretVault(key)

    secret_text = "mx0vglDemoSecretKey987654321"
    ct1 = vault.encrypt(secret_text)
    ct2 = vault.encrypt(secret_text)

    assert ct1.startswith("v1:")
    assert ct1 != ct2  # Unique random 12-byte nonce per encryption
    assert secret_text not in ct1
    assert vault.decrypt(ct1) == secret_text
    assert vault.decrypt(ct2) == secret_text

    # Tampered ciphertext must raise ValueError
    tampered = ct1[:-2] + ("AA" if ct1[-2:] != "AA" else "BB")
    with pytest.raises(ValueError, match="Invalid or tampered ciphertext"):
        vault.decrypt(tampered)

    # Wrong key must raise ValueError
    other_vault = SecretVault(os.urandom(32))
    with pytest.raises(ValueError, match="Invalid or tampered ciphertext"):
        other_vault.decrypt(ct1)


def test_mask_and_redact_helpers():
    assert mask_secret("mx0vglABCDEF1234") == "mx0v...1234"
    assert mask_secret("short") == "••••••••"

    sample = {
        "provider_name": "mexc",
        "api_key": "raw-api-key-value",
        "nested": {"api_secret": "raw-secret", "label": "main"},
        "items": [{"token": "abc", "name": "keep"}],
    }
    redacted = redact_secrets(sample)
    assert redacted["provider_name"] == "mexc"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["api_secret"] == "[REDACTED]"
    assert redacted["nested"]["label"] == "main"
    assert redacted["items"][0]["token"] == "[REDACTED]"
    assert redacted["items"][0]["name"] == "keep"
    # Original dict remains untouched
    assert sample["api_key"] == "raw-api-key-value"


def test_argon2id_and_rfc6238_totp():
    pw = "SuperStrongOwnerPass!2026"
    pw_hash = hash_password(pw)
    assert pw_hash.startswith("$argon2id$")
    assert verify_password(pw, pw_hash) is True
    assert verify_password("WrongPass!2026", pw_hash) is False

    secret = generate_totp_secret()
    uri = build_totp_uri(secret, "owner@apex.local")
    assert uri.startswith("otpauth://totp/")
    assert f"secret={secret}" in uri

    now = int(time.time())
    code = generate_totp_code(secret, for_time=now)
    assert len(code) == 6 and code.isdigit()
    assert verify_totp_code(secret, code, for_time=now) is True
    assert verify_totp_code(secret, code, for_time=now + 30) is True  # window=1
    wrong_code = "000000" if code != "000000" else "999999"
    assert verify_totp_code(secret, wrong_code, for_time=now) is False


def test_structural_separation_between_paper_and_live_tables(isolated_env):
    _, _, engine, _ = isolated_env
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    expected_paper = {"paper_accounts", "paper_orders", "paper_trades"}
    expected_live = {"live_authorizations", "live_orders", "live_trades"}
    assert expected_paper.issubset(tables)
    assert expected_live.issubset(tables)

    for model in (PaperAccount, PaperOrder, PaperTrade, LiveAuthorization, LiveOrder, LiveTrade):
        col_names = {col.name for col in model.__table__.columns}
        assert "is_simulated" not in col_names


def test_full_phase2_api_auth_vault_notifications_and_audit_chain(isolated_env):
    client, SessionLocal, _, _ = isolated_env

    # 1. Health & Auth status before setup
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    h_data = health.json()
    assert h_data["status"] == "ok"
    assert h_data["engine"] == "connected"
    assert h_data["mexc"] == "disconnected"
    assert h_data["ai"] == "disconnected"
    assert h_data["auth_setup_completed"] is False
    assert h_data["audit_chain_valid"] is True

    status_resp = client.get("/api/v1/auth/status")
    assert status_resp.status_code == 200
    assert status_resp.json() == {"setup_completed": False, "authenticated": False, "user": None}

    # Unauthenticated protected calls must return 401
    assert client.get("/api/v1/settings").status_code == 401

    # 2. Owner setup + duplicate setup rejection (409)
    setup_resp = client.post(
        "/api/v1/auth/setup",
        json={
            "email": "Owner@ApexLab.io",
            "display_name": "Ali",
            "password": "StrongPassword!123",
        },
    )
    assert setup_resp.status_code == 201
    setup_data = setup_resp.json()
    assert setup_data["user"]["email"] == "owner@apexlab.io"
    assert setup_data["user"]["totp_enabled"] is False
    totp_secret = setup_data["totp_secret"]
    assert totp_secret
    assert setup_data["totp_uri"].startswith("otpauth://totp/")

    dup_resp = client.post(
        "/api/v1/auth/setup",
        json={
            "email": "second@apexlab.io",
            "display_name": "Attacker",
            "password": "AnotherPassword!123",
        },
    )
    assert dup_resp.status_code == 409

    # 3. Enroll & activate TOTP 2FA
    enroll_resp = client.post("/api/v1/auth/totp/enroll")
    assert enroll_resp.status_code == 200
    assert enroll_resp.json()["totp_secret"] == totp_secret

    bad_activate = client.post("/api/v1/auth/totp/activate", json={"totp_code": "000000" if generate_totp_code(totp_secret) != "000000" else "999999"})
    assert bad_activate.status_code == 400

    valid_code = generate_totp_code(totp_secret)
    activate_resp = client.post("/api/v1/auth/totp/activate", json={"totp_code": valid_code})
    assert activate_resp.status_code == 200
    assert activate_resp.json()["totp_enabled"] is True

    # 4. Logout & Login enforcing TOTP
    logout_resp = client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 200
    assert client.get("/api/v1/settings").status_code == 401

    login_no_totp = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@apexlab.io", "password": "StrongPassword!123"},
    )
    assert login_no_totp.status_code == 401
    assert login_no_totp.json()["detail"] == "TOTP_REQUIRED"

    wrong_totp = "000000" if valid_code != "000000" else "999999"
    login_bad_totp = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@apexlab.io", "password": "StrongPassword!123", "totp_code": wrong_totp},
    )
    assert login_bad_totp.status_code == 401
    assert login_bad_totp.json()["detail"] == "INVALID_TOTP"

    login_ok = client.post(
        "/api/v1/auth/login",
        json={
            "email": "owner@apexlab.io",
            "password": "StrongPassword!123",
            "totp_code": generate_totp_code(totp_secret),
        },
    )
    assert login_ok.status_code == 200
    assert login_ok.json()["user"]["totp_enabled"] is True

    # 5. Settings persistence
    put_settings = client.put(
        "/api/v1/settings",
        json={"theme": "light", "lang": "ar", "sidebarCollapsed": True},
    )
    assert put_settings.status_code == 200
    assert put_settings.json() == {"theme": "light", "lang": "ar", "sidebarCollapsed": True}
    assert client.get("/api/v1/settings").json() == {"theme": "light", "lang": "ar", "sidebarCollapsed": True}

    # 6. Encrypted Credentials Vault
    raw_api_key = "mx0vglSuperRealKey9999"
    raw_api_secret = "superSecretValueXYZ123456"
    cred_resp = client.post(
        "/api/v1/credentials",
        json={
            "provider_type": "exchange",
            "provider_name": "mexc",
            "label": "MEXC Spot Main",
            "api_key": raw_api_key,
            "api_secret": raw_api_secret,
        },
    )
    assert cred_resp.status_code == 201
    cred_data = cred_resp.json()
    assert cred_data["api_key_masked"] == "mx0v...9999"
    assert cred_data["has_secret"] is True
    assert raw_api_key not in str(cred_data)
    assert raw_api_secret not in str(cred_data)

    # Verify raw plaintext does NOT appear in the DB row
    with SessionLocal() as db:
        stored = db.query(ApiCredential).filter(ApiCredential.id == cred_data["id"]).one()
        assert raw_api_key not in stored.api_key_encrypted
        assert stored.api_secret_encrypted is not None
        assert raw_api_secret not in stored.api_secret_encrypted

    list_creds = client.get("/api/v1/credentials")
    assert list_creds.status_code == 200
    assert len(list_creds.json()["items"]) == 1

    # 7. Notifications flow
    notifs_resp = client.get("/api/v1/notifications")
    assert notifs_resp.status_code == 200
    notifs = notifs_resp.json()
    assert notifs["unread_count"] >= 2
    first_id = notifs["items"][0]["id"]

    mark_one = client.post(f"/api/v1/notifications/{first_id}/read")
    assert mark_one.status_code == 200
    assert mark_one.json()["is_read"] is True

    mark_all = client.post("/api/v1/notifications/read-all")
    assert mark_all.status_code == 200
    assert client.get("/api/v1/notifications").json()["unread_count"] == 0

    # 8. Audit log hash chain & secret redaction + tamper detection
    audit_resp = client.get("/api/v1/audit-logs")
    assert audit_resp.status_code == 200
    audit_data = audit_resp.json()
    assert audit_data["chain_valid"] is True
    assert audit_data["total_entries"] >= 4

    cred_logs = [item for item in audit_data["items"] if item["action"] == "credentials.created"]
    assert len(cred_logs) == 1
    assert cred_logs[0]["payload_redacted"]["api_key"] == "[REDACTED]"
    assert cred_logs[0]["payload_redacted"]["api_secret"] == "[REDACTED]"
    assert raw_api_key not in str(cred_logs[0])
    assert raw_api_secret not in str(cred_logs[0])

    # Tamper with an audit log row directly in DB and verify detection
    with SessionLocal() as db:
        row = db.query(AuditLog).order_by(AuditLog.id.asc()).first()
        assert row is not None
        row.action = "tampered.action"
        db.commit()
        valid, _, err = verify_audit_chain(db)
        assert valid is False
        assert err is not None

    tampered_audit_resp = client.get("/api/v1/audit-logs")
    assert tampered_audit_resp.status_code == 200
    assert tampered_audit_resp.json()["chain_valid"] is False

    # Delete credential cleanup check
    del_resp = client.delete(f"/api/v1/credentials/{cred_data['id']}")
    assert del_resp.status_code == 200
    assert client.get("/api/v1/credentials").json()["items"] == []
