"""Config flow for PD Dashboard Bridge."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    DashboardApiClient,
    DashboardApiError,
    DashboardAuthError,
    DashboardCannotConnect,
    normalize_panel_url,
)
from .const import (
    CONF_AGENT_TOKEN,
    CONF_ENDPOINTS,
    CONF_ENTITIES_INTERVAL,
    CONF_HEARTBEAT_INTERVAL,
    CONF_INSTANCE_ID,
    CONF_INSTANCE_NAME,
    CONF_LOCATION_NAME,
    CONF_PAIRING_CODE,
    CONF_PANEL_URL,
    CONF_SEND_ALL_ENTITIES,
    DEFAULT_ENTITIES_INTERVAL,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_PANEL_URL,
    DEFAULT_SEND_ALL_ENTITIES,
    DOMAIN,
    MIN_ENTITIES_INTERVAL,
    MIN_HEARTBEAT_INTERVAL,
)


class PDDashboardBridgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PD Dashboard Bridge."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            panel_url = normalize_panel_url(str(user_input[CONF_PANEL_URL]))
            pairing_code = str(user_input[CONF_PAIRING_CODE]).strip()
            client = DashboardApiClient(async_get_clientsession(self.hass), panel_url)

            try:
                result = await client.pair(
                    pairing_code,
                    app_version="0.1.0",
                    ha_version=HA_VERSION,
                )
            except DashboardAuthError:
                errors["base"] = "invalid_pairing_code"
            except DashboardCannotConnect:
                errors["base"] = "cannot_connect"
            except DashboardApiError:
                errors["base"] = "unknown"
            else:
                instance_id = int(result.get("instance_id") or 0)
                if instance_id:
                    await self.async_set_unique_id(f"pd_dashboard_bridge_{instance_id}")
                    self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=str(result.get("instance_name") or "PD Dashboard Bridge"),
                    data={
                        CONF_PANEL_URL: panel_url,
                        CONF_AGENT_TOKEN: str(result["agent_token"]),
                        CONF_INSTANCE_ID: instance_id,
                        CONF_INSTANCE_NAME: str(
                            result.get("instance_name") or "Home Assistant"
                        ),
                        CONF_LOCATION_NAME: str(result.get("location_name") or ""),
                        CONF_ENDPOINTS: dict(result.get("endpoints") or {}),
                    },
                    options={
                        CONF_HEARTBEAT_INTERVAL: int(
                            user_input[CONF_HEARTBEAT_INTERVAL]
                        ),
                        CONF_ENTITIES_INTERVAL: int(user_input[CONF_ENTITIES_INTERVAL]),
                        CONF_SEND_ALL_ENTITIES: bool(user_input[CONF_SEND_ALL_ENTITIES]),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PANEL_URL, default=DEFAULT_PANEL_URL): str,
                    vol.Required(CONF_PAIRING_CODE): str,
                    vol.Required(
                        CONF_HEARTBEAT_INTERVAL,
                        default=DEFAULT_HEARTBEAT_INTERVAL,
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_HEARTBEAT_INTERVAL)),
                    vol.Required(
                        CONF_ENTITIES_INTERVAL,
                        default=DEFAULT_ENTITIES_INTERVAL,
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_ENTITIES_INTERVAL)),
                    vol.Required(
                        CONF_SEND_ALL_ENTITIES,
                        default=DEFAULT_SEND_ALL_ENTITIES,
                    ): bool,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""

        return PDDashboardBridgeOptionsFlow()


class PDDashboardBridgeOptionsFlow(config_entries.OptionsFlow):
    """Handle integration options."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Manage integration options."""

        errors: dict[str, str] = {}
        data = self.config_entry.data
        if user_input is not None:
            panel_url = normalize_panel_url(str(user_input[CONF_PANEL_URL]))
            pairing_code = str(user_input.get(CONF_PAIRING_CODE) or "").strip()
            entry_data = dict(data)

            if pairing_code:
                client = DashboardApiClient(async_get_clientsession(self.hass), panel_url)
                try:
                    result = await client.pair(
                        pairing_code,
                        app_version="0.1.0",
                        ha_version=HA_VERSION,
                    )
                except DashboardAuthError:
                    errors["base"] = "invalid_pairing_code"
                except DashboardCannotConnect:
                    errors["base"] = "cannot_connect"
                except DashboardApiError:
                    errors["base"] = "unknown"
                else:
                    instance_id = int(result.get("instance_id") or 0)
                    entry_data.update(
                        {
                            CONF_PANEL_URL: panel_url,
                            CONF_AGENT_TOKEN: str(result["agent_token"]),
                            CONF_INSTANCE_ID: instance_id,
                            CONF_INSTANCE_NAME: str(
                                result.get("instance_name") or "Home Assistant"
                            ),
                            CONF_LOCATION_NAME: str(result.get("location_name") or ""),
                            CONF_ENDPOINTS: dict(result.get("endpoints") or {}),
                        }
                    )
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        title=str(result.get("instance_name") or self.config_entry.title),
                        data=entry_data,
                    )
            else:
                entry_data[CONF_PANEL_URL] = panel_url
                if entry_data != data:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=entry_data,
                    )

            if not errors:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_HEARTBEAT_INTERVAL: int(
                            user_input[CONF_HEARTBEAT_INTERVAL]
                        ),
                        CONF_ENTITIES_INTERVAL: int(user_input[CONF_ENTITIES_INTERVAL]),
                        CONF_SEND_ALL_ENTITIES: bool(user_input[CONF_SEND_ALL_ENTITIES]),
                    },
                )

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PANEL_URL,
                        default=data.get(CONF_PANEL_URL, DEFAULT_PANEL_URL),
                    ): str,
                    vol.Optional(CONF_PAIRING_CODE, default=""): str,
                    vol.Required(
                        CONF_HEARTBEAT_INTERVAL,
                        default=options.get(
                            CONF_HEARTBEAT_INTERVAL,
                            DEFAULT_HEARTBEAT_INTERVAL,
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_HEARTBEAT_INTERVAL)),
                    vol.Required(
                        CONF_ENTITIES_INTERVAL,
                        default=options.get(
                            CONF_ENTITIES_INTERVAL,
                            DEFAULT_ENTITIES_INTERVAL,
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_ENTITIES_INTERVAL)),
                    vol.Required(
                        CONF_SEND_ALL_ENTITIES,
                        default=options.get(
                            CONF_SEND_ALL_ENTITIES,
                            DEFAULT_SEND_ALL_ENTITIES,
                        ),
                    ): bool,
                }
            ),
            errors=errors,
        )
