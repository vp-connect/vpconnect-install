"""
Константы по умолчанию для клиента vpconnect-install.

Порты, таймауты, пути на сервере для WireGuard, URL/ветка репозитория **remote** скриптов 00–03.
Менять здесь предпочтительнее, чем размазывать литералы по коду.
"""

from __future__ import annotations

# SSH / runner — RSA ключа оператора в provision-artifacts (размер модуля, бит).
OPERATOR_SSH_RSA_KEY_BITS = 2048
SSH_CONNECT_TIMEOUT = 30
COMMAND_TIMEOUT = 3600
REBOOT_WAIT_TIMEOUT = 300
SSH_POLL_INTERVAL = 5

# WireGuard / MTProxy / VPManage default ports
WG_PORT_DEFAULT = 443
MTPROXY_PORT_DEFAULT = 25
VPM_HTTP_PORT_DEFAULT = 80

# Server paths for client artifacts (WireGuard)
WG_CLIENT_CERT_PATH_DEFAULT = "/usr/wireguard/client_cert"
WG_CLIENT_CONFIG_PATH_DEFAULT = "/usr/wireguard/client_config"

# Generated secrets length (approx)
SECRET_TOKEN_BYTES = 16

# [vp-connect/vpconnect-configure](https://github.com/vp-connect/vpconnect-configure.git) — скрипты 00–03 на сервере
VPCONFIGURE_REPO_URL_DEFAULT = "https://github.com/vp-connect/vpconnect-configure.git"
# Ветка для raw.githubusercontent.com при скачивании 00–03 (не настраивается в UI/CLI)
VPCONFIGURE_RAW_GIT_BRANCH = "main"
# Path inside that repo before script name (no leading/trailing slash)
REMOTE_SCRIPTS_REPO_PATH = "remote"
