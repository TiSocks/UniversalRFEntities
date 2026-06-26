import json
import re

# Update en.json
with open("custom_components/rf_entities/translations/en.json", "r") as f:
    trans = json.load(f)

# Reorder options and fix text
trans["options"]["step"]["init"]["data"]["action"] = "Select Action"
trans["options"]["step"]["init"]["description"] = "Choose an action to manage this RF device's buttons and sensors."

trans["options"]["step"]["add_button"] = {
    "title": "Add Button",
    "description": "Create a new button entity.",
    "data": {
        "name": "Button Name",
        "code": "RF Code (Leave blank to auto-learn)",
        "learn_code_now": "Learn RF Code Now"
    }
}
trans["options"]["step"]["add_another"] = {
    "title": "Button Created!",
    "description": "Your button has been successfully created. Would you like to add another one?",
    "data": {
        "next_action": "Next Action"
    }
}
trans["options"]["step"]["learn_success"]["description"] = "Captured Code: {code}\nProtocol: {protocol}\n\nClick Submit to save."

with open("custom_components/rf_entities/translations/en.json", "w") as f:
    json.dump(trans, f, indent=2)

# Read config_flow.py
with open("custom_components/rf_entities/config_flow.py", "r") as f:
    flow = f.read()

# Replace async_step_init
init_replace = """
    async def async_step_init(self, user_input=None):
        \"\"\"Manage the options.\"\"\"
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

        actions = [
            "add_button",
            "add_sensor",
            "delete_entity",
            "learn_command",
            "edit_transceiver",
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action", default="add_button"): vol.In(actions)
            })
        )
"""
flow = re.sub(r'    async def async_step_init.*?    async def async_step_add_button', init_replace.strip('\n') + '\n\n    async def async_step_add_button', flow, flags=re.DOTALL)

# Replace async_step_add_button
add_button_replace = """
    async def async_step_add_button(self, user_input=None):
        \"\"\"Add a new button entity.\"\"\"
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
        \"\"\"Ask if user wants to add another button.\"\"\"
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
"""
flow = re.sub(r'    async def async_step_add_button.*?    async def async_step_add_sensor', add_button_replace.strip('\n') + '\n\n    async def async_step_add_sensor', flow, flags=re.DOTALL)

# Update async_step_learn_success
learn_success_replace = """
    async def async_step_learn_success(self, user_input=None):
        \"\"\"Show success and save code.\"\"\"
        if user_input is not None:
            new_data = dict(self.config_entry.options)
            
            if getattr(self, "_learn_entity", None) is None and hasattr(self, "_new_button_name"):
                # We are creating a NEW button from the rapid-fire wizard
                buttons = dict(new_data.get(CONF_BUTTONS, {}))
                name = self._new_button_name
                import re
                slug = re.sub(r'[^a-z0-9_]+', '_', name.lower()).strip('_')
                buttons[slug] = {
                    "name": name,
                    "code": self._learned_data.get("code", ""),
                    "protocol": self._learned_data.get("protocol", ""),
                    "pulse_length": self._learned_data.get("pulse_length", ""),
                }
                new_data[CONF_BUTTONS] = buttons
                self.hass.config_entries.async_update_entry(self.config_entry, options=new_data)
                return await self.async_step_add_another()
            else:
                # We are updating an EXISTING entity from the Learn RF Code menu
                entity_id = self._learn_entity
                domain = entity_id.split('.')[0]
                slug = entity_id.split('.')[1]
                
                if domain == "button":
                    entities = dict(new_data.get(CONF_BUTTONS, {}))
                    if slug in entities:
                        entities[slug]["code"] = self._learned_data.get("code", "")
                        entities[slug]["protocol"] = self._learned_data.get("protocol", "")
                        entities[slug]["pulse_length"] = self._learned_data.get("pulse_length", "")
                    new_data[CONF_BUTTONS] = entities
                elif domain in ["sensor", "binary_sensor"]:
                    entities = dict(new_data.get(CONF_SENSORS, {}))
                    if slug in entities:
                        entities[slug]["state_on_code"] = self._learned_data.get("code", "")
                    new_data[CONF_SENSORS] = entities
                    
                self.hass.config_entries.async_update_entry(self.config_entry, options=new_data)
                return self.async_create_entry(title="", data=dict(self.config_entry.options))

        code_str = self._learned_data.get("code", "Unknown")
        protocol_str = self._learned_data.get("protocol", "Unknown")
        return self.async_show_form(
            step_id="learn_success",
            description_placeholders={"code": code_str, "protocol": protocol_str},
        )
"""
flow = re.sub(r'    async def async_step_learn_success.*?        return self.async_show_form\(.*?        \)', learn_success_replace.strip('\n'), flow, flags=re.DOTALL)

with open("custom_components/rf_entities/config_flow.py", "w") as f:
    f.write(flow)
