"""Shared fixtures with all Nogin.nl requests mocked."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.nogin_nl.api import NoginNLApiClient
from custom_components.nogin_nl.const import CONF_PERSONS, DOMAIN

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def mock_api() -> Generator[AsyncMock]:
    """Mock the API at every integration entry point."""
    client = AsyncMock(spec=NoginNLApiClient)
    client.async_get_data.return_value = [
        {"name": "sjaak", "isNogInNL": True},
        {"name": "harrie", "isNogInNL": False},
    ]
    with (
        patch("custom_components.nogin_nl.NoginNLApiClient", return_value=client),
        patch(
            "custom_components.nogin_nl.config_flow.NoginNLApiClient",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Provide an entry with one selected person."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Family",
        data={CONF_PERSONS: ["sjaak"]},
    )
