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
            tx_service = user_input.get("bridge_service") or user_input.get(CONF_TX_SERVICE)

            if not tx_service:
                errors["base"] = "missing_transceiver"
            elif "." not in tx_service:
                errors[CONF_TX_SERVICE] = "invalid_service"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_DEVICE_NAME],
                    data={
                        CONF_DEVICE_NAME: user_input[CONF_DEVICE_NAME],
                        CONF_TX_SERVICE: tx_service,
                        CONF_RX_EVENT: user_input.get(CONF_RX_EVENT) or DEFAULT_RX_EVENT,
                        CONF_TRANSCEIVER_ENTITY: "",
                    },
                    options={
                        CONF_BUTTONS: {},
                        CONF_SENSORS: {},
                    },
                )

        esphome_services = self.hass.services.async_services().get("esphome", {})
        bridges = []
        for service_name in esphome_services:
            if service_name.endswith("_send_raw_rf"):
                bridges.append(f"esphome.{service_name}")

        schema_fields = {
            vol.Required(CONF_DEVICE_NAME, default="Universal RF Entities"): str,
        }

        if bridges:
            schema_fields[vol.Optional("bridge_service", default=bridges[0])] = vol.In(bridges)
            schema_fields[vol.Optional(CONF_TX_SERVICE)] = str
        else:
            schema_fields[vol.Optional(CONF_TX_SERVICE, default="esphome.rfbridge433_send_raw_rf")] = str

        schema_fields.update({
            vol.Optional(CONF_RX_EVENT, default=DEFAULT_RX_EVENT): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema_fields),
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
        """Manage the options flow menu."""
        if user_input is not None:
            action = user_input["action"]
            if action == "learn_command":
                return await self.async_step_learn_command()
            if action == "add_button":
                return await self.async_step_add_button()
            if action == "add_sensor":
                return await self.async_step_add_sensor()
            if action == "delete_entity":
                return await self.async_step_delete_entity()
            if action == "edit_transceiver":
                return await self.async_step_edit_transceiver()

        actions = {
            "learn_command": "Learn RF Code (Recommended)",
            "add_button": "Add Button Entity",
            "add_sensor": "Add Sensor Entity",
            "delete_entity": "Remove Entity",
            "edit_transceiver": "Edit Transceiver Settings",
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In(actions),
            }),
        )


    async def async_step_learn_command(self, user_input=None):
        """Select an entity to learn a code for."""
        buttons = self.config_entry.options.get(CONF_BUTTONS, {})
        sensors = self.config_entry.options.get(CONF_SENSORS, {})
        
        entities = {}
        for slug, config in buttons.items():
            entities[f"btn_{slug}"] = f"Button: {config[CONF_BUTTON_NAME]}"
        for slug, config in sensors.items():
            entities[f"sens_{slug}"] = f"Sensor: {config[CONF_SENSOR_NAME]}"

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
        
        rx_event = self.config_entry.data.get(CONF_RX_EVENT, DEFAULT_RX_EVENT)

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
            new_options = dict(self.config_entry.options)
            code = self._learned_data.get("code")
            protocol = self._learned_data.get("protocol", "")
            pulse_length = self._learned_data.get("pulse_length", "")
            
            if self._learn_entity.startswith("btn_"):
                slug = self._learn_entity[4:]
                buttons = dict(new_options.get(CONF_BUTTONS, {}))
                btn = dict(buttons[slug])
                btn[CONF_BUTTON_CODE] = code
                if protocol: btn[CONF_BUTTON_PROTOCOL] = protocol
                if pulse_length: btn[CONF_BUTTON_PULSE_LENGTH] = pulse_length
                buttons[slug] = btn
                new_options[CONF_BUTTONS] = buttons
            else:
                slug = self._learn_entity[5:]
                sensors = dict(new_options.get(CONF_SENSORS, {}))
                sens = dict(sensors[slug])
                sens[CONF_SENSOR_STATE_ON_CODE] = code
                sensors[slug] = sens
                new_options[CONF_SENSORS] = sensors
                
            return self.async_create_entry(title="", data=new_options)

        return self.async_show_form(
            step_id="learn_success",
            description_placeholders={
                "code": self._learned_data.get("code", "Unknown"),
                "protocol": self._learned_data.get("protocol", "None"),
            },
        )

    async def async_step_add_button(self, user_input=None):
        """Add a new button entity configuration."""
        errors = {}
        if user_input is not None:
            name = user_input[CONF_BUTTON_NAME]
            slug = slugify(name)
            
            # Retrieve existing configuration
            buttons = dict(self.config_entry.options.get(CONF_BUTTONS, {}))
            
            buttons[slug] = {
                CONF_BUTTON_NAME: name,
                CONF_BUTTON_CODE: user_input.get(CONF_BUTTON_CODE, ""),
                CONF_BUTTON_PROTOCOL: user_input.get(CONF_BUTTON_PROTOCOL, ""),
                CONF_BUTTON_PULSE_LENGTH: user_input.get(CONF_BUTTON_PULSE_LENGTH, ""),
            }
            
            new_options = dict(self.config_entry.options)
            new_options[CONF_BUTTONS] = buttons
            
            return self.async_create_entry(title="", data=new_options)

        schema = vol.Schema({
            vol.Required(CONF_BUTTON_NAME): str,
            vol.Optional(CONF_BUTTON_CODE): str,
            vol.Optional(CONF_BUTTON_PROTOCOL): str,
            vol.Optional(CONF_BUTTON_PULSE_LENGTH): str,
        })

        return self.async_show_form(
            step_id="add_button",
            data_schema=schema,
            errors=errors,
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
            tx_service = user_input.get("bridge_service") or user_input.get(CONF_TX_SERVICE)
            new_data = dict(self.config_entry.data)
            new_data.update({
                CONF_TX_SERVICE: tx_service,
                CONF_RX_EVENT: user_input.get(CONF_RX_EVENT),
            })
            
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data=dict(self.config_entry.options))

        esphome_services = self.hass.services.async_services().get("esphome", {})
        bridges = []
        for service_name in esphome_services:
            if service_name.endswith("_send_raw_rf"):
                bridges.append(f"esphome.{service_name}")
        
        current_tx_service = self.config_entry.data.get(CONF_TX_SERVICE, DEFAULT_TX_SERVICE)
        current_rx_event = self.config_entry.data.get(CONF_RX_EVENT, DEFAULT_RX_EVENT)

        schema_fields = {}
        if bridges:
            default_bridge = current_tx_service if current_tx_service in bridges else bridges[0]
            schema_fields[vol.Optional("bridge_service", default=default_bridge)] = vol.In(bridges)
            
        schema_fields.update({
            vol.Optional(CONF_TX_SERVICE, default=current_tx_service if current_tx_service not in bridges else ""): str,
            vol.Optional(CONF_RX_EVENT, default=current_rx_event): str,
        })

        return self.async_show_form(
            step_id="edit_transceiver",
            data_schema=vol.Schema(schema_fields),
            errors=errors,
        )