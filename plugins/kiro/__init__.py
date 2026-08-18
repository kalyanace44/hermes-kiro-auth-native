import os
import sys
import time
import atexit
import signal
import subprocess
import shutil
import urllib.request
import urllib.parse
import urllib.error
import json
import logging
import sqlite3
import threading
import webbrowser
from datetime import datetime, timezone

logger = logging.getLogger("hermes.plugins.kiro")

PORT = 8997           # External port Hermes connects to (Python compaction proxy)
INTERNAL_PORT = 8996  # Go gateway listens here
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(PLUGIN_DIR, "bin")
BIN_PATH = os.path.join(BIN_DIR, "go-kiro-gateway")

_gateway_process = None

# ── Isolated Hermes Auth Store ────────────────────────────────────────
HERMES_DIR = os.path.expanduser("~/.hermes")
HERMES_KIRO_DB = os.path.join(HERMES_DIR, "kiro-auth.sqlite3")
HERMES_KIRO_ACCOUNTS = os.path.join(HERMES_DIR, "kiro-accounts.json")

# AWS SSO OIDC defaults
SSO_OIDC_ENDPOINT = "https://oidc.{region}.amazonaws.com"
DEFAULT_SSO_REGION = "ap-south-1"
DEFAULT_API_REGION = "eu-central-1"
DEFAULT_START_URL = "https://vegapay.awsapps.com/start"
DEFAULT_PROFILE_ARN = "arn:aws:codewhisperer:eu-central-1:020807489866:profile/EUWNCR9VVUM7"

SSO_SCOPES = ["codewhisperer:completions", "codewhisperer:analysis", "codewhisperer:conversations"]
SSO_CLIENT_NAME = "hermes-kiro-plugin"
SSO_CLIENT_TYPE = "public"
SSO_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
SSO_REFRESH_GRANT = "refresh_token"


# ── Time / Timestamp Helpers ──────────────────────────────────────────
def format_iso_time(timestamp: float | int | None = None) -> str:
    """Format timestamp into ISO 8601 UTC string (required by go-kiro-gateway)."""
    if timestamp is None:
        timestamp = time.time()
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_expiry_timestamp(expires_val) -> int:
    """Parse integer, float, or ISO string expiry into epoch integer."""
    if not expires_val:
        return 0
    if isinstance(expires_val, (int, float)):
        return int(expires_val)
    if isinstance(expires_val, str):
        try:
            return int(datetime.fromisoformat(expires_val.replace("Z", "+00:00")).timestamp())
        except Exception:
            try:
                return int(float(expires_val))
            except Exception:
                return 0
    return 0


# ── Accounts JSON Management ──────────────────────────────────────────
def get_accounts_file_path() -> str:
    return HERMES_KIRO_ACCOUNTS


def load_accounts_data() -> dict:
    path = get_accounts_file_path()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"version": 1, "accounts": [], "activeIndex": 0}


def save_accounts_data(data: dict):
    path = get_accounts_file_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def get_active_account() -> dict | None:
    data = load_accounts_data()
    accounts = data.get("accounts", [])
    if not accounts:
        return None
    active_idx = data.get("activeIndex", 0)
    if active_idx < 0 or active_idx >= len(accounts):
        active_idx = 0
    return accounts[active_idx]


# ── Isolated SQLite DB for go-kiro-gateway ────────────────────────────
def init_hermes_kiro_db():
    """Create the isolated SQLite DB with the schema go-kiro-gateway expects."""
    os.makedirs(HERMES_DIR, exist_ok=True)
    conn = sqlite3.connect(HERMES_KIRO_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS auth_kv (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()


def write_credentials_to_db(device_registration: dict, token_data: dict):
    """Write credentials to isolated Hermes SQLite DB with ISO string timestamps."""
    init_hermes_kiro_db()

    # Ensure device registration has both casing styles
    reg_copy = dict(device_registration)
    if "clientId" in reg_copy and "client_id" not in reg_copy:
        reg_copy["client_id"] = reg_copy["clientId"]
    if "clientSecret" in reg_copy and "client_secret" not in reg_copy:
        reg_copy["client_secret"] = reg_copy["clientSecret"]

    # Ensure token data has ISO strings for expires_at / expiresAt
    tok_copy = dict(token_data)
    if "accessToken" in tok_copy and "access_token" not in tok_copy:
        tok_copy["access_token"] = tok_copy["accessToken"]
    if "refreshToken" in tok_copy and "refresh_token" not in tok_copy:
        tok_copy["refresh_token"] = tok_copy["refreshToken"]

    exp_ts = parse_expiry_timestamp(tok_copy.get("expires_at") or tok_copy.get("expiresAt"))
    if exp_ts <= 0:
        exp_ts = int(time.time()) + 3600

    iso_expiry = format_iso_time(exp_ts)
    tok_copy["expires_at"] = iso_expiry
    tok_copy["expiresAt"] = iso_expiry  # Must be string for Go struct JSON unmarshal

    conn = sqlite3.connect(HERMES_KIRO_DB)
    conn.execute(
        "INSERT OR REPLACE INTO auth_kv (key, value) VALUES (?, ?)",
        ("kirocli:odic:device-registration", json.dumps(reg_copy))
    )
    conn.execute(
        "INSERT OR REPLACE INTO auth_kv (key, value) VALUES (?, ?)",
        ("kirocli:odic:token", json.dumps(tok_copy))
    )
    conn.commit()
    conn.close()


def read_token_from_db() -> dict | None:
    """Read token from isolated Hermes SQLite DB."""
    if not os.path.exists(HERMES_KIRO_DB):
        return None
    try:
        conn = sqlite3.connect(HERMES_KIRO_DB)
        cur = conn.cursor()
        cur.execute("SELECT value FROM auth_kv WHERE key='kirocli:odic:token'")
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return json.loads(row[0])
    except Exception:
        pass
    return None


def read_device_registration_from_db() -> dict | None:
    """Read device registration from isolated Hermes SQLite DB."""
    if not os.path.exists(HERMES_KIRO_DB):
        return None
    try:
        conn = sqlite3.connect(HERMES_KIRO_DB)
        cur = conn.cursor()
        cur.execute("SELECT value FROM auth_kv WHERE key='kirocli:odic:device-registration'")
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return json.loads(row[0])
    except Exception:
        pass
    return None


# ── Token Refresh ─────────────────────────────────────────────────────
def refresh_sso_token(client_id: str, client_secret: str, refresh_token: str, region: str = DEFAULT_SSO_REGION) -> dict:
    """Refresh the SSO OIDC token using the refresh token."""
    url = SSO_OIDC_ENDPOINT.format(region=region) + "/token"
    body = json.dumps({
        "clientId": client_id,
        "clientSecret": client_secret,
        "grantType": SSO_REFRESH_GRANT,
        "refreshToken": refresh_token
    }).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def ensure_fresh_token() -> bool:
    """Check token expiry and refresh if needed. Updates the DB."""
    token_data = read_token_from_db()
    if not token_data:
        return False

    expires_at_ts = parse_expiry_timestamp(token_data.get("expires_at") or token_data.get("expiresAt"))
    now = int(time.time())

    # Still valid if more than 5 minutes remaining
    if expires_at_ts > (now + 300):
        return True

    # Token is expired or expiring soon — refresh it
    device_reg = read_device_registration_from_db()
    if not device_reg:
        return False

    client_id = device_reg.get("client_id") or device_reg.get("clientId")
    client_secret = device_reg.get("client_secret") or device_reg.get("clientSecret")
    refresh_tok = token_data.get("refresh_token") or token_data.get("refreshToken")
    region = device_reg.get("region") or token_data.get("region") or DEFAULT_SSO_REGION

    if not all([client_id, client_secret, refresh_tok]):
        return False

    try:
        new_token = refresh_sso_token(client_id, client_secret, refresh_tok, region)
        access_tok = new_token.get("accessToken") or new_token.get("access_token")
        if not access_tok:
            return False

        token_data["access_token"] = access_tok
        token_data["accessToken"] = access_tok
        if new_token.get("refreshToken") or new_token.get("refresh_token"):
            new_ref = new_token.get("refreshToken") or new_token.get("refresh_token")
            token_data["refresh_token"] = new_ref
            token_data["refreshToken"] = new_ref

        expires_in = new_token.get("expiresIn", new_token.get("expires_in", 3600))
        new_exp_ts = int(time.time()) + expires_in
        token_data["expires_at"] = format_iso_time(new_exp_ts)
        token_data["expiresAt"] = format_iso_time(new_exp_ts)

        write_credentials_to_db(device_reg, token_data)
        logger.info("[Kiro] Successfully refreshed SSO token.")
        return True
    except Exception as e:
        logger.error(f"[Kiro] SSO token refresh error: {e}")
        return False


# ── Import from Kiro CLI (Bootstrap / Re-import) ───────────────────────
def find_kiro_cli_db() -> str | None:
    """Find the Kiro CLI SQLite database on the system."""
    candidates = [
        os.path.expanduser("~/Library/Application Support/kiro-cli/data.sqlite3"),
        os.path.expanduser("~/.local/share/kiro-cli/data.sqlite3"),
        os.path.expanduser("~/.local/share/amazon-q/data.sqlite3"),
        os.path.expanduser("~/.config/kiro-cli/data.sqlite3"),
    ]
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(os.path.join(appdata, "kiro-cli", "data.sqlite3"))
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        candidates.append(os.path.join(localappdata, "kiro-cli", "data.sqlite3"))

    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def import_from_kiro_cli(force: bool = False) -> bool:
    """Import credentials from Kiro CLI SQLite into isolated Hermes store."""
    if not force and read_token_from_db() is not None:
        return True

    cli_db = find_kiro_cli_db()
    if not cli_db:
        return False

    try:
        conn = sqlite3.connect(cli_db)
        cur = conn.cursor()

        cur.execute("SELECT value FROM auth_kv WHERE key='kirocli:odic:device-registration'")
        reg_row = cur.fetchone()

        cur.execute("SELECT value FROM auth_kv WHERE key='kirocli:odic:token'")
        tok_row = cur.fetchone()

        conn.close()

        if reg_row and tok_row and reg_row[0] and tok_row[0]:
            device_reg = json.loads(reg_row[0])
            token_data = json.loads(tok_row[0])

            arn, sso_reg, api_reg = get_profile_info()
            if arn:
                device_reg["profileArn"] = arn
                device_reg["profile_arn"] = arn

            write_credentials_to_db(device_reg, token_data)

            # Update accounts file
            data = load_accounts_data()
            sso_region = device_reg.get("region") or token_data.get("region") or sso_reg
            start_url = token_data.get("start_url") or device_reg.get("startUrl") or DEFAULT_START_URL

            data["accounts"] = [{
                "source": "imported-from-kiro-cli",
                "ssoRegion": sso_region,
                "apiRegion": api_reg,
                "startUrl": start_url,
                "profileArn": arn,
                "importedAt": int(time.time())
            }]
            data["activeIndex"] = 0
            save_accounts_data(data)

            logger.info("[Kiro] Imported credentials from Kiro CLI into isolated Hermes store.")
            return True
    except Exception as e:
        logger.error(f"[Kiro] Failed to import from Kiro CLI: {e}")

    return False


# ── Gateway Binary Management ─────────────────────────────────────────
def get_binary_url() -> str:
    machine = os.uname().machine.lower()
    system = os.uname().sysname.lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "amd64"
    if "darwin" in system:
        os_name = "darwin"
    elif "linux" in system:
        os_name = "linux"
    else:
        os_name = "windows"
        arch += ".exe"
    return f"https://github.com/chasedputnam/go-kiro-gateway/releases/latest/download/go-kiro-gateway-{os_name}-{arch}"


def ensure_binary() -> str | None:
    if os.path.exists(BIN_PATH) and os.access(BIN_PATH, os.X_OK):
        return BIN_PATH
    os.makedirs(BIN_DIR, exist_ok=True)
    url = get_binary_url()
    logger.info(f"[Kiro] Downloading Kiro gateway binary from {url}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Hermes-Agent/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp, open(BIN_PATH, "wb") as f:
            f.write(resp.read())
        os.chmod(BIN_PATH, 0o755)
        logger.info("[Kiro] Binary downloaded successfully.")
        return BIN_PATH
    except Exception as e:
        logger.error(f"[Kiro] Failed to download binary: {e}")
        return None


# ── Profile & Region Resolution ───────────────────────────────────────
def get_profile_info() -> tuple[str, str, str]:
    """
    Returns (profile_arn, sso_region, api_region).
    CodeWhisperer API endpoints are in eu-central-1 or us-east-1,
    while SSO OIDC can be in ap-south-1, eu-central-1, etc.
    """
    device_reg = read_device_registration_from_db() or {}
    token_data = read_token_from_db() or {}

    sso_region = device_reg.get("region") or token_data.get("region") or DEFAULT_SSO_REGION
    profile_arn = device_reg.get("profileArn") or device_reg.get("profile_arn")

    # Try resolving via kiro-cli whoami
    if not profile_arn:
        for cmd in ["kiro-cli", "kiro"]:
            for prefix in [os.path.expanduser("~/.local/bin"), "/usr/local/bin", ""]:
                exe = os.path.join(prefix, cmd) if prefix else shutil.which(cmd)
                if exe and os.path.exists(exe):
                    try:
                        out = subprocess.check_output([exe, "whoami"], stderr=subprocess.DEVNULL, timeout=5).decode("utf-8")
                        for line in out.splitlines():
                            if "arn:aws:codewhisperer:" in line:
                                profile_arn = line.strip()
                                break
                    except Exception:
                        pass
                if profile_arn:
                    break
            if profile_arn:
                break

    if not profile_arn:
        profile_arn = DEFAULT_PROFILE_ARN

    # Determine API region from profile ARN or default
    api_region = DEFAULT_API_REGION
    if profile_arn and "arn:aws:codewhisperer:" in profile_arn:
        parts = profile_arn.split(":")
        if len(parts) >= 4 and parts[3] in ("eu-central-1", "us-east-1"):
            api_region = parts[3]

    return profile_arn, sso_region, api_region


# ── Gateway Lifecycle ─────────────────────────────────────────────────
def is_port_in_use(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def is_gateway_healthy(port: int = PORT) -> bool:
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/health")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def kill_existing_gateway():
    try:
        subprocess.run(["pkill", "-9", "go-kiro-gateway"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except Exception:
        pass


def start_gateway():
    global _gateway_process

    if is_gateway_healthy(INTERNAL_PORT):
        logger.info(f"[Kiro] Gateway already healthy on port {INTERNAL_PORT}.")
        return

    # If port has lingering non-responsive process, clean it up
    if is_port_in_use(INTERNAL_PORT):
        kill_existing_gateway()
        time.sleep(0.5)

    bin_file = ensure_binary()
    if not bin_file:
        logger.error("[Kiro] Cannot start gateway: binary unavailable.")
        return

    # If no credentials in isolated Hermes store, skip startup — user must run /kiro-login
    if not read_token_from_db():
        logger.info("[Kiro] No credentials in isolated store. Skipping gateway start. Run /kiro-login to authenticate.")
        return

    # Pre-flight token refresh if needed
    ensure_fresh_token()

    profile_arn, sso_region, api_region = get_profile_info()

    env = os.environ.copy()
    env["PROXY_API_KEY"] = "mock"
    env["KIRO_REGION"] = api_region
    env["PROFILE_ARN"] = profile_arn
    env["KIRO_CLI_DB_FILE"] = HERMES_KIRO_DB

    log_path = os.path.join(HERMES_DIR, "logs", "kiro-gateway.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    log_file = open(log_path, "a", encoding="utf-8")

    logger.info(f"[Kiro] Launching Kiro gateway on port {PORT} (API region: {api_region}, SSO region: {sso_region}, DB: {HERMES_KIRO_DB})...")

    try:
        _gateway_process = subprocess.Popen(
            [bin_file, "-port", str(INTERNAL_PORT)],
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid if hasattr(os, "setsid") else None
        )

        for _ in range(30):
            time.sleep(0.2)
            if is_gateway_healthy(INTERNAL_PORT):
                logger.info(f"[Kiro] Gateway successfully listening on http://127.0.0.1:{INTERNAL_PORT}")
                break
    except Exception as e:
        logger.error(f"[Kiro] Failed to launch gateway process: {e}")


def stop_gateway():
    global _gateway_process
    if _gateway_process:
        try:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(_gateway_process.pid), signal.SIGTERM)
            else:
                _gateway_process.terminate()
        except Exception:
            pass
        _gateway_process = None


def restart_gateway():
    stop_gateway()
    kill_existing_gateway()
    time.sleep(0.5)
    start_gateway()


# ── Periodic Token & Process Watcher ──────────────────────────────────
def _start_token_watcher():
    """Periodically check token freshness and ensure gateway is running."""
    def watch_loop():
        while True:
            time.sleep(300)  # Check every 5 minutes
            try:
                ensure_fresh_token()
                if not is_port_in_use(INTERNAL_PORT):
                    logger.info("[Kiro] Gateway not responding on port 8996, restarting...")
                    start_gateway()
            except Exception:
                pass

    t = threading.Thread(target=watch_loop, daemon=True)
    t.start()


# ── OAuth Device Flow for /kiro-login ─────────────────────────────────
def perform_sso_login(region: str = None, start_url: str = None) -> tuple[bool, str]:
    """Perform AWS SSO OIDC device authorization flow directly into isolated Hermes store."""
    data = load_accounts_data()
    active = get_active_account() or {}

    resolved_region = region.strip() if region and region.strip() else (active.get("ssoRegion") or DEFAULT_SSO_REGION)
    resolved_start_url = start_url.strip() if start_url and start_url.strip() else (active.get("startUrl") or DEFAULT_START_URL)

    base_url = SSO_OIDC_ENDPOINT.format(region=resolved_region)

    try:
        # Step 1: Register client
        register_body = json.dumps({
            "clientName": SSO_CLIENT_NAME,
            "clientType": SSO_CLIENT_TYPE,
            "scopes": SSO_SCOPES
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{base_url}/client/register",
            data=register_body,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            client_data = json.loads(resp.read().decode("utf-8"))

        client_id = client_data["clientId"]
        client_secret = client_data["clientSecret"]

        # Step 2: Start device authorization
        device_body = json.dumps({
            "clientId": client_id,
            "clientSecret": client_secret,
            "startUrl": resolved_start_url
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{base_url}/device_authorization",
            data=device_body,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            device_data = json.loads(resp.read().decode("utf-8"))

        verification_uri = device_data["verificationUriComplete"]
        device_code = device_data["deviceCode"]
        user_code = device_data["userCode"]
        interval = device_data.get("interval", 5)
        expires_in = device_data.get("expiresIn", 600)

        # Step 3: Open browser
        webbrowser.open(verification_uri)

        # Step 4: Poll for token
        deadline = time.time() + expires_in
        while time.time() < deadline:
            time.sleep(interval)
            token_body = json.dumps({
                "clientId": client_id,
                "clientSecret": client_secret,
                "deviceCode": device_code,
                "grantType": SSO_GRANT_TYPE
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{base_url}/token",
                data=token_body,
                headers={"Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    token_data = json.loads(resp.read().decode("utf-8"))

                # Store credentials in isolated DB
                device_registration = {
                    "client_id": client_id,
                    "clientId": client_id,
                    "client_secret": client_secret,
                    "clientSecret": client_secret,
                    "region": resolved_region,
                    "startUrl": resolved_start_url,
                }

                expires_in_secs = token_data.get("expiresIn", token_data.get("expires_in", 3600))
                exp_ts = int(time.time()) + expires_in_secs
                iso_exp = format_iso_time(exp_ts)

                token_data["expires_at"] = iso_exp
                token_data["expiresAt"] = iso_exp
                token_data["region"] = resolved_region
                token_data["start_url"] = resolved_start_url

                if "accessToken" in token_data:
                    token_data["access_token"] = token_data["accessToken"]
                if "refreshToken" in token_data:
                    token_data["refresh_token"] = token_data["refreshToken"]

                write_credentials_to_db(device_registration, token_data)

                # Save account metadata
                data["accounts"] = [{
                    "source": "hermes-kiro-login",
                    "ssoRegion": resolved_region,
                    "startUrl": resolved_start_url,
                    "loggedInAt": int(time.time()),
                    "userCode": user_code
                }]
                data["activeIndex"] = 0
                save_accounts_data(data)

                return True, "✅ AWS Kiro login successful! Gateway restarting with fresh credentials..."

            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                if "authorization_pending" in err_body:
                    continue
                elif "slow_down" in err_body:
                    interval += 2
                    continue
                elif "expired_token" in err_body:
                    return False, "❌ Login timed out. Please run `/kiro-login` again."
                else:
                    return False, f"❌ Login failed: HTTP {e.code} — {err_body[:200]}"

        return False, "❌ Login timed out. Please run `/kiro-login` again."

    except Exception as e:
        return False, f"❌ Login initialization error: {str(e)}"


# ── Slash Command Handlers ────────────────────────────────────────────
def handle_kiro_login(args: str = "") -> str:
    """Handler for /kiro-login [region] [start_url] slash command."""
    parts = args.strip().split() if args else []
    region = parts[0] if len(parts) > 0 else None
    start_url = parts[1] if len(parts) > 1 else None

    success, message = perform_sso_login(region=region, start_url=start_url)
    if success:
        restart_gateway()
    return message


def handle_kiro_accounts(args: str = "") -> str:
    """Handler for /kiro-accounts / /kiro slash command."""
    data = load_accounts_data()
    accounts = data.get("accounts", [])
    token_data = read_token_from_db()
    device_reg = read_device_registration_from_db()
    profile_arn, sso_region, api_region = get_profile_info()

    if not accounts and not token_data:
        return "No Kiro accounts configured. Use `/kiro-login` or `/kiro-import` to authenticate."

    lines = ["**Hermes AWS Kiro Gateway** (Isolated Authentication Store)\n"]
    lines.append(f"• **SSO Region**: `{sso_region}`")
    lines.append(f"• **API Region**: `{api_region}`")
    lines.append(f"• **Profile ARN**: `{profile_arn}`")
    lines.append(f"• **Gateway URL**: `http://127.0.0.1:{PORT}/v1` (Active: {is_port_in_use(PORT)})")

    if accounts:
        lines.append("\n**Configured Profiles:**")
        for i, acct in enumerate(accounts):
            active_marker = "👉 " if i == data.get("activeIndex", 0) else "   "
            source = acct.get("source", "unknown")
            url = acct.get("startUrl", "AWS SSO")
            lines.append(f"{active_marker}`{i + 1}.` **{source}** ({url})")

    if token_data:
        exp_ts = parse_expiry_timestamp(token_data.get("expires_at") or token_data.get("expiresAt"))
        now = int(time.time())
        if exp_ts > now:
            mins_left = (exp_ts - now) // 60
            lines.append(f"\n🔑 **Token Status**: Valid (~{mins_left}m remaining)")
        else:
            lines.append("\n⚠️ **Token Status**: Expired (Auto-refresh on next request)")

        has_refresh = bool(token_data.get("refreshToken") or token_data.get("refresh_token"))
        lines.append(f"🔄 **Refresh Token**: {'Available' if has_refresh else 'Missing'}")
    else:
        lines.append("\n⚠️ No token found in isolated store. Run `/kiro-login` or `/kiro-import`.")

    lines.append("\n*Commands: `/kiro-login`, `/kiro-import`, `/kiro-reload`, `/kiro-accounts`*")
    return "\n".join(lines)


def handle_kiro_reload(args: str = "") -> str:
    """Handler for /kiro-reload slash command."""
    ensure_fresh_token()
    restart_gateway()
    return "✅ Kiro gateway reloaded with refreshed credentials from isolated Hermes store."


def handle_kiro_import(args: str = "") -> str:
    """Handler for /kiro-import — force re-import from Kiro CLI / IDE."""
    success = import_from_kiro_cli(force=True)
    if success:
        restart_gateway()
        return "✅ Successfully imported credentials from Kiro CLI into isolated Hermes store. Gateway restarted."
    else:
        return "❌ Could not find Kiro CLI credentials. Ensure `kiro-cli whoami` works, then try again."


# ── CLI Command Handlers ──────────────────────────────────────────────
def setup_argparse(subparser):
    subs = subparser.add_subparsers(dest="kiro_subcommand")
    subs.add_parser("login", help="Log in a new AWS Kiro SSO account for Hermes")
    subs.add_parser("accounts", help="View Hermes Kiro account status and token health")
    subs.add_parser("list", help="List configured Kiro accounts")
    subs.add_parser("reload", help="Refresh token and restart Kiro gateway")
    subs.add_parser("import", help="Import credentials from Kiro CLI into isolated Hermes store")


def handle_cli(args):
    cmd = getattr(args, "kiro_subcommand", None)
    if cmd == "login":
        print(handle_kiro_login(""))
    elif cmd in ("accounts", "list"):
        print(handle_kiro_accounts(""))
    elif cmd == "reload":
        print(handle_kiro_reload(""))
    elif cmd == "import":
        print(handle_kiro_import(""))
    else:
        print(handle_kiro_accounts(""))


def _mock_pre_llm_call(*args, **kwargs):
    return None


# ── Plugin Registration ───────────────────────────────────────────────
def register(ctx):
    # CLI command: hermes kiro ...
    if hasattr(ctx, "register_cli_command"):
        ctx.register_cli_command(
            name="kiro",
            help="Manage AWS Kiro authentication and gateway for Hermes",
            setup_fn=setup_argparse,
            handler_fn=handle_cli
        )

    # In-session slash commands
    ctx.register_command(
        "kiro",
        handler=handle_kiro_accounts,
        description="View AWS Kiro account status, token health, and gateway info"
    )
    ctx.register_command(
        "kiro-accounts",
        handler=handle_kiro_accounts,
        description="View AWS Kiro account status and token health"
    )
    ctx.register_command(
        "kiro-login",
        handler=handle_kiro_login,
        description="Login to AWS Kiro (SSO) for Hermes — isolated from Kiro IDE"
    )
    ctx.register_command(
        "kiro-reload",
        handler=handle_kiro_reload,
        description="Refresh token and restart Kiro gateway"
    )
    ctx.register_command(
        "kiro-import",
        handler=handle_kiro_import,
        description="Re-import credentials from Kiro CLI into isolated Hermes store"
    )

    if hasattr(ctx, "register_hook"):
        ctx.register_hook("pre_llm_call", _mock_pre_llm_call)


atexit.register(stop_gateway)

# ── Compaction Proxy (port 8997 → Go gateway on 8996) ─────────────────
from http.server import HTTPServer, BaseHTTPRequestHandler

MAX_CONTEXT_CHARS = 900_000

def _compact_messages_kiro(messages):
    """Compact large message histories for Kiro/Claude context limits."""
    if len(messages) <= 100:
        return messages

    total_chars = sum(len(json.dumps(m, default=str)) for m in messages)
    if total_chars <= MAX_CONTEXT_CHARS:
        return messages

    system_msgs = [m for m in messages if m.get("role") in ("system", "developer")]
    non_system = [m for m in messages if m.get("role") not in ("system", "developer")]

    if len(non_system) <= 85:
        return messages

    head = non_system[:5]
    tail = non_system[-80:]
    middle = non_system[5:-80]

    compacted_middle = []
    for msg in middle:
        role = msg.get("role", "")
        if role == "tool":
            continue
        if msg.get("tool_calls"):
            continue
        content = msg.get("content")
        if content and isinstance(content, str) and content.strip():
            truncated = content[:300] + "…" if len(content) > 300 else content
            compacted_middle.append({"role": role, "content": truncated})

    separator = {"role": "user", "content": "[Earlier conversation compacted. Recent messages below.]"}
    result = system_msgs + head + [separator] + compacted_middle + tail

    result_chars = sum(len(json.dumps(m, default=str)) for m in result)
    if result_chars > MAX_CONTEXT_CHARS:
        result = system_msgs + head + [separator] + tail

    return result


class KiroCompactionProxy(BaseHTTPRequestHandler):
    """Thin proxy: compacts large sessions, forwards everything else unchanged."""

    def log_message(self, format, *args):
        pass  # Suppress default logging

    def do_GET(self):
        self._proxy_passthrough("GET")

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len else b""

        # Only compact /v1/chat/completions with large message arrays
        if "/v1/chat/completions" in self.path and body:
            try:
                data = json.loads(body)
                messages = data.get("messages", [])
                if len(messages) > 100:
                    original_count = len(messages)
                    data["messages"] = _compact_messages_kiro(messages)
                    compacted_count = len(data["messages"])
                    if compacted_count < original_count:
                        logger.info(f"[Kiro Proxy] Compacted {original_count} → {compacted_count} messages")
                    body = json.dumps(data).encode("utf-8")
            except Exception:
                pass  # Forward original on parse failure

        self._proxy_forward("POST", body)

    def _proxy_passthrough(self, method):
        self._proxy_forward(method, None)

    def _proxy_forward(self, method, body):
        """Forward request to Go gateway on INTERNAL_PORT."""
        url = f"http://127.0.0.1:{INTERNAL_PORT}{self.path}"
        headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length")}
        if body:
            headers["Content-Length"] = str(len(body))

        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            resp = urllib.request.urlopen(req, timeout=180)

            self.send_response(resp.status)
            # Check if streaming
            content_type = resp.headers.get("Content-Type", "")
            for header, value in resp.headers.items():
                if header.lower() not in ("transfer-encoding", "connection"):
                    self.send_header(header, value)
            self.end_headers()

            if "text/event-stream" in content_type:
                # Stream SSE
                try:
                    while True:
                        chunk = resp.read(4096)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except Exception:
                    pass
            else:
                resp_body = resp.read()
                self.wfile.write(resp_body)
                self.wfile.flush()

        except urllib.error.HTTPError as he:
            self.send_response(he.code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(he.read())
            self.wfile.flush()
        except Exception as e:
            error_body = json.dumps({"error": {"message": f"Kiro proxy error: {e}", "type": "proxy_error"}}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(error_body)))
            self.end_headers()
            self.wfile.write(error_body)
            self.wfile.flush()

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except Exception:
            pass


def start_compaction_proxy():
    """Start the compaction proxy on PORT (8997) in a daemon thread."""
    from http.server import ThreadingHTTPServer

    def run_proxy():
        server = ThreadingHTTPServer(("127.0.0.1", PORT), KiroCompactionProxy)
        server.daemon_threads = True
        logger.info(f"[Kiro] Compaction proxy listening on http://127.0.0.1:{PORT} → Go gateway on {INTERNAL_PORT}")
        server.serve_forever()

    t = threading.Thread(target=run_proxy, daemon=True)
    t.start()


# ── Auto-start on plugin load ─────────────────────────────────────────
# NOTE: We intentionally do NOT auto-import from Kiro CLI/IDE on startup.
# Doing so reads Kiro IDE's own SQLite DB and can trigger Kiro IDE to re-login.
# Users must explicitly run /kiro-login (native SSO flow) or /kiro-import
# (one-time manual import from Kiro CLI) to authenticate.
try:
    init_hermes_kiro_db()
    # Only start gateway if Hermes-native credentials already exist
    if read_token_from_db():
        start_gateway()
        start_compaction_proxy()
        _start_token_watcher()
    else:
        logger.info("[Kiro] No credentials in isolated Hermes store. Run /kiro-login to authenticate.")
except Exception as e:
    logger.error(f"[Kiro] Init error: {e}")
