# Universal RF Entities

A streamlined Home Assistant integration for easily managing RF-controlled devices. Built primarily to complement ESPHome-based RF Bridges (like Sonoff RF Bridge or custom ESP32 + CC1101 setups).

![HACS Valid](https://img.shields.io/badge/HACS-Custom-orange.svg)
![Version](https://img.shields.io/github/v/release/TiSocks/UniversalRFEntities)

## Features
- **Zero-Configuration Setup**: Automatically detects ESPHome bridges configured with the `_send_raw_rf` action pattern!
- **Rapid-Fire Learning Workflow**: Add your remotes instantly. Check "Learn RF Code Now" when adding a button, press the remote, and it's permanently saved to your button! Keep looping through to clone an entire remote in minutes.
- **Support for CC1101 / ESP32**: Don't want to buy an off-the-shelf RF Bridge? You can build an extremely powerful and long-range RF transceiver using a standard ESP32 development board wired to a cheap CC1101 module!

## Installation

### Via HACS (Recommended)
1. Open HACS in your Home Assistant instance.
2. Go to **Integrations** -> Click the 3 dots in the top right corner -> **Custom repositories**.
3. Add the URL of this repository: `https://github.com/TiSocks/UniversalRFEntities`
4. Select category: **Integration**.
5. Click **Add** and then install **Universal RF Entities**.
6. Restart Home Assistant!

### ESPHome Configuration
To use this integration, you need an RF transceiver running ESPHome. We have provided a complete example configuration in the `examples/` directory!

1. Open ESPHome and create a new device (e.g. `rfbridge433`).
2. Copy the contents of `examples/esphome_rfbridge433.yaml` into your ESPHome configuration.
3. This works natively with standard Sonoff RF Bridges, but you can also wire up a custom ESP32 and CC1101 module for exceptional range!
4. Install it to your ESP device.
5. In Home Assistant, add a new Integration -> "Universal RF Entities" and it will automatically detect your ESPHome bridge!

## Quick Start (Adding Devices)
1. Go to **Settings** -> **Devices & Services** -> **Universal RF Entities**.
2. Click **Configure** on your new device.
3. Select **Add Button Entity**.
4. Type a name (e.g., "Fan Speed 1") and leave the **Learn RF Code Now** box checked!
5. Press the button on your physical remote. The code will instantly register and save!
6. Click "Add Another Button" to rapidly clone all your remote keys!
