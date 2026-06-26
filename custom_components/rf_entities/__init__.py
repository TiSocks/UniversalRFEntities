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

    # Register the learn_command service globally if not already registered
    if not hass.services.has_service(DOMAIN, SERVICE_LEARN_COMMAND):
        async def handle_learn_command(call: ServiceCall) -> None:
            await async_handle_learn_command(hass, call)

        hass.services.async_register(
            DOMAIN,
            SERVICE_LEARN_COMMAND,
            handle_learn_command,
            schema=LEARN_SERVICE_SCHEMA,
        )

    # Listen for option updates
    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # If no entries are left, clean up service
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_LEARN_COMMAND)
            
    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_handle_learn_command(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle learning RF commands from receiving transceiver events."""
    target_entity_id = call.data[ATTR_TARGET_ENTITY]
    timeout = call.data[ATTR_TIMEOUT]

    # Resolve target entity to its config entry and unique ID
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(target_entity_id)

    if not entity_entry or entity_entry.platform != DOMAIN:
        _LOGGER.error("Entity %s does not belong to the rf_entities integration", target_entity_id)
        notify_create(
            hass,
            f"Error: {target_entity_id} is not a valid RF Entity.",
            title="RF Entities Learning Error",
            notification_id="rf_entities_learn_error",
        )
        return

    entry_id = entity_entry.config_entry_id
    config_entry = hass.config_entries.async_get_entry(entry_id)

    if not config_entry:
        _LOGGER.error("Config entry not found for entity %s", target_entity_id)
        return

    # Determine unique key and type (button or sensor) from the unique ID
    # Unique ID format is: {entry_id}_{type}_{slug}
    unique_id = entity_entry.unique_id
    parts = unique_id.split("_", 2)
    if len(parts) < 3:
        _LOGGER.error("Invalid unique ID format: %s", unique_id)
        return

    entity_type = parts[1]  # "button", "sensor", "binary"
    entity_slug = parts[2]

    # Check if learning is already active for this entry
    if hass.data[DOMAIN][entry_id]["learning_active"]:
        _LOGGER.warning("Learning mode is already running for this device")
        return

    hass.data[DOMAIN][entry_id]["learning_active"] = True

    # Identify the configured receiver event
    rx_event = config_entry.options.get(CONF_RX_EVENT) or config_entry.data.get(CONF_RX_EVENT) or DEFAULT_RX_EVENT

    # Show notification to the user
    notification_id = f"rf_entities_learn_{entry_id}"
    notify_create(
        hass,
        f"Learning mode active for **{entity_entry.original_name or entity_slug}**.<br>"
        f"Please press the button on your RF remote now.<br>"
        f"Listening for event `{rx_event}` (timeout in {timeout}s)...",
        title="RF Entities: Learning Mode",
        notification_id=notification_id,
    )

    learned_event = asyncio.Event()
    learned_data = {}

    @callback
    def handle_rf_event(event):
        """Handle incoming RF transceiver events."""
        data = event.data
        _LOGGER.debug("Received RF transceiver event data: %s", data)

        # Smart extraction of protocol, code, and pulse length
        code = None
        for key in ["code", "value", "raw", "data", "key"]:
            if key in data:
                code = str(data[key])
                break

        protocol = None
        for key in ["protocol", "proto", "type"]:
            if key in data:
                protocol = str(data[key])
                break

        pulse_length = None
        for key in ["pulse_length", "pulse", "length", "pulselength"]:
            if key in data:
                pulse_length = str(data[key])
                break

        if code:
            learned_data["code"] = code
            if protocol:
                learned_data["protocol"] = protocol
            if pulse_length:
                learned_data["pulse_length"] = pulse_length
            learned_event.set()

    # Register event listener
    remove_listener = hass.bus.async_listen(rx_event, handle_rf_event)

    try:
        # Wait for the event or timeout
        await asyncio.wait_for(learned_event.wait(), timeout=timeout)
        
        # Save learned code back to config entry options
        new_options = dict(config_entry.options)
        
        if entity_type == "button":
            buttons = dict(new_options.get(CONF_BUTTONS, {}))
            if entity_slug in buttons:
                btn_config = dict(buttons[entity_slug])
                btn_config[CONF_BUTTON_CODE] = learned_data.get("code")
                if "protocol" in learned_data:
                    btn_config[CONF_BUTTON_PROTOCOL] = learned_data["protocol"]
                if "pulse_length" in learned_data:
                    btn_config[CONF_BUTTON_PULSE_LENGTH] = learned_data["pulse_length"]
                buttons[entity_slug] = btn_config
                new_options[CONF_BUTTONS] = buttons
                _LOGGER.info("Learned code '%s' for button '%s'", btn_config[CONF_BUTTON_CODE], entity_slug)
        else:
            # It is a sensor or binary sensor
            sensors = dict(new_options.get(CONF_SENSORS, {}))
            if entity_slug in sensors:
                sens_config = dict(sensors[entity_slug])
                # By default, save to ON code
                sens_config[CONF_SENSOR_STATE_ON_CODE] = learned_data.get("code")
                sensors[entity_slug] = sens_config
                new_options[CONF_SENSORS] = sensors
                _LOGGER.info("Learned code '%s' for sensor '%s'", sens_config[CONF_SENSOR_STATE_ON_CODE], entity_slug)

        # Write options change (triggers update_listener and reload)
        hass.config_entries.async_update_entry(config_entry, options=new_options)

        notify_create(
            hass,
            f"Successfully learned code! 🎉<br>"
            f"**Code**: `{learned_data.get('code')}`<br>"
            f"**Protocol**: `{learned_data.get('protocol', 'N/A')}`<br>"
            f"**Pulse Length**: `{learned_data.get('pulse_length', 'N/A')}`",
            title="RF Entities: Learning Success",
            notification_id=notification_id,
        )

    except asyncio.TimeoutError:
        _LOGGER.warning("Learning mode timed out for entity %s", target_entity_id)
        notify_create(
            hass,
            f"Learning mode timed out for **{entity_entry.original_name or entity_slug}** after {timeout} seconds.",
            title="RF Entities: Learning Timed Out",
            notification_id=notification_id,
        )
    finally:
        remove_listener()
        hass.data[DOMAIN][entry_id]["learning_active"] = False
