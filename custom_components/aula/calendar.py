"""Calendar."""
from datetime import datetime, timedelta
import json
import logging

from homeassistant import config_entries, core
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle

from .client import Client
from .const import CONF_SCHOOLSCHEDULE, DOMAIN

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Async setup."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    if config_entry.options:
        config.update(config_entry.options)
    if config[CONF_SCHOOLSCHEDULE] is not True:
        return True
    client: Client = hass.data[DOMAIN]["client"]
    calendar_devices = []
    calendar = []
    for _i, child in enumerate(client.children):
        childid = child["id"]
        name = child["name"]
        calendar_devices.append(CalendarDevice(hass, calendar, name, childid))
    async_add_entities(calendar_devices)


class CalendarDevice(CalendarEntity):
    """Calendar."""

    def __init__(self, hass: HomeAssistant, calendar, name, childid) -> None:
        """Init."""
        self.data = CalendarData(hass, calendar, childid)
        self._cal_data = {}
        self._name = "Skoleskema " + name
        self._childid = childid

    @property
    def event(self):
        """Return the next upcoming event."""
        return self.data.event

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def unique_id(self):
        """Uniqueid."""
        unique_id = "aulacalendar" + str(self._childid)
        _LOGGER.debug(f"Unique ID for calendar {str(self._childid)} {unique_id}")  # noqa: G004
        return unique_id

    def update(self):
        """Update all Calendars."""
        self.data.update()

    async def async_get_events(self, hass: HomeAssistant, start_date, end_date):
        """Get all events in a specific time frame."""
        return await self.data.async_get_events(hass, start_date, end_date)


class CalendarData:
    """CalendarData."""

    def __init__(self, hass: HomeAssistant, calendar, childid) -> None:
        """Init."""
        self.event = None

        self._hass = hass
        self._calendar = calendar
        self._childid = childid

        self.all_events = []
        self._client = hass.data[DOMAIN]["client"]

    def parseCalendarData(self, i=None):
        """Parse data."""

        try:
            with open("skoleskema.json", encoding="utf-8") as openfile:
                _data = json.load(openfile)
            data = json.loads(_data)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.warning("Could not open and parse file skoleskema.json!")
            return False
        events = []
        _LOGGER.debug("Parsing skoleskema.json")
        for c in data["data"]:
            if c["type"] == "lesson" and c["belongsToProfiles"][0] == self._childid:
                summary = c["title"]
                start = datetime.strptime(c["startDateTime"], "%Y-%m-%dT%H:%M:%S%z")
                end = datetime.strptime(c["endDateTime"], "%Y-%m-%dT%H:%M:%S%z")
                vikar = 0
                for p in c["lesson"]["participants"]:
                    if p["participantRole"] == "substituteTeacher":
                        teacher = "VIKAR: " + p["teacherName"]
                        vikar = 1
                        break
                if vikar == 0:
                    try:
                        teacher = c["lesson"]["participants"][0]["teacherInitials"]
                    except Exception:  # pylint: disable=broad-except
                        try:
                            _LOGGER.debug(f"Lesson json dump {str(c["lesson"])}")  # noqa: G004
                            teacher = c["lesson"]["participants"][0]["teacherName"]
                        except Exception:  # pylint: disable=broad-except
                            _LOGGER.debug(
                                f"Could not find any teacher information for {summary} at {str(start)}"  # noqa: G004
                            )  # noqa: G004
                            teacher = ""
                event = CalendarEvent(
                    summary=summary + ", " + teacher,
                    start=start,
                    end=end,
                )
                events.append(event)
        return events

    async def async_get_events(self, hass: HomeAssistant, start_date, end_date):
        """Get events."""
        events = self.parseCalendarData()
        return events

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Update."""
        _LOGGER.debug("Updating calendars")
        self.parseCalendarData(self)
