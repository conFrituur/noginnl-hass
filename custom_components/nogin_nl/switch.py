from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription

from .entity import NoginNLEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import NoginNLDataUpdateCoordinator
    from .data import NoginNLConfigEntry

ENTITY_DESCRIPTIONS = (
    SwitchEntityDescription(
        key="nogin_nl_stefan",
        name="Nogin.nl Stefan",
        icon="mdi:map-marker-account",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: NoginNLConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    async_add_entities(
        NoginNLSwitch(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class NoginNLSwitch(NoginNLEntity, SwitchEntity):
    """Represent a person's Nogin.nl status."""

    def __init__(
        self,
        coordinator: NoginNLDataUpdateCoordinator,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch class."""
        super().__init__(coordinator)
        self.entity_description = entity_description

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        for person in self.coordinator.data:
            if person.get("name") == "stefan":
                return person.get("isNogInNL")
        return None

    async def _async_set_status(self, *, is_nog_in_nl: bool) -> None:
        """Publish the status confirmed by PATCH without waiting for a GET."""
        person = (
            await self.coordinator.config_entry.runtime_data.client.async_set_nog_in_nl(
                "stefan", is_nog_in_nl
            )
        )
        updated_people = []
        for item in self.coordinator.data:
            if item.get("name") == "stefan":
                updated_people.append(person)
            else:
                updated_people.append(item)

        self.coordinator.async_set_updated_data(updated_people)

    async def async_turn_on(self, **_: Any) -> None:
        """Turn on the switch."""
        await self._async_set_status(is_nog_in_nl=True)

    async def async_turn_off(self, **_: Any) -> None:
        """Turn off the switch."""
        await self._async_set_status(is_nog_in_nl=False)
