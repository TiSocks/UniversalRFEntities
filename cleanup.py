import json

# 1. Cleanup __init__.py
with open("custom_components/rf_entities/__init__.py", "r") as f:
    content = f.read()

content = content.split('async def async_handle_learn_command')[0]

reg_code = """    # Register the learn_command service globally if not already registered
    if not hass.services.has_service(DOMAIN, SERVICE_LEARN_COMMAND):
        async def handle_learn_command(call: ServiceCall) -> None:
            await async_handle_learn_command(hass, call)

        hass.services.async_register(
            DOMAIN,
            SERVICE_LEARN_COMMAND,
            handle_learn_command,
            schema=LEARN_SERVICE_SCHEMA,
        )"""
content = content.replace(reg_code, "")

unreg_code = """        # If no entries are left, clean up service
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_LEARN_COMMAND)"""
content = content.replace(unreg_code, "")

with open("custom_components/rf_entities/__init__.py", "w") as f:
    f.write(content.strip() + "\n")

# 2. Add has_entity_name = True to platforms
for file in ["button.py", "sensor.py", "binary_sensor.py"]:
    with open(f"custom_components/rf_entities/{file}", "r") as f:
        c = f.read()
    c = c.replace("self._attr_unique_id = ", "self._attr_has_entity_name = True\n        self._attr_unique_id = ")
    with open(f"custom_components/rf_entities/{file}", "w") as f:
        f.write(c)

# 3. Update translations
with open("custom_components/rf_entities/translations/en.json", "r") as f:
    trans = json.load(f)

trans["options"]["step"]["learn_command"] = {
    "title": "Learn RF Code",
    "description": "Select the entity you want to program an RF code for.",
    "data": {
        "entity_id": "Target Entity"
    }
}
trans["options"]["step"]["learn_timeout"] = {
    "title": "Learning Timed Out",
    "description": "{error}"
}
trans["options"]["step"]["learn_success"] = {
    "title": "Successfully Learned RF Code!",
    "description": "Captured Code: {code}\nProtocol: {protocol}\n\nClick Submit to save this code to the entity."
}
trans["options"]["progress"] = {
    "listening_for_rf": "Please press the button on your physical RF remote now. Waiting for a signal..."
}

with open("custom_components/rf_entities/translations/en.json", "w") as f:
    json.dump(trans, f, indent=2)

