"""Switches for the people selected in the Nogin.nl configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .const import CONF_PERSONS
from .entity import NoginNLEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import NoginNLDataUpdateCoordinator
    from .data import NoginNLConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NoginNLConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator = entry.runtime_data.coordinator
    registry = er.async_get(hass)
    known_people: set[str] = set()

    @callback
    def async_sync_selected_people() -> None:
        """Add and remove selected switches while leaving retained switches alone."""
        selected = entry.options.get(CONF_PERSONS, entry.data.get(CONF_PERSONS, []))
        selected_ids = {f"{entry.entry_id}_{name}" for name in selected}
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            if (
                entity.domain == "switch"
                and entity.platform == entry.domain
                and entity.unique_id not in selected_ids
            ):
                registry.async_remove(entity.entity_id)

        entities = []
        known_people.intersection_update(selected)
        for name in selected:
            if name not in known_people:
                known_people.add(name)
                entities.append(NoginNLSwitch(coordinator, name))
        if entities:
            async_add_entities(entities)

    async def async_update_options(
        _hass: HomeAssistant,
        _entry: NoginNLConfigEntry,
    ) -> None:
        """Apply options to this platform without reloading the config entry."""
        async_sync_selected_people()

    async_sync_selected_people()
    entry.async_on_unload(entry.add_update_listener(async_update_options))


class NoginNLSwitch(NoginNLEntity, SwitchEntity):
    """Represent a person's Nogin.nl status."""

    def __init__(
        self,
        coordinator: NoginNLDataUpdateCoordinator,
        person_name: str,
    ) -> None:
        """Initialize the switch class."""
        super().__init__(coordinator)
        self._person_name = person_name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{person_name}"
        self.entity_description = SwitchEntityDescription(
            key=person_name,
            name=person_name.capitalize(),
            icon="mdi:map-marker-account",
        )

    @property
    def available(self) -> bool:
        """Return whether polling succeeded and this person still exists."""
        return super().available and any(
            person.get("name") == self._person_name for person in self.coordinator.data
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        for person in self.coordinator.data:
            if person.get("name") == self._person_name:
                return person.get("isNogInNL")
        return None

    async def _async_set_status(self, *, is_nog_in_nl: bool) -> None:
        """Publish the status confirmed by PATCH without waiting for a GET."""
        person = (
            await self.coordinator.config_entry.runtime_data.client.async_set_nog_in_nl(
                self._person_name, is_nog_in_nl
            )
        )
        # Update local cache with PATCH reponse data
        updated_people = []
        for item in self.coordinator.data:
            if item.get("name") == self._person_name:
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
