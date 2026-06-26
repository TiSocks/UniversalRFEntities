"""Config flow and options flow for RF Entities integration."""

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.util import slugify

from .const import (
    CONF_BUTTON_CODE,
    CONF_BUTTON_NAME,
    CONF_BUTTON_PROTOCOL,
    CONF_BUTTON_PULSE_LENGTH,
    CONF_BUTTONS,
    CONF_DEVICE_NAME,
    CONF_RX_EVENT,
    CONF_SENSOR_AUTO_OFF_SEC,
    CONF_SENSOR_NAME,
    CONF_SENSOR_STATE_OFF_CODE,
    CONF_SENSOR_STATE_ON_CODE,
    CONF_SENSOR_TYPE,
    CONF_SENSORS,
    CONF_TRANSCEIVER_ENTITY,
    CONF_TX_SERVICE,
    DEFAULT_RX_EVENT,
    DEFAULT_TX_SERVICE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class RFEntitiesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RF Entities."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self.new_device_name = user_input["device_name"]
            
            if user_input["bridge_service"] == "Custom":
                self.new_device_retries = user_input.get("tx_retries", 3)
                self.new_device_delay = user_input.get("tx_delay_ms", 15)
                return await self.async_step_custom()
            else:
                return self.async_create_entry(
                    title=self.new_device_name,
                    data={
                        "device_name": self.new_device_name,
                        "tx_service": user_input["bridge_service"],
                        "rx_event": "esphome.rf_code_received",
                        "transceiver_entity": "",
                        "tx_retries": user_input.get("tx_retries", 3),
                        "tx_delay_ms": user_input.get("tx_delay_ms", 15),
                    },
                    options={"buttons": {}, "sensors": {}},
                )

        esphome_services = self.hass.services.async_services().get("esphome", {})
        bridges = []
        for service_name in esphome_services:
            if service_name.endswith("_send_raw_rf"):
                bridges.append(f"esphome.{service_name}")
                
        bridges.append("Custom")

        schema_fields = {
            vol.Required("device_name", default="Universal RF Entities"): str,
            vol.Required("bridge_service", default=bridges[0]): vol.In(bridges),
            vol.Optional("tx_retries", default=3): int,
            vol.Optional("tx_delay_ms", default=15): int,
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema_fields),
            errors=errors,
        )

    async def async_step_custom(self, user_input=None):
        """Handle custom transceiver details."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title=self.new_device_name,
                data={
                    "device_name": self.new_device_name,
                    "tx_service": user_input["tx_service"],
                    "rx_event": user_input["rx_event"],
                    "transceiver_entity": "",
                    "tx_retries": getattr(self, "new_device_retries", 3),
                    "tx_delay_ms": getattr(self, "new_device_delay", 15),
                },
                options={"buttons": {}, "sensors": {}},
            )

        return self.async_show_form(
            step_id="custom",
            data_schema=vol.Schema({
                vol.Required("tx_service"): str,
                vol.Required("rx_event", default="esphome.rf_code_received"): str,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return RFEntitiesOptionsFlow()


class RFEntitiesOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for the RF device configuration."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self.selected_action = None
        # self.config_entry is automatically populated by the parent OptionsFlow class in newer HA versions.

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            action = user_input["action"]
            if action == "add_button":
                return await self.async_step_add_button()
            elif action == "add_sensor":
                return await self.async_step_add_sensor()
            elif action == "delete_entity":
                return await self.async_step_delete_entity()
            elif action == "learn_command":
                return await self.async_step_learn_command()
            elif action == "edit_transceiver":
                return await self.async_step_edit_transceiver()

        from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectOptionDict, SelectSelectorMode
        
        actions = [
            SelectOptionDict(value="add_button", label="Add Button Entity"),
            SelectOptionDict(value="add_sensor", label="Add Sensor Entity"),
            SelectOptionDict(value="delete_entity", label="Remove Entity"),
            SelectOptionDict(value="learn_command", label="Learn RF Code (Recommended)"),
            SelectOptionDict(value="edit_transceiver", label="Edit Transceiver Settings"),
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action", default="add_button"): SelectSelector(
                    SelectSelectorConfig(options=actions, mode=SelectSelectorMode.LIST)
                )
            }),
        )

    async def async_step_learn_command(self, user_input=None):
        """Select an entity to learn a code for."""
        buttons = self.config_entry.options.get("buttons", {})
        sensors = self.config_entry.options.get("sensors", {})
        
        entities = {}
        for slug, config in buttons.items():
            entities[f"btn_{slug}"] = f"Button: {config.get('name')}"
        for slug, config in sensors.items():
            entities[f"sens_{slug}"] = f"Sensor: {config.get('name')}"

        if not entities:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({}),
                errors={"base": "no_entities_to_delete"},
            )

        if user_input is not None:
            self._learn_entity = user_input["entity_id"]
            
            self._learn_task = self.hass.async_create_task(
                self._async_listen_for_rf_code()
            )
            return self.async_show_progress(
                step_id="learn_progress",
                progress_action="listening_for_rf",
            )

        return self.async_show_form(
            step_id="learn_command",
            data_schema=vol.Schema({
                vol.Required("entity_id"): vol.In(entities),
            }),
        )

    async def _async_listen_for_rf_code(self):
        """Background task to listen for RF code."""
        import asyncio
        from homeassistant.core import callback
        
        learned_event = asyncio.Event()
        self._learned_data = {}
        
        rx_event = self.config_entry.data.get("rx_event", "esphome.rf_code_received")

        @callback
        def handle_event(event):
            data = event.data
            code = None
            for key in ["code", "value", "raw", "data", "key"]:
                if key in data:
                    code = str(data[key])
                    break
            
            if code:
                self._learned_data["code"] = code
                if "protocol" in data or "proto" in data:
                    self._learned_data["protocol"] = str(data.get("protocol") or data.get("proto"))
                if "pulse_length" in data or "pulse" in data:
                    self._learned_data["pulse_length"] = str(data.get("pulse_length") or data.get("pulse"))
                learned_event.set()

        remove_listener = self.hass.bus.async_listen(rx_event, handle_event)
        
        try:
            await asyncio.wait_for(learned_event.wait(), timeout=30)
            self._learn_error = False
        except asyncio.TimeoutError:
            self._learn_error = True
        finally:
            remove_listener()
            # Manually trigger the flow to advance (critical for OptionsFlows!)
            self.hass.async_create_task(
                self.hass.config_entries.options.async_configure(flow_id=self.flow_id)
            )

    async def async_step_learn_progress(self, user_input=None):
        """Handle completion of the learn task."""
        if getattr(self, "_learn_error", False):
            return self.async_show_progress_done(next_step_id="learn_timeout")
        return self.async_show_progress_done(next_step_id="learn_success")

    async def async_step_learn_timeout(self, user_input=None):
        """Show timeout error."""
        if user_input is not None:
            return await self.async_step_init()
            
        return self.async_show_form(
            step_id="learn_timeout",
            description_placeholders={"error": "No RF code received within 30 seconds."},
        )

    async def async_step_learn_success(self, user_input=None):
        """Show success and save code."""
        if user_input is not None:
            new_data = dict(self.config_entry.options)
            
            if getattr(self, "_learn_entity", None) is None and hasattr(self, "_new_button_name"):
                # We are creating a NEW button from the rapid-fire wizard
                buttons = dict(new_data.get("buttons", {}))
                name = self._new_button_name
                import re
                slug = re.sub(r'[^a-z0-9_]+', '_', name.lower()).strip('_')
                buttons[slug] = {
                    "name": name,
                    "code": self._learned_data.get("code", ""),
                    "protocol": self._learned_data.get("protocol", ""),
                    "pulse_length": self._learned_data.get("pulse_length", ""),
                }
                new_data["buttons"] = buttons
                self.hass.config_entries.async_update_entry(self.config_entry, options=new_data)
                return await self.async_step_add_another()
            else:
                # We are updating an EXISTING entity from the Learn RF Code menu
                entity_id = getattr(self, "_learn_entity", "")
                if entity_id:
                    domain = entity_id.split('_')[0]
                    slug = entity_id[len(domain)+1:]
                    
                    if domain == "btn":
                        entities = dict(new_data.get("buttons", {}))
                        if slug in entities:
                            entities[slug]["code"] = self._learned_data.get("code", "")
                            entities[slug]["protocol"] = self._learned_data.get("protocol", "")
                            entities[slug]["pulse_length"] = self._learned_data.get("pulse_length", "")
                        new_data["buttons"] = entities
                    elif domain == "sens":
                        entities = dict(new_data.get("sensors", {}))
                        if slug in entities:
                            entities[slug]["state_on_code"] = self._learned_data.get("code", "")
                        new_data["sensors"] = entities
                        
                self.hass.config_entries.async_update_entry(self.config_entry, options=new_data)
                return self.async_create_entry(title="", data=dict(self.config_entry.options))

        code_str = self._learned_data.get("code", "Unknown")
        protocol_str = self._learned_data.get("protocol", "Unknown")
        return self.async_show_form(
            step_id="learn_success",
            description_placeholders={"code": code_str, "protocol": protocol_str},
        )

    async def async_step_add_button(self, user_input=None):
        """Add a new button entity."""
        if user_input is not None:
            name = user_input["name"]
            code = user_input.get("code", "")
            
            # Store in memory temporarily
            self._new_button_name = name
            
            if user_input.get("learn_code_now", not bool(code)):
                self._learn_entity = None # Signals that we are creating a new button, not updating an existing one
                self._learn_task = self.hass.async_create_task(
                    self._async_listen_for_rf_code()
                )
                return self.async_show_progress(
                    step_id="learn_progress",
                    progress_action="listening_for_rf",
                )
            else:
                new_data = dict(self.config_entry.options)
                buttons = dict(new_data.get(CONF_BUTTONS, {}))
                
                # Create slug
                import re
                slug = re.sub(r'[^a-z0-9_]+', '_', name.lower()).strip('_')
                
                buttons[slug] = {
                    "name": name,
                    "code": code,
                    "protocol": "",
                    "pulse_length": "",
                }
                new_data[CONF_BUTTONS] = buttons
                self.hass.config_entries.async_update_entry(self.config_entry, options=new_data)
                
                return await self.async_step_add_another()

        return self.async_show_form(
            step_id="add_button",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Optional("code"): str,
                vol.Optional("learn_code_now", default=True): bool,
            })
        )

    async def async_step_add_another(self, user_input=None):
        """Ask if user wants to add another button."""
        if user_input is not None:
            if user_input["next_action"] == "Add Another Button":
                return await self.async_step_add_button()
            else:
                return self.async_create_entry(title="", data=dict(self.config_entry.options))
                
        return self.async_show_form(
            step_id="add_another",
            data_schema=vol.Schema({
                vol.Required("next_action", default="Add Another Button"): vol.In(["Add Another Button", "Finish and Close"])
            })
        )

    async def async_step_add_sensor(self, user_input=None):
        """Add a new sensor or binary sensor entity configuration."""
        errors = {}
        if user_input is not None:
            name = user_input[CONF_SENSOR_NAME]
            slug = slugify(name)
            
            sensors = dict(self.config_entry.options.get(CONF_SENSORS, {}))
            
            sensors[slug] = {
                CONF_SENSOR_NAME: name,
                CONF_SENSOR_TYPE: user_input[CONF_SENSOR_TYPE],
                CONF_SENSOR_STATE_ON_CODE: user_input.get(CONF_SENSOR_STATE_ON_CODE, ""),
                CONF_SENSOR_STATE_OFF_CODE: user_input.get(CONF_SENSOR_STATE_OFF_CODE, ""),
                CONF_SENSOR_AUTO_OFF_SEC: user_input.get(CONF_SENSOR_AUTO_OFF_SEC, 0),
            }
            
            new_options = dict(self.config_entry.options)
            new_options[CONF_SENSORS] = sensors
            
            return self.async_create_entry(title="", data=new_options)

        types = {
            "binary": "Binary Sensor (ON/OFF)",
            "sensor": "State Sensor (Receives RF value/state)",
        }

        schema = vol.Schema({
            vol.Required(CONF_SENSOR_NAME): str,
            vol.Required(CONF_SENSOR_TYPE): vol.In(types),
            vol.Optional(CONF_SENSOR_STATE_ON_CODE): str,
            vol.Optional(CONF_SENSOR_STATE_OFF_CODE): str,
            vol.Optional(CONF_SENSOR_AUTO_OFF_SEC, default=0): int,
        })

        return self.async_show_form(
            step_id="add_sensor",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_delete_entity(self, user_input=None):
        """Remove a button or sensor entity configuration."""
        errors = {}
        
        buttons = self.config_entry.options.get(CONF_BUTTONS, {})
        sensors = self.config_entry.options.get(CONF_SENSORS, {})
        
        entities = {}
        for slug, config in buttons.items():
            entities[f"btn_{slug}"] = f"Button: {config[CONF_BUTTON_NAME]}"
        for slug, config in sensors.items():
            entities[f"sens_{slug}"] = f"Sensor: {config[CONF_SENSOR_NAME]} ({config[CONF_SENSOR_TYPE]})"

        if not entities:
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({}),
                errors={"base": "no_entities_to_delete"},
            )

        if user_input is not None:
            selected = user_input["entity_id"]
            new_options = dict(self.config_entry.options)
            
            if selected.startswith("btn_"):
                slug = selected[4:]
                btn_dict = dict(new_options.get(CONF_BUTTONS, {}))
                btn_dict.pop(slug, None)
                new_options[CONF_BUTTONS] = btn_dict
            elif selected.startswith("sens_"):
                slug = selected[5:]
                sens_dict = dict(new_options.get(CONF_SENSORS, {}))
                sens_dict.pop(slug, None)
                new_options[CONF_SENSORS] = sens_dict
                
            return self.async_create_entry(title="", data=new_options)

        schema = vol.Schema({
            vol.Required("entity_id"): vol.In(entities),
        })

        return self.async_show_form(
            step_id="delete_entity",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_edit_transceiver(self, user_input=None):
        """Modify transceiver parameters."""
        errors = {}
        if user_input is not None:
            if user_input["bridge_service"] == "Custom":
                self.edit_retries = user_input.get("tx_retries", 3)
                self.edit_delay = user_input.get("tx_delay_ms", 15)
                return await self.async_step_custom_options()
                
            new_data = dict(self.config_entry.data)
            new_data.update({
                "tx_service": user_input["bridge_service"],
                "rx_event": "esphome.rf_code_received",
                "tx_retries": user_input.get("tx_retries", 3),
                "tx_delay_ms": user_input.get("tx_delay_ms", 15),
            })
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data=dict(self.config_entry.options))

        esphome_services = self.hass.services.async_services().get("esphome", {})
        bridges = []
        for service_name in esphome_services:
            if service_name.endswith("_send_raw_rf"):
                bridges.append(f"esphome.{service_name}")
                
        current_tx = self.config_entry.data.get("tx_service")
        if current_tx not in bridges:
            bridges.append("Custom")
            default_bridge = "Custom"
        else:
            bridges.append("Custom")
            default_bridge = current_tx

        return self.async_show_form(
            step_id="edit_transceiver",
            data_schema=vol.Schema({
                vol.Required("bridge_service", default=default_bridge): vol.In(bridges),
                vol.Optional("tx_retries", default=self.config_entry.data.get("tx_retries", 3)): int,
                vol.Optional("tx_delay_ms", default=self.config_entry.data.get("tx_delay_ms", 15)): int,
            }),
            errors=errors,
        )

    async def async_step_custom_options(self, user_input=None):
        if user_input is not None:
            new_data = dict(self.config_entry.data)
            new_data.update({
                "tx_service": user_input["tx_service"],
                "rx_event": user_input["rx_event"],
                "tx_retries": getattr(self, "edit_retries", 3),
                "tx_delay_ms": getattr(self, "edit_delay", 15),
            })
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data=dict(self.config_entry.options))

        return self.async_show_form(
            step_id="custom_options",
            data_schema=vol.Schema({
                vol.Required("tx_service", default=self.config_entry.data.get("tx_service", "")): str,
                vol.Required("rx_event", default=self.config_entry.data.get("rx_event", "esphome.rf_code_received")): str,
            })
        )