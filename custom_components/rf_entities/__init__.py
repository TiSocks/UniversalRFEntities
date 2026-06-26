"""Core setup for the RF Entities integration."""

import asyncio
import logging
import voluptuous as vol

from homeassistant.components.persistent_notification import (
    async_create as notify_create,
    async_dismiss as notify_dismiss,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import (
    ATTR_TARGET_ENTITY,
    ATTR_TIMEOUT,
    CONF_BUTTON_CODE,
    CONF_BUTTON_PROTOCOL,
    CONF_BUTTON_PULSE_LENGTH,
    CONF_BUTTONS,
    CONF_RX_EVENT,
    CONF_SENSOR_STATE_OFF_CODE,
    CONF_SENSOR_STATE_ON_CODE,
    CONF_SENSORS,
    DEFAULT_RX_EVENT,
    DOMAIN,
    LEARNING_TIMEOUT,
    SERVICE_LEARN_COMMAND,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON, Platform.SENSOR, Platform.BINARY_SENSOR]

LEARN_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TARGET_ENTITY): cv.entity_id,
        vol.Optional(ATTR_TIMEOUT, default=LEARNING_TIMEOUT): cv.positive_int,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RF Entities from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Store options or fallback to entry data if options are not set yet
    config = {}
    config.update(entry.data)
    config.update(entry.options)
    
    hass.data[DOMAIN][entry.entry_id] = {
        "config": config,
        "learning_active": False,
    }

    # Register platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)



    # Listen for option updates
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        

            
    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
