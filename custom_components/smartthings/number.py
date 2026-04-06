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

from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfArea,
    UnitOfEnergy,
    UnitOfMass,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolume,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SmartThingsNumberDescription(NumberEntityDescription):
    """Describe a SmartThings capability exposed as a NumberEntity."""

    key: Capability
    attribute: Attribute
    command: Command
    default_name: str

# Keep this mapping intentionally small until more number capabilities are
# proven useful. Right now it only covers the existing cooling setpoint entity
# plus the added writable audio volume control.
CAPABILITIES_TO_NUMBER: dict[Capability, SmartThingsNumberDescription] = {
    Capability.THERMOSTAT_COOLING_SETPOINT: SmartThingsNumberDescription(
        key=Capability.THERMOSTAT_COOLING_SETPOINT,
        attribute=Attribute.COOLING_SETPOINT,
        translation_key="thermostat_cooling_setpoint",
        native_unit_of_measurement="F",
        default_name="coolingSetpoint",
        min_value=-22,
        max_value=500,
        step=1,
        mode=NumberMode.AUTO,
        command=Command.SET_COOLING_SETPOINT,
    ),
    Capability.AUDIO_VOLUME: SmartThingsNumberDescription(
        key=Capability.AUDIO_VOLUME,
        attribute=Attribute.VOLUME,
        translation_key="audio_volume",
        native_unit_of_measurement=PERCENTAGE,
        default_name="Volume",
        min_value=0,
        max_value=100,
        step=1,
        mode=NumberMode.AUTO,
        command=Command.SET_VOLUME,
    ),
}

UNITS = {
    "C": UnitOfTemperature.CELSIUS,
    "F": UnitOfTemperature.FAHRENHEIT,
    "lux": LIGHT_LUX,
    "mG": None,
    "μg/m^3": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add supported SmartThings number entities for a config entry."""
    _LOGGER.debug("NB Add number entities for a config entry")
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsNumberEntity(
            entry_data.client,
            device,
            component,
            capability,
        )
        for device in entry_data.devices.values()
        for component in device.status
        for capability in CAPABILITIES_TO_NUMBER
        if capability in device.status[component]
    )


class SmartThingsNumberEntity(SmartThingsEntity, NumberEntity):
    """Define a SmartThings number entity."""

    _attr_native_step = 1.0
    _attr_mode = NumberMode.AUTO

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        component,
        capability: Capability,
    ) -> None:
        """Initialize the number entity for a supported capability."""

        _LOGGER.debug(
        "NB SmartThingsNumberEntity(init) Device:%s component:%s capability:%s",
        device.device.label,
        component,
        capability,
        )

        super().__init__(client, device, {capability}, component)

        description = CAPABILITIES_TO_NUMBER[capability]
        self.entity_description = description
        self._attribute = description.attribute
        self.capability = capability
        self._attr_translation_key = description.translation_key
        if capability == Capability.THERMOSTAT_COOLING_SETPOINT:
            self._attr_name = f"{component} coolingSetpoint"
        else:
            if component == MAIN:
                self._attr_name = description.default_name
            else:
                self._attr_name = f"{component} {description.default_name}"
        self._attr_mode = description.mode
        self._attr_unique_id = (
            f"{device.device.device_id}_{component}_{capability}_{self._attribute}"
        )

    @property
    def options(self) -> dict | None:
        """Return the supported range when the capability exposes one."""
        if self.capability != Capability.THERMOSTAT_COOLING_SETPOINT:
            return None

        ranges = self.get_attribute_value(
            Capability.THERMOSTAT_COOLING_SETPOINT,
            Attribute.COOLING_SETPOINT_RANGE,
        )
        _LOGGER.debug("NB Number options (range):%s", ranges,)
        return ranges

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        value = self.get_attribute_value(self.capability, self._attribute)
        if value is None:
            return None
        if self.capability == Capability.AUDIO_VOLUME:
            return int(value)
        return float(value)

    @property
    def native_min_value(self):
        """Return the minimum value."""
        range = self.options
        if range is not None and isinstance(range, dict) and "minimum" in range:
            return int(range["minimum"])
        return self.entity_description.min_value

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        range = self.options
        if range is not None and isinstance(range, dict) and "maximum" in range:
            return int(range["maximum"])
        return self.entity_description.max_value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit this state is expressed in."""
        unit = self._internal_state[self.capability][self._attribute].unit
        return (
            UNITS.get(unit, unit)
            if unit
            else self.entity_description.native_unit_of_measurement
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.execute_device_command(
            self.capability,
            self.entity_description.command,
            int(value),
        )
