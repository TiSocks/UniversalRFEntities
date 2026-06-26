"""Button platform for RF Entities."""

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_BUTTON_CODE,
    CONF_BUTTON_NAME,
    CONF_BUTTON_PROTOCOL,
    CONF_BUTTON_PULSE_LENGTH,
    CONF_BUTTONS,
    CONF_DEVICE_NAME,
    CONF_TRANSCEIVER_ENTITY,
    CONF_TX_SERVICE,
    DEFAULT_TX_SERVICE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the RF Button entities from a config entry."""
    entry_id = config_entry.entry_id
    config = hass.data[DOMAIN][entry_id]["config"]
    
    buttons_config = config.get(CONF_BUTTONS, {})
    entities = []

    for slug, btn_config in buttons_config.items():
        entities.append(
            RFButtonEntity(
                hass=hass,
                entry_id=entry_id,
                device_name=config[CONF_DEVICE_NAME],
                slug=slug,
                name=btn_config[CONF_BUTTON_NAME],
                code=btn_config.get(CONF_BUTTON_CODE),
                protocol=btn_config.get(CONF_BUTTON_PROTOCOL),
                pulse_length=btn_config.get(CONF_BUTTON_PULSE_LENGTH),
                transceiver_config=config,
            )
        )

    async_add_entities(entities)


class RFButtonEntity(ButtonEntity):
    """Representation of an RF transmitter button."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        device_name: str,
        slug: str,
        name: str,
        code: str,
        protocol: str,
        pulse_length: str,
        transceiver_config: dict[str, Any],
    ) -> None:
        """Initialize the RF Button."""
        self.hass = hass
        self._entry_id = entry_id
        self._device_name = device_name
        self._slug = slug
        self._attr_name = name
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{entry_id}_button_{slug}"
        self._code = code
        self._protocol = protocol
        self._pulse_length = pulse_length
        self._transceiver_config = transceiver_config

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information linking this button to the RF Device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._device_name,
            manufacturer="RF Entities",
            model="Virtual RF Device",
        )

    async def async_press(self) -> None:
        """Press the button to send the RF command."""
        if not self._code:
            _LOGGER.warning(
                "Button '%s' pressed but no RF code is configured. Call learn_command to program it",
                self._attr_name,
            )
            return

        tx_service = self._transceiver_config.get(CONF_TX_SERVICE) or DEFAULT_TX_SERVICE
        transceiver_entity = self._transceiver_config.get(CONF_TRANSCEIVER_ENTITY)

        if "." not in tx_service:
            _LOGGER.error("Invalid transmitter service format: %s", tx_service)
            return

        domain, service = tx_service.split(".", 1)
        service_data = {}

        import json

        if tx_service == "remote.send_command":
            if not transceiver_entity:
                _LOGGER.error("Cannot call remote.send_command without a transceiver remote entity configured")
                return
            service_data["entity_id"] = transceiver_entity
            
            # If code is a JSON list (e.g. raw codes), parse it
            try:
                parsed_code = json.loads(self._code) if self._code.strip().startswith("[") else self._code
            except json.JSONDecodeError:
                parsed_code = self._code
                
            service_data["command"] = [parsed_code] if not isinstance(parsed_code, list) else parsed_code
            if self._protocol:
                service_data["device"] = self._protocol
        else:
            # Custom ESPHome transmitter service (e.g. esphome.rfbridge433_send_byronsx_command)
            # If the code is a JSON dictionary, use it directly as the service data!
            try:
                if self._code.strip().startswith("{"):
                    service_data = json.loads(self._code)
                else:
                    raise ValueError("Not a JSON dict")
            except (ValueError, json.JSONDecodeError):
                # Fallback to standard mapping
                try:
                    service_data["code"] = int(self._code)
                except ValueError:
                    # Maybe it's a JSON list? (e.g. raw RF array)
                    try:
                        if self._code.strip().startswith("["):
                            service_data["code"] = json.loads(self._code)
                        else:
                            service_data["code"] = self._code
                    except json.JSONDecodeError:
                        service_data["code"] = self._code

                if self._protocol:
                    try:
                        service_data["protocol"] = int(self._protocol)
                    except ValueError:
                        service_data["protocol"] = self._protocol

                if self._pulse_length:
                    try:
                        service_data["pulse_length"] = int(self._pulse_length)
                    except ValueError:
                        service_data["pulse_length"] = self._pulse_length

        _LOGGER.info(
            "Sending RF code for button '%s' using service %s: %s",
            self._attr_name,
            tx_service,
            service_data,
        )

        try:
            await self.hass.services.async_call(domain, service, service_data, blocking=True)
        except Exception as err:
            _LOGGER.error("Failed to send RF code for button %s: %s", self._attr_name, err)
