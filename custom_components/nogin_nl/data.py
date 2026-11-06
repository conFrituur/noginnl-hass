"""Typed configuration entries and runtime data for Nogin.nl."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import NoginNLApiClient
    from .coordinator import NoginNLDataUpdateCoordinator


type NoginNLConfigEntry = ConfigEntry[NoginNLData]


@dataclass
class NoginNLData:
    """Hold the API client, polling coordinator, and integration metadata."""

    client: NoginNLApiClient
    coordinator: NoginNLDataUpdateCoordinator
    integration: Integration
