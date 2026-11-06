"""Configure which Nogin.nl people have switches."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NoginNLApiClient, NoginNLApiClientError
from .const import CONF_PERSONS, DOMAIN

if TYPE_CHECKING:
    from .data import NoginNLConfigEntry


async def _async_person_form(
    flow: config_entries.ConfigFlow | config_entries.OptionsFlow,
    step_id: str,
    selected: list[str],
    user_input: dict[str, Any] | None,
) -> config_entries.ConfigFlowResult:
    """Fetch choices and handle the shared person selection form."""
    errors: dict[str, str] = {}
    names = set(selected)
    try:
        client = NoginNLApiClient(async_get_clientsession(flow.hass))
        people = await client.async_get_data()
    except NoginNLApiClientError:
        errors["base"] = "connection"
    else:
        names.update(person["name"] for person in people)
        if user_input is not None:
            chosen = user_input.get(CONF_PERSONS, [])
            if set(chosen).issubset(names):
                return flow.async_create_entry(
                    title="Nogin.nl", data={CONF_PERSONS: chosen}
                )
            errors[CONF_PERSONS] = "invalid_person"

    return flow.async_show_form(
        step_id=step_id,
        data_schema=vol.Schema(
            {
                vol.Required(CONF_PERSONS, default=selected): selector.SelectSelector(
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
        errors=errors,
    )


class NoginNLFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle initial person selection."""

    VERSION = 1

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
        return await _async_person_form(self, "user", [], user_input)


class NoginNLOptionsFlow(config_entries.OptionsFlowWithReload):
    """Update person selection and reload the integration."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Show current selections and any newly available people."""
        selected = self.config_entry.options.get(
            CONF_PERSONS, self.config_entry.data.get(CONF_PERSONS, [])
        )
        return await _async_person_form(self, "init", selected, user_input)
