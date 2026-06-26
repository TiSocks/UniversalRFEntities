# Walkthrough: RF Entities Custom Integration

This walkthrough details the setup, configuration, and operation of the `rf_entities` integration inside Home Assistant.

---

## 1. Installation
To install the custom integration, copy the `custom_components/rf_entities` directory to your Home Assistant `config/custom_components` directory:

```bash
cp -r custom_components/rf_entities /path/to/your/homeassistant/config/custom_components/
```

After copying the files, restart Home Assistant to load the integration.

---

## 2. Configuration Flow (Adding a Virtual Device)
Once restarted, you can add virtual RF devices directly from the Home Assistant UI:

1. Navigate to **Settings** -> **Devices & Services** -> **Add Integration**.
2. Search for **RF Entities**.
3. Fill out the configuration form:
   - **Device Name**: Give the device a recognizable name (e.g., `Living Room Fan`).
   - **Transceiver Remote Entity**: Select your ESPHome transceiver remote entity (e.g., `remote.living_room_transceiver`) if available.
   - **Custom TX Service (Optional)**: If you are using custom service calls to transmit RF codes, type it here (default: `remote.send_command`).
   - **Receiver Event (Optional)**: If your ESPHome configuration fires a custom event type, specify it here (default: `esphome.rf_code_received`).
4. Click **Submit**. A new device is registered!

---

## 3. Options Flow (Managing Buttons & Sensors)
To add buttons (for transmission) or sensors (for state monitoring):

1. Go to **Settings** -> **Devices & Services** -> **RF Entities**.
2. Click **Configure** on the device entry you created.
3. Select an action from the menu:
   - **Add Button Entity**: Creates a button entity that, when clicked, transmits a specific RF code.
   - **Add Sensor Entity**: Creates a sensor or binary sensor (e.g., motion/door detector).
   - **Remove Entity**: Deletes an existing button/sensor entity from the device.
   - **Edit Transceiver Settings**: Updates the transceiver entity or service calls.

---

## 4. Learning RF Commands
The command learning feature enables mapping buttons and sensors to physical RF remote controls on the fly.

### Running the Learning Service
To program a button (e.g. `button.living_room_fan_speed_1`) or a sensor (e.g. `binary_sensor.living_room_fan_motion`):

1. Go to the **Developer Tools** -> **Services** tab in Home Assistant.
2. Select the service `rf_entities.learn_command`.
3. Select your target entity (e.g., `button.living_room_fan_speed_1`).
4. (Optional) Adjust the timeout duration.
5. Click **Call Service**.
6. A persistent notification will appear in your Home Assistant notification center showing that learning mode is active.
7. Press the button on your physical RF remote control.
8. The integration will intercept the incoming event, store the RF code (including protocol and pulse length), and save it.
9. A success notification will appear showing the captured code and protocol. The button entity is now fully programmed and ready to send commands!

---

## 5. ESPHome Configuration Template

For full functionality, your ESPHome-based 433MHz transceiver must be configured to forward received signals to Home Assistant as events. Using a **Universal Raw** setup is highly recommended as it makes the integration compatible with virtually any 433MHz device.

### Receiver (Filtering Noise & Forwarding Signals)
Ensure your ESPHome receiver fires the matching event and filters out background noise.

```yaml
remote_receiver:
  pin: GPIO2 
  dump: raw 
  on_raw:
    then:
      # Filter out random 433MHz static noise (only forward real commands)
      - if:
          condition:
            lambda: 'return x.size() > 20;'
          then:
            - homeassistant.event:
                event: esphome.rf_code_received
                data:
                  protocol: "raw"
                  code: !lambda |-
                    std::string res = "[";
                    for (size_t i = 0; i < x.size(); i++) {
                      res += std::to_string(x[i]);
                      if (i < x.size() - 1) res += ", ";
                    }
                    res += "]";
                    return res;
```

### Transmitter (Transmitting Raw Arrays)
Define a custom service that accepts integer arrays (`int[]`) and transmits them. Set the integration's **Custom TX Service** to `esphome.rfbridge433_send_raw_rf`.

```yaml
api:
  services:
    - service: send_raw_rf
      variables:
        code: int[] # Important: Name this 'code' so the integration maps it automatically!
      then:
        - repeat: 
            count: 15
            then:
              - remote_transmitter.transmit_raw:
                  code: !lambda 'return std::vector<int32_t>(code.begin(), code.end());'
              - delay: 15ms
```
