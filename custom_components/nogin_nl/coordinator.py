"""Coordinate polling and API error handling for Nogin.nl."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    NoginNLApiClientAuthenticationError,
    NoginNLApiClientError,
    NoginNLApiClientRateLimitError,
)
from .const import (
    CONF_LOCAL_PEOPLE,
    CONF_LOCAL_TESTING_MODE,
    DOMAIN,
    FAILURE_GRACE_PERIOD,
    FAILURE_UPDATE_INTERVAL,
    LOGGER,
    UPDATE_INTERVAL,
)

if TYPE_CHECKING:
    from datetime import datetime, timedelta

    from homeassistant.core import HomeAssistant

    from .data import NoginNLConfigEntry


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class NoginNLDataUpdateCoordinator(DataUpdateCoordinator):
    """
    Class to manage fetching data from the API.

    Short API outages, such as a server reboot, are bridged by keeping the last
    known data for up to FAILURE_GRACE_PERIOD while polling every
    FAILURE_UPDATE_INTERVAL. Only when the API stays unreachable for longer do
    the entities become unavailable.
    """

    config_entry: NoginNLConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: NoginNLConfigEntry) -> None:
        """Initialize the coordinator with the interval matching the entry's mode."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=self._normal_update_interval(config_entry),
            config_entry=config_entry,
        )
        self._failing_since: datetime | None = None

    @staticmethod
    def _normal_update_interval(
        config_entry: NoginNLConfigEntry,
    ) -> timedelta | None:
        """Return the polling interval to use while the API is healthy."""
        if config_entry.data.get(CONF_LOCAL_TESTING_MODE, False):
            return None
        return UPDATE_INTERVAL

    @callback
    def async_reset_polling(self) -> None:
        """Forget earlier failures and restore the interval for the current mode."""
        self._failing_since = None
        self.update_interval = self._normal_update_interval(self.config_entry)

    async def _async_update_data(self) -> Any:
        """Update data via library."""
        if self.config_entry.data.get(CONF_LOCAL_TESTING_MODE, False):
            return self.config_entry.data[CONF_LOCAL_PEOPLE]
        try:
            data = await self.config_entry.runtime_data.client.async_get_data()
        except NoginNLApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except NoginNLApiClientRateLimitError as exception:
            raise UpdateFailed(
                exception,
                retry_after=exception.retry_after,
            ) from exception
        except NoginNLApiClientError as exception:
            return self._handle_failure(exception)

        if self._failing_since is not None and self.last_update_success:
            LOGGER.info("Nogin.nl API is reachable again")
        self.async_reset_polling()
        return data

    def _handle_failure(self, exception: NoginNLApiClientError) -> Any:
        """
        Keep the last known data during the grace period, then fail.

        Polling is fast during the grace period to bridge short outages, and
        returns to the normal interval once the entities are unavailable.
        """
        now = dt_util.utcnow()
        first_failure = self._failing_since is None
        if self._failing_since is None:
            self._failing_since = now

        if self.data is not None and now - self._failing_since < FAILURE_GRACE_PERIOD:
            self.update_interval = FAILURE_UPDATE_INTERVAL
            if first_failure:
                LOGGER.warning(
                    "Nogin.nl API unreachable, keeping last known states for up "
                    "to %d seconds: %s",
                    FAILURE_GRACE_PERIOD.total_seconds(),
                    exception,
                )
            else:
                LOGGER.debug("Nogin.nl API still unreachable: %s", exception)
            return self.data
        self.update_interval = self._normal_update_interval(self.config_entry)
        raise UpdateFailed(exception) from exception
