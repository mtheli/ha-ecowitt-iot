"""Platform for sensor integration."""

import dataclasses
import re
from datetime import datetime
from typing import Final, Any
import logging
from wittiot import MultiSensorInfo, WittiotDataTypes, SubSensorname
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    DEGREE,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTime,
    UnitOfPower,
    UnitOfEnergy,
    UnitOfElectricPotential,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
    UnitOfElectricPotential,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
    UnitOfConductivity,
)

# Issue #79: HA Core 2026.8 弃用 CONCENTRATION_* 常量（2027.8 移除），
# 新版改用 UnitOfRatio/UnitOfDensity。两者字符串值相同（"ppm"/"µg/m³"），
# 不影响实体单位。此处提供兼容 shim：新版 HA 用新枚举，旧版回退旧常量。
try:
    from homeassistant.const import UnitOfDensity, UnitOfRatio

    CONCENTRATION_PARTS_PER_MILLION = UnitOfRatio.PARTS_PER_MILLION
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER = UnitOfDensity.MICROGRAMS_PER_CUBIC_METER
except ImportError:  # HA < 2026.8，旧常量仍可用
    from homeassistant.const import (
        CONCENTRATION_PARTS_PER_MILLION,
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    )
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN, SENSOR_ID_INVALID_VALUES
from .coordinator import EcowittDataUpdateCoordinator
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key="tempinf",
        translation_key="tempinf",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tempf",
        translation_key="tempf",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="feellike",
        translation_key="feellike",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="apparent",
        translation_key="apparent",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="dewpoint",
        translation_key="dewpoint",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tf_co2",
        translation_key="tf_co2",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="bgt",
        translation_key="bgt",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="wbgt",
        translation_key="wbgt",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidityin",
        translation_key="humidityin",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humi_co2",
        translation_key="humi_co2",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="baromrelin",
        translation_key="baromrelin",
        native_unit_of_measurement=UnitOfPressure.INHG,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="baromabsin",
        translation_key="baromabsin",
        native_unit_of_measurement=UnitOfPressure.INHG,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="vpd",
        translation_key="vpd",
        native_unit_of_measurement=UnitOfPressure.INHG,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    SensorEntityDescription(
        key="winddir",
        translation_key="winddir",
        icon="mdi:weather-windy",
        native_unit_of_measurement=DEGREE,
    ),
    SensorEntityDescription(
        key="winddir10",
        translation_key="winddir10",
        icon="mdi:weather-windy",
        native_unit_of_measurement=DEGREE,
    ),
    SensorEntityDescription(
        key="windspeedmph",
        translation_key="windspeedmph",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="windgustmph",
        translation_key="windgustmph",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="daywindmax",
        translation_key="daywindmax",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.MILES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="uv",
        translation_key="uv",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:brightness-5",
    ),
    SensorEntityDescription(
        key="solarradiation",
        translation_key="solarradiation",
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        device_class=SensorDeviceClass.IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="rainratein",
        translation_key="rainratein",
        native_unit_of_measurement=UnitOfVolumetricFlux.INCHES_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="eventrainin",
        translation_key="eventrainin",
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="dailyrainin",
        translation_key="dailyrainin",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="weeklyrainin",
        translation_key="weeklyrainin",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="monthlyrainin",
        translation_key="monthlyrainin",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="yearlyrainin",
        translation_key="yearlyrainin",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="totalrainin",
        translation_key="totalrainin",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="24hrainin",
        translation_key="24hrainin",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="rrain_piezo",
        translation_key="rrain_piezo",
        native_unit_of_measurement=UnitOfVolumetricFlux.INCHES_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="erain_piezo",
        translation_key="erain_piezo",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="drain_piezo",
        translation_key="drain_piezo",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="wrain_piezo",
        translation_key="wrain_piezo",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="mrain_piezo",
        translation_key="mrain_piezo",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="yrain_piezo",
        translation_key="yrain_piezo",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="train_piezo",
        translation_key="train_piezo",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="24hrain_piezo",
        translation_key="24hrain_piezo",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.INCHES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="co2in",
        translation_key="co2in",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co2",
        translation_key="co2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co2in_24h",
        translation_key="co2in_24h",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="co2_24h",
        translation_key="co2_24h",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm25_co2",
        translation_key="pm25_co2",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm25_aqi_co2",
        translation_key="pm25_aqi_co2",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm25_24h_co2",
        translation_key="pm25_24h_co2",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm10_co2",
        translation_key="pm10_co2",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm10_aqi_co2",
        translation_key="pm10_aqi_co2",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm10_24h_co2",
        translation_key="pm10_24h_co2",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm1_24h_co2_add",
        translation_key="pm1_24h_co2_add",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm4_24h_co2_add",
        translation_key="pm4_24h_co2_add",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm25_24h_co2_add",
        translation_key="pm25_24h_co2_add",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm10_24h_co2_add",
        translation_key="pm10_24h_co2_add",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="lightning",
        translation_key="lightning",
        icon="mdi:lightning-bolt",
        native_unit_of_measurement=UnitOfLength.MILES,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="lightning_time",
        translation_key="lightning_time",
        icon="mdi:lightning-bolt",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="lightning_num",
        translation_key="lightning_num",
        icon="mdi:lightning-bolt",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="con_batt",
        translation_key="con_batt",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="con_batt_volt",
        translation_key="con_batt_volt",
        icon="mdi:battery",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="con_ext_volt",
        translation_key="con_ext_volt",
        icon="mdi:battery",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="piezora_batt",
        translation_key="piezora_batt",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # SensorEntityDescription(
    #     key="srain_piezo",
    #     translation_key="srain_piezo",
    #     icon="mdi:weather-rainy",
    # ),
    SensorEntityDescription(
        key="pm1_co2",
        translation_key="pm1_co2",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm1_aqi_co2",
        translation_key="pm1_aqi_co2",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm1_24h_co2",
        translation_key="pm1_24h_co2",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm4_co2",
        translation_key="pm4_co2",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm4_aqi_co2",
        translation_key="pm4_aqi_co2",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pm4_24h_co2",
        translation_key="pm4_24h_co2",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

ECOWITT_SENSORS_MAPPING: Final = {
    WittiotDataTypes.TEMPERATURE: SensorEntityDescription(
        key="TEMPERATURE",
        native_unit_of_measurement="°F",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotDataTypes.HUMIDITY: SensorEntityDescription(
        key="HUMIDITY",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotDataTypes.MOISTURE: SensorEntityDescription(
        key="MOISTURE",
        device_class=SensorDeviceClass.MOISTURE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotDataTypes.PM25: SensorEntityDescription(
        key="PM25",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotDataTypes.AQI: SensorEntityDescription(
        key="AQI",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotDataTypes.LEAK: SensorEntityDescription(
        key="LEAK",
        icon="mdi:water-alert",
    ),
    WittiotDataTypes.BATTERY: SensorEntityDescription(
        key="BATTERY",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WittiotDataTypes.EC: SensorEntityDescription(
        key="EC",
        device_class=SensorDeviceClass.CONDUCTIVITY,
        native_unit_of_measurement=UnitOfConductivity.MICROSIEMENS_PER_CM,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotDataTypes.DISTANCE: SensorEntityDescription(
        key="DISTANCE",
        native_unit_of_measurement=UnitOfLength.FEET,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:arrow-expand-vertical",
    ),
    WittiotDataTypes.HEAT: SensorEntityDescription(
        key="HEAT",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    WittiotDataTypes.BATTERY_BINARY: SensorEntityDescription(
        key="BATTERY_BINARY",
        icon="mdi:battery",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    WittiotDataTypes.SIGNAL: SensorEntityDescription(
        key="SIGNAL",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:signal",
    ),
    WittiotDataTypes.RSSI: SensorEntityDescription(
        key="RSSI",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:wifi",
    ),
    # WQT01 水质检测仪参数（数据由 wittiot 库展开为 wqt01_* 扁平键）
    WittiotDataTypes.TOC: SensorEntityDescription(
        key="TOC",
        native_unit_of_measurement="mg/L",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:flask-outline",
    ),
    WittiotDataTypes.TURB: SensorEntityDescription(
        key="TURB",
        native_unit_of_measurement="NTU",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:waves",
    ),
    WittiotDataTypes.COD: SensorEntityDescription(
        key="COD",
        native_unit_of_measurement="mg/L",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:flask-outline",
    ),
    WittiotDataTypes.TDS: SensorEntityDescription(
        key="TDS",
        native_unit_of_measurement="mg/L",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:beaker-outline",
    ),
    WittiotDataTypes.CO2: SensorEntityDescription(
        key="CO2",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:molecule-co2",
    ),
    WittiotDataTypes.STATUS: SensorEntityDescription(
        key="STATUS",
        icon="mdi:alert-circle-outline",
    ),
}
# 定义 IoT 设备的传感器描述
IOT_SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key="iotbatt",
        translation_key="iotbatt",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="signal",
        translation_key="signal",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:signal",
    ),
    # SensorEntityDescription(
    #     key="rfnet_state",
    #     translation_key="rfnet_state",
    #     entity_category=EntityCategory.DIAGNOSTIC,
    # ),
    # SensorEntityDescription(
    #     key="iot_running",
    #     translation_key="iot_running",
    #     entity_category=EntityCategory.DIAGNOSTIC,
    # ),
    SensorEntityDescription(
        key="run_time",
        translation_key="run_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorEntityDescription(
        key="ver",
        translation_key="ver",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="wfc02_position",
        translation_key="wfc02_position",
        icon="mdi:valve",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="wfc02_flow_velocity",
        translation_key="wfc02_flow_velocity",
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
    ),
    SensorEntityDescription(
        key="velocity_total",
        translation_key="velocity_total",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
    ),
    SensorEntityDescription(
        key="flow_velocity",
        translation_key="flow_velocity",
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
    ),
    SensorEntityDescription(
        key="data_water_t",
        translation_key="data_water_t",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="data_ac_v",
        translation_key="data_ac_v",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    SensorEntityDescription(
        key="elect_total",
        translation_key="elect_total",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="realtime_power",
        translation_key="realtime_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
    ),
)


def async_remove_old_sub_device(hass: HomeAssistant) -> None:
    """删除旧的子设备"""

    device_reg = dr.async_get(hass)

    prefixes = SubSensorname.prefixes
    deviceid = []
    for dev in device_reg.devices.values():
        if not dev.identifiers:
            continue
        for identifier in dev.identifiers:
            if len(identifier) < 2:
                continue
            if isinstance(identifier[1], (str, list)):
                if [prefix for prefix in prefixes if prefix in identifier[1]]:
                    deviceid.append(dev.id)

    for oldsub in deviceid:
        device_reg.async_remove_device(oldsub)
        _LOGGER.debug("Old sub device %s removed successfully", oldsub)


def _is_channel_id_key(key: str) -> bool:
    """判断是否为通道型传感器的 sensor_id 键（如 Soilmoisture_ch1_id）."""
    return key.endswith("_id") and "_ch" in key


def _build_sensor_id_entities(
    coordinator: EcowittDataUpdateCoordinator, device_name: str
) -> tuple[list["SensorIdSensor"], set[str]]:
    """构建所有已存在 sensor_id 数据对应的诊断实体，返回 (实体列表, 已注册 key 集合)."""
    entities: list[SensorIdSensor] = []
    registered: set[str] = set()
    for sid_key in coordinator.data:
        if not _is_channel_id_key(sid_key):
            continue
        entities.append(SensorIdSensor(coordinator, device_name, sid_key))
        registered.add(sid_key)
    return entities, registered


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor entities based on a config entry."""
    async_remove_old_sub_device(hass)

    coordinator = hass.data[DOMAIN][entry.entry_id]
    registered_main: set[str] = set()
    async_add_entities(
        MainDevEcowittSensor(coordinator, entry.unique_id, desc)
        for desc in SENSOR_DESCRIPTIONS
        if desc.key in coordinator.data
    )
    for desc in SENSOR_DESCRIPTIONS:
        if desc.key in coordinator.data:
            registered_main.add(desc.key)
    # Subdevice Data
    subsensors: list[SubDevEcowittSensor] = []
    registered_sub: set[str] = set()
    for key in coordinator.data:
        if key in coordinator.api.sensor_info:
            if key in coordinator.api.sensor_info and coordinator.api.sensor_info[key][
                "data_type"
            ] in (WittiotDataTypes.LEAK, WittiotDataTypes.BATTERY_BINARY):
                continue
            mapping = ECOWITT_SENSORS_MAPPING[
                coordinator.api.sensor_info[key]["data_type"]
            ]
            description = dataclasses.replace(
                mapping,
                key=key,
                name=coordinator.api.sensor_info[key]["name"],
            )
            subsensors.append(
                SubDevEcowittSensor(
                    coordinator,
                    entry.unique_id,
                    coordinator.api.sensor_info[key]["dev_type"],
                    description,
                )
            )
            registered_sub.add(key)
    async_add_entities(subsensors)

    # 为每个通道型传感器创建独立的 sensor_id 诊断实体（方便在仪表盘/自动化中直接引用）
    sensor_id_entities, registered_sensor_id = _build_sensor_id_entities(
        coordinator, entry.unique_id
    )
    async_add_entities(sensor_id_entities)

    if "iot_list" in coordinator.data:
        iot_sensors: list[IotDeviceSensor] = []
        desc_map = {desc.key: desc for desc in IOT_SENSOR_DESCRIPTIONS}
        iot_data = coordinator.data["iot_list"]
        commands = iot_data["command"]
        registered_iot: set[str] = set()
        for i, item in enumerate(commands):
            nickname = item.get("nickname")
            if nickname is None:
                continue
            for key in list(item):
                if key in desc_map:
                    desc = desc_map[key]
                    device_desc = dataclasses.replace(
                        desc,
                        key=f"{nickname}_{desc.key}",
                        # name=f"{device_info.get('name', f'设备 {device_id}')} {desc.name}",
                    )
                    # 添加到实体列表
                    iot_sensors.append(
                        IotDeviceSensor(
                            coordinator=coordinator,
                            device_id=nickname,
                            description=device_desc,
                            unique_id=entry.unique_id,
                        )
                    )
                    # _LOGGER.info("%s : %s : %s", key, item[key], item["nickname"])
                    registered_iot.add(f"{nickname}_{desc.key}")
        async_add_entities(iot_sensors)
    else:
        registered_iot = set()

    async def _process_new_data() -> None:
        new_entities: list[SensorEntity] = []
        for desc in SENSOR_DESCRIPTIONS:
            if desc.key in coordinator.data and desc.key not in registered_main:
                new_entities.append(
                    MainDevEcowittSensor(coordinator, entry.unique_id, desc)
                )
                registered_main.add(desc.key)
        for key in coordinator.data:
            if key in coordinator.api.sensor_info:
                info = coordinator.api.sensor_info[key]
                if info["data_type"] in (
                    WittiotDataTypes.LEAK,
                    WittiotDataTypes.BATTERY_BINARY,
                ):
                    continue
                if key not in registered_sub:
                    mapping = ECOWITT_SENSORS_MAPPING[info["data_type"]]
                    description = dataclasses.replace(
                        mapping,
                        key=key,
                        name=info["name"],
                    )
                    new_entities.append(
                        SubDevEcowittSensor(
                            coordinator,
                            entry.unique_id,
                            info["dev_type"],
                            description,
                        )
                    )
                    registered_sub.add(key)
        # 动态创建新出现的 sensor_id 诊断实体
        for sid_key in coordinator.data:
            if not _is_channel_id_key(sid_key):
                continue
            if sid_key not in registered_sensor_id:
                new_entities.append(
                    SensorIdSensor(coordinator, entry.unique_id, sid_key)
                )
                registered_sensor_id.add(sid_key)
        if "iot_list" in coordinator.data:
            desc_map = {desc.key: desc for desc in IOT_SENSOR_DESCRIPTIONS}
            iot_data = coordinator.data["iot_list"]
            commands = iot_data["command"]
            for i, item in enumerate(commands):
                nickname = item.get("nickname")
                if nickname is None:
                    continue
                for key in list(item):
                    if key in desc_map:
                        desc = desc_map[key]
                        composed_key = f"{nickname}_{desc.key}"
                        if composed_key not in registered_iot:
                            device_desc = dataclasses.replace(
                                desc,
                                key=composed_key,
                            )
                            new_entities.append(
                                IotDeviceSensor(
                                    coordinator=coordinator,
                                    device_id=nickname,
                                    description=device_desc,
                                    unique_id=entry.unique_id,
                                )
                            )
                            registered_iot.add(composed_key)
        if new_entities:
            async_add_entities(new_entities)

    coordinator.async_add_listener(lambda: hass.async_create_task(_process_new_data()))


class MainDevEcowittSensor(
    CoordinatorEntity[EcowittDataUpdateCoordinator], SensorEntity
):
    """Define a Local sensor."""

    _attr_has_entity_name = True
    entity_description: SensorEntityDescription

    _TIMESTAMP_FORMATS = ["%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"]

    def __init__(
        self,
        coordinator: EcowittDataUpdateCoordinator,
        device_name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{device_name}")},
            manufacturer="Ecowitt",
            name=f"{device_name}",
            model=coordinator.data["ver"],
            configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}",
        )

        # adding mac address as connection info
        mac = coordinator.data["mac"]
        if mac:
            self._attr_device_info["connections"] = {
                (dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac))
            }

        self._attr_unique_id = f"{device_name}_{description.key}"
        self.entity_description = description

        self._my_tk = getattr(description, "translation_key", None)

    async def async_added_to_hass(self) -> None:
        """实体添加到HA时加载翻译名称."""
        await super().async_added_to_hass()
        if not self._my_tk:
            return
        from homeassistant.helpers.translation import async_get_translations
        lang = self.hass.config.language or "en"
        translations = await async_get_translations(self.hass, lang, "entity", [DOMAIN])
        key = f"component.{DOMAIN}.entity.sensor.{self._my_tk}.name"
        name = translations.get(key)
        if name:
            self._attr_name = name

    def _parse_timestamp(self, val: str) -> datetime | None:
        """Parse a timestamp string in known formats."""
        for fmt in self._TIMESTAMP_FORMATS:
            try:
                naive_dt = datetime.strptime(val, fmt)
                if naive_dt.year < 2000:
                    return None
                return dt_util.as_utc(naive_dt)
            except ValueError:
                continue
        return None

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the state."""
        val = self.coordinator.data.get(self.entity_description.key)
        if (
            self.entity_description.device_class == SensorDeviceClass.BATTERY
            and val == "DC"
        ):
            return 100
        if (
            self.entity_description.device_class == SensorDeviceClass.TIMESTAMP
            and isinstance(val, str)
        ):
            return self._parse_timestamp(val)
        return val

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.entity_description.key in self.coordinator.data

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity specific state attributes."""
        attrs = {}
        val = self.coordinator.data.get(self.entity_description.key)
        if (
            self.entity_description.device_class == SensorDeviceClass.BATTERY
            and val == "DC"
        ):
            attrs["power_source"] = "DC"
        last_seen = self.coordinator.data.get("_last_seen")
        if last_seen is not None:
            attrs["last_seen"] = last_seen
        return attrs or None

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        val = self.coordinator.data.get(self.entity_description.key)
        if self.entity_description.device_class == SensorDeviceClass.BATTERY:
            if val == "DC":
                return "mdi:power-plug"
            try:
                # 支持 20, 40, 60, 80, 100 阶梯动态图标
                level = int(val)
                if level <= 10:
                    return "mdi:battery-outline"
                if level <= 30:
                    return "mdi:battery-20"
                if level <= 50:
                    return "mdi:battery-40"
                if level <= 70:
                    return "mdi:battery-60"
                if level <= 90:
                    return "mdi:battery-80"
                return "mdi:battery"
            except (ValueError, TypeError):
                pass
        return super().icon


class SubDevEcowittSensor(
    CoordinatorEntity[EcowittDataUpdateCoordinator], SensorEntity
):
    """Define an Local sensor."""

    _attr_has_entity_name = True
    entity_description: SensorEntityDescription

    _TIMESTAMP_FORMATS = ["%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"]

    def __init__(
        self,
        coordinator: EcowittDataUpdateCoordinator,
        device_name: str,
        sensor_type: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{device_name}")},
            manufacturer="Ecowitt",
            name=f"{device_name}",
            model=coordinator.data["ver"],
            configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}",
        )
        
        # 保持旧的 unique_id 格式（基于通道号），确保向后兼容
        self._attr_unique_id = f"{device_name}_{description.key}"
        
        # 获取传感器唯一 ID 用于属性显示
        self._sensor_id = coordinator.data.get(f"{description.key}_id")
        
        self.entity_description = description

        # 子设备名称：设备自定义名称优先，否则用wittiot默认英文名
        info = coordinator.api.sensor_info.get(description.key, {})
        self._my_tk = info.get("translation_key", "")
        self._my_ch = ""
        if info.get("custom_name"):
            self.entity_description = dataclasses.replace(
                description,
                name=info["name"],
            )
        else:
            ch_match = re.match(
                r"(.+)_ch(\d+)(?:_(batt|signal|rssi))?$", description.key
            )
            if ch_match:
                self._my_ch = ch_match.group(2)

    async def async_added_to_hass(self) -> None:
        """子设备：加载翻译名称并拼接通道号."""
        await super().async_added_to_hass()
        if not self._my_tk:
            return
        from homeassistant.helpers.translation import async_get_translations
        lang = self.hass.config.language or "en"
        translations = await async_get_translations(self.hass, lang, "entity", [DOMAIN])
        key = f"component.{DOMAIN}.entity.sensor.{self._my_tk}.name"
        name = translations.get(key)
        if name:
            self._attr_name = f"{name} CH{self._my_ch}" if self._my_ch else name

    def _parse_timestamp(self, val: str) -> datetime | None:
        """Parse a timestamp string in known formats."""
        for fmt in self._TIMESTAMP_FORMATS:
            try:
                naive_dt = datetime.strptime(val, fmt)
                if naive_dt.year < 2000:
                    return None
                return dt_util.as_utc(naive_dt)
            except ValueError:
                continue
        return None

    @property
    def native_value(self) -> str | int | float | datetime | None:
        """Return the state."""
        val = self.coordinator.data.get(self.entity_description.key)
        if (
            self.entity_description.device_class == SensorDeviceClass.BATTERY
            and val == "DC"
        ):
            return 100
        if (
            self.entity_description.device_class == SensorDeviceClass.TIMESTAMP
            and isinstance(val, str)
        ):
            return self._parse_timestamp(val)
        return val

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.entity_description.key in self.coordinator.data

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity specific state attributes."""
        attrs = {}
        val = self.coordinator.data.get(self.entity_description.key)
        if (
            self.entity_description.device_class == SensorDeviceClass.BATTERY
            and val == "DC"
        ):
            attrs["power_source"] = "DC"
        last_seen = self.coordinator.data.get("_last_seen")
        if last_seen is not None:
            attrs["last_seen"] = last_seen
        # 添加传感器唯一 ID（如果可用）
        if (
            self._sensor_id
            and str(self._sensor_id).upper() not in SENSOR_ID_INVALID_VALUES
        ):
            attrs["sensor_id"] = self._sensor_id
        return attrs or None

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        val = self.coordinator.data.get(self.entity_description.key)
        if self.entity_description.device_class == SensorDeviceClass.BATTERY:
            if val == "DC":
                return "mdi:power-plug"
            try:
                # 支持 20, 40, 60, 80, 100 阶梯动态图标
                level = int(val)
                if level <= 10:
                    return "mdi:battery-outline"
                if level <= 30:
                    return "mdi:battery-20"
                if level <= 50:
                    return "mdi:battery-40"
                if level <= 70:
                    return "mdi:battery-60"
                if level <= 90:
                    return "mdi:battery-80"
                return "mdi:battery"
            except (ValueError, TypeError):
                pass
        return super().icon


class SensorIdSensor(
    CoordinatorEntity[EcowittDataUpdateCoordinator], SensorEntity
):
    """用于显示传感器物理唯一 ID 的诊断实体（独立实体，便于仪表盘/自动化引用）."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:identifier"

    def __init__(
        self,
        coordinator: EcowittDataUpdateCoordinator,
        device_name: str,
        id_key: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        # id_key 形如 Soilmoisture_ch1_id
        channel_key = id_key[:-3]  # 去掉 "_id"
        self._id_key = id_key

        # 从通道号提取传感器类型，用于命名
        ch_match = re.match(r"(.+)_ch(\d+)$", channel_key)
        self._base_name = ch_match.group(1) if ch_match else channel_key
        self._my_ch = ch_match.group(2) if ch_match else ""

        # 复用对应数据实体的翻译键（如 soil/temph 等），保证名称一致可识别
        info = coordinator.api.sensor_info.get(channel_key, {})
        self._my_tk = info.get("translation_key", "")

        # 兜底名称：当 sensor_info 无该通道键（如合成键 lds_ch1）时，
        # 从同基名的任意条目提取 dev_type（如 "CH1 Lds" -> "Lds"）
        self._fallback_name = ""
        if not self._my_tk:
            for k, v in coordinator.api.sensor_info.items():
                if k.startswith(self._base_name + "_ch"):
                    dev_type = v.get("dev_type", "")
                    if dev_type:
                        # 去掉通道前缀，如 "CH1 Lds" -> "Lds"
                        self._fallback_name = re.sub(
                            r"^CH\d+\s*", "", dev_type
                        )
                        break
            if not self._fallback_name:
                self._fallback_name = self._base_name.upper()

        self._attr_unique_id = f"{device_name}_{id_key}"
        self.entity_description = SensorEntityDescription(
            key=id_key,
            name=f"{self._fallback_name or self._base_name} Sensor ID",
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{device_name}")},
            manufacturer="Ecowitt",
            name=f"{device_name}",
            model=coordinator.data.get("ver", ""),
            configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}",
        )

    async def async_added_to_hass(self) -> None:
        """实体添加到HA时，加载翻译名称并拼接通道号，避免所有通道同名."""
        await super().async_added_to_hass()
        base_name = self._fallback_name or self._base_name
        if self._my_tk:
            from homeassistant.helpers.translation import async_get_translations
            lang = self.hass.config.language or "en"
            translations = await async_get_translations(self.hass, lang, "entity", [DOMAIN])
            key = f"component.{DOMAIN}.entity.sensor.{self._my_tk}.name"
            name = translations.get(key)
            if name:
                base_name = name
        # 名称 = "Soil" + " Sensor ID" + " CH1"
        self._attr_name = f"{base_name} Sensor ID"
        if self._my_ch:
            self._attr_name = f"{self._attr_name} CH{self._my_ch}"

    @property
    def native_value(self) -> str | None:
        """返回传感器物理 ID."""
        val = self.coordinator.data.get(self._id_key)
        if val is None:
            return None
        return str(val)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        val = self.coordinator.data.get(self._id_key)
        if not super().available or self._id_key not in self.coordinator.data or val is None:
            return False
        return str(val).upper() not in SENSOR_ID_INVALID_VALUES

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity specific state attributes."""
        return None


class IotDeviceSensor(CoordinatorEntity, SensorEntity):
    """表示 IoT 设备的传感器实体"""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EcowittDataUpdateCoordinator,
        device_id: str,
        description: SensorEntityDescription,
        unique_id: str,
    ) -> None:
        """初始化 IoT 设备传感器"""
        super().__init__(coordinator)
        self.device_id = device_id
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

        # 设置设备信息
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{device_id}")},
            name=f"{device_id}",
            manufacturer="Ecowitt",
            model=coordinator.data["ver"],
            configuration_url=f"http://{coordinator.config_entry.data[CONF_HOST]}",
            via_device=(DOMAIN, unique_id),
        )

    @property
    def native_value(self) -> str | int | float | None:
        """获取传感器值"""
        # # 从协调器获取设备数据
        val = None
        if "iot_list" in self.coordinator.data:
            iot_data = self.coordinator.data["iot_list"]
            commands = iot_data["command"]
            for i, item in enumerate(commands):
                nickname = item.get("nickname")
                if nickname is None:
                    continue
                if nickname == self.device_id:
                    key = self.entity_description.key.split("_", 1)[1]
                    val = item.get(key, None)
                    break

        if (
            self.entity_description.device_class == SensorDeviceClass.BATTERY
            and val == "DC"
        ):
            return 100
        return val

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return entity specific state attributes."""
        attrs = {}
        val = None
        if "iot_list" in self.coordinator.data:
            iot_data = self.coordinator.data["iot_list"]
            commands = iot_data["command"]
            for i, item in enumerate(commands):
                nickname = item.get("nickname")
                if nickname is None:
                    continue
                if nickname == self.device_id:
                    key = self.entity_description.key.split("_", 1)[1]
                    val = item.get(key, None)
                    break

        if (
            self.entity_description.device_class == SensorDeviceClass.BATTERY
            and val == "DC"
        ):
            attrs["power_source"] = "DC"
        last_seen = self.coordinator.data.get("_last_seen")
        if last_seen is not None:
            attrs["last_seen"] = last_seen
        return attrs or None

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        val = None
        if "iot_list" in self.coordinator.data:
            iot_data = self.coordinator.data["iot_list"]
            commands = iot_data["command"]
            for i, item in enumerate(commands):
                nickname = item.get("nickname")
                if nickname is None:
                    continue
                if nickname == self.device_id:
                    key = self.entity_description.key.split("_", 1)[1]
                    val = item.get(key, None)
                    break

        if self.entity_description.device_class == SensorDeviceClass.BATTERY:
            if val == "DC":
                return "mdi:power-plug"
            try:
                # 支持 20, 40, 60, 80, 100 阶梯动态图标
                level = int(val)
                if level <= 10:
                    return "mdi:battery-outline"
                if level <= 30:
                    return "mdi:battery-20"
                if level <= 50:
                    return "mdi:battery-40"
                if level <= 70:
                    return "mdi:battery-60"
                if level <= 90:
                    return "mdi:battery-80"
                return "mdi:battery"
            except (ValueError, TypeError):
                pass
        return super().icon
