#!/bin/bash
if [ "$EUID" -ne 0 ]; then echo "Por favor, rode como root (sudo)"; exit; fi
echo "[+] Copiando servicos para /etc/systemd/system/..."
cp systemd/*.service /etc/systemd/system/
echo "[+] Recarregando daemon do systemd..."
systemctl daemon-reload
echo "[+] Habilitando inicio automatico no boot..."
systemctl enable spectre-fusion spectre-api spectre-web
echo "[*] Instalacao concluida! Para iniciar os servicos agora, rode:"
echo "    systemctl start spectre-api spectre-web spectre-fusion"
