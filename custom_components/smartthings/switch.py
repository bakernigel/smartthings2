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

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity

_LOGGER = logging.getLogger(__name__)

# Generic native-capability switch support.
AIR_CONDITIONER_DISPLAY = getattr(
    Capability,
    "SAMSUNG_CE_AIR_CONDITIONER_DISPLAY",
    "samsungce.airConditionerDisplay",
)
AIR_CONDITIONER_LIGHTING = getattr(
    Capability,
    "SAMSUNG_CE_AIR_CONDITIONER_LIGHTING",
    "samsungce.airConditionerLighting",
)
DISPLAY_ATTRIBUTE = getattr(Attribute, "DISPLAY", "display")
LIGHTING_ATTRIBUTE = getattr(Attribute, "LIGHTING", "lighting")

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
    },
    AIR_CONDITIONER_DISPLAY: {
        "attribute": DISPLAY_ATTRIBUTE,
        "name": "Display",
        "is_on_key": "on",
        "off_command": Command.OFF,
        "on_command": Command.ON,
    },
    AIR_CONDITIONER_LIGHTING: {
        "attribute": LIGHTING_ATTRIBUTE,
        "name": "Display",
        "is_on_key": "on",
        "off_command": Command.OFF,
        "on_command": Command.ON,
    },
}    


def _has_capability(component_status, capability) -> bool:
    """Return whether a component exposes a capability."""
    if capability in component_status:
        return True
    capability_name = str(capability)
    return any(str(status_capability) == capability_name for status_capability in component_status)

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
        if _supports_ocf_display_switch(device):
            entities.append(
                SamsungOcfDisplaySwitch(
                    entry_data.client,
                    device,
                    MAIN,
                )
            )
    
        for component in device.status: 
            _LOGGER.debug(
                  "NB switch component loop Device: %s Component: %s",
                   device.device.label,
                   component,
                   
            )                          
               
            for capability in CAPABILITIES:
                if capability == AIR_CONDITIONER_DISPLAY and _has_capability(
                    device.status[component], AIR_CONDITIONER_LIGHTING
                ):
                    continue
                if not _has_capability(device.status[component], capability):
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
            return f"{self.device.device.label} {switch_name}"

        return f"{self.device.device.label} {self._component} {switch_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""

        if self._capability in (AIR_CONDITIONER_DISPLAY, AIR_CONDITIONER_LIGHTING):
            attribute = CAPABILITIES[self._capability]["attribute"]
            return (
                f"{self.device.device.device_id}.{self._component}."
                f"{self._capability}.{attribute}"
            )
        
        switch_name = ""
        
        if self._component == "main":
            if self._capability == Capability.SWITCH:
                return f"{self.device.device.device_id}.{switch_name}"
            else:    
                return f"{self.device.device.device_id}.{self._capability}.{switch_name}"
        return f"{self.device.device.device_id}.{self._component}.{switch_name}" 
                              
        
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


# Samsung OCF display support for specific AC models.
OCF_DISPLAY_SUPPORTED_MODELS = {"ARTIK051_PRAC_20K"}
OCF_DISPLAY_PAGE = "/mode/vs/0"
OCF_DISPLAY_KEY = "x.com.samsung.da.options"
OCF_DISPLAY_ON_VALUE = ["Light_On"]
OCF_DISPLAY_OFF_VALUE = ["Light_Off"]


def _device_model(device: FullDevice) -> str | None:
    """Return the Samsung model identifier when available."""
    if device.device.ocf and device.device.ocf.model_number:
        return device.device.ocf.model_number.split("|")[0]

    ocf_status = device.status.get(MAIN, {}).get(Capability.OCF)
    if ocf_status is None:
        return None

    model_status = ocf_status.get(Attribute.MNMO)
    if model_status is None or model_status.value is None:
        return None
    return str(model_status.value).split("|")[0]


def _supports_ocf_display_switch(device: FullDevice) -> bool:
    """Return whether the device should use the Samsung OCF display switch path."""
    main_status = device.status.get(MAIN)
    if main_status is None:
        return False

    if _has_capability(main_status, AIR_CONDITIONER_DISPLAY) or _has_capability(
        main_status, AIR_CONDITIONER_LIGHTING
    ):
        return False

    return _device_model(device) in OCF_DISPLAY_SUPPORTED_MODELS and _has_capability(
        main_status, Capability.EXECUTE
    )


def _is_display_visible(options: list[str] | str) -> bool | None:
    """Return the visible display state for Samsung OCF payload values.

    This model reports the display control with inverted semantics:
    - ``Light_On`` means the panel light/display is turned off/hidden
    - ``Light_Off`` means the panel light/display is turned on/visible

    Keep this inversion explicit here so the behavior is obvious to future
    maintainers instead of being buried in optimistic update logic.
    """
    if isinstance(options, str):
        options = [options]

    if any(option in options for option in OCF_DISPLAY_ON_VALUE):
        return False
    if any(option in options for option in OCF_DISPLAY_OFF_VALUE):
        return True
    return None


class SamsungOcfDisplaySwitch(SmartThingsEntity, SwitchEntity):
    """Samsung OCF display switch for models without a native display capability.

    ARTIK051_PRAC_20K does not expose a native SmartThings display/light
    capability in diagnostics, but it does support the Samsung OCF execute
    page at ``/mode/vs/0``. Keep this logic narrow and separate from the
    generic switch handling.
    """

    _attr_has_entity_name = True
    _attr_name = "Display"
    _attr_assumed_state = True

    def __init__(
        self,
        client,
        device: FullDevice,
        component: str,
    ) -> None:
        """Initialize the OCF display switch."""
        super().__init__(client, device, {Capability.EXECUTE}, component)
        self._is_on: bool | None = None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.device.device.device_id}.{self.component}.ocf_display"

    def _update_attr(self) -> None:
        """Update cached switch state from execute payload data."""
        status = self._internal_state.get(Capability.EXECUTE, {}).get(Attribute.DATA)
        if status is None:
            return

        href = None
        payload = None
        if isinstance(status.data, dict):
            href = status.data.get("href")
            if isinstance(status.data.get("payload"), dict):
                payload = status.data["payload"]

        if payload is None and isinstance(status.value, dict):
            if isinstance(status.value.get("payload"), dict):
                payload = status.value["payload"]
            href = href or status.value.get("href")

        if href not in (None, OCF_DISPLAY_PAGE) or not isinstance(payload, dict):
            return

        options = payload.get(OCF_DISPLAY_KEY)
        display_visible = _is_display_visible(options)
        if display_visible is not None:
            self._is_on = display_visible

    def _set_execute_state(self, options: list[str], is_on: bool) -> None:
        """Optimistically update local execute state.

        ``is_on`` represents the Home Assistant switch state, meaning the AC
        display is visible. This intentionally does not match the Samsung OCF
        command names for this model, which are inverted.
        """
        status = self._internal_state.get(Capability.EXECUTE, {}).get(Attribute.DATA)
        if status is not None:
            status.value = {"payload": {OCF_DISPLAY_KEY: options}}
            status.data = {"href": OCF_DISPLAY_PAGE}
        self._is_on = is_on

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates and request initial execute state."""
        await super().async_added_to_hass()
        await self.execute_device_command(
            Capability.EXECUTE,
            Command.EXECUTE,
            argument=[OCF_DISPLAY_PAGE],
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the display off.

        Samsung's OCF payload is inverted on this model:
        sending ``Light_On`` hides the panel display.
        """
        await self.execute_device_command(
            Capability.EXECUTE,
            Command.EXECUTE,
            argument=[OCF_DISPLAY_PAGE, {OCF_DISPLAY_KEY: OCF_DISPLAY_ON_VALUE}],
        )
        self._set_execute_state(OCF_DISPLAY_ON_VALUE, False)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the display on.

        Samsung's OCF payload is inverted on this model:
        sending ``Light_Off`` makes the panel display visible.
        """
        await self.execute_device_command(
            Capability.EXECUTE,
            Command.EXECUTE,
            argument=[OCF_DISPLAY_PAGE, {OCF_DISPLAY_KEY: OCF_DISPLAY_OFF_VALUE}],
        )
        self._set_execute_state(OCF_DISPLAY_OFF_VALUE, True)
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if the display is on."""
        return bool(self._is_on)
  
#samsungce.powerCool
#activated
#false
# Capability.SAMSUNG_CE_POWER_COOL: [Attribute.ACTIVATED],
#    Capability.SAMSUNG_CE_POWER_FREEZE: [Attribute.ACTIVATED],
#CAPABILITY_ATTRIBUTES: dict[Capability, list[Attribute]] = {            
