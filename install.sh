#!/usr/bin/env bash

cd /root

XRAY_VERSION="26.10.21"
ARGO_VERSION="2026.10.3"
TTYD_VERSION="1.7.7"
SUPERCRONIC_VERSION="0.2.51"

curl -sSL -o Xray-linux-64.zip https://github.com/XTLS/Xray-core/releases/download/v$XRAY_VERSION/Xray-linux-64.zip
unzip -q Xray-linux-64.zip
mv xray /usr/local/bin/xy
rm -rf *

mkdir -p /etc/xy
openssl req -x509 -nodes -newkey ec:<(openssl ecparam -name prime256v1) \
  -keyout /etc/xy/key.pem \
  -out /etc/xy/cert.pem \
  -subj "/CN=www.bing.com" \
  -addext "subjectAltName=DNS:www.bing.com" \
  -days 36500

curl -sSL -o /etc/xy/xy-direct.json https://raw.githubusercontent.com/vevc/modal-deploy/refs/heads/main/xray-config.json
curl -sSL -o /etc/xy/xy-warp.json https://raw.githubusercontent.com/vevc/modal-deploy/refs/heads/main/xray-warp-config.json

curl -sSL -o /usr/local/bin/cf https://github.com/cloudflare/cloudflared/releases/download/$ARGO_VERSION/cloudflared-linux-amd64
chmod +x /usr/local/bin/cf

curl -sSL -o /usr/local/bin/td https://github.com/tsl0922/ttyd/releases/download/$TTYD_VERSION/ttyd.x86_64
chmod +x /usr/local/bin/td

curl -sSL -o /usr/local/bin/sc https://github.com/aptible/supercronic/releases/download/v$SUPERCRONIC_VERSION/supercronic-linux-amd64
chmod +x /usr/local/bin/sc

# xy startup
cat > /usr/local/bin/start_xy.sh <<'EOF'
#!/usr/bin/env bash

cd /etc/xy

if [ -n "$P" ]; then
    cp -f xy-warp.json xy.json
    sed -i "s|YOUR_WARP_PRIVATE_KEY|$P|g" xy.json
    sed -i "s|YOUR_WARP_UUID|$W|g" xy.json
else
    cp -f xy-direct.json xy.json
fi

sed -i "s|YOUR_UUID|$U|g" xy.json
exec xy -c xy.json

EOF
chmod +x /usr/local/bin/start_xy.sh

cat > /etc/supervisor/conf.d/xy.conf <<EOF
[program:xy]
command=start_xy.sh
autostart=true
autorestart=true
stdout_logfile = /dev/null
stderr_logfile = /dev/null

EOF

# cf startup
cat > /etc/supervisor/conf.d/cf.conf <<EOF
[program:cf]
command=cf tunnel --no-autoupdate run --token %(ENV_T)s
autostart=true
autorestart=true
stdout_logfile = /dev/null
stderr_logfile = /dev/null

EOF

# td startup
cat > /etc/supervisor/conf.d/td.conf <<EOF
[program:td]
command=td -p 80 -W bash
autostart=true
autorestart=true
stdout_logfile = /dev/null
stderr_logfile = /dev/null

EOF

# sc startup
cat > /usr/local/bin/keepalive.sh <<'EOF'
#!/bin/bash

# sleep random 0~299 seconds
sleep $((RANDOM % 300))

status=$(curl -o /dev/null -s -w "%{http_code}" $E/status)
echo `date "+%Y-%m-%d %H:%M:%S"` - Request: $E/status, Response: $status > /tmp/keepalive.log

EOF
chmod +x /usr/local/bin/keepalive.sh

cat > /etc/my-crontab <<EOF
*/5 * * * * /usr/local/bin/keepalive.sh

EOF

cat > /etc/supervisor/conf.d/sc.conf <<EOF
[program:sc]
directory=/etc
command=sc my-crontab
autostart=%(ENV_ENABLE_SC)s
autorestart=true
stdout_logfile = /dev/null
stderr_logfile = /dev/null

EOF
