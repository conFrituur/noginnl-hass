"""Verify local testing never contacts the API after the initial snapshot."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant import config_entries
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir

from custom_components.nogin_nl.const import (
    CONF_LOCAL_PEOPLE,
    CONF_LOCAL_TESTING_MODE,
    CONF_PERSONS,
    DOMAIN,
)

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry


async def test_local_mode(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """Snapshot once, persist writes across reload, and select locally in options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert (
        result["data_schema"]({"person_selection": {}, "testing": {}})["testing"][
            CONF_LOCAL_TESTING_MODE
        ]
        is False
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "person_selection": {CONF_PERSONS: ["sjaak"]},
            "testing": {CONF_LOCAL_TESTING_MODE: True},
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    registry = ir.async_get(hass)
    issue_id = f"local_testing_mode_{entry.entry_id}"
    issue = registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.is_persistent
    assert issue.config_entry_id == entry.entry_id
    mock_api.async_get_data.assert_awaited_once()
    assert entry.data[CONF_LOCAL_PEOPLE] == mock_api.async_get_data.return_value
    assert entry.runtime_data.coordinator.update_interval is None
    mock_api.async_get_data.reset_mock()
    mock_api.async_get_data.side_effect = AssertionError("Unexpected live read")
    mock_api.async_set_nog_in_nl.side_effect = AssertionError("Unexpected live write")

    await hass.services.async_call(
        "switch",
        "turn_off",
        {ATTR_ENTITY_ID: "switch.nogin_nl_sjaak"},
        blocking=True,
    )
    assert entry.data[CONF_LOCAL_PEOPLE][0]["isNogInNL"] is False
    await entry.runtime_data.coordinator.async_refresh()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("switch.nogin_nl_sjaak").state == STATE_OFF
    assert registry.async_get_issue(DOMAIN, issue_id) is issue

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert (
        result["data_schema"]({"person_selection": {}, "testing": {}})["testing"][
            CONF_LOCAL_TESTING_MODE
        ]
        is True
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "person_selection": {CONF_PERSONS: ["sjaak", "harrie"]},
            "testing": {},
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert hass.states.get("switch.nogin_nl_harrie").state == STATE_OFF
    mock_api.async_get_data.assert_not_awaited()
    mock_api.async_set_nog_in_nl.assert_not_awaited()
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_change_mode_in_options(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Both mode transitions apply immediately without uploading test states."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data.coordinator
    registry = ir.async_get(hass)
    issue_id = f"local_testing_mode_{config_entry.entry_id}"
    assert registry.async_get_issue(DOMAIN, issue_id) is None
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert (
        result["data_schema"]({"person_selection": {}, "testing": {}})["testing"][
            CONF_LOCAL_TESTING_MODE
        ]
        is False
    )
    mock_api.async_get_data.reset_mock()
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "person_selection": {CONF_PERSONS: ["sjaak"]},
            "testing": {CONF_LOCAL_TESTING_MODE: True},
        },
    )
    await hass.async_block_till_done()
    assert config_entry.data[CONF_LOCAL_TESTING_MODE] is True
    issue = registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert coordinator.update_interval is None
    mock_api.async_get_data.assert_not_awaited()
    await hass.services.async_call(
        "switch",
        "turn_off",
        {ATTR_ENTITY_ID: "switch.family_sjaak"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("switch.family_sjaak").state == STATE_OFF
    assert registry.async_get_issue(DOMAIN, issue_id) is issue
    mock_api.async_get_data.assert_not_awaited()
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert (
        result["data_schema"]({"person_selection": {}, "testing": {}})["testing"][
            CONF_LOCAL_TESTING_MODE
        ]
        is True
    )
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "person_selection": {CONF_PERSONS: ["sjaak"]},
            "testing": {CONF_LOCAL_TESTING_MODE: False},
        },
    )
    await hass.async_block_till_done()
    assert config_entry.data[CONF_LOCAL_TESTING_MODE] is False
    assert registry.async_get_issue(DOMAIN, issue_id) is None
    assert coordinator.update_interval is not None
    assert config_entry.runtime_data.coordinator is coordinator
    mock_api.async_get_data.assert_awaited_once()
    mock_api.async_set_nog_in_nl.assert_not_awaited()
