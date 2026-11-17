"""Let users leave local testing mode directly from the repair dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.repairs import RepairsFlow

from .const import CONF_LOCAL_TESTING_MODE

if TYPE_CHECKING:
    from homeassistant.components.repairs import RepairsFlowResult
    from homeassistant.core import HomeAssistant


class NoginNLLocalTestingRepairFlow(RepairsFlow):
    """Turn off local testing mode for one config entry."""

    def __init__(self, entry_id: str) -> None:
        """Remember which entry the issue belongs to."""
        self._entry_id = entry_id

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> RepairsFlowResult:
        """Start with the confirmation step."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> RepairsFlowResult:
        """Disable local testing mode once the user confirms."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return self.async_abort(reason="entry_not_found")
        if user_input is not None:
            # Update listeners resume polling and clear the issue.
            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_LOCAL_TESTING_MODE: False}
            )
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="confirm", description_placeholders={"name": entry.title}
        )


async def async_create_fix_flow(
    hass: HomeAssistant,  # noqa: ARG001
    issue_id: str,  # noqa: ARG001
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the fix flow for a local testing mode issue."""
    return NoginNLLocalTestingRepairFlow(str((data or {})["entry_id"]))
