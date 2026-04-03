"""Project defaults (ports, git, systemd names, timeouts). Change here instead of scattered literals."""

from __future__ import annotations

# Git / VPManage deploy
GIT_URL = "https://github.com/vpconnect/selfvpn.git"
GIT_BRANCH = "main"
INSTALL_PATH = "/opt/selfvpn"
SYSTEMD_SERVICE_VPMANAGE = "selfvpn"

# SSH / runner
SSH_CONNECT_TIMEOUT = 30
COMMAND_TIMEOUT = 3600
REBOOT_WAIT_TIMEOUT = 300
SSH_POLL_INTERVAL = 5

# WireGuard / MTProxy / VPManage default ports
WG_PORT_DEFAULT = 51820
MTPROXY_PORT_DEFAULT = 443
VPM_HTTP_PORT_DEFAULT = 80

# Server paths for client artifacts (WireGuard)
WG_CLIENT_CERT_PATH_DEFAULT = "/usr/wireguard/client_cert"
WG_CLIENT_CONFIG_PATH_DEFAULT = "/usr/wireguard/client_config"

# systemd unit name for MTProxy (finalize.sh / status)
MTPROXY_SYSTEMD_SERVICE = "mtproxy"

REMOTE_WORKDIR = "/root/.vpconnect-install"

# When auto_setup=True, enable these feature groups by default
AUTO_SETUP_SET_WIREGUARD = True
AUTO_SETUP_SET_MTPROXY = True
AUTO_SETUP_SET_VPMANAGE = True
# Generated secrets length (approx)
SECRET_TOKEN_BYTES = 16

# [vp-connect/vpconnect-configure](https://github.com/vp-connect/vpconnect-configure.git) — скрипты 00–03 на сервере
VPCONFIGURE_REPO_URL_DEFAULT = "https://github.com/vp-connect/vpconnect-configure.git"
# Ветка для raw.githubusercontent.com при скачивании 00–03 (не настраивается в UI/CLI)
VPCONFIGURE_RAW_GIT_BRANCH = "main"
# Path inside that repo before script name (no leading/trailing slash)
REMOTE_SCRIPTS_REPO_PATH = "remote"

# HTTP service: returns FQDN for domain_client_key (plain text first line, or JSON {"domain":"..."})
DOMAIN_CLIENT_SERVICE_URL = "https://example.com/api/vpconnect-domain"
DOMAIN_CLIENT_SERVICE_TIMEOUT = 30
