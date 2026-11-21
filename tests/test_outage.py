"""Verify short API outages are bridged before switches become unavailable."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import async_fire_time_changed

from custom_components.nogin_nl.api import (
    NoginNLApiClientCommunicationError,
    NoginNLApiClientError,
)
from custom_components.nogin_nl.const import (
    CONF_LOCAL_PEOPLE,
    CONF_LOCAL_TESTING_MODE,
    FAILURE_GRACE_PERIOD,
    FAILURE_UPDATE_INTERVAL,
    UPDATE_INTERVAL,
)

if TYPE_CHECKING:
    from datetime import timedelta
    from unittest.mock import AsyncMock

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry

ENTITY_ID = "switch.family_sjaak"
OUTAGE = NoginNLApiClientCommunicationError("Connection refused")


async def _advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    """Move time forward and run any polls that became due."""
    freezer.tick(delta)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


async def _setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the entry while the API is healthy."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON


async def _start_outage(
    hass: HomeAssistant, mock_api: AsyncMock, freezer: FrozenDateTimeFactory
) -> None:
    """Let the API fail and run the first failing poll."""
    mock_api.async_get_data.reset_mock()
    mock_api.async_get_data.side_effect = OUTAGE
    await _advance(hass, freezer, UPDATE_INTERVAL)
    mock_api.async_get_data.assert_awaited_once()


async def test_outage_becomes_unavailable_after_grace_period(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Poll every 15s for two minutes, then go unavailable and poll every minute."""
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data.coordinator
    await _start_outage(hass, mock_api, freezer)
    assert coordinator.update_interval == FAILURE_UPDATE_INTERVAL

    polls_in_grace = int(FAILURE_GRACE_PERIOD / FAILURE_UPDATE_INTERVAL) - 1
    for _ in range(polls_in_grace):
        await _advance(hass, freezer, FAILURE_UPDATE_INTERVAL)
        assert hass.states.get(ENTITY_ID).state == STATE_ON
        assert coordinator.last_update_success
    assert mock_api.async_get_data.await_count == 1 + polls_in_grace

    await _advance(hass, freezer, FAILURE_UPDATE_INTERVAL)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert not coordinator.last_update_success

    # Once unavailable, polling returns to the normal interval.
    assert coordinator.update_interval == UPDATE_INTERVAL
    mock_api.async_get_data.reset_mock()
    await _advance(hass, freezer, FAILURE_UPDATE_INTERVAL)
    mock_api.async_get_data.assert_not_awaited()
    await _advance(hass, freezer, UPDATE_INTERVAL - FAILURE_UPDATE_INTERVAL)
    mock_api.async_get_data.assert_awaited_once()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert coordinator.update_interval == UPDATE_INTERVAL

    mock_api.async_get_data.side_effect = None
    mock_api.async_get_data.return_value = [{"name": "sjaak", "isNogInNL": False}]
    await _advance(hass, freezer, UPDATE_INTERVAL)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    assert coordinator.update_interval == UPDATE_INTERVAL


async def test_recovery_within_grace_period(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A reboot shorter than the grace period never makes switches unavailable."""
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data.coordinator
    await _start_outage(hass, mock_api, freezer)
    assert (
        "Nogin.nl API unreachable, keeping last known states for up to 120 seconds: "
        "Connection refused"
    ) in caplog.text
    await _advance(hass, freezer, FAILURE_UPDATE_INTERVAL)
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    mock_api.async_get_data.side_effect = None
    mock_api.async_get_data.return_value = [{"name": "sjaak", "isNogInNL": False}]
    await _advance(hass, freezer, FAILURE_UPDATE_INTERVAL)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    assert coordinator.update_interval == UPDATE_INTERVAL

    # A later outage gets a full new grace period instead of continuing the old one.
    await _advance(hass, freezer, FAILURE_GRACE_PERIOD)
    await _start_outage(hass, mock_api, freezer)
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    assert coordinator.last_update_success


async def test_http_errors_use_grace_period(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A proxy answering 502 while the API restarts is also bridged."""
    await _setup(hass, config_entry)
    mock_api.async_get_data.side_effect = NoginNLApiClientError("HTTP 502")
    await _advance(hass, freezer, UPDATE_INTERVAL)
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert config_entry.runtime_data.coordinator.last_update_success


async def test_mode_change_resets_outage(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Switching local testing mode off again starts with a fresh grace period."""
    await _setup(hass, config_entry)
    coordinator = config_entry.runtime_data.coordinator
    await _start_outage(hass, mock_api, freezer)

    hass.config_entries.async_update_entry(
        config_entry,
        data={
            **config_entry.data,
            CONF_LOCAL_TESTING_MODE: True,
            CONF_LOCAL_PEOPLE: coordinator.data,
        },
    )
    await hass.async_block_till_done()
    assert coordinator.update_interval is None

    await _advance(hass, freezer, FAILURE_GRACE_PERIOD * 2)
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, CONF_LOCAL_TESTING_MODE: False}
    )
    await hass.async_block_till_done()
    # The refresh after leaving local mode fails, but this is a new outage.
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert coordinator.last_update_success
    assert coordinator.update_interval == FAILURE_UPDATE_INTERVAL


async def test_toggle_during_grace_period(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed write explains itself, and a successful write is published."""
    await _setup(hass, config_entry)
    await _start_outage(hass, mock_api, freezer)

    mock_api.async_set_nog_in_nl.side_effect = OUTAGE
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            "switch", "turn_off", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    assert exc_info.value.translation_key == "set_status_failed"
    assert str(exc_info.value) == (
        "Could not update state for Sjaak on Nogin.nl: Connection refused"
    )
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    mock_api.async_set_nog_in_nl.side_effect = None
    mock_api.async_set_nog_in_nl.return_value = {"name": "sjaak", "isNogInNL": False}
    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


async def test_unavailable_switch_cannot_be_toggled(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Once the grace period is over, service calls never reach the API."""
    await _setup(hass, config_entry)
    await _start_outage(hass, mock_api, freezer)
    await _advance(hass, freezer, FAILURE_GRACE_PERIOD)
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_api.async_set_nog_in_nl.assert_not_awaited()
