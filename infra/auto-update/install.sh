#!/usr/bin/env bash
# Install the automatic update timer on the server, or remove it. Run once, as root, from the
# project checkout:
#   sudo bash infra/auto-update/install.sh          # check GitHub every 5 minutes from now on
#   sudo bash infra/auto-update/install.sh remove   # stop automatic updates
set -euo pipefail

APP_DIR=$(cd "$(dirname "$0")/../.." && pwd)
APP_USER=$(stat -c %U "$APP_DIR")
UNIT=talentflow-update

if [ "${1:-}" = remove ]; then
  systemctl disable --now "$UNIT.timer" 2> /dev/null || true
  rm -f "/etc/systemd/system/$UNIT.service" "/etc/systemd/system/$UNIT.timer"
  systemctl daemon-reload
  echo "Automatic updates removed."
  exit 0
fi

cat > "/etc/systemd/system/$UNIT.service" << EOF
[Unit]
Description=Deploy the newest TalentFlow commit that passed CI
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
Environment=APP_DIR=$APP_DIR APP_USER=$APP_USER
ExecStart=/usr/bin/bash $APP_DIR/infra/auto-update/update.sh
TimeoutStartSec=45min
EOF

cat > "/etc/systemd/system/$UNIT.timer" << EOF
[Unit]
Description=Check GitHub for a new TalentFlow version every 5 minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now "$UNIT.timer"
echo "Automatic updates installed for $APP_DIR."
echo "Next check:  systemctl list-timers $UNIT.timer"
echo "Logs:        journalctl -u $UNIT -n 50"
