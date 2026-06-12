"""Diagnostic sensors for PD Dashboard Bridge."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PDDashboardBridgeCoordinator


@dataclass(frozen=True)
class BridgeSensorDescription:
    """Description of a diagnostic bridge sensor."""

    key: str
    name: str
    value_fn: Callable[[dict[str, Any]], Any]
    icon: str


SENSORS: tuple[BridgeSensorDescription, ...] = (
    BridgeSensorDescription(
        key="status",
        name="Status",
        value_fn=lambda data: data.get("status") or "unknown",
        icon="mdi:cloud-sync",
    ),
    BridgeSensorDescription(
        key="app_version",
        name="Wersja aplikacji",
        value_fn=lambda data: data.get("app_version") or "unknown",
        icon="mdi:package-variant",
    ),
    BridgeSensorDescription(
        key="entity_count",
        name="Liczba encji",
        value_fn=lambda data: data.get("entity_count") or 0,
        icon="mdi:counter",
    ),
    BridgeSensorDescription(
        key="sent_entities",
        name="Wysylane encje",
        value_fn=lambda data: data.get("sent_entity_count") or len(data.get("sent_entities") or []),
        icon="mdi:format-list-bulleted",
    ),
    BridgeSensorDescription(
        key="last_heartbeat_at",
        name="Ostatni heartbeat",
        value_fn=lambda data: data.get("last_heartbeat_at") or "brak",
        icon="mdi:heart-pulse",
    ),
    BridgeSensorDescription(
        key="last_entities_at",
        name="Ostatnia wysylka encji",
        value_fn=lambda data: data.get("last_entities_at") or "brak",
        icon="mdi:database-arrow-up",
    ),
    BridgeSensorDescription(
        key="last_entities_stored",
        name="Ostatnio zapisane encje",
        value_fn=lambda data: data.get("last_entities_stored") or 0,
        icon="mdi:database-check",
    ),
    BridgeSensorDescription(
        key="last_command_count",
        name="Komendy z panelu",
        value_fn=lambda data: data.get("last_command_count") or 0,
        icon="mdi:playlist-check",
    ),
    BridgeSensorDescription(
        key="last_error",
        name="Ostatni blad",
        value_fn=lambda data: data.get("last_error") or "brak",
        icon="mdi:alert-circle-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up diagnostic sensors for a config entry."""

    coordinator: PDDashboardBridgeCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        BridgeSensor(coordinator, entry, description) for description in SENSORS
    )


class BridgeSensor(CoordinatorEntity[PDDashboardBridgeCoordinator], SensorEntity):
    """Diagnostic sensor for bridge state."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PDDashboardBridgeCoordinator,
        entry: ConfigEntry,
        description: BridgeSensorDescription,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator)
        self._description = description
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(coordinator.instance_id or entry.entry_id))},
            "name": coordinator.instance_name,
            "manufacturer": "Best-Net",
            "model": "PD Dashboard Bridge",
            "configuration_url": coordinator.panel_url,
        }

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""

        return self._description.value_fn(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return useful diagnostics."""

        data = self.coordinator.data or {}
        return {
            "panel_url": data.get("panel_url"),
            "app_version": data.get("app_version"),
            "ha_version": data.get("ha_version"),
            "instance_id": data.get("instance_id"),
            "instance_name": data.get("instance_name"),
            "location_name": data.get("location_name"),
            "send_all_entities": data.get("send_all_entities"),
            "entities_interval_seconds": data.get("entities_interval_seconds"),
            "sent_entity_count": data.get("sent_entity_count"),
            "sent_entities": data.get("sent_entities") or [],
            "last_error": data.get("last_error"),
        }
