"""Verify request payloads, response decoding, and API error details."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest
from yarl import URL

from custom_components.nogin_nl.api import (
    NoginNLApiClient,
    NoginNLApiClientAuthenticationError,
    NoginNLApiClientCommunicationError,
    NoginNLApiClientError,
    NoginNLApiClientRateLimitError,
)

API_URL = "https://api.nogin.nl/persons"


@pytest.fixture
def response() -> Mock:
    """Provide a successful JSON response without making network requests."""
    return Mock(
        spec=aiohttp.ClientResponse,
        status=200,
        headers={},
        json=AsyncMock(return_value={"name": "sjaak", "isNogInNL": False}),
    )


@pytest.fixture
def session(response: Mock) -> Mock:
    """Provide an aiohttp session whose requests are mocked."""
    return Mock(spec=aiohttp.ClientSession, request=AsyncMock(return_value=response))


async def test_get_and_patch(session: Mock, response: Mock) -> None:
    """Read people and PATCH the named person with a JSON boolean."""
    client = NoginNLApiClient(session)
    people = [{"name": "sjaak", "isNogInNL": True}]
    response.json.return_value = people
    assert await client.async_get_data() == people
    session.request.assert_awaited_with(
        method="get", url=API_URL, headers=None, json=None
    )
    person = {"name": "harrie", "isNogInNL": False}
    response.json.return_value = person
    assert await client.async_set_nog_in_nl("harrie", False) == person
    session.request.assert_awaited_with(
        method="patch",
        url=f"{API_URL}/harrie",
        headers={"Content-type": "application/json; charset=UTF-8"},
        json={"isNogInNL": False},
    )


@pytest.mark.parametrize("status", [401, 403])
async def test_authentication_error(session: Mock, response: Mock, status: int) -> None:
    """Access denial stays an authentication error instead of a generic error."""
    response.status = status
    with pytest.raises(NoginNLApiClientAuthenticationError):
        await NoginNLApiClient(session).async_get_data()
    response.json.assert_not_awaited()


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, 60),
        ("3", 3),
        ("1.2", 2),
        ("0", 0),
        ("-1", 60),
        ("bad", 60),
        ("nan", 60),
        ("inf", 60),
    ],
)
async def test_rate_limit(
    session: Mock, response: Mock, header: str | None, expected: int
) -> None:
    """Honor numeric Retry-After and fall back safely for invalid headers."""
    response.status = 429
    response.headers = {} if header is None else {"Retry-After": header}
    with pytest.raises(NoginNLApiClientRateLimitError) as error:
        await NoginNLApiClient(session).async_get_data()
    assert error.value.retry_after == expected
    response.json.assert_not_awaited()


@pytest.mark.parametrize("status", [404, 500, 503])
async def test_http_error_details(session: Mock, response: Mock, status: int) -> None:
    """Unexpected HTTP errors retain method, URL, status, and original cause."""
    response.status = status
    cause = aiohttp.ClientResponseError(
        request_info=Mock(real_url=URL(API_URL)),
        history=(),
        status=status,
        message="Service error",
    )
    response.raise_for_status.side_effect = cause
    with pytest.raises(NoginNLApiClientError, match=f"HTTP {status}") as error:
        await NoginNLApiClient(session).async_get_data()
    assert type(error.value) is NoginNLApiClientError
    assert f"GET {API_URL}" in str(error.value)
    assert error.value.__cause__ is cause


@pytest.mark.parametrize("cause", [TimeoutError(), aiohttp.ClientConnectionError()])
async def test_connection_error(session: Mock, cause: Exception) -> None:
    """Timeouts and transport failures are retryable communication errors."""
    session.request.side_effect = cause
    with pytest.raises(NoginNLApiClientCommunicationError) as error:
        await NoginNLApiClient(session).async_get_data()
    assert error.value.__cause__ is cause


async def test_invalid_json(session: Mock, response: Mock) -> None:
    """Unexpected decoding failures include exception type and request context."""
    response.json.side_effect = ValueError("Invalid JSON")
    with pytest.raises(
        NoginNLApiClientError, match="ValueError: Invalid JSON"
    ) as error:
        await NoginNLApiClient(session).async_get_data()
    assert f"GET {API_URL}" in str(error.value)
