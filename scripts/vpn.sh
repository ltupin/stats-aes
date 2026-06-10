#!/bin/bash
# Pilotage VPN Japon via OpenVPN CLI (NordVPN). Usage: vpn.sh up|down|status
# Neutralise l'app NordVPN (qui sinon reprend la route) avant de monter le tunnel.
DIR="$HOME/.nordvpn-ovpn"
OVPN="$DIR/active.ovpn"; AUTH="$DIR/auth.txt"
BIN="/opt/homebrew/opt/openvpn/sbin/openvpn"
poll() { # $1=code pays attendu, $2=essais
  for _ in $(seq 1 "${2:-30}"); do
    [ "$(curl -s --max-time 5 'http://ip-api.com/json/?fields=countryCode' | grep -oE '[A-Z]{2}')" = "$1" ] && return 0
  done; return 1
}
stop_app() {  # quitte l'app NordVPN et attend que sa route tombe
  osascript -e 'quit app "NordVPN"' 2>/dev/null || true
  for _ in $(seq 1 60); do route -n get default 2>/dev/null | grep -q 'interface: utun' || return 0; done
  pkill -f 'NordVPN.app/Contents/MacOS/NordVPN' 2>/dev/null || true
  for _ in $(seq 1 200); do route -n get default 2>/dev/null | grep -q 'interface: utun' || return 0; done
}
case "$1" in
  up)
    stop_app
    sudo /usr/bin/pkill -f nordvpn-ovpn 2>/dev/null || true
    sudo "$BIN" --config "$OVPN" --auth-user-pass "$AUTH" --daemon \
        --log "$DIR/vpn.log" --writepid "$DIR/vpn.pid" --connect-retry-max 3
    if poll JP 40; then echo "VPN up (JP)"; else echo "ECHEC up (voir $DIR/vpn.log)"; exit 1; fi ;;
  down)
    sudo /usr/bin/pkill -f nordvpn-ovpn 2>/dev/null || true
    osascript -e 'quit app "NordVPN"' 2>/dev/null || true
    if poll FR 25; then echo "VPN down (FR)"; else echo "ECHEC down"; exit 1; fi ;;
  status) curl -s --max-time 8 "http://ip-api.com/json/?fields=countryCode,query" ;;
  *) echo "usage: vpn.sh up|down|status"; exit 2 ;;
esac
