import json

with open("custom_components/rf_entities/config_flow.py", "r") as f:
    content = f.read()

# Replace async_step_user
new_user_step = """    async def async_step_user(self, user_input=None):
        \"\"\"Handle the initial step.\"\"\"
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
        )"""

import re
content = re.sub(r'    async def async_step_user.*?    @staticmethod', new_user_step + '\n\n    @staticmethod', content, flags=re.DOTALL)

# Replace async_step_edit_transceiver
new_edit_step = """    async def async_step_edit_transceiver(self, user_input=None):
        \"\"\"Modify transceiver parameters.\"\"\"
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
        )"""

content = re.sub(r'    async def async_step_edit_transceiver.*', new_edit_step, content, flags=re.DOTALL)

with open("custom_components/rf_entities/config_flow.py", "w") as f:
    f.write(content)

# Update translations
with open("custom_components/rf_entities/translations/en.json", "r") as f:
    trans = json.load(f)

trans["step"]["user"] = {
    "title": "Create RF Device",
    "description": "Configure a new virtual RF device. The integration will auto-detect your ESPHome bridge if it uses the approved 'send_raw_rf' pattern.",
    "data": {
        "device_name": "Device Name",
        "bridge_service": "Detected ESPHome RF Bridge",
        "tx_service": "Custom TX Service (Optional)",
        "rx_event": "Receiver Event"
    }
}

trans["options"]["step"]["edit_transceiver"] = {
    "title": "Edit Transceiver",
    "description": "Update the RF transceiver bridge configuration.",
    "data": {
        "bridge_service": "Detected ESPHome RF Bridge",
        "tx_service": "Custom TX Service (Optional)",
        "rx_event": "Receiver Event"
    }
}

with open("custom_components/rf_entities/translations/en.json", "w") as f:
    json.dump(trans, f, indent=2)

