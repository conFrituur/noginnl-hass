"""Exercise real Home Assistant switch entities with mocked API responses."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er

from custom_components.nogin_nl.api import NoginNLApiClientError
from custom_components.nogin_nl.const import CONF_PERSONS
from custom_components.nogin_nl.switch import NoginNLSwitch

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry


async def test_selected_people_only(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Only selected people get switches, including after new people appear."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("switch.family_sjaak")
    assert state is not None
    assert state.state == STATE_ON
    assert hass.states.get("switch.family_harrie") is None
    registry = er.async_get(hass)
    entity = registry.async_get(state.entity_id)
    assert entity.unique_id == f"{config_entry.entry_id}_sjaak"
    coordinator = config_entry.runtime_data.coordinator
    mock_api.async_get_data.return_value.append({"name": "new", "isNogInNL": True})
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("switch.family_new") is None


@pytest.mark.parametrize(
    ("service", "expected"), [("turn_on", True), ("turn_off", False)]
)
async def test_toggle_uses_patch_response(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    config_entry: MockConfigEntry,
    service: str,
    expected: bool,  # noqa: FBT001
) -> None:
    """Publish the PATCH response immediately without another GET or data loss."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_api.async_get_data.reset_mock()
    mock_api.async_set_nog_in_nl.return_value = {"name": "sjaak", "isNogInNL": expected}
    await hass.services.async_call(
        "switch", service, {ATTR_ENTITY_ID: "switch.family_sjaak"}, blocking=True
    )
    mock_api.async_set_nog_in_nl.assert_awaited_once_with("sjaak", expected)
    mock_api.async_get_data.assert_not_awaited()
    assert hass.states.get("switch.family_sjaak").state == (
        STATE_ON if expected else STATE_OFF
    )
    assert config_entry.runtime_data.coordinator.data[1] == {
        "name": "harrie",
        "isNogInNL": False,
    }


async def test_patch_failure_preserves_state(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """A failed write must not falsely publish the requested state."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_api.async_set_nog_in_nl.side_effect = NoginNLApiClientError("PATCH failed")
    with pytest.raises(NoginNLApiClientError, match="PATCH failed"):
        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: "switch.family_sjaak"}, blocking=True
        )
    assert hass.states.get("switch.family_sjaak").state == STATE_ON


async def test_missing_person_and_recovery(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Missing people become unavailable and recover without being recreated."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data.coordinator
    mock_api.async_get_data.return_value = []
    await coordinator.async_refresh()
    assert hass.states.get("switch.family_sjaak").state == STATE_UNAVAILABLE
    missing_switch = NoginNLSwitch(coordinator, "sjaak")
    assert missing_switch.is_on is None
    assert not missing_switch.available
    mock_api.async_get_data.return_value = [{"name": "sjaak", "isNogInNL": False}]
    await coordinator.async_refresh()
    assert hass.states.get("switch.family_sjaak").state == STATE_OFF


async def test_unique_person_switches(
    hass: HomeAssistant, mock_api: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Two selected people have independent states and stable unique IDs."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, data={CONF_PERSONS: ["sjaak", "harrie"]}
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("switch.family_sjaak").state == STATE_ON
    assert hass.states.get("switch.family_harrie").state == STATE_OFF
    registry = er.async_get(hass)
    assert (
        registry.async_get("switch.family_sjaak").unique_id
        != registry.async_get("switch.family_harrie").unique_id
    )
    mock_api.async_set_nog_in_nl.return_value = {"name": "harrie", "isNogInNL": True}
    await hass.services.async_call(
        "switch", "turn_on", {ATTR_ENTITY_ID: "switch.family_harrie"}, blocking=True
    )
    mock_api.async_set_nog_in_nl.assert_awaited_once_with("harrie", True)
    assert hass.states.get("switch.family_sjaak").state == STATE_ON
