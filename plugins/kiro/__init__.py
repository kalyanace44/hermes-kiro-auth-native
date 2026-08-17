import os
import sys
import time
import atexit
import signal
import subprocess
import shutil
import urllib.request
import json
import logging

logger = logging.getLogger("hermes.plugins.kiro")

PORT = 8997
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_DIR = os.path.join(PLUGIN_DIR, "bin")
BIN_PATH = os.path.join(BIN_DIR, "go-kiro-gateway")

_gateway_process = None

def get_binary_url():
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

def ensure_binary():
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

def find_sqlite_db():
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

def get_profile_info():
    # 1. Try CLI whoami
    for cmd in ["kiro-cli", "kiro"]:
        exe = shutil.which(cmd) or (f"/usr/local/bin/{cmd}" if os.path.exists(f"/usr/local/bin/{cmd}") else None)
        if exe:
            try:
                out = subprocess.check_output([exe, "whoami"], stderr=subprocess.DEVNULL, timeout=5).decode("utf-8")
                arn = None
                region = "eu-central-1"
                for line in out.splitlines():
                    if "arn:aws:codewhisperer:" in line:
                        arn = line.strip()
                        parts = arn.split(":")
                        if len(parts) >= 4:
                            region = parts[3]
                if arn:
                    return arn, region
            except Exception:
                pass

    # 2. Try reading from SQLite device registration
    db_file = find_sqlite_db()
    if db_file:
        try:
            import sqlite3
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT val FROM auth_kv WHERE key LIKE '%device-registration%' LIMIT 1")
            row = cursor.fetchone()
            if row and row[0]:
                reg_data = json.loads(row[0])
                region = reg_data.get("region", "eu-central-1")
                profile_arn = reg_data.get("profileArn") or reg_data.get("profile_arn")
                if profile_arn:
                    return profile_arn, region
                return f"arn:aws:codewhisperer:{region}:020807489866:profile/EUWNCR9VVUM7", region
        except Exception:
            pass

    return "arn:aws:codewhisperer:eu-central-1:020807489866:profile/EUWNCR9VVUM7", "eu-central-1"

def is_port_in_use(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def start_gateway():
    global _gateway_process
    
    if is_port_in_use(PORT):
        logger.info(f"[Kiro] Gateway already active on port {PORT}.")
        return

    bin_file = ensure_binary()
    if not bin_file:
        logger.error("[Kiro] Cannot start gateway: binary unavailable.")
        return

    db_file = find_sqlite_db()
    arn, region = get_profile_info()

    env = os.environ.copy()
    env["PROXY_API_KEY"] = "mock"
    env["KIRO_REGION"] = region
    env["PROFILE_ARN"] = arn
    if db_file:
        env["KIRO_CLI_DB_FILE"] = db_file

    logger.info(f"[Kiro] Launching Kiro gateway on port {PORT} (region: {region})...")
    
    try:
        _gateway_process = subprocess.Popen(
            [bin_file, "-port", str(PORT)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid if hasattr(os, "setsid") else None
        )
        
        for _ in range(25):
            time.sleep(0.2)
            if is_port_in_use(PORT):
                logger.info(f"[Kiro] Gateway successfully listening on http://127.0.0.1:{PORT}")
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

atexit.register(stop_gateway)

# Automatically start gateway upon plugin load
try:
    start_gateway()
except Exception as e:
    logger.error(f"[Kiro] Init error: {e}")
