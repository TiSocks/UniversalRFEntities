import json

with open("custom_components/rf_entities/translations/en.json", "r") as f:
    trans = json.load(f)

trans["config"]["step"]["user"] = {
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

