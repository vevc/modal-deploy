import base64
import hashlib
import json
import modal
import os
import subprocess
import uuid
from urllib.parse import unquote, urlparse

INSTALL_SCRIPT_VERSION = 9

# Optional deploy-time settings (read when `modal deploy` loads this file):
#   MODAL_APP_NAME          Custom app name (default: "vevc-app").
#   MODAL_SECRET_NAME       Custom secret name (default: "custom-secret").
#   MODAL_REGION            Comma-separated region ids (e.g. "us-east" or "ap-northeast-1,eu-west-1").
#                           Unset or empty = Modal default scheduling (no fixed region).
#                           See https://modal.com/docs/guide/region-selection
#   MODAL_NONPREEMPTIBLE    Set to the string "true" to enable nonpreemptible on the Function; omit or "false" otherwise.
def _modal_function_options():
    """Build optional kwargs for @app.function from environment (CI / local deploy)."""
    opts = {}
    raw_region = os.environ.get("MODAL_REGION", "").strip()
    if raw_region:
        parts = [p.strip() for p in raw_region.split(",") if p.strip()]
        if parts:
            opts["region"] = parts
    if os.environ.get("MODAL_NONPREEMPTIBLE", "").strip() == "true":
        opts["nonpreemptible"] = True
    return opts

APP_NAME = os.environ.get("MODAL_APP_NAME", "").strip() or "vevc-app"
SECRET_NAME = os.environ.get("MODAL_SECRET_NAME", "").strip() or "custom-secret"

app = modal.App(APP_NAME)
vevc_image = (
    modal.Image.debian_slim()
        .apt_install("curl", "unzip", "supervisor", "procps", "openssl", "sudo", "wget", "ca-certificates", "openssh-client", "vim", "net-tools", "iputils-ping", "telnet", "git", "iproute2")
        .run_commands(
            f'curl -sSL "https://raw.githubusercontent.com/vevc/modal-deploy/refs/heads/dev/install.sh?v={INSTALL_SCRIPT_VERSION}" | bash'
        )
        .pip_install("fastapi[standard]")
)

_supervisor_started = False
_cert_fingerprint = None

def get_cert_fingerprint():
    global _cert_fingerprint
    if _cert_fingerprint is not None:
        return _cert_fingerprint

    cert_path = "/etc/xy/cert.pem"

    try:
        out = subprocess.check_output(
            ["openssl", "x509", "-noout", "-fingerprint", "-sha256", "-in", cert_path],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        _cert_fingerprint = out.split("=")[-1].replace(":", "").strip().upper()
        return _cert_fingerprint
    except Exception:
        pass

    try:
        if os.path.exists(cert_path):
            with open(cert_path, "r", encoding="utf-8") as f:
                content = f.read()
            lines = [
                line.strip()
                for line in content.splitlines()
                if line.strip() and not line.startswith("-----")
            ]
            der = base64.b64decode("".join(lines))
            _cert_fingerprint = hashlib.sha256(der).hexdigest().upper()
            return _cert_fingerprint
    except Exception:
        pass

    return ""

def parse_socks5(url_str):
    if not url_str:
        return None
    url = url_str.strip()
    if not (url.startswith("socks5://") or url.startswith("socks5h://") or url.startswith("socks://")):
        url = "socks5://" + url
    parsed = urlparse(url)
    if not parsed.hostname or not parsed.port:
        return None
    res = {
        "address": parsed.hostname,
        "port": parsed.port,
    }
    if parsed.username:
        res["user"] = unquote(parsed.username)
    if parsed.password:
        res["pass"] = unquote(parsed.password)
    return res

def configure_xy():
    u = os.environ.get("U", "").strip()
    if not u:
        return

    config_path = "/etc/xy/xy.json"
    if not os.path.exists(config_path):
        return

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    for ib in cfg.get("inbounds", []):
        for c in ib.get("settings", {}).get("clients", []):
            if c.get("email") == "native-user":
                if "id" in c:
                    c["id"] = u
                if "auth" in c:
                    c["auth"] = u
        for udp in ib.get("streamSettings", {}).get("finalmask", {}).get("udp", []):
            url = udp.get("settings", {}).get("url", "")
            if "YOUR_UUID" in url:
                udp["settings"]["url"] = url.replace("YOUR_UUID", u)

    p_key = os.environ.get("P", "").strip()
    if p_key:
        w_uuid = str(uuid.uuid5(uuid.NAMESPACE_OID, f"warp:{u}"))
        os.environ["W_UUID"] = w_uuid
        for ib in cfg.get("inbounds", []):
            proto = ib.get("protocol")
            if proto == "vless":
                ib.setdefault("settings", {}).setdefault("clients", []).append(
                    {"id": w_uuid, "email": "warp-user", "flow": ""}
                )
            elif proto == "hysteria":
                ib.setdefault("settings", {}).setdefault("clients", []).append(
                    {"auth": w_uuid, "email": "warp-user"}
                )
        cfg.setdefault("outbounds", []).append(
            {
                "tag": "warp-out",
                "protocol": "wireguard",
                "settings": {
                    "secretKey": p_key,
                    "address": ["172.16.0.2/32"],
                    "peers": [
                        {
                            "publicKey": "bmXOC+F1FxEMF9dyiK2H5/1SUtzH0JuVo51h2wPfgyo=",
                            "endpoint": "engage.cloudflareclient.com:2408",
                        }
                    ],
                    "reserved": [0, 0, 0],
                },
            }
        )
        cfg.setdefault("routing", {}).setdefault("rules", []).append(
            {"type": "field", "user": ["warp-user"], "outboundTag": "warp-out"}
        )

    s_raw = os.environ.get("S", "").strip()
    s_conf = parse_socks5(s_raw) if s_raw else None
    if s_conf:
        s_uuid = str(uuid.uuid5(uuid.NAMESPACE_OID, f"socks5:{u}"))
        os.environ["S_UUID"] = s_uuid
        for ib in cfg.get("inbounds", []):
            proto = ib.get("protocol")
            if proto == "vless":
                ib.setdefault("settings", {}).setdefault("clients", []).append(
                    {"id": s_uuid, "email": "socks-user", "flow": ""}
                )
            elif proto == "hysteria":
                ib.setdefault("settings", {}).setdefault("clients", []).append(
                    {"auth": s_uuid, "email": "socks-user"}
                )
        cfg.setdefault("outbounds", []).append(
            {
                "tag": "socks-out",
                "protocol": "socks",
                "settings": s_conf,
            }
        )
        cfg.setdefault("routing", {}).setdefault("rules", []).append(
            {"type": "field", "user": ["socks-user"], "outboundTag": "socks-out"}
        )

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def start_supervisor():
    global _supervisor_started
    if not _supervisor_started:
        os.environ["ENABLE_SC"] = "true" if "E" in os.environ else "false"
        configure_xy()
        subprocess.run(["supervisord"], env=os.environ.copy())
        _supervisor_started = True

@app.function(
    image=vevc_image,
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    min_containers=1,
    max_containers=1,
    scaledown_window=1200,
    **_modal_function_options(),
)
@modal.asgi_app()
def main():
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse

    start_supervisor()
    web_app = FastAPI()
    uuid_str = os.environ["U"].strip()

    @web_app.get("/status", response_class=PlainTextResponse)
    async def status():
        start_supervisor()
        return "UP"

    @web_app.get(f"/{uuid_str}", response_class=PlainTextResponse)
    async def sub():
        start_supervisor()
        domain = os.environ["D"].strip()
        pin_sha256 = get_cert_fingerprint()

        sub_items = [
            f"vless://{uuid_str}@{domain}:443?encryption=none&security=tls&sni={domain}&fp=chrome&insecure=0&allowInsecure=0&type=ws&host={domain}&path=%2F%3Fed%3D2560#modal-ws-argo",
            f"hysteria2+realm://public@realm.hy2.io:443/{uuid_str}?sni=www.bing.com&pinSHA256={pin_sha256}&auth={uuid_str}&stun=stun.nextcloud.com%3A3478&stun=global.stun.twilio.com%3A3478#modal-hy2-realm",
        ]

        if "W_UUID" in os.environ:
            w_uuid = os.environ["W_UUID"]
            sub_items.extend([
                f"vless://{w_uuid}@{domain}:443?encryption=none&security=tls&sni={domain}&fp=chrome&insecure=0&allowInsecure=0&type=ws&host={domain}&path=%2F%3Fed%3D2560#modal-ws-warp",
                f"hysteria2+realm://public@realm.hy2.io:443/{uuid_str}?sni=www.bing.com&pinSHA256={pin_sha256}&auth={w_uuid}&stun=stun.nextcloud.com%3A3478&stun=global.stun.twilio.com%3A3478#modal-hy2-warp",
            ])

        if "S_UUID" in os.environ:
            s_uuid = os.environ["S_UUID"]
            sub_items.extend([
                f"vless://{s_uuid}@{domain}:443?encryption=none&security=tls&sni={domain}&fp=chrome&insecure=0&allowInsecure=0&type=ws&host={domain}&path=%2F%3Fed%3D2560#modal-ws-socks",
                f"hysteria2+realm://public@realm.hy2.io:443/{uuid_str}?sni=www.bing.com&pinSHA256={pin_sha256}&auth={s_uuid}&stun=stun.nextcloud.com%3A3478&stun=global.stun.twilio.com%3A3478#modal-hy2-socks",
            ])

        sub_content = "\n".join(sub_items)
        return base64.b64encode(sub_content.encode("utf-8"))

    return web_app
