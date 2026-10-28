#!/bin/bash
# Pilotage VPN Japon via OpenVPN CLI (NordVPN). Usage: vpn.sh up|down|status|refresh
# Neutralise l'app NordVPN (qui sinon reprend la route) avant de monter le tunnel.
DIR="$HOME/.nordvpn-ovpn"
OVPN="$DIR/active.ovpn"; AUTH="$DIR/auth.txt"
BIN="/opt/homebrew/opt/openvpn/sbin/openvpn"
refresh_profile() {
  local country_id hostname profile_tmp
  country_id=$(curl -fsS --max-time 10 'https://api.nordvpn.com/v1/servers/countries' \
    | /usr/bin/jq -r '.[] | select(.code == "JP") | .id' | head -1)
  [ -n "$country_id" ] || { echo "Impossible de trouver le pays Japon dans l'API NordVPN" >&2; return 1; }
  hostname=$(curl -fsS -G --max-time 15 'https://api.nordvpn.com/v1/servers/recommendations' \
    --data-urlencode "filters[country_id]=$country_id" --data-urlencode 'limit=1' \
    | /usr/bin/jq -r '.[0].hostname // empty')
  [[ "$hostname" =~ ^jp[0-9]+\.nordvpn\.com$ ]] \
    || { echo "L'API NordVPN n'a pas retourné de serveur japonais valide" >&2; return 1; }
  profile_tmp=$(mktemp "$DIR/active.XXXXXX") || return 1
  if ! curl -fsSL --retry 2 --max-time 20 \
      "https://downloads.nordcdn.com/configs/files/ovpn_udp/servers/$hostname.udp.ovpn" \
      -o "$profile_tmp" \
      || ! grep -Fq "verify-x509-name CN=$hostname" "$profile_tmp" \
      || ! grep -q '^remote ' "$profile_tmp" \
      || ! grep -q '^proto udp$' "$profile_tmp"; then
    rm -f "$profile_tmp"
    echo "Échec de téléchargement ou de validation du profil OpenVPN ($hostname)" >&2
    return 1
  fi
  chmod 600 "$profile_tmp" && mv -f "$profile_tmp" "$OVPN" \
    || { rm -f "$profile_tmp"; return 1; }
  echo "Profil OpenVPN actualisé : $hostname (UDP)"
}
poll() { # $1=code pays attendu, $2=essais
  for _ in $(seq 1 "${2:-30}"); do
    [ "$(curl -s --max-time 5 'http://ip-api.com/json/?fields=countryCode' | grep -oE '[A-Z]{2}')" = "$1" ] && return 0
    sleep 2
  done; return 1
}
show_errors() {
  sudo /usr/bin/grep -Ei 'AUTH_FAILED|TLS Error|VERIFY ERROR|Options error|RESOLVE:|Network is unreachable|Connection refused|ERROR:' "$DIR/vpn.log" | /usr/bin/tail -20 || true
}
stop_app() {  # quitte l'app NordVPN et attend que sa route tombe
  osascript -e 'quit app "NordVPN"' 2>/dev/null || true
  for _ in $(seq 1 60); do route -n get default 2>/dev/null | grep -q 'interface: utun' || return 0; done
  pkill -f 'NordVPN.app/Contents/MacOS/NordVPN' 2>/dev/null || true
  for _ in $(seq 1 200); do route -n get default 2>/dev/null | grep -q 'interface: utun' || return 0; done
}
case "$1" in
  refresh)
    refresh_profile ;;
  up)
    refresh_profile || exit 1
    stop_app
    sudo /usr/bin/pkill -f nordvpn-ovpn 2>/dev/null || true
    sudo "$BIN" --config "$OVPN" --auth-user-pass "$AUTH" --daemon \
        --log "$DIR/vpn.log" --writepid "$DIR/vpn.pid" --connect-retry-max 3
    if poll JP 40; then echo "VPN up (JP)"; else
      echo "ECHEC up après 80 s (sortie actuelle : $(curl -s --max-time 5 'http://ip-api.com/json/?fields=countryCode' | grep -oE '[A-Z]{2}' | head -1 || echo inconnue))"
      echo "Diagnostics OpenVPN :"
      show_errors
      exit 1
    fi ;;
  down)
    sudo /usr/bin/pkill -f nordvpn-ovpn 2>/dev/null || true
    osascript -e 'quit app "NordVPN"' 2>/dev/null || true
    if poll FR 25; then echo "VPN down (FR)"; else echo "ECHEC down après 50 s"; show_errors; exit 1; fi ;;
  status) curl -s --max-time 8 "http://ip-api.com/json/?fields=countryCode,query" ;;
  *) echo "usage: vpn.sh up|down|status|refresh"; exit 2 ;;
esac
