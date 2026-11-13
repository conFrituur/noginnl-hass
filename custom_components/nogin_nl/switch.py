"""Switches for the people selected in the Nogin.nl configuration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .const import CONF_LOCAL_PEOPLE, CONF_LOCAL_TESTING_MODE, CONF_PERSONS
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
    local_mode = entry.data.get(CONF_LOCAL_TESTING_MODE, False)

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
        """Apply person selections and mode changes without reloading switches."""
        nonlocal local_mode
        requested_local = entry.data.get(CONF_LOCAL_TESTING_MODE, False)
        if requested_local != local_mode:
            local_mode = requested_local
            coordinator.update_interval = None if local_mode else timedelta(minutes=1)
            if local_mode:
                coordinator.async_set_updated_data(entry.data[CONF_LOCAL_PEOPLE])
            else:
                await coordinator.async_request_refresh()
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
        """Persist local changes or publish the status confirmed by the API."""
        entry = self.coordinator.config_entry
        local_mode = entry.data.get(CONF_LOCAL_TESTING_MODE, False)
        if local_mode:
            person = {"name": self._person_name, "isNogInNL": is_nog_in_nl}
        else:
            person = await entry.runtime_data.client.async_set_nog_in_nl(
                self._person_name, is_nog_in_nl
            )
        # Update the coordinator cache with the confirmed state.
        updated_people = []
        for item in self.coordinator.data:
            if item.get("name") == self._person_name:
                updated_people.append(person)
            else:
                updated_people.append(item)
        if local_mode:
            self.hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_LOCAL_PEOPLE: updated_people}
            )
        self.coordinator.async_set_updated_data(updated_people)

    async def async_turn_on(self, **_: Any) -> None:
        """Turn on the switch."""
        await self._async_set_status(is_nog_in_nl=True)

    async def async_turn_off(self, **_: Any) -> None:
        """Turn off the switch."""
        await self._async_set_status(is_nog_in_nl=False)
