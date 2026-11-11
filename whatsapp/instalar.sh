#!/bin/bash
# Ejecutar en la Mac: bash instalar.sh
set -e
U="$USER"
mkdir -p ~/Library/LaunchAgents
for name in personal vilar; do
  f=com.vilarkptl.whatsapp-$name.plist
  sed "s#/Users/USUARIO#/Users/$U#" "$(dirname "$0")/$f" > ~/Library/LaunchAgents/$f
  launchctl unload ~/Library/LaunchAgents/$f 2>/dev/null || true
  launchctl load ~/Library/LaunchAgents/$f
done
echo "Listo: se abrieron dos Chrome. Escanea el QR de tu personal en uno y el de Vilar en el otro."
