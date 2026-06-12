#!/bin/bash
# Vérifie si le scan quotidien (LaunchAgent 7:00) a tourné, et son résultat.
LOG="$HOME/Library/Logs/stats-aes-daily.log"
echo "── Derniers passages (log) ──"
grep -E '===== daily_scan|fin daily_scan|main ->|ECHEC|VPN (up|down)' "$LOG" 2>/dev/null | tail -8 || echo "  (aucun log : jamais lancé)"
echo "── Dernier commit automatique ──"
git -C "$(dirname "$0")/.." log -1 --format='%ci  %s' --grep='Scan quotidien automatique' 2>/dev/null || echo "  aucun"
echo "── État LaunchAgent ──"
launchctl print "gui/$(id -u)/com.stats-aes.dailyscan" 2>/dev/null | grep -iE 'last exit code|runs =' || echo "  non chargé (launchctl list | grep stats-aes)"
