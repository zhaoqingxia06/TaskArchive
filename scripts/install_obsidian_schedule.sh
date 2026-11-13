#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=$(command -v python3)
LABEL="com.taskarchive.obsidian-sync"
DIR="$HOME/Library/LaunchAgents"
LOGDIR="$HOME/Library/Logs"
mkdir -p "$DIR" "$LOGDIR"
PLIST="$DIR/$LABEL.plist"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>$LABEL</string>
<key>ProgramArguments</key><array><string>$PYTHON</string><string>$ROOT/scripts/sync_obsidian.py</string></array>
<key>WorkingDirectory</key><string>$ROOT</string>
<key>StartCalendarInterval</key><dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
<key>StandardOutPath</key><string>$LOGDIR/taskarchive-obsidian.log</string>
<key>StandardErrorPath</key><string>$LOGDIR/taskarchive-obsidian-error.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "已安装每天 09:00 的本机扫描任务（预览模式）：$PLIST"
