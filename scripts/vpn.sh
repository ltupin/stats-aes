#!/bin/bash
# Pilotage VPN Japon via OpenVPN CLI (NordVPN). Usage: vpn.sh up|down|status
DIR="$HOME/.nordvpn-ovpn"
OVPN="$DIR/active.ovpn"
AUTH="$DIR/auth.txt"
BIN="/opt/homebrew/opt/openvpn/sbin/openvpn"
poll() { # $1=code pays attendu, $2=essais
  for _ in $(seq 1 "${2:-30}"); do
    cc=$(curl -s --max-time 5 "http://ip-api.com/json/?fields=countryCode" | grep -oE '[A-Z]{2}')
    [ "$cc" = "$1" ] && return 0
  done; return 1
}
case "$1" in
  up)
    sudo "$BIN" --config "$OVPN" --auth-user-pass "$AUTH" --daemon \
        --log "$DIR/vpn.log" --writepid "$DIR/vpn.pid" --connect-retry-max 3
    if poll JP 30; then echo "VPN up (JP)"; else echo "ECHEC up (voir $DIR/vpn.log)"; exit 1; fi ;;
  down)
    sudo /usr/bin/pkill -f nordvpn-ovpn
    if poll FR 20; then echo "VPN down (FR)"; else echo "ECHEC down"; exit 1; fi ;;
  status)
    curl -s --max-time 8 "http://ip-api.com/json/?fields=countryCode,query" ;;
  *) echo "usage: vpn.sh up|down|status"; exit 2 ;;
esac
