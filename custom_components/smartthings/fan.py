"""Support for fans through the SmartThings cloud API."""

from __future__ import annotations

import logging

import math
from typing import Any

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
    ordered_list_item_to_percentage, percentage_to_ordered_list_item,
)
from homeassistant.util.scaling import int_states_in_range

from . import FullDevice, SmartThingsConfigEntry
from .entity import SmartThingsEntity

_LOGGER = logging.getLogger(__name__)

SPEED_RANGE = (1, 3)  # off is not included
HOOD_SPEED_RANGE = (1, 4)  # off is not included
ORDERED_NAMED_HOOD_SPEEDS = ["low", "medium", "high", "max"]  # off is not included

# SAMSUNG_CE_HOOD_FAN_SPEED = "samsungce.hoodFanSpeed"
# HOOD_FAN_SPEED = "hoodFanSpeed"
# SET_HOOD_FAN_SPEED = "setHoodFanSpeed"

async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add fans for a config entry."""
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsSamsungceHoodFan(entry_data.client, device, component)
        if Capability.SAMSUNG_CE_HOOD_FAN_SPEED in device.status[component]
        else SmartThingsFan(entry_data.client, device)
        for device in entry_data.devices.values()
        for component in device.status
        if any(
            capability in device.status[component]
            for capability in (
                Capability.FAN_SPEED,
                Capability.AIR_CONDITIONER_FAN_MODE,
                Capability.SAMSUNG_CE_HOOD_FAN_SPEED,
            )
        )
        and Capability.THERMOSTAT_COOLING_SETPOINT not in device.status[component]
    )

class SmartThingsFan(SmartThingsEntity, FanEntity):
    """Define a SmartThings Fan."""

    _attr_name = None
    _attr_speed_count = int_states_in_range(SPEED_RANGE)

    def __init__(self, client: SmartThings, device: FullDevice) -> None:
        """Init the class."""
        super().__init__(
            client,
            device,
            {
                Capability.SWITCH,
                Capability.FAN_SPEED,
                Capability.AIR_CONDITIONER_FAN_MODE,
            },
        )
        self._attr_supported_features = self._determine_features()
        
    def _determine_features(self):
        flags = FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON

        if self.supports_capability(Capability.FAN_SPEED):
            flags |= FanEntityFeature.SET_SPEED
        if self.supports_capability(Capability.AIR_CONDITIONER_FAN_MODE):
            flags |= FanEntityFeature.PRESET_MODE

        return flags

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.execute_device_command(Capability.SWITCH, Command.OFF)
        else:
            value = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
            await self.execute_device_command(
                Capability.FAN_SPEED,
                Command.SET_FAN_SPEED,
                argument=value,
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset_mode of the fan."""
        await self.execute_device_command(
            Capability.AIR_CONDITIONER_FAN_MODE,
            Command.SET_FAN_MODE,
            argument=preset_mode,
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if (
            FanEntityFeature.SET_SPEED in self._attr_supported_features
            and percentage is not None
        ):
            await self.async_set_percentage(percentage)
        else:
            await self.execute_device_command(Capability.SWITCH, Command.ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self.execute_device_command(Capability.SWITCH, Command.OFF)

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        return self.get_attribute_value(Capability.SWITCH, Attribute.SWITCH) == "on"

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        return ranged_value_to_percentage(
            SPEED_RANGE,
            self.get_attribute_value(Capability.FAN_SPEED, Attribute.FAN_SPEED),
        )

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., auto, smart, interval, favorite.

        Requires FanEntityFeature.PRESET_MODE.
        """
        if not self.supports_capability(Capability.AIR_CONDITIONER_FAN_MODE):
            return None
        return self.get_attribute_value(
            Capability.AIR_CONDITIONER_FAN_MODE, Attribute.FAN_MODE
        )

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Requires FanEntityFeature.PRESET_MODE.
        """
        if not self.supports_capability(Capability.AIR_CONDITIONER_FAN_MODE):
            return None
        return self.get_attribute_value(
            Capability.AIR_CONDITIONER_FAN_MODE, Attribute.SUPPORTED_AC_FAN_MODES
        )
        
class SmartThingsSamsungceHoodFan(SmartThingsEntity, FanEntity):
    """Define a SmartThings Fan."""

    _attr_name = None
    _attr_speed_count = int_states_in_range(HOOD_SPEED_RANGE)

    def __init__(self, client: SmartThings, device: FullDevice, component) -> None:
        """Init the class."""
        super().__init__(
            client,
            device,
            {
                Capability.SWITCH,
                Capability.FAN_SPEED,
                Capability.AIR_CONDITIONER_FAN_MODE,
                Capability.SAMSUNG_CE_HOOD_FAN_SPEED,
            },
            component,
        )

        self._component = component
        _LOGGER.debug(
                  "NB creating a SmartThingsSamsungceHoodFan Device: %s Component: %s",
                   device.device.label,
                   component,                 
        )

        supported_fan_speeds = self.get_attribute_value(
            Capability.SAMSUNG_CE_HOOD_FAN_SPEED, Attribute.SUPPORTED_HOOD_FAN_SPEED
        )

        self._speed_steps: list[str | int] = []
        self._supports_off_via_speed = False

        if isinstance(supported_fan_speeds, list):
            self._supports_off_via_speed = "off" in supported_fan_speeds or 0 in supported_fan_speeds
            self._speed_steps = [
                speed for speed in supported_fan_speeds if speed not in ("off", 0)
            ]

        if not self._speed_steps:
            self._speed_steps = list(ORDERED_NAMED_HOOD_SPEEDS)
            self._supports_off_via_speed = True

        self._use_str_speeds = isinstance(self._speed_steps[0], str)
        self._split_switch = (
            Capability.SWITCH in device.status[component]
            and not self._supports_off_via_speed
        )
        self._default_speed = self._speed_steps[-1]
        self._attr_speed_count = len(self._speed_steps)

        _LOGGER.debug(
            "NB supported_fan_speeds: %s self._use_str_speeds %s split_switch %s",
            supported_fan_speeds,
            self._use_str_speeds,
            self._split_switch,
        )
                            
        
    @property
    def name(self) -> str:
        """Return the name of the fan."""

        switch_name = "Fan"
                
        if self._component == "main":
            return f"{switch_name}"
        return f"{self._component} {switch_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        

        switch_name = "fan"
        
        if self._component == "main":
            return f"{switch_name}"
        return f"{self._component}.{switch_name}"
        
    @property
    def supported_features(self):
#        return FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
# Remove preset mode for now 
        return FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF                 

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self._handle_turn_off()
        else:
            speed_value = self._percentage_to_speed_value(percentage)
            if self._split_switch:
                await self.execute_device_command(Capability.SWITCH, Command.ON)
            await self._set_speed_value(speed_value)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset_mode of the fan."""
        await self.execute_device_command(
            Capability.AIR_CONDITIONER_FAN_MODE,
            Command.SET_FAN_MODE,
            argument=preset_mode,
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if (
            FanEntityFeature.SET_SPEED in self._attr_supported_features
            and percentage is not None
        ):
            await self.async_set_percentage(percentage)
        else:
            if self._split_switch:
                await self.execute_device_command(Capability.SWITCH, Command.ON)
            await self._set_speed_value(self._default_speed)
                
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._handle_turn_off()

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        if self._split_switch:
            return (
                self.get_attribute_value(Capability.SWITCH, Attribute.SWITCH) == "on"
            )

        value = self.get_attribute_value(
            Capability.SAMSUNG_CE_HOOD_FAN_SPEED, Attribute.HOOD_FAN_SPEED
        )
        if self._supports_off_via_speed:
            return value not in ("off", 0, None)
        return value is not None

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
            
        hood_fan_speed = self.get_attribute_value(
            Capability.SAMSUNG_CE_HOOD_FAN_SPEED, Attribute.HOOD_FAN_SPEED
        )
        return self._percentage_from_speed_value(hood_fan_speed)


    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, e.g., auto, smart, interval, favorite.

        Requires FanEntityFeature.PRESET_MODE.
        """
        if not self.supports_capability(Capability.AIR_CONDITIONER_FAN_MODE):
            return None
        return self.get_attribute_value(
            Capability.AIR_CONDITIONER_FAN_MODE, Attribute.FAN_MODE
        )

    @property
    def preset_modes(self) -> list[str] | None:
        """Return a list of available preset modes.

        Requires FanEntityFeature.PRESET_MODE.
        """
        if not self.supports_capability(Capability.AIR_CONDITIONER_FAN_MODE):
            return None
        return self.get_attribute_value(
            Capability.AIR_CONDITIONER_FAN_MODE, Attribute.SUPPORTED_AC_FAN_MODES
        )
        
    def _update_attr(self) -> None:
        """Update entity attributes when the device status has changed."""
        
        hood_fan_speed = self.get_attribute_value(
            Capability.SAMSUNG_CE_HOOD_FAN_SPEED, Attribute.HOOD_FAN_SPEED
        )
        self._attr_percentage = self._percentage_from_speed_value(hood_fan_speed)

    def _percentage_to_speed_value(self, percentage: int) -> str | int:
        """Translate a percentage to the closest available speed value."""
        try:
            return percentage_to_ordered_list_item(self._speed_steps, percentage)
        except ValueError:
            return self._default_speed

    def _percentage_from_speed_value(self, speed_value: Any) -> int:
        """Translate a device speed value to HA percentage."""
        if self._split_switch and self.get_attribute_value(
            Capability.SWITCH, Attribute.SWITCH
        ) == "off":
            return 0

        if self._supports_off_via_speed and speed_value in ("off", 0, None):
            return 0

        if speed_value not in self._speed_steps:
            return 0

        try:
            return ordered_list_item_to_percentage(self._speed_steps, speed_value)
        except ValueError:
            return 0

    async def _set_speed_value(self, speed_value: str | int) -> None:
        """Send the speed command to the device."""
        await self.execute_device_command(
            Capability.SAMSUNG_CE_HOOD_FAN_SPEED,
            Command.SET_HOOD_FAN_SPEED,
            [speed_value],
        )

    async def _handle_turn_off(self) -> None:
        """Handle turning the fan off for both split and single-capability devices."""
        if self._split_switch:
            await self.execute_device_command(Capability.SWITCH, Command.OFF)
            return

        if self._supports_off_via_speed:
            await self._set_speed_value("off" if self._use_str_speeds else 0)
            return

        await self.execute_device_command(Capability.SWITCH, Command.OFF)
        
