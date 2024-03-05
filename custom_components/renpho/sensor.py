"""Platform for sensor integration."""

from __future__ import annotations
import asyncio

from datetime import datetime

from .coordinator import create_coordinator

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import slugify
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_REFRESH,
    CONF_UNIT_OF_MEASUREMENT,
    DOMAIN,
    KG_TO_LBS,
    MASS_KILOGRAMS,
    MASS_POUNDS,
)
from .api_renpho import _LOGGER, RenphoWeight
from .sensor_configs import sensor_configurations

async def sensors_list(
    hass: HomeAssistant, config_entry: ConfigEntry, coordinator
) -> list[RenphoSensor]:
    """Return a list of sensors, initialized with the coordinator."""
    return [
        RenphoSensor(coordinator, **sensor, unit_of_measurement=hass.data[CONF_UNIT_OF_MEASUREMENT])
        for sensor in sensor_configurations
    ]



async def async_setup(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    sensor_entities = await sensors_list(hass, config_entry)
    async_add_entities(sensor_entities)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    # Create the coordinator
    coordinator = await create_coordinator(hass, hass.data[DOMAIN], config_entry)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    # Create sensor entities and pass them the coordinator
    sensor_entities = await sensors_list(hass, config_entry, coordinator)
    async_add_entities(sensor_entities)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
):
    """Set up the sensor platform asynchronously."""
    try:
        sensor_entities = await sensors_list(hass, discovery_info)
        async_add_entities(sensor_entities)
    except ConnectionError as ex:
        _LOGGER.error(f"Error: {ex}")
        return False


class RenphoSensor(SensorEntity):
    """Representation of a Renpho sensor."""

    def __init__(
        self,
        coordinator,
        id: str,
        name: str,
        unit: str,
        category: str,
        label: str,
        metric: str,
        unit_of_measurement: str,
    ) -> None:
        """Initialize the sensor with the coordinator."""
        self.coordinator = coordinator
        self._metric = metric
        self._id = id
        self._name = f"Renpho {name}"
        self._unit = unit
        self._category = category
        self._label = label
        self._unit_of_measurement = unit_of_measurement
        self._state = None

    @property
    def should_poll(self) -> bool:
        """Sensor should not poll for updates; it will receive updates from the coordinator."""
        return False

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def available(self):
        """Return if sensor is available."""
        return self.coordinator.last_update_success

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"renpho_{slugify(self._name)}"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            "timestamp": self._timestamp,
            "category": self._category,
            "label": self._label,
        }

    @property
    def extra_state_attributes(self):
        # Updated property name for HA compatibility
        return {
            "timestamp": self._timestamp,
            "category": self._category,
            "label": self._label,
        }

    @property
    def name(self) -> str:
        return self._name

    @property
    def category(self) -> str:
        """Return the category of the sensor."""
        return self._category

    @property
    def label(self) -> str:
        """Return the label of the sensor."""
        return self._label

    @property
    def unit_of_measurement(self) -> str:
        # Return the correct unit of measurement based on user configuration
        if self._unit_of_measurement == MASS_POUNDS and self._unit == MASS_KILOGRAMS:
            return MASS_POUNDS
        elif self._unit_of_measurement == MASS_KILOGRAMS and self._unit == MASS_KILOGRAMS:
            return MASS_KILOGRAMS
        elif self._unit_of_measurement == MASS_POUNDS and self._unit == MASS_POUNDS:
            return MASS_POUNDS
        elif self._unit_of_measurement == MASS_KILOGRAMS or MASS_POUNDS and self._unit != MASS_KILOGRAMS or MASS_POUNDS:
            return self._unit

    @property
    def unit(self) -> str:
        """Return the unit of the sensor."""
        if self._unit_of_measurement == MASS_POUNDS and self._unit == MASS_KILOGRAMS:
            return MASS_POUNDS
        elif self._unit_of_measurement == MASS_KILOGRAMS and self._unit == MASS_KILOGRAMS:
            return MASS_KILOGRAMS
        elif self._unit_of_measurement == MASS_POUNDS and self._unit == MASS_POUNDS:
            return MASS_POUNDS
        elif self._unit_of_measurement == MASS_KILOGRAMS or MASS_POUNDS and self._unit != MASS_KILOGRAMS or MASS_POUNDS:
            return self._unit

    @property
    async def state(self):
        """Return the current state of the sensor."""
        try:
            metric_value = await self.coordinator.get_specific_metric(
                metric_type=self._metric,
                metric=self._id,
                user_id=None
            )

            if metric_value is not None:
                if self._unit_of_measurement == MASS_POUNDS and self._unit == MASS_KILOGRAMS:
                    self._state = round(metric_value * KG_TO_LBS, 2)
                elif self._unit_of_measurement == MASS_KILOGRAMS and self._unit == MASS_KILOGRAMS:
                    self._state = round(metric_value, 2)
                else:
                    self._state = metric_value
                self._timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                _LOGGER.info(f"Successfully updated {self._name} for metric type {self._metric} with value {self._state} with unit {self._unit}")
            else:
                self._state = None  # You might choose to clear the state or leave it unchanged

        except (ConnectionError, TimeoutError) as e:
            _LOGGER.error(
                f"{type(e).__name__} occurred while updating {self._name} for metric type {self._metric}: {e}"
            )

        except Exception as e:
            _LOGGER.critical(
                f"An unexpected error occurred while updating {self._name} for metric type {self._metric}: {e}"
            )

    async def async_update_data(self):
        """Request an immediate update of the coordinator data."""
        await self.coordinator.async_request_refresh()
