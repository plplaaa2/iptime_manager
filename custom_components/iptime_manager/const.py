DOMAIN = 'iptime_manager'

CONF_URL = 'iptime_url'
CONF_ID = 'iptime_id'
CONF_PASSWORD = 'iptime_pw'
CONF_TARGET = 'targets'
CONF_NAME = 'name'
CONF_MAC = 'mac'
DEFAULT_INTERVAL = 5
RSS_LIMIT = -81

HOSTINFO_URN = '/login/hostinfo2.cgi'
LOGIN_URN = '/sess-bin/login_handler.cgi'
LOGIN_NEW_URN = '/login/login.cgi'
LOGOUT_URN = '/sess-bin/login_session.cgi?logout=1'
WLAN_2G_URN = '/sess-bin/timepro.cgi?tmenu=iframe&smenu=macauth_pcinfo_status&bssidx=0'
WLAN_5G_URN = '/sess-bin/timepro.cgi?tmenu=iframe&smenu=macauth_pcinfo_status&bssidx=65536'
MESH_URN = '/sess-bin/timepro.cgi?tmenu=wirelessconf&smenu=easymesh'
M_LOGIN_URN = '/m_handler.cgi'
M_LOGOUT_URN = '/m_login.cgi?logout=1'
M_WLAN_2G_URN = '/cgi/iux_get.cgi?tmenu=wirelessconf&smenu=macauth&act=status&wlmode=2g&bssidx=0'
M_WLAN_5G_URN = '/cgi/iux_get.cgi?tmenu=wirelessconf&smenu=macauth&act=status&wlmode=5g&bssidx=65536'
M_MESH_URN = '/cgi/iux_get.cgi?tmenu=sysconf&smenu=info&act=status'
MESH_STATION_URN = '/easymesh/api.cgi?key=topology'
BETA_UI_URN = '/ui/'
BETA_SERVICE_URN = '/cgi/service.cgi'
TIME_OUT = 5
CONF_CONSIDER_HOME = 'consider_home'
DEFAULT_CONSIDER_HOME = 180 # 기본값 3분 (초 단위)

OID_IPTIME_ROOT = ".1.3.6.1.4.1.12874"
OID_MODEL = ".1.3.6.1.4.1.12874.1.1.2.0"
OID_VERSION = ".1.3.6.1.4.1.12874.1.1.3.0"
OID_IFACE_DESCR = ".1.3.6.1.4.1.12874.1.2.2.1.2"
OID_IFACE_STATUS = ".1.3.6.1.4.1.12874.1.2.2.1.4"
OID_REBOOT_IPTIME = ".1.3.6.1.4.1.12874.1.5.7.0"
OID_LAN_MAC = ".1.3.6.1.4.1.12874.1.5.1.0"
OID_WAN_MAC = ".1.3.6.1.4.1.12874.1.5.2.0"
OID_PRIMARY_DNS = ".1.3.6.1.4.1.12874.1.5.3.0"
OID_SECONDARY_DNS = ".1.3.6.1.4.1.12874.1.5.4.0"
OID_WIFI_SSID = ".1.3.6.1.4.1.12874.1.4.2.1.2"
OID_WIFI_MODE = ".1.3.6.1.4.1.12874.1.4.2.1.4"
OID_WIFI_CHANNEL = ".1.3.6.1.4.1.12874.1.4.2.1.10"

# SNMP 설정
CONF_USE_SNMP = 'use_snmp'
CONF_SNMP_MODE = 'snmp_mode'
SNMP_MODE_RO = 'read_only'
SNMP_MODE_RW = 'read_write'
CONF_SNMP_VERSION = 'snmp_version'
CONF_SNMP_COMMUNITY = 'snmp_community'
CONF_SNMP_USER = 'snmp_user'
CONF_SNMP_AUTH_PROTOCOL = 'snmp_auth_protocol'
CONF_SNMP_AUTH_KEY = 'snmp_auth_key'
CONF_SNMP_PRIV_PROTOCOL = 'snmp_priv_protocol'
CONF_SNMP_PRIV_KEY = 'snmp_priv_key'
CONF_SNMP_PORT = 'snmp_port'

DEFAULT_SNMP_VERSION = 'v2c'
DEFAULT_SNMP_AUTH_PROTOCOL = 'md5'
DEFAULT_SNMP_PRIV_PROTOCOL = 'none'
DEFAULT_SNMP_COMMUNITY = 'public'
DEFAULT_SNMP_PORT = 161

# SNMP OIDs (Standard)
OID_UPTIME = ".1.3.6.1.2.1.1.3.0"