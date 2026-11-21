"""Test setup and options through Home Assistant's flow manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from custom_components.nogin_nl.api import (
    NoginNLApiClientAuthenticationError,
    NoginNLApiClientCommunicationError,
    NoginNLApiClientError,
    NoginNLApiClientRateLimitError,
)
from custom_components.nogin_nl.const import CONF_PERSONS, DOMAIN

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry


def _selection(persons: list[str]) -> dict:
    """Build form input for the person selection section."""
    return {"person_selection": {CONF_PERSONS: persons}, "testing": {}}


@pytest.mark.parametrize("step", ["user", "init"])
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (NoginNLApiClientAuthenticationError("denied"), "auth"),
        (NoginNLApiClientRateLimitError("slow down", retry_after=60), "rate_limit"),
        (NoginNLApiClientCommunicationError("offline"), "connection"),
        (NoginNLApiClientError("HTTP 503"), "unknown"),
    ],
)
async def test_api_errors_and_retry(  # noqa: PLR0913
    hass: HomeAssistant,
    mock_api: AsyncMock,
    config_entry: MockConfigEntry,
    step: str,
    error: NoginNLApiClientError,
    expected: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Display distinct errors, keep the submitted selection, and allow a retry."""
    mock_api.async_get_data.side_effect = error
    if step == "user":
        manager = hass.config_entries.flow
        result = await manager.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    else:
        config_entry.add_to_hass(hass)
        manager = hass.config_entries.options
        result = await manager.async_init(config_entry.entry_id)
    assert result["errors"] == {"base": expected}

    result = await manager.async_configure(result["flow_id"], _selection([]))
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}
    defaults = result["data_schema"]({"person_selection": {}, "testing": {}})
    assert defaults["person_selection"] == {CONF_PERSONS: []}
    if expected == "unknown":
        assert "Unexpected API error while fetching people: HTTP 503" in caplog.text

    mock_api.async_get_data.side_effect = None
    result = await manager.async_configure(result["flow_id"], _selection([]))
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_empty_api(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """An empty API keeps setup open with a clear message."""
    mock_api.async_get_data.return_value = []
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_persons"}


async def test_person_removed_before_submission(
    hass: HomeAssistant, mock_api: AsyncMock
) -> None:
    """Reject a person who disappeared after the selection form was displayed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_api.async_get_data.return_value = [{"name": "harrie", "isNogInNL": False}]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _selection(["sjaak"])
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_person"}


async def test_options_deselect_removes_switch(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Unticking a person removes their switch from the entity registry."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert registry.async_get("switch.family_sjaak") is not None

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], _selection(["harrie"])
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert registry.async_get("switch.family_sjaak") is None
    assert hass.states.get("switch.family_sjaak") is None
    assert hass.states.get("switch.family_harrie") is not None
    mock_api.async_set_nog_in_nl.assert_not_awaited()
