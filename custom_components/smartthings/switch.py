# MODIFIED VERSION
"""Support for switches through the SmartThings cloud API."""

from __future__ import annotations

import logging

from typing import Any

from pysmartthings import Attribute, Capability, Command

from pysmartthings.attribute import(
    CAPABILITY_ATTRIBUTES,
)

from pysmartthings.command import(
    CAPABILITY_COMMANDS,
)


from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity

_LOGGER = logging.getLogger(__name__)

CAPABILITIES = {
    Capability.SWITCH: {
        "attribute" : Attribute.SWITCH,
        "name" : "switch",
        "is_on_key" : "on",
        "off_command" : "off",
        "on_command" : "on"
    },    
    Capability.SWITCH_LEVEL: {
        "attribute" : Attribute.SWITCH,
        "name" : "switch",
        "is_on_key" : "on",
        "off_command" : "off",
        "on_command" : "on"
    },
    Capability.COLOR_CONTROL: {
        "attribute" : Attribute.SWITCH,
        "name" : "switch",
        "is_on_key" : "on",
        "off_command" : "off",
        "on_command" : "on"    
    },
    Capability.COLOR_TEMPERATURE: {
        "attribute" : Attribute.SWITCH,
        "name" : "switch",
        "is_on_key" : "on",
        "off_command" : "off",
        "on_command" : "on"    
    },
    Capability.FAN_SPEED: {
        "attribute" : Attribute.SWITCH,
        "name" : "switch",
        "is_on_key" : "on",
        "off_command" : "off",
        "on_command" : "on"    
    },
    Capability.SAMSUNG_CE_POWER_COOL: {
        "attribute" : Attribute.ACTIVATED,
        "name" : "powerCool",
        "is_on_key" : "True",
        "off_command" : Command.DEACTIVATE,
        "on_command" : Command.ACTIVATE
    },    
    Capability.SAMSUNG_CE_POWER_FREEZE: {
        "attribute" : Attribute.ACTIVATED,
        "name" : "powerFreeze",       
        "is_on_key" : "True",
        "off_command" : Command.DEACTIVATE,
        "on_command" : Command.ACTIVATE
    }        
}    

#AC_CAPABILITIES = (
#    Capability.AIR_CONDITIONER_MODE,
#    Capability.AIR_CONDITIONER_FAN_MODE,
#    Capability.TEMPERATURE_MEASUREMENT,
#    Capability.THERMOSTAT_COOLING_SETPOINT,
#)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add switches for a config entry."""
    entry_data = entry.runtime_data
    entities = []
    for device in entry_data.devices.values():
    
        for component in device.status: 
            _LOGGER.debug(
                  "NB switch component loop Device: %s Component: %s",
                   device.device.label,
                   component,
                   
            )                          
               
            for capability in CAPABILITIES:
                if capability not in device.status[component]:
                    _LOGGER.debug(
                        "NB Capability not on device - continuing to next capability Device:%s Component:%s Capability:%s",
                        device.device.label,
                        component,
                        capability,                       
                    ) 
                    continue
                            
                _LOGGER.debug(
                    "NB Found a switch to add Device:%s component:%s capability:%s",
                    device.device.label,
                    component,
                    capability,                       
                ) 
                                    
                switch = SmartThingsSwitch(entry_data.client, device, component, capability)
                entities.append(switch)
        
    async_add_entities(entities)


class SmartThingsSwitch(SmartThingsEntity, SwitchEntity):
    """Define a SmartThings switch."""
    
    _attr_has_entity_name = True
    
    def __init__(self, client: SmartThings, device, component, capability: Capability) -> None:
        """Init the class."""
        
        _LOGGER.debug(
        "NB SmartThingsSwitch(init) Device:%s component:%s capability:%s",
        device.device.label,
        component,
        capability,                       
        )                                     
        
        super().__init__(client, device, {capability}, component,)
        self._component = component
        self._capability = capability
#        self._attribute = attribute
            
    @property
    def name(self) -> str:
        """Return the name of the switch."""

        switch_name = CAPABILITIES[self._capability]["name"]
                
        if self._component == "main":
            return f"{switch_name}"

        return f"{self._component} {switch_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        

        switch_name = ""
        
        if self._component == "main":
            if self._capability == Capability.SWITCH:
                return f"{switch_name}"
            else:    
                return f"{self._capability}.{switch_name}"
        return f"{self._component}.{switch_name}"                       
        
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        command_to_use = CAPABILITIES[self._capability]["off_command"]

        await self.execute_device_command(
            self._capability,
            command_to_use,
        )        

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        command_to_use = CAPABILITIES[self._capability]["on_command"]

        await self.execute_device_command(
            self._capability,
            command_to_use,
        )        

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        attribute_to_use = CAPABILITIES[self._capability]["attribute"]
        return (self.get_attribute_value(self._capability, attribute_to_use) == CAPABILITIES[self._capability]["is_on_key"])
  
#samsungce.powerCool
#activated
#false
# Capability.SAMSUNG_CE_POWER_COOL: [Attribute.ACTIVATED],
#    Capability.SAMSUNG_CE_POWER_FREEZE: [Attribute.ACTIVATED],
#CAPABILITY_ATTRIBUTES: dict[Capability, list[Attribute]] = {            
