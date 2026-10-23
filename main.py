import base64
import hashlib
import modal
import os
import subprocess
import uuid

INSTALL_SCRIPT_VERSION = 4

# Optional deploy-time settings (read when `modal deploy` loads this file):
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

app = modal.App("vevc-app")
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

def start_supervisor():
    global _supervisor_started
    if not _supervisor_started:
        os.environ["ENABLE_SC"] = "true" if "E" in os.environ else "false"
        if os.environ.get("P"):
            u = os.environ.get("U", "")
            os.environ["W"] = str(uuid.uuid5(uuid.NAMESPACE_OID, f"warp:{u}"))
        subprocess.run(["supervisord"], env=os.environ.copy())
        _supervisor_started = True

@app.function(
    image=vevc_image,
    secrets=[modal.Secret.from_name("custom-secret")],
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
    uuid_str = os.environ["U"]

    @web_app.get("/status", response_class=PlainTextResponse)
    async def status():
        start_supervisor()
        return "UP"

    @web_app.get(f"/{uuid_str}", response_class=PlainTextResponse)
    async def sub():
        start_supervisor()
        domain = os.environ["D"]
        pin_sha256 = get_cert_fingerprint()

        sub_items = [
            f"vless://{uuid_str}@{domain}:443?encryption=none&security=tls&sni={domain}&fp=chrome&insecure=0&allowInsecure=0&type=ws&host={domain}&path=%2F%3Fed%3D2560#modal-ws-argo",
            f"hysteria2+realm://public@realm.hy2.io:443/{uuid_str}?sni=www.bing.com&pinSHA256={pin_sha256}&auth={uuid_str}&stun=stun.nextcloud.com%3A3478&stun=global.stun.twilio.com%3A3478#modal-hy2-realm",
        ]

        if "W" in os.environ:
            w_uuid = os.environ["W"]
            sub_items.extend([
                f"vless://{w_uuid}@{domain}:443?encryption=none&security=tls&sni={domain}&fp=chrome&insecure=0&allowInsecure=0&type=ws&host={domain}&path=%2F%3Fed%3D2560#modal-ws-warp",
                f"hysteria2+realm://public@realm.hy2.io:443/{uuid_str}?sni=www.bing.com&pinSHA256={pin_sha256}&auth={w_uuid}&stun=stun.nextcloud.com%3A3478&stun=global.stun.twilio.com%3A3478#modal-hy2-warp",
            ])

        sub_content = "\n".join(sub_items)
        return base64.b64encode(sub_content.encode("utf-8"))

    return web_app
