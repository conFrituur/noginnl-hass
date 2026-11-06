"""Test setup and options through Home Assistant's flow manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

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
    from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_setup_selection(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """Initially tick everyone, display capitalized labels, and save a subset."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    schema = result["data_schema"]
    assert schema({}) == {CONF_PERSONS: ["harrie", "sjaak"]}
    select = next(iter(schema.schema.values()))
    assert select.config["options"] == [
        {"value": "harrie", "label": "Harrie"},
        {"value": "sjaak", "label": "Sjaak"},
    ]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PERSONS: ["sjaak"]}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_PERSONS: ["sjaak"]}
    mock_api.async_get_data.assert_awaited()


@pytest.mark.parametrize("selected", [[], ["harrie"]])
async def test_options_selection(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    config_entry: MockConfigEntry,
    selected: list[str],
) -> None:
    """Options preserve defaults and reload switches when selection changes."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["data_schema"]({}) == {CONF_PERSONS: ["sjaak"]}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_PERSONS: selected}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_PERSONS: selected}
    assert hass.states.get("switch.family_sjaak") is None
    assert (hass.states.get("switch.family_harrie") is not None) == bool(selected)
    assert mock_api.async_get_data.await_count > 1


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
    """Display distinct errors, block saving, and allow a successful retry."""
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
    result = await manager.async_configure(result["flow_id"], {CONF_PERSONS: []})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}
    if expected == "unknown":
        assert "Unexpected API error while fetching people: HTTP 503" in caplog.text
    mock_api.async_get_data.side_effect = None
    result = await manager.async_configure(result["flow_id"], {CONF_PERSONS: []})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_empty_api_and_recovery(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """An empty API keeps setup open with a clear message until retried."""
    mock_api.async_get_data.return_value = []
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["errors"] == {"base": "no_persons"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PERSONS: []}
    )
    assert result["type"] is FlowResultType.FORM
    mock_api.async_get_data.return_value = [{"name": "sjaak", "isNogInNL": True}]
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PERSONS: ["sjaak"]}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_missing_selected_person(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """An empty API still lets options retain or remove previous selections."""
    config_entry.add_to_hass(hass)
    mock_api.async_get_data.return_value = []
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["errors"] == {"base": "no_persons"}
    assert result["data_schema"]({}) == {CONF_PERSONS: ["sjaak"]}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_PERSONS: []}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {CONF_PERSONS: []}


async def test_duplicate_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A second setup redirects users to the existing integration's options."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_person_removed_before_submission(
    hass: HomeAssistant, mock_api: AsyncMock
) -> None:
    """Reject a person who disappeared after the selection form was displayed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_api.async_get_data.return_value = [{"name": "harrie", "isNogInNL": False}]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PERSONS: ["sjaak"]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_PERSONS: "invalid_person"}
