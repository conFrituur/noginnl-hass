"""Constants for the Nogin.nl integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

API_BASE_URL = "https://api.nogin.nl"
DOMAIN = "nogin_nl"
CONF_PERSONS = "persons"
ATTRIBUTION = ""
CONF_LOCAL_TESTING_MODE = "local_testing_mode"
CONF_LOCAL_PEOPLE = "local_people"
