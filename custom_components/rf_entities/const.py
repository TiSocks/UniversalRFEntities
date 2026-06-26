"""Constants for the RF Entities integration."""

DOMAIN = "rf_entities"

# Configuration keys
CONF_TRANSCEIVER_ENTITY = "transceiver_entity"
CONF_TX_SERVICE = "tx_service"
CONF_TX_SERVICE_DATA_TEMPLATE = "tx_service_data_template"
CONF_RX_EVENT = "rx_event"

CONF_DEVICES = "devices"
CONF_DEVICE_NAME = "device_name"
CONF_BUTTONS = "buttons"
CONF_SENSORS = "sensors"

# Sub-config keys
CONF_BUTTON_NAME = "name"
CONF_BUTTON_CODE = "code"
CONF_BUTTON_PROTOCOL = "protocol"
CONF_BUTTON_PULSE_LENGTH = "pulse_length"

CONF_SENSOR_NAME = "name"
CONF_SENSOR_TYPE = "type"  # "binary" or "sensor"
CONF_SENSOR_STATE_ON_CODE = "state_on_code"
CONF_SENSOR_STATE_OFF_CODE = "state_off_code"
CONF_SENSOR_STATE_MATCHES = "state_matches"  # Dict of code -> state string
CONF_SENSOR_AUTO_OFF_SEC = "auto_off_sec"

# Default values
DEFAULT_RX_EVENT = "esphome.rf_code_received"
DEFAULT_TX_SERVICE = "remote.send_command"

# Services
SERVICE_LEARN_COMMAND = "learn_command"
ATTR_DEVICE_ENTRY_ID = "device_entry_id"
ATTR_TARGET_ENTITY = "target_entity"
ATTR_TIMEOUT = "timeout"

# Internal flags / events
LEARNING_TIMEOUT = 30
EVENT_LEARNED_CODE = "rf_entities_learned_code"
