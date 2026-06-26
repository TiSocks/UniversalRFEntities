"""Sensor platform for RF Entities."""

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE_NAME,
    CONF_RX_EVENT,
    CONF_SENSOR_NAME,
    CONF_SENSOR_STATE_OFF_CODE,
    CONF_SENSOR_STATE_ON_CODE,
    CONF_SENSOR_TYPE,
    CONF_SENSORS,
    DEFAULT_RX_EVENT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the RF Sensor entities from a config entry."""
    entry_id = config_entry.entry_id
    config = hass.data[DOMAIN][entry_id]["config"]
    
    sensors_config = config.get(CONF_SENSORS, {})
    entities = []

    for slug, sens_config in sensors_config.items():
        if sens_config.get(CONF_SENSOR_TYPE) == "sensor":
            entities.append(
                RFSensorEntity(
                    hass=hass,
                    entry_id=entry_id,
                    device_name=config[CONF_DEVICE_NAME],
                    slug=slug,
                    name=sens_config[CONF_SENSOR_NAME],
                    state_on_code=sens_config.get(CONF_SENSOR_STATE_ON_CODE),
                    state_off_code=sens_config.get(CONF_SENSOR_STATE_OFF_CODE),
                    rx_event=config.get(CONF_RX_EVENT) or DEFAULT_RX_EVENT,
                )
            )

    async_add_entities(entities)


class RFSensorEntity(SensorEntity):
    """Representation of an RF state sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        device_name: str,
        slug: str,
        name: str,
        state_on_code: str,
        state_off_code: str,
        rx_event: str,
    ) -> None:
        """Initialize the RF Sensor."""
        self.hass = hass
        self._entry_id = entry_id
        self._device_name = device_name
        self._slug = slug
        self._attr_name = name
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{entry_id}_sensor_{slug}"
        self._state_on_code = state_on_code
        self._state_off_code = state_off_code
        self._rx_event = rx_event
        self._state = "unknown"
        self._extra_attributes = {}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information linking this sensor to the RF Device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=self._device_name,
            manufacturer="RF Entities",
            model="Virtual RF Device",
        )

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self._extra_attributes

    async def async_added_to_hass(self) -> None:
        """Register event listener for incoming RF signals."""
        self.async_on_remove(
            self.hass.bus.async_listen(self._rx_event, self._handle_rf_event)
        )

    @callback
    def _handle_rf_event(self, event) -> None:
        """Handle incoming transceiver RF event."""
        data = event.data
        
        # Extract code from the event data
        code = None
        for key in ["code", "value", "raw", "data", "key"]:
            if key in data:
                code = str(data[key])
                break

        if not code:
            return

        # Check if code matches a configured state
        if self._state_on_code and code == self._state_on_code:
            self._state = "on"
        elif self._state_off_code and code == self._state_off_code:
            self._state = "off"
        else:
            # Default to showing the raw received code as the state
            self._state = code

        # Update metadata attributes
        self._extra_attributes["last_code"] = code
        self._extra_attributes["last_protocol"] = data.get("protocol") or data.get("proto")
        self._extra_attributes["last_pulse_length"] = data.get("pulse_length") or data.get("pulse")
        
        self.async_write_ha_state()
