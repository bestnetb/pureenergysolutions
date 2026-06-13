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
    APP_VERSION,
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


async def _async_pair(
    hass,
    panel_url: str,
    pairing_code: str,
) -> dict[str, Any]:
    """Pair with the dashboard and return the API payload."""

    client = DashboardApiClient(async_get_clientsession(hass), panel_url)
    return await client.pair(
        pairing_code,
        app_version=APP_VERSION,
        ha_version=HA_VERSION,
    )


def _entry_data_from_pairing(panel_url: str, result: dict[str, Any]) -> dict[str, Any]:
    """Build config entry data from a successful pairing payload."""

    return {
        CONF_PANEL_URL: panel_url,
        CONF_AGENT_TOKEN: str(result["agent_token"]),
        CONF_INSTANCE_ID: int(result.get("instance_id") or 0),
        CONF_INSTANCE_NAME: str(result.get("instance_name") or "Home Assistant"),
        CONF_LOCATION_NAME: str(result.get("location_name") or ""),
        CONF_ENDPOINTS: dict(result.get("endpoints") or {}),
    }


def _pairing_matches_entry(entry_data: dict[str, Any], result: dict[str, Any]) -> bool:
    """Return true when a fresh pairing result belongs to the same instance."""

    current_id = int(entry_data.get(CONF_INSTANCE_ID) or 0)
    paired_id = int(result.get("instance_id") or 0)

    return current_id <= 0 or paired_id <= 0 or current_id == paired_id


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

            try:
                result = await _async_pair(self.hass, panel_url, pairing_code)
            except DashboardAuthError:
                errors["base"] = "invalid_pairing_code"
            except DashboardCannotConnect:
                errors["base"] = "cannot_connect"
            except DashboardApiError:
                errors["base"] = "unknown"
            else:
                instance_id = int(result.get("instance_id") or 0)
                entry_data = _entry_data_from_pairing(panel_url, result)
                if instance_id:
                    await self.async_set_unique_id(f"pd_dashboard_bridge_{instance_id}")
                    for entry in self._async_current_entries():
                        if (
                            entry.unique_id == f"pd_dashboard_bridge_{instance_id}"
                            or int(entry.data.get(CONF_INSTANCE_ID) or 0) == instance_id
                        ):
                            new_data = dict(entry.data)
                            new_data.update(entry_data)
                            self.hass.config_entries.async_update_entry(
                                entry,
                                title=str(result.get("instance_name") or entry.title),
                                data=new_data,
                            )
                            self.hass.async_create_task(
                                self.hass.config_entries.async_reload(entry.entry_id)
                            )
                            return self.async_abort(reason="reauth_successful")

                return self.async_create_entry(
                    title=str(result.get("instance_name") or "PD Dashboard Bridge"),
                    data=entry_data,
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

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle reauthentication when the stored agent token is rejected."""

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Repair the stored agent token with a fresh pairing code."""

        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        current_data = dict(entry.data) if entry is not None else {}

        if user_input is not None:
            panel_url = normalize_panel_url(str(user_input[CONF_PANEL_URL]))
            pairing_code = str(user_input[CONF_PAIRING_CODE]).strip()

            try:
                result = await _async_pair(self.hass, panel_url, pairing_code)
            except DashboardAuthError:
                errors["base"] = "invalid_pairing_code"
            except DashboardCannotConnect:
                errors["base"] = "cannot_connect"
            except DashboardApiError:
                errors["base"] = "unknown"
            else:
                if entry is None:
                    return self.async_abort(reason="unknown")

                if not _pairing_matches_entry(current_data, result):
                    errors["base"] = "wrong_instance"
                else:
                    new_data = current_data | _entry_data_from_pairing(panel_url, result)
                    self.hass.config_entries.async_update_entry(
                        entry,
                        title=str(result.get("instance_name") or entry.title),
                        data=new_data,
                    )
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(entry.entry_id)
                    )
                    return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PANEL_URL,
                        default=current_data.get(CONF_PANEL_URL, DEFAULT_PANEL_URL),
                    ): str,
                    vol.Required(CONF_PAIRING_CODE): str,
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
            should_reload = False

            if pairing_code:
                try:
                    result = await _async_pair(self.hass, panel_url, pairing_code)
                except DashboardAuthError:
                    errors["base"] = "invalid_pairing_code"
                except DashboardCannotConnect:
                    errors["base"] = "cannot_connect"
                except DashboardApiError:
                    errors["base"] = "unknown"
                else:
                    if not _pairing_matches_entry(data, result):
                        errors["base"] = "wrong_instance"
                    else:
                        entry_data.update(
                            _entry_data_from_pairing(panel_url, result)
                        )
                        self.hass.config_entries.async_update_entry(
                            self.config_entry,
                            title=str(result.get("instance_name") or self.config_entry.title),
                            data=entry_data,
                        )
                        should_reload = True
            else:
                entry_data[CONF_PANEL_URL] = panel_url
                if entry_data != data:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=entry_data,
                    )
                    should_reload = True

            if not errors:
                if should_reload:
                    self.hass.async_create_task(
                        self.hass.config_entries.async_reload(self.config_entry.entry_id)
                    )

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
