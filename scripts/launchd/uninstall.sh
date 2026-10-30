#!/usr/bin/env bash
# Stop and remove the morning briefing LaunchAgent. Logs and briefings stay.
set -euo pipefail

LABEL="com.marcobraun.jarvis.morning-briefing"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
echo "Removed $LABEL"
