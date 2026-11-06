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
    client: NoginNLApiClient
    coordinator: NoginNLDataUpdateCoordinator
    integration: Integration
