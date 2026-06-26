import re

with open("custom_components/rf_entities/config_flow.py", "r") as f:
    content = f.read()

# Add action to menu
content = content.replace('"add_button": "Add Button Entity",', '"learn_command": "Learn RF Code (Recommended)",\n            "add_button": "Add Button Entity",')

content = content.replace('if action == "add_button":', 'if action == "learn_command":\n                return await self.async_step_learn_command()\n            if action == "add_button":')

# Add new steps
new_methods = """
    async def async_step_learn_command(self, user_input=None):
        \"\"\"Select an entity to learn a code for.\"\"\"
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
                progress_task=self._learn_task,
            )

        return self.async_show_form(
            step_id="learn_command",
            data_schema=vol.Schema({
                vol.Required("entity_id"): vol.In(entities),
            }),
        )

    async def _async_listen_for_rf_code(self):
        \"\"\"Background task to listen for RF code.\"\"\"
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

    async def async_step_learn_progress(self, user_input=None):
        \"\"\"Handle completion of the learn task.\"\"\"
        if getattr(self, "_learn_error", False):
            return self.async_show_progress_done(next_step_id="learn_timeout")
        return self.async_show_progress_done(next_step_id="learn_success")

    async def async_step_learn_timeout(self, user_input=None):
        \"\"\"Show timeout error.\"\"\"
        if user_input is not None:
            return await self.async_step_init()
            
        return self.async_show_form(
            step_id="learn_timeout",
            description_placeholders={"error": "No RF code received within 30 seconds."},
        )

    async def async_step_learn_success(self, user_input=None):
        \"\"\"Show success and save code.\"\"\"
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
"""
content = content.replace("    async def async_step_add_button", new_methods + "\n    async def async_step_add_button")

with open("custom_components/rf_entities/config_flow.py", "w") as f:
    f.write(content)

