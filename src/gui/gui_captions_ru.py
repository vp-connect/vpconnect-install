"""
Однострочные подписи элементов GUI (русский/смешанный), вынесенные из `gui_tk.py`.

Порядок констант соответствует порядку элементов в UI (лог — последним).
"""

from __future__ import annotations

# Верхняя строка (баннер)
CAP_BANNER = "SSH: сервер — debian / centos / freebsd (vpconnect-configure; подробности в README)"

# Режим
CAP_MODE_LABEL = "Режим:"
CAP_MODE_SIMPLE = "Упрощённый (auto_setup)"
CAP_MODE_ADVANCED = "Расширенный"

# Подключение
CAP_SECTION_CONNECTION = "Подключение"
CAP_HOST = "Host"
CAP_SSH_PORT = "SSH port"
CAP_ROOT_PASSWORD = "Root password"
CAP_SSH_PRIVATE_KEY = "SSH Private key"
CAP_BROWSE_FILE = "Файл…"
CAP_SSH_KEY_PASSPHRASE = "SSH Key passphrase"
CAP_VPCONFIGURE_REPO = "Репозиторий vpconnect-configure"

# Настройка подключения (на сервере)
CAP_SECTION_NEW_CONNECT = "Настройка подключения (на сервере)"
CAP_ENABLE = "Включить"
CAP_NEW_ROOT_PASSWORD = "Новый пароль root"
CAP_NEW_SSH_PORT = "Новый SSH port"
CAP_NEW_SSH_PUBLIC_KEY = "Новый SSH Public key"
CAP_ENABLE_FIREWALL = "Включить файервол (ufw)"
CAP_ENABLE_FIREWALL_CHECKBOX = ""

# Домен
CAP_SECTION_DOMAIN = "Домен (имя сервера в конфигурациях)"
CAP_SET_DOMAIN = "Указать домен"
CAP_DOMAIN_FQDN = "Домен (FQDN)"

# WireGuard
CAP_SECTION_WIREGUARD = "WireGuard (VPN сервер)"
CAP_INSTALL = "Установить"
CAP_WG_UDP_PORT = "Порт UDP"
CAP_WG_CLIENT_NETWORK = "Сеть WG подключений"
CAP_WG_CLIENT_CERT = "Каталог сертификатов (на сервере)"
CAP_WG_CLIENT_CONFIG = "Каталог конфигураций (на сервере)"
CAP_WG_SERVER_PRIVATE_KEY = "Приватный ключ WG сервера"

# MTProxy
CAP_SECTION_MTPROXY = "MTProxy (Proxy для Telegram)"
CAP_MTPROXY_TCP_PORT = "TCP порт"
CAP_MTPROXY_SECRET = "Ключ MTProxy сервера"

# VPManage
CAP_SECTION_VPMANAGE = "VPManage (управление клиентами VPN)"
CAP_VPM_HTTP_PORT = "HTTP порт"
CAP_VPM_PASSWORD = "Пароль доступа"

# Кнопки
CAP_START = "Start"
CAP_EXIT = "Exit"

# Лог (последний)
CAP_LOG = "Log"
