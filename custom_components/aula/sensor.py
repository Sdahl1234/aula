"""Sensors."""
from datetime import datetime, timedelta
import json
import logging

import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import Client
from .const import CONF_SCHOOLSCHEDULE, CONF_UGEPLAN, DOMAIN

_LOGGER = logging.getLogger(__name__)


API_CALL_SERVICE_NAME = "api_call"
API_CALL_SCHEMA = vol.Schema(
    {
        vol.Required("uri"): cv.string,
        vol.Optional("post_data"): cv.string,
    }
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Async Setup sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]

    if config_entry.options:
        config.update(config_entry.options)
    # from .client import Client
    client = Client(
        config[CONF_USERNAME],
        config[CONF_PASSWORD],
        config[CONF_SCHOOLSCHEDULE],
        config[CONF_UGEPLAN],
    )
    hass.data[DOMAIN]["client"] = client

    async def async_update_data():
        client = hass.data[DOMAIN]["client"]
        await hass.async_add_executor_job(client.update_data)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sensor",
        update_method=async_update_data,
        update_interval=timedelta(minutes=5),
    )

    # Immediate refresh
    await coordinator.async_request_refresh()

    entities = []
    client = hass.data[DOMAIN]["client"]
    await hass.async_add_executor_job(client.update_data)
    for _i, child in enumerate(client.children):
        # _LOGGER.debug("Presence data for child "+str(child["id"])+" : "+str(client.presence[str(child["id"])]))
        if client.presence[str(child["id"])] == 1:
            if str(child["id"]) in client.daily_overview:
                _LOGGER.debug(
                    f"Found presence data for childid {str(child["id"])} adding sensor entity"  # noqa: G004
                )
                entities.append(AulaSensor(hass, coordinator, child))
        else:
            entities.append(AulaSensor(hass, coordinator, child))
    # We have data and can now set up the calendar platform:
    if config[CONF_SCHOOLSCHEDULE]:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, "calendar")
        )
    ####
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "binary_sensor")
    )
    ####

    global ugeplan  # noqa: PLW0603
    ugeplan = bool(config[CONF_UGEPLAN])
    async_add_entities(entities, update_before_add=True)

    def custom_api_call_service(call: ServiceCall) -> ServiceResponse:
        if "post_data" in call.data and len(call.data["post_data"]) > 0:
            data = client.custom_api_call(call.data["uri"], call.data["post_data"])
        else:
            data = client.custom_api_call(call.data["uri"], 0)
        return data

    hass.services.async_register(
        DOMAIN,
        API_CALL_SERVICE_NAME,
        custom_api_call_service,
        schema=API_CALL_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


class AulaSensor(Entity):
    """AulaSensor."""

    def __init__(self, hass: HomeAssistant, coordinator, child) -> None:
        """Init."""
        self._hass = hass
        self._coordinator = coordinator
        self._child = child
        self._client = hass.data[DOMAIN]["client"]

    @property
    def name(self):
        """Name."""
        childname = self._client.childnames_[self._child["id"]].split()[0]
        institution = self._client.institutions[self._child["id"]]
        return institution + " " + childname

    @property
    def state(self):
        """States."""
        # 0 = IKKE KOMMET
        # 1 = SYG
        # 2 = FERIE/FRI
        # 3 = KOMMET/TIL STEDE
        # 4 = PÅ TUR
        # 5 = SOVER
        # 8 = HENTET/GÅET
        if self._client.presence[str(self._child["id"])] == 1:
            states = [
                "Ikke kommet",
                "Syg",
                "Ferie/Fri",
                "Kommet/Til stede",
                "På tur",
                "Sover",
                "6",
                "7",
                "Gået",
                "9",
                "10",
                "11",
                "12",
                "13",
                "14",
                "15",
            ]
            daily_info = self._client.daily_overview[str(self._child["id"])]
            return states[daily_info["status"]]
        _LOGGER.debug(f"Setting state to n/a for child {str(self._child['id'])}")  # noqa: G004
        return "n/a"

    @property
    def extra_state_attributes(self):
        """Attr."""
        if self._client.presence[str(self._child["id"])] == 1:
            daily_info = self._client.daily_overview[str(self._child["id"])]
            try:
                profilePicture = daily_info["institutionProfile"]["profilePicture"][
                    "url"
                ]
            except Exception:  # pylint: disable=broad-except
                profilePicture = None

        fields = [
            "location",
            "sleepIntervals",
            "checkInTime",
            "checkOutTime",
            "activityType",
            "entryTime",
            "exitTime",
            "exitWith",
            "comment",
            "spareTimeActivity",
            "selfDeciderStartTime",
            "selfDeciderEndTime",
        ]
        attributes = {}
        # _LOGGER.debug("Dump of ugep_attr: "+str(self._client.ugep_attr))
        # _LOGGER.debug("Dump of ugepnext_attr: "+str(self._client.ugepnext_attr))
        if ugeplan:
            if "0030" in self._client.widgets:
                try:
                    name = self._child["name"].split()[0]
                    try:
                        opgaver = self._client.opg_attr[name]
                        attributes["opgaver"] = json.dumps(opgaver)
                    except Exception:  # pylint: disable=broad-except
                        attributes["Opgaver"] = "Not available"
                    try:
                        opgaver_next = self._client.opgnext_attr[name]
                        attributes["opgaver_next"] = json.dumps(opgaver_next)
                    except Exception:  # pylint: disable=broad-except
                        attributes["opgaver_next"] = "Not available"
                except Exception:  # pylint: disable=broad-except
                    attributes["Opgaver"] = "Not available"

            if "0062" in self._client.widgets:
                try:
                    attributes["huskelisten"] = self._client.huskeliste[
                        self._child["name"].split()[0]
                    ]
                except Exception:  # pylint: disable=broad-except
                    attributes["huskelisten"] = "Not available"
            try:
                attributes["ugeplan"] = self._client.ugep_attr[
                    self._child["name"].split()[0]
                ]
            except Exception:  # pylint: disable=broad-except
                attributes["ugeplan"] = "Not available"
            try:
                attributes["ugeplan_next"] = self._client.ugepnext_attr[
                    self._child["name"].split()[0]
                ]
            except Exception:  # pylint: disable=broad-except
                attributes["ugeplan_next"] = "Not available"
                _LOGGER.debug(
                    f"Could not get ugeplan for next week for child {str(self._child["name"].split()[0])}. Perhaps not available yet"  # noqa: G004
                )
        if self._client.presence[str(self._child["id"])] == 1:
            for attribute in fields:
                if attribute == "exitTime" and daily_info[attribute] == "23:59:00":
                    attributes[attribute] = None
                else:
                    try:
                        attributes[attribute] = datetime.strptime(
                            daily_info[attribute], "%H:%M:%S"
                        ).strftime("%H:%M")
                    except Exception:  # pylint: disable=broad-except
                        attributes[attribute] = daily_info[attribute]
            attributes["profilePicture"] = profilePicture
        return attributes

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def available(self):
        """Return if entity is available."""
        return self._coordinator.last_update_success

    @property
    def unique_id(self):
        """UniqueId."""
        unique_id = "aula" + str(self._child["id"])
        _LOGGER.debug(f"Unique ID for child {str(self._child["id"])} {unique_id}")  # noqa: G004
        return unique_id

    @property
    def icon(self):
        """Icon."""
        return "mdi:account-school"

    async def async_update(self):
        """Update the entity. Only used by the generic entity update service."""
        await self._coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )
