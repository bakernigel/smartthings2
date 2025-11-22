"""Support for lights through the SmartThings cloud API."""

from __future__ import annotations

import logging

import asyncio
import math
from typing import Any, cast

from pysmartthings import Attribute, Capability, Command, DeviceEvent, SmartThings

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    brightness_supported,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import FullDevice, SmartThingsConfigEntry
from .entity import SmartThingsEntity

_LOGGER = logging.getLogger(__name__)

CAPABILITIES = (
    Capability.SWITCH_LEVEL,
    Capability.COLOR_CONTROL,
    Capability.COLOR_TEMPERATURE,
    Capability.SAMSUNG_CE_LAMP,
)

# samsungce.lamp brightnessLevel off/high
# SAMSUNG_CE_LAMP = "samsungce.lamp"

async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add lights for a config entry."""
    entry_data = entry.runtime_data
    entities = []
    for device in entry_data.devices.values():
        for component in device.status:
            _LOGGER.debug(
                  "NB light component loop: %s",
                   component,
                   
            )              
#            has_switch = Capability.SWITCH in device.status[component]
            has_switch = True
            has_any_capability = False
            for capability in CAPABILITIES:
                if capability in device.status[component]:
                    has_any_capability = True
                    break
            if has_switch and has_any_capability:
                _LOGGER.debug(
                            "NB Found a light to add. Device:%s component:%s capability:%s",
                            device.device.label,
                            component,
                            capability,                       
                )                                     
                entity = SmartThingsLight(entry_data.client, device, component, capability)
                entities.append(entity)
    async_add_entities(entities)

def convert_scale(
    value: float, value_scale: int, target_scale: int, round_digits: int = 4
) -> float:
    """Convert a value to a different scale."""
    return round(value * target_scale / value_scale, round_digits)


class SmartThingsLight(SmartThingsEntity, LightEntity, RestoreEntity):
    """Define a SmartThings Light."""

    _attr_name = None
    _attr_supported_color_modes: set[ColorMode]

    # SmartThings does not expose this attribute, instead it's
    # implemented within each device-type handler. This value is the
    # lowest kelvin found supported across 20+ handlers.
    _attr_min_color_temp_kelvin = 2000  # 500 mireds

    # SmartThings does not expose this attribute, instead it's
    # implemented within each device-type handler. This value is the
    # highest kelvin found supported across 20+ handlers.
    _attr_max_color_temp_kelvin = 9000  # 111 mireds

    def __init__(self, client: SmartThings, device: FullDevice, component, capability: Capability) -> None:
        """Initialize a SmartThingsLight."""
        supported_caps = {
            cap
            for cap in (
                Capability.COLOR_CONTROL,
                Capability.COLOR_TEMPERATURE,
                Capability.SWITCH_LEVEL,
                Capability.SWITCH,
                Capability.SAMSUNG_CE_LAMP,
            )
            if cap in device.status[component]
        }
        # Always track the requested capability even if it is the only one present
        # so the entity can consume updates for auxiliary capabilities like switch.
        if not supported_caps:
            supported_caps = {capability}
        super().__init__(client, device, supported_caps, component)

        self._component = component
        self._capability = capability

        self._lamp_supported_levels: list[str] = []
        self._lamp_supports_off = False
        self._lamp_split_switch = False
        self._lamp_default_level = "high"

        if Capability.SAMSUNG_CE_LAMP in supported_caps:
            brightness_levels = self.get_attribute_value(
                Capability.SAMSUNG_CE_LAMP,
                Attribute.SUPPORTED_BRIGHTNESS_LEVEL,
            )
            if brightness_levels:
                self._lamp_supported_levels = list(brightness_levels)
                self._lamp_supports_off = "off" in brightness_levels
                self._lamp_default_level = next(
                    (
                        level
                        for level in reversed(brightness_levels)
                        if level != "off"
                    ),
                    self._lamp_default_level,
                )
            self._lamp_split_switch = (
                Capability.SWITCH in supported_caps and not self._lamp_supports_off
            )

        color_modes = set()
        if self.supports_capability(Capability.COLOR_TEMPERATURE):
            color_modes.add(ColorMode.COLOR_TEMP)
            self._attr_color_mode = ColorMode.COLOR_TEMP
        if self.supports_capability(Capability.COLOR_CONTROL):
            color_modes.add(ColorMode.HS)
            self._attr_color_mode = ColorMode.HS
        if not color_modes and self.supports_capability(Capability.SWITCH_LEVEL):
            color_modes.add(ColorMode.BRIGHTNESS)

        if self._capability == Capability.SAMSUNG_CE_LAMP:
            color_modes.add(ColorMode.BRIGHTNESS)

        if not color_modes:
            color_modes.add(ColorMode.ONOFF)
        if len(color_modes) == 1:
            self._attr_color_mode = list(color_modes)[0]
        self._attr_supported_color_modes = color_modes
        features = LightEntityFeature(0)

        if self.supports_capability(Capability.SWITCH_LEVEL):
            features |= LightEntityFeature.TRANSITION
        self._attr_supported_features = features
    
            
    @property
    def name(self) -> str:
        """Return the name of the light."""

        switch_name = "Light"
                
        if self._component == "main":
            return f"{self.device.device.label} {switch_name}"
        return f"{self.device.device.label} {self._component} {switch_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        

        switch_name = ""
        
        if self._component == "main":
            return f"{self.device.device.device_id}.{switch_name}"
        return f"{self.device.device.device_id}.{self._component}.{switch_name}"    

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_extra_data()) is not None:
            self._attr_color_mode = last_state.as_dict()[ATTR_COLOR_MODE]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        tasks = []
        # Color temperature
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            tasks.append(self.async_set_color_temp(kwargs[ATTR_COLOR_TEMP_KELVIN]))
        # Color
        if ATTR_HS_COLOR in kwargs:
            tasks.append(self.async_set_color(kwargs[ATTR_HS_COLOR]))
        if tasks:
            # Set temp/color first
            await asyncio.gather(*tasks)

        # Switch/brightness/transition
        if ATTR_BRIGHTNESS in kwargs:
            await self.async_set_level(
                kwargs[ATTR_BRIGHTNESS], kwargs.get(ATTR_TRANSITION, 0)
            )
        else:
            if self._capability == Capability.SAMSUNG_CE_LAMP:
                await self._turn_on_lamp_default()
            else:
                await self.execute_device_command(
                    Capability.SWITCH,
                    Command.ON,
                )                    

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        # Switch/transition
        if ATTR_TRANSITION in kwargs:
            await self.async_set_level(0, int(kwargs[ATTR_TRANSITION]))
        else:
            if self._capability != Capability.SAMSUNG_CE_LAMP:
                await self.execute_device_command(
                    Capability.SWITCH,
                    Command.OFF,
                )
            else:
                if self._lamp_split_switch:
                    await self.execute_device_command(
                        Capability.SWITCH,
                        Command.OFF,
                    )
                else:
                    await self.execute_device_command(
                        self._capability,
                        Command.SET_BRIGHTNESS_LEVEL,
                        ["off"],
                    )

    def _update_attr(self) -> None:
        """Update entity attributes when the device status has changed."""
        # Brightness and transition
        if brightness_supported(self._attr_supported_color_modes):
            if self._capability != Capability.SAMSUNG_CE_LAMP:
                if (
                    brightness := self.get_attribute_value(
                        Capability.SWITCH_LEVEL, Attribute.LEVEL
                    )
                ) is None:
                    self._attr_brightness = None
                else:
                    self._attr_brightness = int(
                        convert_scale(
                            brightness,
                            100,
                            255,
                            0,
                        )
                    )
            else:
                brightness_level = self.get_attribute_value(
                    Capability.SAMSUNG_CE_LAMP, Attribute.BRIGHTNESS_LEVEL
                )
                switch_state = (
                    self.get_attribute_value(Capability.SWITCH, Attribute.SWITCH)
                    if self._lamp_split_switch
                    else None
                )
                self._attr_brightness = self._lamp_level_to_brightness(
                    brightness_level, switch_state
                )
                    
        # Color Temperature
        if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            self._attr_color_temp_kelvin = self.get_attribute_value(
                Capability.COLOR_TEMPERATURE, Attribute.COLOR_TEMPERATURE
            )
        # Color
        if ColorMode.HS in self._attr_supported_color_modes:
            if (
                hue := self.get_attribute_value(Capability.COLOR_CONTROL, Attribute.HUE)
            ) is None:
                self._attr_hs_color = None
            else:
                self._attr_hs_color = (
                    convert_scale(
                        hue,
                        100,
                        360,
                    ),
                    self.get_attribute_value(
                        Capability.COLOR_CONTROL, Attribute.SATURATION
                    ),
                )

    async def async_set_color(self, hs_color):
        """Set the color of the device."""
        hue = convert_scale(float(hs_color[0]), 360, 100)
        hue = max(min(hue, 100.0), 0.0)
        saturation = max(min(float(hs_color[1]), 100.0), 0.0)
        await self.execute_device_command(
            Capability.COLOR_CONTROL,
            Command.SET_COLOR,
            argument={"hue": hue, "saturation": saturation},
        )

    async def async_set_color_temp(self, value: int):
        """Set the color temperature of the device."""
        kelvin = max(min(value, 30000), 1)
        await self.execute_device_command(
            Capability.COLOR_TEMPERATURE,
            Command.SET_COLOR_TEMPERATURE,
            argument=kelvin,
        )

    async def async_set_level(self, brightness: int, transition: int) -> None:
        """Set the brightness of the light over transition."""
        if self._capability == Capability.SAMSUNG_CE_LAMP:
            lamp_level = self._select_lamp_level_for_brightness(brightness)
            if lamp_level is None:
                if self._lamp_split_switch:
                    await self.execute_device_command(
                        Capability.SWITCH,
                        Command.OFF,
                    )
                return

            if self._lamp_split_switch and brightness > 0:
                await self.execute_device_command(
                    Capability.SWITCH,
                    Command.ON,
                )

            if lamp_level == "off":
                if Capability.SWITCH in self.capabilities:
                    await self.execute_device_command(Capability.SWITCH, Command.OFF)
                await self.execute_device_command(
                    self._capability,
                    Command.SET_BRIGHTNESS_LEVEL,
                    [lamp_level],
                )
                return

            await self.execute_device_command(
                self._capability,
                Command.SET_BRIGHTNESS_LEVEL,
                [lamp_level],
            )
        else:
            level = int(convert_scale(brightness, 255, 100, 0))
            # Due to rounding, set level to 1 (one) so we don't inadvertently
            # turn off the light when a low brightness is set.
            level = 1 if level == 0 and brightness > 0 else level
            level = max(min(level, 100), 0)
            duration = int(transition)
            await self.execute_device_command(
                Capability.SWITCH_LEVEL,
                Command.SET_LEVEL,
                argument=[level, duration],
            )

    def _update_handler(self, event: DeviceEvent) -> None:
        """Handle device updates."""
        if event.capability in (Capability.COLOR_CONTROL, Capability.COLOR_TEMPERATURE):
            self._attr_color_mode = {
                Capability.COLOR_CONTROL: ColorMode.HS,
                Capability.COLOR_TEMPERATURE: ColorMode.COLOR_TEMP,
            }[cast(Capability, event.capability)]
        super()._update_handler(event)
        
    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        if self._capability != Capability.SAMSUNG_CE_LAMP:
            if (
                state := self.get_attribute_value(Capability.SWITCH, Attribute.SWITCH)
            ) is None:
                return None
            return state == "on"
        else:
            if self._lamp_split_switch:
                state = self.get_attribute_value(
                    Capability.SWITCH, Attribute.SWITCH
                )
                return state == "on"

            state = self.get_attribute_value(
                self._capability, Attribute.BRIGHTNESS_LEVEL
            )
            return state != "off"

    def _select_lamp_level_for_brightness(self, brightness: int) -> str | None:
        """Map HA brightness to an available lamp level."""
        if brightness <= 0:
            if self._lamp_supports_off:
                return "off"
            return None

        levels = [level for level in self._lamp_supported_levels if level != "off"]
        if not levels:
            return self._lamp_default_level

        step = 255 / len(levels)
        level_index = min(len(levels) - 1, max(0, math.ceil(brightness / step) - 1))
        return levels[level_index]

    def _lamp_level_to_brightness(
        self, level: str | None, switch_state: str | None
    ) -> int | None:
        """Convert lamp level and switch state to HA brightness."""
        if level is None:
            return None

        if self._lamp_split_switch and switch_state == "off":
            return 0

        if level == "off":
            return 0

        levels = [item for item in self._lamp_supported_levels if item != "off"]
        if not levels:
            return 255

        if level not in levels:
            return 255

        step = 255 / len(levels)
        return int(step * (levels.index(level) + 1))

    async def _turn_on_lamp_default(self) -> None:
        """Turn on a samsungce lamp with a sensible default for split controls."""
        if self._lamp_split_switch:
            await self.execute_device_command(Capability.SWITCH, Command.ON)
        await self.execute_device_command(
            self._capability,
            Command.SET_BRIGHTNESS_LEVEL,
            [self._lamp_default_level],
        )
