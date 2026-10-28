"""
HTTP client for the Personal Intelligence app (HUB-04, ADR-042).

Reads two routes of its API (personal-intelligence SPECS API-01) with the
Bearer token (SEC-04/SEC-05). The token is read from ``PI_API_TOKEN`` or the
token file on every call and never logged, printed or put into an error
message.
"""

import os
from pathlib import Path
from typing import Any

import httpx

TOKEN_ENV = "PI_API_TOKEN"
DIRECTION_MAP_PATH = "/api/topics/career/direction-map"
SERVICES_PATH = "/api/services"


class PersonalIntelligenceUnavailableError(Exception):
    """The API could not be reached or refused the request. Never carries the token."""


def read_token(token_file: str) -> str:
    """Return the Bearer token from ``PI_API_TOKEN``, else from *token_file*.

    Raises PersonalIntelligenceUnavailableError if neither holds a token.
    """
    token = os.environ.get(TOKEN_ENV, "").strip()
    if token:
        return token
    path = Path(token_file).expanduser()
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise PersonalIntelligenceUnavailableError(
            f"No API token: {TOKEN_ENV} is unset and {path} can't be read ({type(e).__name__})."
        ) from None
    if not token:
        raise PersonalIntelligenceUnavailableError(f"No API token: {path} is empty.")
    return token


class PersonalIntelligenceClient:
    """Thin read-only client for the Personal Intelligence API."""

    def __init__(
        self,
        base_url: str,
        token_file: str,
        timeout_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._token_file = token_file
        self._timeout = timeout_seconds
        self._transport = transport

    def direction_map(self) -> dict[str, Any] | None:
        """The current career direction map, or None if the app has none yet (404)."""
        return self._get(DIRECTION_MAP_PATH, none_on_404=True)

    def services(self) -> dict[str, Any]:
        """The suite health list (``{"services": [...]}``)."""
        result = self._get(SERVICES_PATH)
        if result is None:  # only possible with none_on_404
            raise PersonalIntelligenceUnavailableError(f"{SERVICES_PATH} returned nothing.")
        return result

    def _get(self, path: str, none_on_404: bool = False) -> dict[str, Any] | None:
        headers = {"Authorization": f"Bearer {read_token(self._token_file)}"}
        url = f"{self._base_url}{path}"
        try:
            with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                response = client.get(url, headers=headers)
        except httpx.TimeoutException:
            raise PersonalIntelligenceUnavailableError(f"{url} timed out after {self._timeout:g}s.") from None
        except httpx.HTTPError as e:
            raise PersonalIntelligenceUnavailableError(
                f"{self._base_url} is not reachable ({type(e).__name__}). Is the app's LaunchAgent running?"
            ) from None
        if response.status_code == 404 and none_on_404:
            return None
        if response.status_code in (401, 403):
            raise PersonalIntelligenceUnavailableError(
                f"{url} refused the token (HTTP {response.status_code}). Check {TOKEN_ENV} or the token file."
            )
        if response.status_code != 200:
            raise PersonalIntelligenceUnavailableError(f"{url} answered HTTP {response.status_code}.")
        try:
            body = response.json()
        except ValueError:
            raise PersonalIntelligenceUnavailableError(f"{url} did not return JSON.") from None
        if not isinstance(body, dict):
            raise PersonalIntelligenceUnavailableError(f"{url} returned {type(body).__name__}, not an object.")
        return body
