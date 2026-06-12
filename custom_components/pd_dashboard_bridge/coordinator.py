"""Coordinator for PD Dashboard Bridge."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DashboardApiClient, DashboardApiError, DashboardAuthError
from .const import (
    APP_VERSION,
    CONF_AGENT_TOKEN,
    CONF_ENDPOINTS,
    CONF_ENTITIES_INTERVAL,
    CONF_HEARTBEAT_INTERVAL,
    CONF_INSTANCE_ID,
    CONF_INSTANCE_NAME,
    CONF_LOCATION_NAME,
    CONF_PANEL_URL,
    CONF_SEND_ALL_ENTITIES,
    DEFAULT_ENTITIES_INTERVAL,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_SEND_ALL_ENTITIES,
    DOMAIN,
    ENTITY_BATCH_SIZE,
    MAX_ENTITY_ATTRIBUTES_DEPTH,
    MIN_ENTITIES_INTERVAL,
    MIN_HEARTBEAT_INTERVAL,
)

LOGGER = logging.getLogger(__name__)


class PDDashboardBridgeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Send HA status and entities to the PD dashboard."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""

        self.entry = entry
        self.panel_url = str(entry.data[CONF_PANEL_URL])
        self.agent_token = str(entry.data[CONF_AGENT_TOKEN])
        self.instance_id = int(entry.data.get(CONF_INSTANCE_ID, 0))
        self.instance_name = str(entry.data.get(CONF_INSTANCE_NAME) or "Home Assistant")
        self.location_name = str(entry.data.get(CONF_LOCATION_NAME) or "")
        self.endpoints = dict(entry.data.get(CONF_ENDPOINTS) or {})
        self.entity_count = 0
        self.last_heartbeat_at: str | None = None
        self.last_entities_at: str | None = None
        self.last_entities_stored = 0
        self.last_sent_entities: list[str] = []
        self.last_command_count = 0
        self.last_error: str | None = None
        self._last_entities_sync: datetime | None = None

        heartbeat_interval = max(
            MIN_HEARTBEAT_INTERVAL,
            int(entry.options.get(CONF_HEARTBEAT_INTERVAL, DEFAULT_HEARTBEAT_INTERVAL)),
        )
        self.entities_interval = timedelta(
            seconds=max(
                MIN_ENTITIES_INTERVAL,
                int(entry.options.get(CONF_ENTITIES_INTERVAL, DEFAULT_ENTITIES_INTERVAL)),
            )
        )
        self.send_all_entities = bool(
            entry.options.get(CONF_SEND_ALL_ENTITIES, DEFAULT_SEND_ALL_ENTITIES)
        )
        self.client = DashboardApiClient(
            async_get_clientsession(hass),
            self.panel_url,
            self.agent_token,
        )

        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{self.instance_id or entry.entry_id}",
            update_interval=timedelta(seconds=heartbeat_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Send heartbeat and periodically send entity states."""

        now = datetime.now(timezone.utc)

        try:
            heartbeat = await self.client.heartbeat(
                {
                    "app_version": APP_VERSION,
                    "ha_version": HA_VERSION,
                    "instance_id": self.instance_id,
                    "instance_name": self.instance_name,
                    "location_name": self.location_name,
                    "entity_count": self.entity_count,
                    "last_entities_at": self.last_entities_at,
                    "supports_commands": True,
                }
            )
            self.last_heartbeat_at = now.isoformat()
            self.last_command_count = len(heartbeat.get("commands") or [])

            if self._should_send_entities(now):
                try:
                    entities_result = await self._send_entities(now)
                except DashboardApiError as err:
                    LOGGER.warning("Cannot send PD Dashboard entities: %s", err)
                    self.last_error = f"Encje: {err}"
                    entities_result = {"ok": False, "message": str(err)}
            else:
                entities_result = None

            if entities_result is None or entities_result.get("ok", True):
                self.last_error = None
            return self._state_payload(heartbeat, entities_result)
        except DashboardAuthError as err:
            self.last_error = str(err)
            LOGGER.warning("PD Dashboard agent token was rejected: %s", err)
            return self._state_payload(
                {"ok": False, "message": str(err)},
                None,
                status="auth_failed",
            )
        except DashboardApiError as err:
            self.last_error = str(err)
            raise UpdateFailed(str(err)) from err

    def _should_send_entities(self, now: datetime) -> bool:
        """Return true when entity states should be sent now."""

        if self.last_entities_at is None:
            return True

        if not self.send_all_entities:
            return False

        return (
            self._last_entities_sync is None
            or now - self._last_entities_sync >= self.entities_interval
        )

    async def _send_entities(self, now: datetime) -> dict[str, Any]:
        """Send all HA entity states to the dashboard."""

        entities = self._build_entities_payload()
        self.entity_count = len(entities)
        if not entities:
            return {
                "ok": True,
                "received": 0,
                "stored": 0,
                "message": "Home Assistant nie zwrocil jeszcze encji; proba zostanie ponowiona.",
            }

        sync_id = now.isoformat()
        result = await self._send_entities_in_batches(entities, sync_id)
        self._last_entities_sync = now
        self.last_entities_at = now.isoformat()
        self.last_entities_stored = int(result.get("stored") or 0)
        if result.get("requires_pairing") or result.get("status") == "auth_failed":
            self.last_error = str(result.get("message") or "Encje wymagaja ponownego parowania.")

        return result

    async def _send_entities_in_batches(
        self,
        entities: list[dict[str, Any]],
        sync_id: str,
    ) -> dict[str, Any]:
        """Send entity states in small batches to avoid large POST failures."""

        batch_count = (len(entities) + ENTITY_BATCH_SIZE - 1) // ENTITY_BATCH_SIZE
        total_received = 0
        total_skipped = 0
        total_stored = 0
        last_result: dict[str, Any] = {}

        for batch_index, start in enumerate(
            range(0, len(entities), ENTITY_BATCH_SIZE),
            start=1,
        ):
            batch = entities[start : start + ENTITY_BATCH_SIZE]
            result = await self.client.entities(
                {
                    "app_version": APP_VERSION,
                    "ha_version": HA_VERSION,
                    "instance_id": self.instance_id,
                    "instance_name": self.instance_name,
                    "location_name": self.location_name,
                    "entity_total": len(entities),
                    "sync_id": sync_id,
                    "batch_index": batch_index,
                    "batch_count": batch_count,
                    "entities": batch,
                }
            )
            last_result = result
            total_received += int(result.get("received") or len(batch))
            total_skipped += int(result.get("skipped") or 0)
            total_stored += int(result.get("stored") or 0)

        return {
            **last_result,
            "received": total_received,
            "skipped": total_skipped,
            "stored": total_stored,
            "batch_count": batch_count,
        }

    def _build_entities_payload(self) -> list[dict[str, Any]]:
        """Build entity state payload from Home Assistant state machine."""

        payload: list[dict[str, Any]] = []

        for state in self.hass.states.async_all():
            if not _state_has_data(state.entity_id, state.state):
                continue

            attributes = dict(state.attributes)
            payload.append(
                {
                    "entity_id": state.entity_id,
                    "state": state.state,
                    "name": attributes.get("friendly_name") or state.name,
                    "unit": attributes.get("unit_of_measurement"),
                    "device_class": attributes.get("device_class"),
                    "state_class": attributes.get("state_class"),
                    "last_changed": state.last_changed.isoformat(),
                    "last_updated": state.last_updated.isoformat(),
                    "attributes": _json_safe(attributes),
                }
            )

        self.last_sent_entities = [item["entity_id"] for item in payload]

        return payload

    def _state_payload(
        self,
        heartbeat: dict[str, Any] | None,
        entities_result: dict[str, Any] | None,
        *,
        status: str = "online",
    ) -> dict[str, Any]:
        """Return data exposed by diagnostic sensors."""

        return {
            "status": status,
            "app_version": APP_VERSION,
            "ha_version": HA_VERSION,
            "instance_id": self.instance_id,
            "instance_name": self.instance_name,
            "location_name": self.location_name,
            "panel_url": self.panel_url,
            "send_all_entities": self.send_all_entities,
            "entities_interval_seconds": int(self.entities_interval.total_seconds()),
            "entity_count": self.entity_count,
            "sent_entity_count": len(self.last_sent_entities),
            "sent_entities": self.last_sent_entities,
            "last_heartbeat_at": self.last_heartbeat_at,
            "last_entities_at": self.last_entities_at,
            "last_entities_stored": self.last_entities_stored,
            "last_command_count": self.last_command_count,
            "heartbeat": heartbeat or {},
            "entities_result": entities_result or {},
            "last_error": self.last_error,
        }


def _state_has_data(entity_id: str, value: Any) -> bool:
    """Return true when a state has usable data for the dashboard."""

    domain = entity_id.split(".", 1)[0].lower()
    if domain != "sensor":
        return False

    state = str(value or "").strip().lower()
    return state not in {"", "unknown", "unavailable", "none"}


def _json_safe(value: Any, depth: int = MAX_ENTITY_ATTRIBUTES_DEPTH) -> Any:
    """Return a JSON-safe representation of a Home Assistant value."""

    if depth <= 0:
        return str(value)[:500]

    if value is None or isinstance(value, (str, int, float, bool)):
        if isinstance(value, str):
            return value[:1000]
        return value

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item, depth - 1) for item in list(value)[:50]]

    if isinstance(value, dict):
        return {
            str(key)[:120]: _json_safe(item, depth - 1)
            for key, item in list(value.items())[:80]
        }

    return str(value)[:500]
