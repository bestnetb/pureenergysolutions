"""HTTP client helpers for PD Dashboard Bridge."""

from __future__ import annotations

import asyncio
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession


class DashboardApiError(Exception):
    """Base error raised by the dashboard API client."""


class DashboardCannotConnect(DashboardApiError):
    """Raised when the integration cannot reach the dashboard."""


class DashboardAuthError(DashboardApiError):
    """Raised when the dashboard rejects credentials or pairing code."""


class DashboardApiClient:
    """Small async client for the PD dashboard API."""

    def __init__(
        self,
        session: ClientSession,
        panel_url: str,
        agent_token: str | None = None,
    ) -> None:
        self._session = session
        self.panel_url = normalize_panel_url(panel_url)
        self.agent_token = agent_token or ""

    async def pair(
        self,
        pairing_code: str,
        app_version: str,
        ha_version: str,
    ) -> dict[str, Any]:
        """Pair this Home Assistant instance with the dashboard."""

        return await self.post(
            "agent_pair",
            {
                "pairing_code": pairing_code,
                "app_version": app_version,
                "ha_version": ha_version,
            },
            include_token=False,
        )

    async def heartbeat(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a heartbeat to the dashboard."""

        return await self.post("agent_heartbeat", payload)

    async def entities(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send entity states to the dashboard."""

        return await self.post("agent_entities", payload)

    async def post(
        self,
        action: str,
        payload: dict[str, Any],
        *,
        include_token: bool = True,
    ) -> dict[str, Any]:
        """POST a JSON payload to a dashboard API action."""

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "pd-dashboard-bridge/0.1.0",
        }
        if include_token and self.agent_token:
            headers["Authorization"] = f"Bearer {self.agent_token}"

        try:
            async with asyncio.timeout(25):
                response = await self._session.post(
                    self.action_url(action),
                    json=payload,
                    headers=headers,
                )
                data = await response.json(content_type=None)
        except (TimeoutError, ClientError) as err:
            raise DashboardCannotConnect(str(err)) from err
        except Exception as err:  # noqa: BLE001 - HA should surface API parse errors as a setup error.
            raise DashboardCannotConnect(str(err)) from err

        if response.status in {401, 403}:
            raise DashboardAuthError(str(data.get("message") or "Brak autoryzacji panelu."))

        try:
            response.raise_for_status()
        except ClientResponseError as err:
            raise DashboardCannotConnect(str(data.get("message") or err)) from err

        if not isinstance(data, dict):
            raise DashboardCannotConnect("Panel zwrocil niepoprawna odpowiedz JSON.")

        if not data.get("ok", False):
            raise DashboardApiError(str(data.get("message") or "Panel odrzucil zadanie."))

        return data

    def action_url(self, action: str) -> str:
        """Build an API URL for a dashboard action."""

        return f"{self.panel_url}/api.php?action={action}"


def normalize_panel_url(value: str) -> str:
    """Normalize dashboard base URL entered by the user."""

    url = str(value or "").strip()
    if not url:
        return "https://pd.best-net.pl"

    url = url.rstrip("/")
    if url.endswith("/api.php"):
        url = url[: -len("/api.php")]
    if url.endswith("/login"):
        url = url[: -len("/login")]

    return url.rstrip("/")
