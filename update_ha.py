import os
import json
import re

# 1. Update const.py
with open("custom_components/rf_entities/const.py", "a") as f:
    f.write('CONF_TX_RETRIES = "tx_retries"\n')
    f.write('CONF_TX_DELAY_MS = "tx_delay_ms"\n')
    f.write('DEFAULT_TX_RETRIES = 3\n')
    f.write('DEFAULT_TX_DELAY_MS = 15\n')

# 2. Update button.py
with open("custom_components/rf_entities/button.py", "r") as f:
    btn_content = f.read()

btn_insert = """
        if tx_service.startswith("esphome."):
            service_data["retries"] = self._transceiver_config.get("tx_retries", 3)
            service_data["delay_ms"] = self._transceiver_config.get("tx_delay_ms", 15)
"""
btn_content = btn_content.replace(
    '_LOGGER.info(\n            "Sending RF code',
    btn_insert.lstrip() + '\n        _LOGGER.info(\n            "Sending RF code'
)
with open("custom_components/rf_entities/button.py", "w") as f:
    f.write(btn_content)

# 3. Rewrite config_flow.py entirely for the new two-step logic
with open("custom_components/rf_entities/config_flow.py", "r") as f:
    flow = f.read()

new_user_flow = """
    async def async_step_user(self, user_input=None):
        \"\"\"Handle the initial step.\"\"\"
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
        \"\"\"Handle custom transceiver details.\"\"\"
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
"""
flow = re.sub(r'    async def async_step_user.*?    @staticmethod', new_user_flow.strip('\n') + '\n\n    @staticmethod', flow, flags=re.DOTALL)

new_edit_flow = """
    async def async_step_edit_transceiver(self, user_input=None):
        \"\"\"Modify transceiver parameters.\"\"\"
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
"""
flow = re.sub(r'    async def async_step_edit_transceiver.*', new_edit_flow.strip('\n'), flow, flags=re.DOTALL)

with open("custom_components/rf_entities/config_flow.py", "w") as f:
    f.write(flow)

# Update Translations
with open("custom_components/rf_entities/translations/en.json", "r") as f:
    trans = json.load(f)

trans["config"]["step"]["user"] = {
    "title": "Create RF Device",
    "description": "Configure a new virtual RF device. The integration will auto-detect your ESPHome bridge if it uses the approved 'send_raw_rf' pattern.",
    "data": {
        "device_name": "Device Name",
        "bridge_service": "Detected ESPHome RF Bridge",
        "tx_retries": "Transmission Retries",
        "tx_delay_ms": "Delay Between Retries (ms)"
    }
}
trans["config"]["step"]["custom"] = {
    "title": "Custom Configuration",
    "description": "Specify your custom transmission service and receiver event.",
    "data": {
        "tx_service": "Custom TX Service",
        "rx_event": "Receiver Event"
    }
}

trans["options"]["step"]["edit_transceiver"] = {
    "title": "Edit Transceiver",
    "description": "Update the RF transceiver bridge configuration.",
    "data": {
        "bridge_service": "Detected ESPHome RF Bridge",
        "tx_retries": "Transmission Retries",
        "tx_delay_ms": "Delay Between Retries (ms)"
    }
}
trans["options"]["step"]["custom_options"] = trans["config"]["step"]["custom"]

with open("custom_components/rf_entities/translations/en.json", "w") as f:
    json.dump(trans, f, indent=2)

