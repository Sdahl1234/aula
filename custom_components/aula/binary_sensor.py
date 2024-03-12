"""Binary sensor."""
from datetime import timedelta
import json

# from homeassistant.util import Throttle
import logging

from homeassistant import config_entries, core
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=300.0)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Async setup."""
    client = hass.data[DOMAIN]["client"]
    if client.unread_messages > 0:
        try:
            messages = json.dumps(client.message)
        except Exception:  # pylint: disable=broad-except
            messages = {}
    else:
        messages = {}

    sensors = []
    device = AulaBinarySensor(
        hass=hass, unread=client.unread_messages, messages=messages
    )
    sensors.append(device)
    async_add_entities(sensors, True)


class AulaBinarySensor(BinarySensorEntity, RestoreEntity):
    """BinarySensor."""

    _state: any
    _messages: any

    def __init__(self, hass: HomeAssistant, unread, messages) -> None:
        """Init."""
        self._hass = hass
        self._unread = unread
        self._messages = messages
        self._client = self._hass.data[DOMAIN]["client"]

    @property
    def extra_state_attributes(self):
        """Attributes."""
        attributes = {}
        attributes["messages"] = json.dumps(self._messages)
        attributes["friendly_name"] = "Aula message"
        return attributes

    @property
    def unique_id(self):
        """Unique id."""
        unique_id = "aulamessage"
        return unique_id

    @property
    def icon(self):
        """Icon."""
        return "mdi:email"

    @property
    def friendly_name(self):
        """Friendlyname."""
        return "Aula message"

    @property
    def is_on(self):
        """Icon."""
        if self._state == 1:
            return True
        if self._state == 0:
            return False

    def update(self):
        """Update."""
        if self._client.unread_messages > 0:
            _LOGGER.debug("There are unread message(s)")
            # _LOGGER.debug("Latest message: "+str(self._client.message))
            self._messages = self._client.message
            self._state = 1
        else:
            _LOGGER.debug("There are NO unread messages")
            self._state = 0
            self._messages = {}
