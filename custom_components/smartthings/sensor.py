"""Support for sensors through the SmartThings cloud API."""

from __future__ import annotations

import logging

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pysmartthings import Attribute, Capability, SmartThings

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity

_LOGGER = logging.getLogger(__name__)

THERMOSTAT_CAPABILITIES = {
    Capability.TEMPERATURE_MEASUREMENT,
    Capability.THERMOSTAT_HEATING_SETPOINT,
    Capability.THERMOSTAT_COOLING_SETPOINT,
    Capability.THERMOSTAT_MODE,
}

JOB_STATE_MAP = {
    "airWash": "air_wash",
    "airwash": "air_wash",
    "aIRinse": "ai_rinse",
    "aISpin": "ai_spin",
    "aIWash": "ai_wash",
    "aIDrying": "ai_drying",
    "internalCare": "internal_care",
    "continuousDehumidifying": "continuous_dehumidifying",
    "thawingFrozenInside": "thawing_frozen_inside",
    "delayWash": "delay_wash",
    "weightSensing": "weight_sensing",
    "freezeProtection": "freeze_protection",
    "preDrain": "pre_drain",
    "preWash": "pre_wash",
    "wrinklePrevent": "wrinkle_prevent",
    "unknown": None,
}

OVEN_JOB_STATE_MAP = {
    "scheduledStart": "scheduled_start",
    "fastPreheat": "fast_preheat",
    "scheduledEnd": "scheduled_end",
    "stone_heating": "stone_heating",
    "timeHoldPreheat": "time_hold_preheat",
}

MEDIA_PLAYBACK_STATE_MAP = {
    "fast forwarding": "fast_forwarding",
}

ROBOT_CLEANER_TURBO_MODE_STATE_MAP = {
    "extraSilence": "extra_silence",
}

ROBOT_CLEANER_MOVEMENT_MAP = {
    "powerOff": "off",
}

OVEN_MODE = {
    "Conventional": "conventional",
    "Bake": "bake",
    "BottomHeat": "bottom_heat",
    "ConvectionBake": "convection_bake",
    "ConvectionRoast": "convection_roast",
    "Broil": "broil",
    "ConvectionBroil": "convection_broil",
    "SteamCook": "steam_cook",
    "SteamBake": "steam_bake",
    "SteamRoast": "steam_roast",
    "SteamBottomHeatplusConvection": "steam_bottom_heat_plus_convection",
    "Microwave": "microwave",
    "MWplusGrill": "microwave_plus_grill",
    "MWplusConvection": "microwave_plus_convection",
    "MWplusHotBlast": "microwave_plus_hot_blast",
    "MWplusHotBlast2": "microwave_plus_hot_blast_2",
    "SlimMiddle": "slim_middle",
    "SlimStrong": "slim_strong",
    "SlowCook": "slow_cook",
    "Proof": "proof",
    "Dehydrate": "dehydrate",
    "Others": "others",
    "StrongSteam": "strong_steam",
    "Descale": "descale",
    "Rinse": "rinse",
}

WASHER_OPTIONS = ["pause", "run", "stop"]


def power_attributes(status: dict[str, Any]) -> dict[str, Any]:
    """Return the power attributes."""
    state = {}
    for attribute in ("start", "end"):
        if (value := status.get(attribute)) is not None:
            state[f"power_consumption_{attribute}"] = value
    return state


@dataclass(frozen=True, kw_only=True)
class SmartThingsSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[Any], str | float | int | datetime | None] = lambda value: value
    extra_state_attributes_fn: Callable[[Any], dict[str, Any]] | None = None
    unique_id_separator: str = "."
    capability_ignore_list: list[set[Capability]] | None = None
    options_attribute: Attribute | None = None
    name: str | None = None  # Added new field

CAPABILITY_TO_SENSORS: dict[
    Capability, dict[Attribute, list[SmartThingsSensorEntityDescription]]
] = {
    Capability.ACTIVITY_LIGHTING_MODE: {
        Attribute.LIGHTING_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.LIGHTING_MODE,
                translation_key="lighting_mode",
                name="Activity Lighting Mode",  # From first doc
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.AIR_CONDITIONER_MODE: {
        Attribute.AIR_CONDITIONER_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.AIR_CONDITIONER_MODE,
                translation_key="air_conditioner_mode",
                name="Air Conditioner Mode",  # From first doc
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.AIR_QUALITY_SENSOR: {
        Attribute.AIR_QUALITY: [
            SmartThingsSensorEntityDescription(
                key=Attribute.AIR_QUALITY,
                translation_key="air_quality",
                name="Air Quality",  # From first doc
                native_unit_of_measurement="CAQI",
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.ALARM: {
        Attribute.ALARM: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ALARM,
                translation_key="alarm",
                name="Alarm",  # From first doc
                options=["both", "strobe", "siren", "off"],
                device_class=SensorDeviceClass.ENUM,
            )
        ]
    },
    Capability.AUDIO_VOLUME: {
        Attribute.VOLUME: [
            SmartThingsSensorEntityDescription(
                key=Attribute.VOLUME,
                translation_key="audio_volume",
                name="Volume",  # From first doc
                native_unit_of_measurement=PERCENTAGE,
            )
        ]
    },
    Capability.BATTERY: {
        Attribute.BATTERY: [
            SmartThingsSensorEntityDescription(
                key=Attribute.BATTERY,
                translation_key="battery",
                name="Battery",  # From first doc
                native_unit_of_measurement=PERCENTAGE,
                device_class=SensorDeviceClass.BATTERY,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.BODY_MASS_INDEX_MEASUREMENT: {
        Attribute.BMI_MEASUREMENT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.BMI_MEASUREMENT,
                translation_key="body_mass_index",
                name="Body Mass Index",  # From first doc
                native_unit_of_measurement=f"{UnitOfMass.KILOGRAMS}/{UnitOfArea.SQUARE_METERS}",
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.BODY_WEIGHT_MEASUREMENT: {
        Attribute.BODY_WEIGHT_MEASUREMENT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.BODY_WEIGHT_MEASUREMENT,
                translation_key="body_weight",
                name="Body Weight",  # From first doc
                native_unit_of_measurement=UnitOfMass.KILOGRAMS,
                device_class=SensorDeviceClass.WEIGHT,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.CARBON_DIOXIDE_MEASUREMENT: {
        Attribute.CARBON_DIOXIDE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.CARBON_DIOXIDE,
                translation_key="carbon_dioxide",
                name="Carbon Dioxide Measurement",  # From first doc
                native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO2,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.CARBON_MONOXIDE_DETECTOR: {
        Attribute.CARBON_MONOXIDE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.CARBON_MONOXIDE,
                translation_key="carbon_monoxide_detector",
                name="Carbon Monoxide Detector",  # From first doc
                options=["detected", "clear", "tested"],
                device_class=SensorDeviceClass.ENUM,
            )
        ]
    },
    Capability.CARBON_MONOXIDE_MEASUREMENT: {
        Attribute.CARBON_MONOXIDE_LEVEL: [
            SmartThingsSensorEntityDescription(
                key=Attribute.CARBON_MONOXIDE_LEVEL,
                translation_key="carbon_monoxide",
                name="Carbon Monoxide Measurement",  # From first doc
                native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.DISHWASHER_OPERATING_STATE: {
        Attribute.MACHINE_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.MACHINE_STATE,
                translation_key="dishwasher_machine_state",
                name="Dishwasher Machine State",  # From first doc
                options=WASHER_OPTIONS,
                device_class=SensorDeviceClass.ENUM,
            )
        ],
        Attribute.DISHWASHER_JOB_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.DISHWASHER_JOB_STATE,
                translation_key="dishwasher_job_state",
                name="Dishwasher Job State",  # From first doc
                options=[
                    "air_wash", "cooling", "drying", "finish", "pre_drain",
                    "prewash", "rinse", "spin", "wash", "wrinkle_prevent", "run",
                ],
                device_class=SensorDeviceClass.ENUM,
                value_fn=lambda value: JOB_STATE_MAP.get(value, value),
            )
        ],
        Attribute.COMPLETION_TIME: [
            SmartThingsSensorEntityDescription(
                key=Attribute.COMPLETION_TIME,
                translation_key="completion_time",
                name="Dishwasher Completion Time",  # From first doc
                device_class=SensorDeviceClass.TIMESTAMP,
                value_fn=dt_util.parse_datetime,
            )
        ],
    },
    Capability.DRYER_MODE: {
        Attribute.DRYER_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.DRYER_MODE,
                translation_key="dryer_mode",
                name="Dryer Mode",  # From first doc
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.DRYER_OPERATING_STATE: {
        Attribute.MACHINE_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.MACHINE_STATE,
                translation_key="dryer_machine_state",
                name="Dryer Machine State",  # From first doc
                options=WASHER_OPTIONS,
                device_class=SensorDeviceClass.ENUM,
            )
        ],
        Attribute.DRYER_JOB_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.DRYER_JOB_STATE,
                translation_key="dryer_job_state",
                name="Dryer Job State",  # From first doc
                options=[
                    "cooling", "delay_wash", "drying", "finished", "none",
                    "refreshing", "weight_sensing", "wrinkle_prevent", "dehumidifying",
                    "ai_drying", "sanitizing", "internal_care", "freeze_protection",
                    "continuous_dehumidifying", "thawing_frozen_inside",
                ],
                device_class=SensorDeviceClass.ENUM,
                value_fn=lambda value: JOB_STATE_MAP.get(value, value),
            )
        ],
        Attribute.COMPLETION_TIME: [
            SmartThingsSensorEntityDescription(
                key=Attribute.COMPLETION_TIME,
                translation_key="completion_time",
                name="Dryer Completion Time",  # From first doc
                device_class=SensorDeviceClass.TIMESTAMP,
                value_fn=dt_util.parse_datetime,
            )
        ],
    },
    Capability.DUST_SENSOR: {
        Attribute.DUST_LEVEL: [
            SmartThingsSensorEntityDescription(
                key=Attribute.DUST_LEVEL,
                translation_key="dust_level",
                name="Dust Level",  # From first doc
                device_class=SensorDeviceClass.PM10,
                native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ],
        Attribute.FINE_DUST_LEVEL: [
            SmartThingsSensorEntityDescription(
                key=Attribute.FINE_DUST_LEVEL,
                translation_key="fine_dust_level",
                name="Fine Dust Level",  # From first doc
                device_class=SensorDeviceClass.PM25,
                native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ],
    },
    Capability.ENERGY_METER: {
        Attribute.ENERGY: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ENERGY,
                translation_key="energy_meter",
                name="Energy Meter",  # From first doc
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL_INCREASING,
            )
        ]
    },
    Capability.EQUIVALENT_CARBON_DIOXIDE_MEASUREMENT: {
        Attribute.EQUIVALENT_CARBON_DIOXIDE_MEASUREMENT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.EQUIVALENT_CARBON_DIOXIDE_MEASUREMENT,
                translation_key="equivalent_carbon_dioxide",
                name="Equivalent Carbon Dioxide Measurement",  # From first doc
                native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO2,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.FORMALDEHYDE_MEASUREMENT: {
        Attribute.FORMALDEHYDE_LEVEL: [
            SmartThingsSensorEntityDescription(
                key=Attribute.FORMALDEHYDE_LEVEL,
                translation_key="formaldehyde",
                name="Formaldehyde Measurement",  # From first doc
                native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.GAS_METER: {
        Attribute.GAS_METER: [
            SmartThingsSensorEntityDescription(
                key=Attribute.GAS_METER,
                translation_key="gas_meter",
                name="Gas Meter",  # From first doc
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ],
        Attribute.GAS_METER_CALORIFIC: [
            SmartThingsSensorEntityDescription(
                key=Attribute.GAS_METER_CALORIFIC,
                translation_key="gas_meter_calorific",
                name="Gas Meter Calorific",  # From first doc
            )
        ],
        Attribute.GAS_METER_TIME: [
            SmartThingsSensorEntityDescription(
                key=Attribute.GAS_METER_TIME,
                translation_key="gas_meter_time",
                name="Gas Meter Time",  # From first doc
                device_class=SensorDeviceClass.TIMESTAMP,
                value_fn=dt_util.parse_datetime,
            )
        ],
        Attribute.GAS_METER_VOLUME: [
            SmartThingsSensorEntityDescription(
                key=Attribute.GAS_METER_VOLUME,
                translation_key="gas_meter_volume",
                name="Gas Meter Volume",  # From first doc
                native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
                device_class=SensorDeviceClass.GAS,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ],
    },
    Capability.ILLUMINANCE_MEASUREMENT: {
        Attribute.ILLUMINANCE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ILLUMINANCE,
                translation_key="illuminance",
                name="Illuminance",  # From first doc
                native_unit_of_measurement=LIGHT_LUX,
                device_class=SensorDeviceClass.ILLUMINANCE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.INFRARED_LEVEL: {
        Attribute.INFRARED_LEVEL: [
            SmartThingsSensorEntityDescription(
                key=Attribute.INFRARED_LEVEL,
                translation_key="infrared_level",
                name="Infrared Level",  # From first doc
                native_unit_of_measurement=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.MEDIA_INPUT_SOURCE: {
        Attribute.INPUT_SOURCE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.INPUT_SOURCE,
                translation_key="media_input_source",
                name="Media Input Source",  # From first doc
                device_class=SensorDeviceClass.ENUM,
                options_attribute=Attribute.SUPPORTED_INPUT_SOURCES,
                value_fn=lambda value: value.lower() if value else None,
            )
        ]
    },
    Capability.MEDIA_PLAYBACK_REPEAT: {
        Attribute.PLAYBACK_REPEAT_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.PLAYBACK_REPEAT_MODE,
                translation_key="media_playback_repeat",
                name="Media Playback Repeat",  # From first doc
            )
        ]
    },
    Capability.MEDIA_PLAYBACK_SHUFFLE: {
        Attribute.PLAYBACK_SHUFFLE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.PLAYBACK_SHUFFLE,
                translation_key="media_playback_shuffle",
                name="Media Playback Shuffle",  # From first doc
            )
        ]
    },
    Capability.MEDIA_PLAYBACK: {
        Attribute.PLAYBACK_STATUS: [
            SmartThingsSensorEntityDescription(
                key=Attribute.PLAYBACK_STATUS,
                translation_key="media_playback_status",
                name="Media Playback Status",  # From first doc
                options=["paused", "playing", "stopped", "fast_forwarding", "rewinding", "buffering"],
                device_class=SensorDeviceClass.ENUM,
                value_fn=lambda value: MEDIA_PLAYBACK_STATE_MAP.get(value, value),
            )
        ]
    },
    Capability.ODOR_SENSOR: {
        Attribute.ODOR_LEVEL: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ODOR_LEVEL,
                translation_key="odor_sensor",
                name="Odor Sensor",  # From first doc
            )
        ]
    },
    # See also Capability.SAMSUNG_CE_OVEN_MODE
    Capability.OVEN_MODE: {
        Attribute.OVEN_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.OVEN_MODE,
                translation_key="oven_mode",
                name="Oven Mode",  # From first doc
                entity_category=EntityCategory.DIAGNOSTIC,
                options=list(OVEN_MODE.values()),
                device_class=SensorDeviceClass.ENUM,
                value_fn=lambda value: OVEN_MODE.get(value, value),
            )
        ]
    },
    Capability.OVEN_OPERATING_STATE: {
        Attribute.MACHINE_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.MACHINE_STATE,
                translation_key="oven_machine_state",
                name="Oven Machine State",  # From first doc
                options=["ready", "running", "paused"],
                device_class=SensorDeviceClass.ENUM,
            )
        ],
        Attribute.OVEN_JOB_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.OVEN_JOB_STATE,
                translation_key="oven_job_state",
                name="Oven Job State",  # From first doc
                options=[
                    "cleaning", "cooking", "cooling", "draining", "preheat",
                    "ready", "rinsing", "finished", "scheduled_start", "warming",
                    "defrosting", "sensing", "searing", "fast_preheat", "scheduled_end",
                    "stone_heating", "time_hold_preheat",
                ],
                device_class=SensorDeviceClass.ENUM,
                value_fn=lambda value: OVEN_JOB_STATE_MAP.get(value, value),
            )
        ],
        Attribute.COMPLETION_TIME: [
            SmartThingsSensorEntityDescription(
                key=Attribute.COMPLETION_TIME,
                translation_key="completion_time",
                name="Oven Completion Time",  # From first doc
            )
        ],
        Attribute.OPERATION_TIME: [
            SmartThingsSensorEntityDescription(
                key="CookTime",
                translation_key="operation_time",
                name="Cook Time",  # From first doc
            )
        ],
        Attribute.PROGRESS: [
            SmartThingsSensorEntityDescription(
                key=Attribute.PROGRESS,
                translation_key="progress",
                name="Progress",  # From first doc
                native_unit_of_measurement=PERCENTAGE,
            )
        ],
    },
    Capability.OVEN_SETPOINT: {
        Attribute.OVEN_SETPOINT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.OVEN_SETPOINT,
                translation_key="oven_setpoint",
                name="Oven Set Point",  # From first doc (note: "Set Point" vs "Setpoint" as in first doc)
            )
        ]
    },
    Capability.POWER_CONSUMPTION_REPORT: {
        Attribute.POWER_CONSUMPTION: [
            SmartThingsSensorEntityDescription(
                key="energy_meter",
                translation_key="energy_meter",
                name="Energy Meter",  # Derived from key (first doc has empty list for this capability)
                state_class=SensorStateClass.TOTAL_INCREASING,
                device_class=SensorDeviceClass.ENERGY,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                value_fn=lambda value: value["energy"] / 1000,
                suggested_display_precision=2,
            ),
            SmartThingsSensorEntityDescription(
                key="power_meter",
                translation_key="power_meter",
                name="Power Meter",  # Derived from key
                state_class=SensorStateClass.MEASUREMENT,
                device_class=SensorDeviceClass.POWER,
                native_unit_of_measurement=UnitOfPower.WATT,
                value_fn=lambda value: value["power"],
                extra_state_attributes_fn=power_attributes,
                suggested_display_precision=2,
            ),
            SmartThingsSensorEntityDescription(
                key="deltaEnergy_meter",
                translation_key="energy_difference",
                name="Energy Difference",  # Derived from translation_key
                state_class=SensorStateClass.TOTAL,
                device_class=SensorDeviceClass.ENERGY,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                value_fn=lambda value: value["deltaEnergy"] / 1000,
                suggested_display_precision=2,
            ),
            SmartThingsSensorEntityDescription(
                key="powerEnergy_meter",
                translation_key="power_energy",
                name="Power Energy",  # Derived from translation_key
                state_class=SensorStateClass.MEASUREMENT,
#                device_class=SensorDeviceClass.ENERGY,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                value_fn=lambda value: value["powerEnergy"] / 1000,
                suggested_display_precision=2,
            ),
            SmartThingsSensorEntityDescription(
                key="energySaved_meter",
                translation_key="energy_saved",
                name="Energy Saved",  # Derived from translation_key
                state_class=SensorStateClass.TOTAL_INCREASING,
                device_class=SensorDeviceClass.ENERGY,
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                value_fn=lambda value: value["energySaved"] / 1000,
                suggested_display_precision=2,
            ),
        ]
    },
    Capability.POWER_METER: {
        Attribute.POWER: [
            SmartThingsSensorEntityDescription(
                key=Attribute.POWER,
                translation_key="power_meter",
                name="Power Meter",  # From first doc
                native_unit_of_measurement=UnitOfPower.WATT,
                device_class=SensorDeviceClass.POWER,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.POWER_SOURCE: {
        Attribute.POWER_SOURCE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.POWER_SOURCE,
                translation_key="power_source",
                name="Power Source",  # From first doc
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.REFRIGERATION_SETPOINT: {
        Attribute.REFRIGERATION_SETPOINT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.REFRIGERATION_SETPOINT,
                translation_key="refrigeration_setpoint",
                name="Refrigeration Setpoint",  # From first doc
                device_class=SensorDeviceClass.TEMPERATURE,
            )
        ]
    },
    Capability.RELATIVE_HUMIDITY_MEASUREMENT: {
        Attribute.HUMIDITY: [
            SmartThingsSensorEntityDescription(
                key=Attribute.HUMIDITY,
                translation_key="relative_humidity",
                name="Relative Humidity Measurement",  # From first doc
                native_unit_of_measurement=PERCENTAGE,
                device_class=SensorDeviceClass.HUMIDITY,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.ROBOT_CLEANER_CLEANING_MODE: {
        Attribute.ROBOT_CLEANER_CLEANING_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ROBOT_CLEANER_CLEANING_MODE,
                translation_key="robot_cleaner_cleaning_mode",
                name="Robot Cleaner Cleaning Mode",  # From first doc
                options=["auto", "part", "repeat", "manual", "stop", "map"],
                device_class=SensorDeviceClass.ENUM,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ],
    },
    Capability.ROBOT_CLEANER_MOVEMENT: {
        Attribute.ROBOT_CLEANER_MOVEMENT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ROBOT_CLEANER_MOVEMENT,
                translation_key="robot_cleaner_movement",
                name="Robot Cleaner Movement",  # From first doc
                options=[
                    "homing", "idle", "charging", "alarm", "off", "reserve",
                    "point", "after", "cleaning", "pause",
                ],
                device_class=SensorDeviceClass.ENUM,
                value_fn=lambda value: ROBOT_CLEANER_MOVEMENT_MAP.get(value, value),
            )
        ]
    },
    Capability.ROBOT_CLEANER_TURBO_MODE: {
        Attribute.ROBOT_CLEANER_TURBO_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ROBOT_CLEANER_TURBO_MODE,
                translation_key="robot_cleaner_turbo_mode",
                name="Robot Cleaner Turbo Mode",  # From first doc
                options=["on", "off", "silence", "extra_silence"],
                device_class=SensorDeviceClass.ENUM,
                value_fn=lambda value: ROBOT_CLEANER_TURBO_MODE_STATE_MAP.get(value, value),
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.SIGNAL_STRENGTH: {
        Attribute.LQI: [
            SmartThingsSensorEntityDescription(
                key=Attribute.LQI,
                translation_key="link_quality",
                name="LQI Signal Strength",  # From first doc
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ],
        Attribute.RSSI: [
            SmartThingsSensorEntityDescription(
                key=Attribute.RSSI,
                translation_key="rssi",
                name="RSSI Signal Strength",  # From first doc
                device_class=SensorDeviceClass.SIGNAL_STRENGTH,
                state_class=SensorStateClass.MEASUREMENT,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ],
    },
    Capability.SMOKE_DETECTOR: {
        Attribute.SMOKE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.SMOKE,
                translation_key="smoke_detector",
                name="Smoke Detector",  # From first doc
                options=["detected", "clear", "tested"],
                device_class=SensorDeviceClass.ENUM,
            )
        ]
    },
    Capability.TEMPERATURE_MEASUREMENT: {
        Attribute.TEMPERATURE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.TEMPERATURE,
                translation_key="temperature",
                name="Temperature Measurement",  # From first doc
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="F",
            )
        ]
    },
    Capability.THERMOSTAT_COOLING_SETPOINT: {
        Attribute.COOLING_SETPOINT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.COOLING_SETPOINT,
                translation_key="thermostat_cooling_setpoint",
                name="Thermostat Cooling Setpoint",  # From first doc
                device_class=SensorDeviceClass.TEMPERATURE,
                native_unit_of_measurement="F",
            )
        ]
    },
    Capability.THERMOSTAT_FAN_MODE: {
        Attribute.THERMOSTAT_FAN_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.THERMOSTAT_FAN_MODE,
                translation_key="thermostat_fan_mode",
                name="Thermostat Fan Mode",  # From first doc
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.THERMOSTAT_HEATING_SETPOINT: {
        Attribute.HEATING_SETPOINT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.HEATING_SETPOINT,
                translation_key="thermostat_heating_setpoint",
                name="Thermostat Heating Setpoint",  # From first doc
                device_class=SensorDeviceClass.TEMPERATURE,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.THERMOSTAT_MODE: {
        Attribute.THERMOSTAT_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.THERMOSTAT_MODE,
                translation_key="thermostat_mode",
                name="Thermostat Mode",  # From first doc
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.THERMOSTAT_OPERATING_STATE: {
        Attribute.THERMOSTAT_OPERATING_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.THERMOSTAT_OPERATING_STATE,
                translation_key="thermostat_operating_state",
                name="Thermostat Operating State",  # From first doc
            )
        ]
    },
    Capability.THERMOSTAT_SETPOINT: {
        Attribute.THERMOSTAT_SETPOINT: [
            SmartThingsSensorEntityDescription(
                key=Attribute.THERMOSTAT_SETPOINT,
                translation_key="thermostat_setpoint",
                name="Thermostat Setpoint",  # From first doc
                device_class=SensorDeviceClass.TEMPERATURE,
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.THREE_AXIS: {
        Attribute.THREE_AXIS: [
            SmartThingsSensorEntityDescription(
                key="X Coordinate",
                translation_key="x_coordinate",
                name="X Coordinate",  # From first doc THREE_AXIS_NAMES
                unique_id_separator=" ",
                value_fn=lambda value: value[0],
            ),
            SmartThingsSensorEntityDescription(
                key="Y Coordinate",
                translation_key="y_coordinate",
                name="Y Coordinate",  # From first doc THREE_AXIS_NAMES
                unique_id_separator=" ",
                value_fn=lambda value: value[1],
            ),
            SmartThingsSensorEntityDescription(
                key="Z Coordinate",
                translation_key="z_coordinate",
                name="Z Coordinate",  # From first doc THREE_AXIS_NAMES
                unique_id_separator=" ",
                value_fn=lambda value: value[2],
            ),
        ]
    },
    Capability.TV_CHANNEL: {
        Attribute.TV_CHANNEL: [
            SmartThingsSensorEntityDescription(
                key=Attribute.TV_CHANNEL,
                translation_key="tv_channel",
                name="Tv Channel",  # From first doc (capitalization preserved)
            )
        ],
        Attribute.TV_CHANNEL_NAME: [
            SmartThingsSensorEntityDescription(
                key=Attribute.TV_CHANNEL_NAME,
                translation_key="tv_channel_name",
                name="Tv Channel Name",  # From first doc
            )
        ],
    },
    Capability.TVOC_MEASUREMENT: {
        Attribute.TVOC_LEVEL: [
            SmartThingsSensorEntityDescription(
                key=Attribute.TVOC_LEVEL,
                translation_key="tvoc",
                name="Tvoc Measurement",  # From first doc (capitalization preserved)
                device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
                native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.ULTRAVIOLET_INDEX: {
        Attribute.ULTRAVIOLET_INDEX: [
            SmartThingsSensorEntityDescription(
                key=Attribute.ULTRAVIOLET_INDEX,
                translation_key="uv_index",
                name="Ultraviolet Index",  # From first doc
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.VOLTAGE_MEASUREMENT: {
        Attribute.VOLTAGE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.VOLTAGE,
                translation_key="voltage",
                name="Voltage Measurement",  # From first doc
                device_class=SensorDeviceClass.VOLTAGE,
                state_class=SensorStateClass.MEASUREMENT,
            )
        ]
    },
    Capability.WASHER_MODE: {
        Attribute.WASHER_MODE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.WASHER_MODE,
                translation_key="washer_mode",
                name="Washer Mode",  # From first doc
                entity_category=EntityCategory.DIAGNOSTIC,
            )
        ]
    },
    Capability.WASHER_OPERATING_STATE: {
        Attribute.MACHINE_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.MACHINE_STATE,
                translation_key="washer_machine_state",
                name="Washer Machine State",  # From first doc
                options=WASHER_OPTIONS,
                device_class=SensorDeviceClass.ENUM,
            )
        ],
        Attribute.WASHER_JOB_STATE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.WASHER_JOB_STATE,
                translation_key="washer_job_state",
                name="Washer Job State",  # From first doc
                options=[
                    "air_wash", "ai_rinse", "ai_spin", "ai_wash", "cooling",
                    "delay_wash", "drying", "finish", "none", "pre_wash",
                    "rinse", "spin", "wash", "weight_sensing", "wrinkle_prevent",
                    "freeze_protection",
                ],
                device_class=SensorDeviceClass.ENUM,
                value_fn=lambda value: JOB_STATE_MAP.get(value, value),
            )
        ],
        Attribute.COMPLETION_TIME: [
            SmartThingsSensorEntityDescription(
                key=Attribute.COMPLETION_TIME,
                translation_key="completion_time",
                name="Washer Completion Time",  # From first doc
                device_class=SensorDeviceClass.TIMESTAMP,
                value_fn=dt_util.parse_datetime,
            )
        ],
    },
    Capability.CUSTOM_WATER_FILTER: {
        Attribute.WATER_FILTER_STATUS: [
            SmartThingsSensorEntityDescription(
                key=Attribute.WATER_FILTER_STATUS,
                translation_key="water_filter_status",
                name="Water Filter Status",  # From first doc (Capability.water_filter)
            )
        ],
        Attribute.WATER_FILTER_USAGE: [
            SmartThingsSensorEntityDescription(
                key=Attribute.WATER_FILTER_USAGE,
                translation_key="water_filter_usage",
                name="Water Filter Usage",  # From first doc
                native_unit_of_measurement=PERCENTAGE,
            )
        ],
    },
    Capability.SAMSUNG_CE_WATER_CONSUMPTION_REPORT: {
        Attribute.WATER_CONSUMPTION: [
            SmartThingsSensorEntityDescription(
                key=Attribute.WATER_CONSUMPTION,
                translation_key="water_consumption",
                name="Water Consumption",  # From first doc (Capability.water_consumption_report)
            )
        ],
    },
    Capability.SAMSUNG_CE_MEAT_PROBE: {
        Attribute.STATUS: [
            SmartThingsSensorEntityDescription(
                key="ProbeStatus",
                translation_key="meat_probe_status",
                name="Probe Status",  # From first doc (Capability.oven_meat_probe)
            )
        ],
        Attribute.TEMPERATURE: [
            SmartThingsSensorEntityDescription(
                key="ProbeTemperature",
                translation_key="probe_temperature",
                name="Probe Temperature",  # Derived (not explicitly in first doc, but aligns with intent)
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="F",
            )
        ],
        Attribute.TEMPERATURE_SETPOINT: [
            SmartThingsSensorEntityDescription(
                key="ProbeTemperatureSetpoint",
                translation_key="probe_temperature_setpoint",
                name="Probe Temperature Setpoint",  # From first doc
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="F",
            )
        ]
    },
    Capability.SAMSUNG_CE_OVEN_MODE: {
        Attribute.OVEN_MODE: [
            SmartThingsSensorEntityDescription(
                key="OvenMode",
                translation_key="oven_mode",
                name="CE Oven Mode",  # Added CE to differentiate from Capability.OVEN_MODE
            )
        ],
    },
    Capability.CUSTOM_COOKTOP_OPERATING_STATE: {
        Attribute.COOKTOP_OPERATING_STATE: [
            SmartThingsSensorEntityDescription(
                key="CooktopOperatingState",
                translation_key="cooktop_operating_state",
                name="Cooktop Operating State",  # Added added for smmarczak
                options=["run", "ready"],
                device_class=SensorDeviceClass.ENUM, 
            )
        ],
    },        
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
    """Add sensors for a config entry."""
    entry_data = entry.runtime_data
    entities = []
    for device in entry_data.devices.values():
        _LOGGER.debug(
                  "NB device loop device: %s Status: %s",
                   device.device.device_id,
                   device.status.keys(),
                   
        )
            
        for component in device.status: 
            _LOGGER.debug(
                 "NB component loop: %s",
                   component,                   
            ) 
                     
            for capability, attributes in CAPABILITY_TO_SENSORS.items():
                _LOGGER.debug(
                      "NB capabilities loop Component: %s Capability:%s Attributes:%s",
                       component,
                       capability,
                       attributes,               
                )     
    
                # Check if capability exists in device status
                if capability not in device.status[component]:
                    _LOGGER.debug(
                      "NB capability not found - restart case loop Component: %s Capability:%s",
                       component,
                       capability,                       
                    )     
                    continue
                    
                _LOGGER.debug(
                      "NB capability FOUND - continue to look for attribute Component: %s Capability:%s",
                       component,
                       capability,                       
                )         
                
                for attribute, descriptions in attributes.items():
                    for description in descriptions:
                        # Handle the complex condition
                        should_skip = False
                        if description.capability_ignore_list:
                            for capability_list in description.capability_ignore_list:
                                all_capabilities_present = True
                                for capability in capability_list:
                                    if capability not in device.status[component]:
                                        all_capabilities_present = False
                                        break
                                if all_capabilities_present:
                                    should_skip = True
                                    break
                        
                        if should_skip:
                            continue
                        
                        # Create and add the entity
                        entity = SmartThingsSensor(entry_data.client, device, component, description, capability, attribute)
                        _LOGGER.debug(
                            "NB Found a sensor to add Device:%s component:%s capability:%s attribute:%s",
                            device.device.label,
                            component,
                            capability,
                            attribute,
                       
                        )     
                        entities.append(entity)

    # Finally, call async_add_entities with the collected entities
    async_add_entities(entities)


class SmartThingsSensor(SmartThingsEntity, SensorEntity):
    """Define a SmartThings Sensor."""

    entity_description: SmartThingsSensorEntityDescription

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        component: str,
        entity_description: SmartThingsSensorEntityDescription,
        capability: Capability,
        attribute: Attribute,
    ) -> None:
        """Init the class."""
        super().__init__(client, device,{capability},  component)
        
        if component == "main":
            self._attr_unique_id = f"{device.device.device_id}{entity_description.unique_id_separator}{entity_description.key}"
        else:
            self._attr_unique_id = f"{device.device.device_id}{entity_description.unique_id_separator}{component}{entity_description.unique_id_separator}{entity_description.key}"
            
        self._attribute = attribute
        self.capability = capability
        self.entity_description = entity_description
        self._component = component
        
        if self._component == "main": 
            self._attr_name = f"{entity_description.name}" 
        else:              
            self._attr_name = f"{component} {entity_description.name}"

    @property
    def native_value(self) -> str | float | datetime | int | None:
        """Return the state of the sensor."""
        res = self.get_attribute_value(self.capability, self._attribute)
        
        _LOGGER.debug(
            "NB SmartThingsSensor Return the state of the sensor. Device:%s component:%s capability:%s attribute:%s RETURN: %s",
                            self.device.device.label,
                            self._component,
                            self.capability,
                            self._attribute,
                            self.entity_description.value_fn(res),                      
        )             
        
        return self.entity_description.value_fn(res)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit this state is expressed in."""
        _LOGGER.debug(
            "NB Return the unit this state is expressed in. Device:%s component:%s capability:%s attribute:%s",
                            self.device.device.label,
                            self._component,
                            self.capability,
                            self._attribute,                      
        )                     
        unit = self._internal_state[self.capability][self._attribute].unit
        return (
            UNITS.get(unit, unit)
            if unit
            else self.entity_description.native_unit_of_measurement
        )

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        if self.entity_description.extra_state_attributes_fn:
            return self.entity_description.extra_state_attributes_fn(
                self.get_attribute_value(self.capability, self._attribute)
            )
        return None

    @property
    def options(self) -> list[str] | None:
        """Return the options for this sensor."""
        if self.entity_description.options_attribute:
            options = self.get_attribute_value(
                self.capability, self.entity_description.options_attribute
            )
            return [option.lower() for option in options]
        return super().options
