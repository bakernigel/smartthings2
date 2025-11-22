"""Support for SmartThings Cloud."""

from __future__ import annotations

import logging
from typing import Any

from pysmartthings import (
    Attribute,
    Capability,
    Command,
    DeviceEvent,
    SmartThings,
    Status,
)

from pysmartthings.exceptions import SmartThingsCommandError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import FullDevice
from .const import DOMAIN, MAIN

_LOGGER = logging.getLogger(__name__)

CUSTOM_DISABLED_COMPONENTS_CAPABILITY = getattr(
    Capability, "CUSTOM_DISABLED_COMPONENTS", "custom.disabledComponents"
)
DISABLED_COMPONENTS_ATTRIBUTE = getattr(
    Attribute, "DISABLED_COMPONENTS", "disabledComponents"
)
CUSTOM_DISABLED_CAPABILITIES_CAPABILITY = getattr(
    Capability, "CUSTOM_DISABLED_CAPABILITIES", "custom.disabledCapabilities"
)
DISABLED_CAPABILITIES_ATTRIBUTE = getattr(
    Attribute, "DISABLED_CAPABILITIES", "disabledCapabilities"
)


class SmartThingsEntity(Entity):
    """Defines a SmartThings entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        capabilities: set[Capability],
        component=MAIN,
    ) -> None:
        """Initialize the instance."""
        self.client = client
        self.capabilities = capabilities
        self.component = component
        self._internal_state: dict[Capability | str, dict[Attribute | str, Status]] = {
            capability: device.status[component][capability]
            for capability in capabilities
            if capability in device.status[component]
        }
        self.device = device
        self._attr_unique_id = device.device.device_id
        self._attr_device_info = DeviceInfo(
            configuration_url="https://account.smartthings.com",
            identifiers={(DOMAIN, device.device.device_id)},
            name=device.device.label,
        )
        if (ocf := device.device.ocf) is not None:
            self._attr_device_info.update(
                {
                    "manufacturer": ocf.manufacturer_name,
                    "model": (
                        (ocf.model_number.split("|")[0]) if ocf.model_number else None
                    ),
                    "hw_version": ocf.hardware_version,
                    "sw_version": ocf.firmware_version,
                }
            )
        if (viper := device.device.viper) is not None:
            self._attr_device_info.update(
                {
                    "manufacturer": viper.manufacturer_name,
                    "model": viper.model_name,
                    "hw_version": viper.hardware_version,
                    "sw_version": viper.software_version,
                }
            )

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        await super().async_added_to_hass()
        for capability in self._internal_state:
            self.async_on_remove(
                self.client.add_device_capability_event_listener(
                    self.device.device.device_id,
                    self.component,
                    capability,
                    self._update_handler,
                )
            )
        self._update_attr()

    def _update_handler(self, event: DeviceEvent) -> None:
        self._internal_state[event.capability][event.attribute].value = event.value
        self._internal_state[event.capability][event.attribute].data = event.data
        self._handle_update()

    def supports_capability(self, capability: Capability) -> bool:
        """Test if device supports a capability."""
        return capability in self.device.status[self.component]

    def _get_status_value(
        self,
        component: str,
        capability: Capability | str,
        attribute: Attribute | str,
    ) -> Any:
        """Safely get a value from the device status."""
        capability_status = self._get_capability_status(component, capability)
        if capability_status is None:
            return None

        if attribute in capability_status:
            return capability_status[attribute].value

        attribute_value = str(attribute)
        for status_attribute, status_value in capability_status.items():
            if str(status_attribute) == attribute_value:
                return status_value.value

        return None

    def _get_capability_status(
        self, component: str, capability: Capability | str
    ) -> dict[Attribute | str, Status] | None:
        """Return the status mapping for a capability on a component."""
        component_status = self.device.status.get(component)
        if component_status is None:
            return None
        if capability in component_status:
            return component_status[capability]

        capability_name = str(capability)
        for status_capability, status_value in component_status.items():
            if str(status_capability) == capability_name:
                return status_value
        return None

    def get_attribute_value(self, capability: Capability, attribute: Attribute) -> Any:
        """Get the value of a device attribute."""
        capability_state = self._internal_state.get(capability)
        if capability_state is not None:
            if attribute in capability_state:
                return capability_state[attribute].value
            attribute_name = str(attribute)
            for status_attribute, status_value in capability_state.items():
                if str(status_attribute) == attribute_name:
                    return status_value.value

        return self._get_status_value(self.component, capability, attribute)

    def _update_attr(self) -> None:
        """Update the attributes."""

    def _handle_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr()
        self.async_write_ha_state()

    async def execute_device_command(
        self,
        capability: Capability,
        command: Command,
        argument: int | str | list[Any] | dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Execute a command on the device."""
        capability_status = self._get_capability_status(self.component, capability)
        if capability_status is None:
            _LOGGER.debug(
                "Skipping command for %s (%s); component=%s missing capability=%s",
                self.device.device.label,
                self.device.device.device_id,
                self.component,
                capability,
            )
            return

        disabled_components = self._get_status_value(
            MAIN,
            CUSTOM_DISABLED_COMPONENTS_CAPABILITY,
            DISABLED_COMPONENTS_ATTRIBUTE,
        )
        if (
            isinstance(disabled_components, list)
            and self.component in disabled_components
        ):
            _LOGGER.debug(
                "Skipping command to disabled component %s for device %s (%s)",
                self.component,
                self.device.device.label,
                self.device.device.device_id,
            )
            return

        disabled_capabilities = self._get_status_value(
            MAIN,
            CUSTOM_DISABLED_CAPABILITIES_CAPABILITY,
            DISABLED_CAPABILITIES_ATTRIBUTE,
        )
        if isinstance(disabled_capabilities, list):
            capability_ids = {str(item) for item in disabled_capabilities}
            if str(capability) in capability_ids or capability in disabled_capabilities:
                _LOGGER.debug(
                    "Skipping command to disabled capability %s on component %s for device %s (%s)",
                    capability,
                    self.component,
                    self.device.device.label,
                    self.device.device.device_id,
                )
                return

        payload: dict[str, Any] = {}
        if argument is not None:
            payload["argument"] = argument
        payload.update(kwargs)

        try:
            await self.client.execute_device_command(
                self.device.device.device_id,
                capability,
                command,
                self.component,
                **payload,
            )
        except SmartThingsCommandError as err:
            error_summary = self._summarize_command_error(err)
            _LOGGER.warning(
                "SmartThings rejected command for %s (%s), component=%s, capability=%s, command=%s: %s",
                self.device.device.label,
                self.device.device.device_id,
                self.component,
                capability,
                command,
                error_summary,
            )

    def _summarize_command_error(self, err: SmartThingsCommandError) -> str:
        """Return a concise description of a SmartThings command error."""
        error_response = getattr(err, "error", None)
        if error_response is None:
            return str(err)

        detail = getattr(error_response, "error", None)
        if detail is None:
            return str(err)

        summary_parts: list[str] = []

        detail_code = getattr(detail, "code", None)
        detail_message = getattr(detail, "message", None)
        detail_target = getattr(detail, "target", None)
        if detail_code or detail_message:
            code_message = (
                f"{detail_code}: {detail_message}"
                if detail_code and detail_message
                else detail_code or detail_message
            )
            if code_message:
                summary_parts.append(code_message)
        if detail_target:
            summary_parts.append(f"target={detail_target}")

        first_detail = None
        detail_list = getattr(detail, "details", None)
        if isinstance(detail_list, list) and detail_list:
            first_detail = detail_list[0]
        if first_detail is not None:
            first_detail_code = getattr(first_detail, "code", None)
            first_detail_message = getattr(first_detail, "message", None)
            first_detail_target = getattr(first_detail, "target", None)
            nested_parts = [
                part
                for part in (
                    first_detail_code,
                    first_detail_message,
                    f"target={first_detail_target}" if first_detail_target else None,
                )
                if part
            ]
            if nested_parts:
                summary_parts.append(f"detail: {' '.join(nested_parts)}")

        request_id = getattr(error_response, "request_id", None)
        if request_id:
            summary_parts.append(f"request_id={request_id}")

        if summary_parts:
            return "; ".join(summary_parts)

        return str(err)
