from __future__ import annotations

import asyncio
import math
import socket
from contextlib import suppress
from http import HTTPStatus
from typing import Any

import aiohttp


class NoginNLApiClientError(Exception):
    """Exception to indicate a general API error."""


class NoginNLApiClientCommunicationError(
    NoginNLApiClientError,
):
    """Exception to indicate a communication error."""


class NoginNLApiClientAuthenticationError(
    NoginNLApiClientError,
):
    """Exception to indicate an authentication error."""


class NoginNLApiClientRateLimitError(
    NoginNLApiClientCommunicationError,
):
    """Exception to indicate the API is rate limiting us."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        """Store the backoff period requested by the API."""
        super().__init__(message)
        self.retry_after = retry_after


def _parse_retry_after(response: aiohttp.ClientResponse) -> int:
    """Return the backoff period (whole seconds) from the Retry-After header."""
    value: float | None = None
    retry_after = response.headers.get("Retry-After")
    if retry_after is not None:
        with suppress(ValueError):
            value = float(retry_after)
    if value is not None and math.isfinite(value) and value >= 0:
        return math.ceil(value)
    return 60


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (401, 403):
        msg = "Invalid credentials"
        raise NoginNLApiClientAuthenticationError(
            msg,
        )
    if response.status == HTTPStatus.TOO_MANY_REQUESTS:
        msg = "Rate limited by the API"
        raise NoginNLApiClientRateLimitError(
            msg,
            retry_after=_parse_retry_after(response),
        )
    response.raise_for_status()


class NoginNLApiClient:
    def __init__(
        self,
        session: aiohttp.ClientSession,
    ) -> None:
        self._session = session

    async def async_get_data(self) -> Any:
        """Get data from the API."""
        return await self._api_wrapper(
            method="get",
            url="https://api.nogin.nl/persons",
        )

    async def async_set_nog_in_nl(self, name: str, is_nog_in_nl: bool) -> Any:
        """Get data from the API."""
        return await self._api_wrapper(
            method="patch",
            url="https://api.nogin.nl/persons/" + name,
            data={"isNogInNL": is_nog_in_nl},
            headers={"Content-type": "application/json; charset=UTF-8"},
        )

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> Any:
        """Get information from the API."""
        try:
            async with asyncio.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                )
                _verify_response_or_raise(response)
                return await response.json()

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise NoginNLApiClientCommunicationError(
                msg,
            ) from exception
        except aiohttp.ClientResponseError as exception:
            msg = (
                f"API response error for {method.upper()} {url}: "
                f"HTTP {exception.status} ({exception.message})"
            )
            raise NoginNLApiClientError(msg) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise NoginNLApiClientCommunicationError(
                msg,
            ) from exception
        except NoginNLApiClientError:
            # Our own typed errors (auth, rate-limit, communication) are already
            # meaningful; re-raise so callers can branch on them instead of masking
            # them with the broad handler below.
            raise
        except Exception as exception:  # pylint: disable=broad-except
            msg = (
                f"Unexpected error for {method.upper()} {url}: "
                f"{type(exception).__name__}: {exception}"
            )
            raise NoginNLApiClientError(
                msg,
            ) from exception
