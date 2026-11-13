"""
Custom integration to integrate integration_blueprint with Home Assistant.

For more details about this integration, please refer to
https://github.com/ludeeus/integration_blueprint
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import NoginNLApiClient
from .const import CONF_LOCAL_TESTING_MODE, DOMAIN, LOGGER
from .coordinator import NoginNLDataUpdateCoordinator
from .data import NoginNLData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import NoginNLConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: NoginNLConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    coordinator = NoginNLDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        update_interval=(
            None
            if entry.data.get(CONF_LOCAL_TESTING_MODE, False)
            else timedelta(minutes=1)
        ),
        config_entry=entry,
    )
    entry.runtime_data = NoginNLData(
        client=NoginNLApiClient(
            session=async_get_clientsession(hass),
        ),
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    await async_update_testing_warning(hass, entry)
    entry.async_on_unload(entry.add_update_listener(async_update_testing_warning))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: NoginNLConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_testing_warning(
    hass: HomeAssistant,
    entry: NoginNLConfigEntry,
) -> None:
    """Keep a persistent reminder while this entry uses local testing mode."""
    issue_id = f"local_testing_mode_{entry.entry_id}"
    if entry.data.get(CONF_LOCAL_TESTING_MODE, False):
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            config_entry_id=entry.entry_id,
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="local_testing_mode",
            translation_placeholders={"name": entry.title},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
