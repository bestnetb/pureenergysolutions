"""Constants for the PD Dashboard Bridge integration."""

from __future__ import annotations

DOMAIN = "pd_dashboard_bridge"
APP_VERSION = "0.1.10"

CONF_PANEL_URL = "panel_url"
CONF_PAIRING_CODE = "pairing_code"
CONF_AGENT_TOKEN = "agent_token"
CONF_INSTANCE_ID = "instance_id"
CONF_INSTANCE_NAME = "instance_name"
CONF_LOCATION_NAME = "location_name"
CONF_ENDPOINTS = "endpoints"
CONF_HEARTBEAT_INTERVAL = "heartbeat_interval"
CONF_ENTITIES_INTERVAL = "entities_interval"
CONF_SEND_ALL_ENTITIES = "send_all_entities"

DEFAULT_PANEL_URL = "https://pd.best-net.pl"
DEFAULT_HEARTBEAT_INTERVAL = 30
DEFAULT_ENTITIES_INTERVAL = 300
DEFAULT_SEND_ALL_ENTITIES = True

MIN_HEARTBEAT_INTERVAL = 15
MIN_ENTITIES_INTERVAL = 60
MAX_ENTITY_ATTRIBUTES_DEPTH = 3
ENTITY_BATCH_SIZE = 100
