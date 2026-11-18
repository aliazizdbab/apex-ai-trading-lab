from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.crypto import SecretVault, mask_secret
from app.core.security import (
    build_totp_uri,
    generate_session_token,
    generate_totp_secret,
    hash_password,
    hash_session_token,
    verify_password,
    verify_totp_code,
)
from app.db.models import (
    AiCopilotConfig,
    ApiCredential,
    AuditLog,
    ExchangeConnection,
    Notification,
    User,
    UserSession,
    utcnow,
)
from app.db.session import get_db
from app.services.audit import append_audit_log, verify_audit_chain
from app.services.mexc_provider import get_cached_mexc_health, get_mexc_client
from exchanges.mexc.market_client import MexcMarketDataClient

router = APIRouter(prefix="/api/v1")


def _vault(settings: Settings = Depends(get_settings)) -> SecretVault:
    return SecretVault(settings.get_master_key_bytes())


def _normalize_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _extract_raw_token(request: Request, settings: Settings) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            return token
    cookie_token = request.cookies.get(settings.session_cookie_name)
    if cookie_token:
        return cookie_token.strip()
    return None


def get_optional_session_and_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> tuple[UserSession | None, User | None]:
    raw_token = _extract_raw_token(request, settings)
    if not raw_token:
        return None, None
    token_hash = hash_session_token(raw_token)
    session_row = db.execute(
        select(UserSession).where(
            UserSession.token_hash == token_hash,
            UserSession.revoked_at.is_(None),
        )
    ).scalar_one_or_none()
    if not session_row:
        return None, None
    if _normalize_utc(session_row.expires_at) <= utcnow():
        return None, None
    user = db.execute(select(User).where(User.id == session_row.user_id)).scalar_one_or_none()
    if not user or not user.is_active:
        return None, None
    return session_row, user


def require_owner(
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> tuple[UserSession, User]:
    session_row, user = ctx
    if not session_row or not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return session_row, user


def _issue_session(
    db: Session,
    response: Response,
    request: Request,
    user: User,
    settings: Settings,
) -> str:
    raw_token, token_hash = generate_session_token()
    now = utcnow()
    expires_at = now + timedelta(hours=settings.session_ttl_hours)
    session_row = UserSession(
        user_id=user.id,
        token_hash=token_hash,
        ip_address=request.client.host if request.client else None,
        user_agent=(request.headers.get("User-Agent") or "")[:255] or None,
        created_at=now,
        expires_at=expires_at,
    )
    db.add(session_row)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )
    return raw_token


def _user_summary(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "totp_enabled": user.totp_enabled,
    }


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class OwnerSetupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)
    totp_code: str | None = Field(default=None, max_length=12)


class TotpActivateRequest(BaseModel):
    totp_code: str = Field(min_length=6, max_length=12)


class SettingsUpdateRequest(BaseModel):
    theme: Literal["dark", "light"] | None = None
    lang: Literal["en", "ar"] | None = None
    sidebarCollapsed: bool | None = None


class CredentialCreateRequest(BaseModel):
    provider_type: Literal["exchange", "ai"]
    provider_name: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    api_key: str = Field(min_length=4, max_length=512)
    api_secret: str | None = Field(default=None, max_length=512)


# ---------------------------------------------------------------------------
# Health & Auth Status
# ---------------------------------------------------------------------------


@router.get("/health")
def health_check(
    db: Session = Depends(get_db),
    mexc_client: MexcMarketDataClient = Depends(get_mexc_client),
) -> dict[str, Any]:
    db_connected = False
    try:
        db.execute(text("SELECT 1"))
        db_connected = True
    except Exception:
        db_connected = False

    owner = db.execute(select(User).limit(1)).scalar_one_or_none() if db_connected else None
    chain_valid, _, _ = verify_audit_chain(db) if db_connected else (False, 0, "Database unavailable")
    mexc_state = get_cached_mexc_health(mexc_client)
    ai_connected = False
    if db_connected:
        has_copilot = (
            db.execute(select(AiCopilotConfig.id).where(AiCopilotConfig.enabled.is_(True)).limit(1)).scalar_one_or_none()
            is not None
        )
        has_ai_cred = (
            db.execute(select(ApiCredential.id).where(ApiCredential.provider_type == "ai").limit(1)).scalar_one_or_none()
            is not None
        )
        ai_connected = has_copilot or has_ai_cred

    return {
        "status": "ok" if db_connected else "degraded",
        "engine": "connected" if db_connected else "error",
        "mexc": mexc_state,
        "ai": "connected" if ai_connected else "disconnected",
        "database": "connected" if db_connected else "error",
        "auth_setup_completed": owner is not None,
        "totp_enabled": bool(owner.totp_enabled) if owner else False,
        "audit_chain_valid": chain_valid,
    }


@router.get("/auth/status")
def auth_status(
    db: Session = Depends(get_db),
    ctx: tuple[UserSession | None, User | None] = Depends(get_optional_session_and_user),
) -> dict[str, Any]:
    owner = db.execute(select(User).limit(1)).scalar_one_or_none()
    _, current_user = ctx
    return {
        "setup_completed": owner is not None,
        "authenticated": current_user is not None,
        "user": _user_summary(current_user) if current_user else None,
    }


# ---------------------------------------------------------------------------
# Owner Setup, Login, Logout, TOTP 2FA
# ---------------------------------------------------------------------------


@router.post("/auth/setup", status_code=status.HTTP_201_CREATED)
def setup_owner(
    payload: OwnerSetupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    vault: SecretVault = Depends(_vault),
) -> dict[str, Any]:
    existing = db.execute(select(User).limit(1)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Owner account already exists",
        )

    clean_email = payload.email.strip().lower()
    if "@" not in clean_email:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid email format")

    totp_secret = generate_totp_secret()
    user = User(
        email=clean_email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        totp_secret_encrypted=vault.encrypt(totp_secret),
        totp_enabled=False,
        preferences_json={"theme": "dark", "lang": "en", "sidebarCollapsed": False},
    )
    db.add(user)
    db.flush()

    raw_token = _issue_session(db, response, request, user, settings)
    append_audit_log(
        db,
        actor=clean_email,
        action="auth.owner_setup",
        entity=f"user:{user.id}",
        payload={"email": clean_email, "display_name": user.display_name},
        owner_id=user.id,
    )
    db.add(
        Notification(
            owner_id=user.id,
            level="info",
            category="security",
            title="Owner account initialized",
            body="Owner credentials stored with Argon2id. Activate TOTP 2FA to harden authentication.",
        )
    )
    db.commit()

    return {
        "user": _user_summary(user),
        "access_token": raw_token,
        "totp_secret": totp_secret,
        "totp_uri": build_totp_uri(totp_secret, clean_email),
    }


@router.post("/auth/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    vault: SecretVault = Depends(_vault),
) -> dict[str, Any]:
    clean_email = payload.email.strip().lower()
    user = db.execute(select(User).where(User.email == clean_email)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        append_audit_log(
            db,
            actor=clean_email,
            action="auth.login_failed",
            entity="auth",
            payload={"reason": "invalid_credentials"},
            owner_id=user.id if user else None,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_CREDENTIALS")

    if user.totp_enabled:
        if not payload.totp_code:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="TOTP_REQUIRED")
        if not user.totp_secret_encrypted:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="TOTP state inconsistent")
        totp_secret = vault.decrypt(user.totp_secret_encrypted)
        if not verify_totp_code(totp_secret, payload.totp_code):
            append_audit_log(
                db,
                actor=clean_email,
                action="auth.login_failed",
                entity=f"user:{user.id}",
                payload={"reason": "invalid_totp"},
                owner_id=user.id,
            )
            db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_TOTP")

    raw_token = _issue_session(db, response, request, user, settings)
    append_audit_log(
        db,
        actor=clean_email,
        action="auth.login",
        entity=f"user:{user.id}",
        payload={"totp_used": user.totp_enabled},
        owner_id=user.id,
    )
    db.commit()

    return {
        "user": _user_summary(user),
        "access_token": raw_token,
    }


@router.post("/auth/logout")
def logout(
    response: Response,
    ctx: tuple[UserSession, User] = Depends(require_owner),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    session_row, user = ctx
    session_row.revoked_at = utcnow()
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    append_audit_log(
        db,
        actor=user.email,
        action="auth.logout",
        entity=f"session:{session_row.id}",
        payload={},
        owner_id=user.id,
    )
    db.commit()
    return {"ok": True}


@router.post("/auth/totp/enroll")
def enroll_totp(
    ctx: tuple[UserSession, User] = Depends(require_owner),
    db: Session = Depends(get_db),
    vault: SecretVault = Depends(_vault),
) -> dict[str, Any]:
    _, user = ctx
    if user.totp_secret_encrypted and not user.totp_enabled:
        secret = vault.decrypt(user.totp_secret_encrypted)
    elif user.totp_enabled and user.totp_secret_encrypted:
        secret = vault.decrypt(user.totp_secret_encrypted)
    else:
        secret = generate_totp_secret()
        user.totp_secret_encrypted = vault.encrypt(secret)
        db.commit()

    return {
        "totp_secret": secret,
        "totp_uri": build_totp_uri(secret, user.email),
        "totp_enabled": user.totp_enabled,
    }


@router.post("/auth/totp/activate")
def activate_totp(
    payload: TotpActivateRequest,
    ctx: tuple[UserSession, User] = Depends(require_owner),
    db: Session = Depends(get_db),
    vault: SecretVault = Depends(_vault),
) -> dict[str, bool]:
    _, user = ctx
    if not user.totp_secret_encrypted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TOTP secret not enrolled")

    secret = vault.decrypt(user.totp_secret_encrypted)
    if not verify_totp_code(secret, payload.totp_code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="INVALID_TOTP")

    user.totp_enabled = True
    append_audit_log(
        db,
        actor=user.email,
        action="auth.totp_activated",
        entity=f"user:{user.id}",
        payload={"totp_enabled": True},
        owner_id=user.id,
    )
    db.add(
        Notification(
            owner_id=user.id,
            level="info",
            category="security",
            title="Two-factor authentication enabled",
            body="TOTP 2FA is now required on subsequent logins.",
        )
    )
    db.commit()
    return {"totp_enabled": True}


# ---------------------------------------------------------------------------
# User Preferences / Settings
# ---------------------------------------------------------------------------


@router.get("/settings")
def get_user_settings(ctx: tuple[UserSession, User] = Depends(require_owner)) -> dict[str, Any]:
    _, user = ctx
    prefs = user.preferences_json or {}
    return {
        "theme": prefs.get("theme", "dark"),
        "lang": prefs.get("lang", "en"),
        "sidebarCollapsed": bool(prefs.get("sidebarCollapsed", False)),
    }


@router.put("/settings")
def update_user_settings(
    payload: SettingsUpdateRequest,
    ctx: tuple[UserSession, User] = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _, user = ctx
    prefs = dict(user.preferences_json or {})
    if payload.theme is not None:
        prefs["theme"] = payload.theme
    if payload.lang is not None:
        prefs["lang"] = payload.lang
    if payload.sidebarCollapsed is not None:
        prefs["sidebarCollapsed"] = payload.sidebarCollapsed

    user.preferences_json = prefs
    append_audit_log(
        db,
        actor=user.email,
        action="settings.updated",
        entity=f"user:{user.id}",
        payload=prefs,
        owner_id=user.id,
    )
    db.commit()

    return {
        "theme": prefs.get("theme", "dark"),
        "lang": prefs.get("lang", "en"),
        "sidebarCollapsed": bool(prefs.get("sidebarCollapsed", False)),
    }


# ---------------------------------------------------------------------------
# Encrypted Credentials Vault (AES-256-GCM)
# ---------------------------------------------------------------------------


def _serialize_credential(row: ApiCredential) -> dict[str, Any]:
    return {
        "id": row.id,
        "provider_type": row.provider_type,
        "provider_name": row.provider_name,
        "label": row.label,
        "api_key_masked": row.api_key_masked,
        "has_secret": row.api_secret_encrypted is not None,
        "created_at": _normalize_utc(row.created_at).isoformat(),
    }


@router.get("/credentials")
def list_credentials(
    ctx: tuple[UserSession, User] = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _, user = ctx
    rows = db.execute(
        select(ApiCredential)
        .where(ApiCredential.owner_id == user.id)
        .order_by(ApiCredential.created_at.desc())
    ).scalars().all()
    return {"items": [_serialize_credential(row) for row in rows]}


@router.post("/credentials", status_code=status.HTTP_201_CREATED)
def create_credential(
    payload: CredentialCreateRequest,
    ctx: tuple[UserSession, User] = Depends(require_owner),
    db: Session = Depends(get_db),
    vault: SecretVault = Depends(_vault),
) -> dict[str, Any]:
    _, user = ctx
    clean_provider = payload.provider_name.strip().lower()
    clean_label = payload.label.strip()
    clean_key = payload.api_key.strip()
    clean_secret = payload.api_secret.strip() if payload.api_secret else None

    connection_id: str | None = None
    if payload.provider_type == "exchange":
        conn = ExchangeConnection(
            owner_id=user.id,
            exchange=clean_provider,
            label=clean_label,
            status="disconnected",
        )
        db.add(conn)
        db.flush()
        connection_id = conn.id

    cred = ApiCredential(
        owner_id=user.id,
        connection_id=connection_id,
        provider_type=payload.provider_type,
        provider_name=clean_provider,
        label=clean_label,
        api_key_masked=mask_secret(clean_key),
        api_key_encrypted=vault.encrypt(clean_key),
        api_secret_encrypted=vault.encrypt(clean_secret) if clean_secret else None,
    )
    db.add(cred)
    db.flush()

    append_audit_log(
        db,
        actor=user.email,
        action="credentials.created",
        entity=f"api_credential:{cred.id}",
        payload={
            "provider_type": payload.provider_type,
            "provider_name": clean_provider,
            "label": clean_label,
            "masked_key": cred.api_key_masked,
            "api_key": clean_key,
            "api_secret": clean_secret,
        },
        owner_id=user.id,
    )
    db.add(
        Notification(
            owner_id=user.id,
            level="info",
            category="security",
            title=f"Encrypted credential stored ({clean_provider})",
            body=f"API key {cred.api_key_masked} encrypted with AES-256-GCM.",
        )
    )
    db.commit()
    return _serialize_credential(cred)


@router.delete("/credentials/{cred_id}")
def delete_credential(
    cred_id: str,
    ctx: tuple[UserSession, User] = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    _, user = ctx
    cred = db.execute(
        select(ApiCredential).where(ApiCredential.id == cred_id, ApiCredential.owner_id == user.id)
    ).scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

    provider_name = cred.provider_name
    masked = cred.api_key_masked
    if cred.connection_id:
        conn = db.execute(
            select(ExchangeConnection).where(ExchangeConnection.id == cred.connection_id)
        ).scalar_one_or_none()
        if conn:
            db.delete(conn)

    db.delete(cred)
    append_audit_log(
        db,
        actor=user.email,
        action="credentials.deleted",
        entity=f"api_credential:{cred_id}",
        payload={"provider_name": provider_name, "masked_key": masked},
        owner_id=user.id,
    )
    db.add(
        Notification(
            owner_id=user.id,
            level="warning",
            category="security",
            title=f"Credential deleted ({provider_name})",
            body=f"Removed credential {masked} from vault.",
        )
    )
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


def _serialize_notification(row: Notification) -> dict[str, Any]:
    return {
        "id": row.id,
        "level": row.level,
        "category": row.category,
        "title": row.title,
        "body": row.body,
        "is_read": row.is_read,
        "created_at": _normalize_utc(row.created_at).isoformat(),
    }


@router.get("/notifications")
def list_notifications(
    ctx: tuple[UserSession, User] = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _, user = ctx
    rows = db.execute(
        select(Notification)
        .where((Notification.owner_id == user.id) | (Notification.owner_id.is_(None)))
        .order_by(Notification.created_at.desc())
        .limit(100)
    ).scalars().all()
    unread = db.execute(
        select(func.count(Notification.id)).where(
            ((Notification.owner_id == user.id) | (Notification.owner_id.is_(None))),
            Notification.is_read.is_(False),
        )
    ).scalar_one()
    return {
        "items": [_serialize_notification(row) for row in rows],
        "unread_count": int(unread),
    }


@router.post("/notifications/{notif_id}/read")
def mark_notification_read(
    notif_id: str,
    ctx: tuple[UserSession, User] = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _, user = ctx
    row = db.execute(
        select(Notification).where(
            Notification.id == notif_id,
            (Notification.owner_id == user.id) | (Notification.owner_id.is_(None)),
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    row.is_read = True
    db.commit()
    return _serialize_notification(row)


@router.post("/notifications/read-all")
def mark_all_notifications_read(
    ctx: tuple[UserSession, User] = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    _, user = ctx
    rows = db.execute(
        select(Notification).where(
            ((Notification.owner_id == user.id) | (Notification.owner_id.is_(None))),
            Notification.is_read.is_(False),
        )
    ).scalars().all()
    for row in rows:
        row.is_read = True
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Audit Logs (Append-only Hash Chain)
# ---------------------------------------------------------------------------


@router.get("/audit-logs")
def get_audit_logs(
    limit: int = 50,
    ctx: tuple[UserSession, User] = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _, user = ctx
    clamped_limit = max(1, min(limit, 200))
    chain_valid, total_entries, error = verify_audit_chain(db)
    rows = db.execute(
        select(AuditLog)
        .where((AuditLog.owner_id == user.id) | (AuditLog.owner_id.is_(None)))
        .order_by(AuditLog.id.desc())
        .limit(clamped_limit)
    ).scalars().all()

    return {
        "chain_valid": chain_valid,
        "total_entries": total_entries,
        "error": error,
        "items": [
            {
                "id": row.id,
                "ts": _normalize_utc(row.ts).isoformat(),
                "actor": row.actor,
                "action": row.action,
                "entity": row.entity,
                "payload_redacted": row.payload_redacted,
                "hash_prev": row.hash_prev,
                "entry_hash": row.entry_hash,
            }
            for row in rows
        ],
    }
