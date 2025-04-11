"""Support for number entities through the SmartThings cloud API."""

from __future__ import annotations

import logging

from dataclasses import dataclass

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.number import NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity

_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True, kw_only=True)
class SmartThingsNumberDescription(NumberEntityDescription):
    """Class describing SmartThings button entities."""
    key: Capability
    command: Command


CAPABILITIES_TO_NUMBER: dict[
    Capability, dict[Attribute, list[SmartThingsNumberDescription]]
] = {
    Capability.THERMOSTAT_COOLING_SETPOINT: {
        Attribute.COOLING_SETPOINT: [
            SmartThingsNumberDescription(
                key=Capability.THERMOSTAT_COOLING_SETPOINT,
                translation_key="coolingSetpoint",
                native_unit_of_measurement="F",
                min_value=-22,
                max_value=500,
                step=1,
                mode=NumberMode.AUTO,
                command=Command.SET_COOLING_SETPOINT,                
            )
        ]
     }       
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add number entities for a config entry."""
    _LOGGER.warning("NB Add number entities for a config entry")            
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsNumberEntity(entry_data.client, device, component)
        for device in entry_data.devices.values()
        for component in device.status
        if Capability.THERMOSTAT_COOLING_SETPOINT in device.status[component]
    )


class SmartThingsNumberEntity(SmartThingsEntity, NumberEntity):
    """Define a SmartThings number."""

    _attr_translation_key = "washer_rinse_cycles"
    _attr_native_step = 1.0
    _attr_mode = NumberMode.SLIDER

    def __init__(self, client: SmartThings, device: FullDevice, component) -> None:
        """Initialize the instance."""
        super().__init__(client, device, {Capability.THERMOSTAT_COOLING_SETPOINT}, component)
        
        self._attr_unique_id = f"{device.device.device_id}_{component}_{Capability.THERMOSTAT_COOLING_SETPOINT}_{Attribute.COOLING_SETPOINT}"
        self._attr_name = f"{component} coolingSetpoint"

    @property
    def options(self) -> dict:        
        """Return the list of options."""
        ranges = self.get_attribute_value(
            Capability.THERMOSTAT_COOLING_SETPOINT,
            Attribute.COOLING_SETPOINT_RANGE,
        )
        _LOGGER.warning("NB Number options (range):%s", ranges,)         
        return ranges        

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return int(
            self.get_attribute_value(
                Capability.THERMOSTAT_COOLING_SETPOINT, Attribute.COOLING_SETPOINT
            )
        )

    @property
    def native_min_value(self) -> int:
        """Return the minimum value."""
        range = self.options
        return int(range['minimum'])         

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        range = self.options
        return int(range['maximum'])                 


    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.execute_device_command(
            Capability.THERMOSTAT_COOLING_SETPOINT,
            Command.SET_COOLING_SETPOINT,
            int(value),
        )