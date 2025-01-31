import json
import os
from typing import Dict, Any

class SettingsManager:
    _instance = None
    _settings: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance._load_settings()
        return cls._instance

    def _load_settings(self):
        """Load settings from settings.json file."""
        settings_path = os.path.join(os.path.dirname(__file__), '..', '..', 'settings.json')
        try:
            with open(settings_path, 'r') as f:
                self._settings = json.load(f)
        except FileNotFoundError:
            print(f"Warning: settings.json not found at {settings_path}, using defaults")
            self._settings = {
                "websocket": {
                    "heartbeat_interval": 5,
                    "heartbeat_timeout": 10
                },
                "player": {
                    "cleanup_interval": 30,
                    "disconnect_timeout": 300
                }
            }

    def get_setting(self, *keys):
        """Get a setting value using dot notation."""
        value = self._settings
        for key in keys:
            value = value.get(key)
            if value is None:
                return None
        return value

# Create a global instance
settings = SettingsManager()