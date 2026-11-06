"""Test integration lifecycle and coordinator polling/error recovery."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.nogin_nl.api import (
    NoginNLApiClientAuthenticationError,
    NoginNLApiClientCommunicationError,
    NoginNLApiClientRateLimitError,
)

if TYPE_CHECKING:
    from unittest.mock import AsyncMock

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_polling_and_unload(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Refresh after one minute, then stop polling when the entry unloads."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    mock_api.async_get_data.reset_mock()
    mock_api.async_get_data.return_value = [{"name": "sjaak", "isNogInNL": False}]
    freezer.move_to(dt_util.utcnow() + timedelta(seconds=65))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    mock_api.async_get_data.assert_awaited_once()
    assert hass.states.get("switch.family_sjaak").state == STATE_OFF
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    mock_api.async_get_data.reset_mock()
    freezer.move_to(dt_util.utcnow() + timedelta(minutes=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    mock_api.async_get_data.assert_not_awaited()


@pytest.mark.parametrize(
    "error",
    [
        NoginNLApiClientCommunicationError("offline"),
        NoginNLApiClientRateLimitError("slow down", retry_after=120),
    ],
)
async def test_update_failure_and_recovery(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    config_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """Polling failures mark switches unavailable, and a later success restores them."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = config_entry.runtime_data.coordinator
    mock_api.async_get_data.side_effect = error
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert hass.states.get("switch.family_sjaak").state == STATE_UNAVAILABLE
    mock_api.async_get_data.side_effect = None
    mock_api.async_get_data.return_value = [{"name": "sjaak", "isNogInNL": False}]
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert hass.states.get("switch.family_sjaak").state == STATE_OFF


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (NoginNLApiClientCommunicationError("offline"), ConfigEntryState.SETUP_RETRY),
        (NoginNLApiClientAuthenticationError("denied"), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_first_refresh_failure(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    config_entry: MockConfigEntry,
    error: Exception,
    state: ConfigEntryState,
) -> None:
    """Failed initial requests do not create apparently working switches."""
    config_entry.add_to_hass(hass)
    mock_api.async_get_data.side_effect = error
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is state
    assert hass.states.get("switch.family_sjaak") is None


async def test_rate_limit_backoff(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Respect Retry-After instead of polling again after the usual minute."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_api.async_get_data.side_effect = NoginNLApiClientRateLimitError(
        "slow down", retry_after=120
    )
    await config_entry.runtime_data.coordinator.async_refresh()
    mock_api.async_get_data.reset_mock()
    mock_api.async_get_data.side_effect = None
    freezer.move_to(dt_util.utcnow() + timedelta(seconds=65))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    mock_api.async_get_data.assert_not_awaited()
    freezer.move_to(dt_util.utcnow() + timedelta(seconds=65))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    mock_api.async_get_data.assert_awaited_once()
