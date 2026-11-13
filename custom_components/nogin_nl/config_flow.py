"""Configure which Nogin.nl people have switches."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    NoginNLApiClient,
    NoginNLApiClientAuthenticationError,
    NoginNLApiClientCommunicationError,
    NoginNLApiClientError,
    NoginNLApiClientRateLimitError,
)
from .const import (
    CONF_LOCAL_PEOPLE,
    CONF_LOCAL_TESTING_MODE,
    CONF_PERSONS,
    DOMAIN,
    LOGGER,
)

if TYPE_CHECKING:
    from .data import NoginNLConfigEntry


async def _async_person_form(
    flow: config_entries.ConfigFlow | config_entries.OptionsFlow,
    step_id: str,
    selected: list[str] | None,
    user_input: dict[str, Any] | None,
) -> config_entries.ConfigFlowResult:
    """Fetch choices and handle the shared person selection form."""
    errors: dict[str, str] = {}
    names = set(selected or [])
    is_options = isinstance(flow, NoginNLOptionsFlow)
    current_local = is_options and flow.config_entry.data.get(
        CONF_LOCAL_TESTING_MODE, False
    )
    requested_local = (
        (user_input or {})
        .get("testing", {})
        .get(CONF_LOCAL_TESTING_MODE, current_local)
    )
    try:
        if current_local:
            people = flow.config_entry.data[CONF_LOCAL_PEOPLE]
        elif requested_local and flow.people is not None:
            people = flow.people
        else:
            client = NoginNLApiClient(async_get_clientsession(flow.hass))
            people = await client.async_get_data()
            flow.people = people or None
    except NoginNLApiClientAuthenticationError:
        errors["base"] = "auth"
    except NoginNLApiClientRateLimitError:
        errors["base"] = "rate_limit"
    except NoginNLApiClientCommunicationError:
        errors["base"] = "connection"
    except NoginNLApiClientError as exception:
        LOGGER.exception("Unexpected API error while fetching people: %s", exception)
        errors["base"] = "unknown"
    else:
        names.update(person["name"] for person in people)
        if not people:
            errors["base"] = "no_persons"
        if user_input is not None and names:
            chosen = user_input.get("person_selection", {}).get(CONF_PERSONS, [])
            if set(chosen).issubset(names):
                data = {CONF_PERSONS: chosen}
                if is_options:
                    entry_data = dict(flow.config_entry.data)
                    entry_data[CONF_LOCAL_TESTING_MODE] = requested_local
                    if requested_local and not current_local:
                        entry_data[CONF_LOCAL_PEOPLE] = people
                    flow.hass.config_entries.async_update_entry(
                        flow.config_entry, data=entry_data
                    )
                elif requested_local:
                    data[CONF_LOCAL_TESTING_MODE] = True
                    data[CONF_LOCAL_PEOPLE] = people
                return flow.async_create_entry(title="Nogin.nl", data=data)
            errors["base"] = "invalid_person"

    if user_input is not None:
        defaults = user_input.get("person_selection", {}).get(CONF_PERSONS, [])
    else:
        defaults = sorted(names) if selected is None else selected

    return flow.async_show_form(
        step_id=step_id,
        data_schema=vol.Schema(
            {
                vol.Required("person_selection"): section(
                    vol.Schema(
                        {
                            vol.Required(
                                CONF_PERSONS, default=defaults
                            ): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=[
                                        {"value": name, "label": name.capitalize()}
                                        for name in sorted(names)
                                    ],
                                    multiple=True,
                                    mode=selector.SelectSelectorMode.LIST,
                                )
                            ),
                        }
                    ),
                    {"collapsed": False},
                ),
                vol.Required("testing"): section(
                    vol.Schema(
                        {
                            vol.Optional(
                                CONF_LOCAL_TESTING_MODE, default=requested_local
                            ): bool,
                        }
                    ),
                    {"collapsed": not requested_local},
                ),
            }
        ),
        errors=errors,
    )


class NoginNLFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle initial person selection."""

    VERSION = 1

    people: list[dict[str, Any]] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: NoginNLConfigEntry,  # noqa: ARG004
    ) -> NoginNLOptionsFlow:
        """Allow changing selected people after setup."""
        return NoginNLOptionsFlow()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show the available people before creating the entry."""
        self._async_abort_entries_match()
        return await _async_person_form(self, "user", None, user_input)

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],  # noqa: ARG002
    ) -> config_entries.ConfigFlowResult:
        """Explain access denial when there are no supported credentials to change."""
        return self.async_abort(reason="authentication_not_supported")


class NoginNLOptionsFlow(config_entries.OptionsFlow):
    """Update person selection without restarting existing switches."""

    people: list[dict[str, Any]] | None = None

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show current selections and any newly available people."""
        selected = self.config_entry.options.get(
            CONF_PERSONS, self.config_entry.data.get(CONF_PERSONS, [])
        )
        return await _async_person_form(self, "init", selected, user_input)
