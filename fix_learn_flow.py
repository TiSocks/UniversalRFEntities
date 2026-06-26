import re

with open("custom_components/rf_entities/config_flow.py", "r") as f:
    flow = f.read()

learn_methods = """
    async def async_step_learn_command(self, user_input=None):
        \"\"\"Select an entity to learn a code for.\"\"\"
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
        \"\"\"Background task to listen for RF code.\"\"\"
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
"""

if "async def async_step_learn_command" not in flow:
    flow = flow.replace('    async def async_step_add_button', learn_methods.strip('\n') + '\n\n    async def async_step_add_button')
    with open("custom_components/rf_entities/config_flow.py", "w") as f:
        f.write(flow)

