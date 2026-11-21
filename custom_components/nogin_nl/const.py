"""Constants for the Nogin.nl integration."""

from datetime import timedelta
from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

API_BASE_URL = "https://api.nogin.nl"
DOMAIN = "nogin_nl"
CONF_PERSONS = "persons"
ATTRIBUTION = ""
CONF_LOCAL_TESTING_MODE = "local_testing_mode"
CONF_LOCAL_PEOPLE = "local_people"

# Polling interval while the API responds normally.
UPDATE_INTERVAL = timedelta(minutes=1)
# Faster polling interval while the API is failing, to pick up recovery quickly.
FAILURE_UPDATE_INTERVAL = timedelta(seconds=15)
# How long to keep the last known states before marking entities unavailable.
FAILURE_GRACE_PERIOD = timedelta(minutes=2)
