from __future__ import annotations

from homeassistant import config_entries
from .const import DOMAIN


class NoginNLFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        return self.async_create_entry(
            title="Nogin.nl",
            data={},
        )
