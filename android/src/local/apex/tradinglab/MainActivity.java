package local.apex.tradinglab;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.ViewGroup;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import org.json.JSONArray;
import org.json.JSONObject;

public class MainActivity extends Activity {
    private static final String CURRENT_VERSION = "1.1.0";
    private static final String GITHUB_LATEST_API =
            "https://api.github.com/repos/aliazizdbab/apex-ai-trading-lab/releases/latest";
    private static final String LOCAL_APP_HOST = "appassets.apex.local";

    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        webView.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
        webView.setBackgroundColor(Color.parseColor("#0b0f17"));
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setLayoutAlgorithm(WebSettings.LayoutAlgorithm.TEXT_AUTOSIZING);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (LOCAL_APP_HOST.equals(uri.getHost())) {
                    return serveLocalAsset(uri.getPath());
                }
                return super.shouldInterceptRequest(view, request);
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (uri != null && "https".equals(uri.getScheme()) && !LOCAL_APP_HOST.equals(uri.getHost())) {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                    return true;
                }
                return false;
            }
        });

        setContentView(webView);
        webView.loadUrl("https://" + LOCAL_APP_HOST + "/");
        checkGithubUpdateInBackground();
    }

    private WebResourceResponse serveLocalAsset(String rawPath) {
        if (rawPath != null && rawPath.startsWith("/api/")) {
            byte[] payload = "{\"detail\":\"standalone_mobile_mode\"}"
                    .getBytes(java.nio.charset.StandardCharsets.UTF_8);
            return new WebResourceResponse(
                    "application/json",
                    "UTF-8",
                    404,
                    "Not Found",
                    null,
                    new java.io.ByteArrayInputStream(payload));
        }
        String cleanPath = (rawPath == null || rawPath.equals("/") || rawPath.isEmpty())
                ? "index.html"
                : rawPath.replaceFirst("^/+", "");
        if (!cleanPath.contains(".")) {
            cleanPath = "index.html";
        }
        String assetPath = "www/" + cleanPath;
        try {
            InputStream stream = getAssets().open(assetPath);
            return new WebResourceResponse(guessMimeType(cleanPath), "UTF-8", stream);
        } catch (IOException ex) {
            try {
                InputStream fallback = getAssets().open("www/index.html");
                return new WebResourceResponse("text/html", "UTF-8", fallback);
            } catch (IOException ignored) {
                return null;
            }
        }
    }

    private String guessMimeType(String path) {
        String lower = path.toLowerCase();
        if (lower.endsWith(".html")) return "text/html";
        if (lower.endsWith(".js") || lower.endsWith(".mjs")) return "application/javascript";
        if (lower.endsWith(".css")) return "text/css";
        if (lower.endsWith(".svg")) return "image/svg+xml";
        if (lower.endsWith(".json") || lower.endsWith(".webmanifest")) return "application/json";
        if (lower.endsWith(".png")) return "image/png";
        return "application/octet-stream";
    }

    private void checkGithubUpdateInBackground() {
        new Thread(() -> {
            try {
                HttpURLConnection conn = (HttpURLConnection) new URL(GITHUB_LATEST_API).openConnection();
                conn.setRequestMethod("GET");
                conn.setConnectTimeout(7000);
                conn.setReadTimeout(7000);
                conn.setRequestProperty("Accept", "application/vnd.github+json");
                conn.setRequestProperty("User-Agent", "APEX-Android-Updater/" + CURRENT_VERSION);
                if (conn.getResponseCode() != 200) {
                    return;
                }
                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder sb = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) {
                    sb.append(line);
                }
                reader.close();
                JSONObject json = new JSONObject(sb.toString());
                String latestTag = json.optString("tag_name", "v" + CURRENT_VERSION);
                String latestVer = latestTag.replaceFirst("^[vV]", "");
                if (!latestVer.equals(CURRENT_VERSION) && isNewerSemver(latestVer, CURRENT_VERSION)) {
                    String apkUrl = json.optString(
                            "html_url",
                            "https://github.com/aliazizdbab/apex-ai-trading-lab/releases/latest");
                    JSONArray assets = json.optJSONArray("assets");
                    if (assets != null) {
                        for (int i = 0; i < assets.length(); i++) {
                            JSONObject a = assets.getJSONObject(i);
                            if (a.optString("name", "").toLowerCase().endsWith(".apk")) {
                                apkUrl = a.optString("browser_download_url", apkUrl);
                                break;
                            }
                        }
                    }
                    final String downloadUrl = apkUrl;
                    runOnUiThread(() -> new AlertDialog.Builder(MainActivity.this)
                            .setTitle("APEX Update Available (" + latestTag + ")")
                            .setMessage("A newer release (" + latestTag + ") is available on GitHub.")
                            .setPositiveButton("Download APK", (d, w) ->
                                    startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(downloadUrl))))
                            .setNegativeButton("Later", null)
                            .show());
                }
            } catch (Exception ignored) {
            }
        }).start();
    }

    private boolean isNewerSemver(String remote, String current) {
        String[] r = remote.split("\\.");
        String[] c = current.split("\\.");
        int len = Math.max(r.length, c.length);
        for (int i = 0; i < len; i++) {
            int rv = i < r.length ? parseIntSafe(r[i]) : 0;
            int cv = i < c.length ? parseIntSafe(c[i]) : 0;
            if (rv != cv) return rv > cv;
        }
        return false;
    }

    private int parseIntSafe(String s) {
        try {
            return Integer.parseInt(s.replaceAll("[^0-9]", ""));
        } catch (Exception e) {
            return 0;
        }
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
