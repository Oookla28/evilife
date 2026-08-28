"""Stable contracts for native health-platform bridges and generic imports."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .lifestyle import ObservationCreate, ObservationRecord


ConnectorId = Literal[
    "apple_healthkit",
    "android_health_connect",
    "huawei_health_kit",
    "generic_import",
]


class HealthConnector(BaseModel):
    id: ConnectorId
    label: str
    status: Literal["requires_native_bridge", "requires_credentials", "available"]
    authorization: str
    transport: str
    docs_url: str
    supported_kinds: list[str]


class ConnectorObservation(BaseModel):
    external_id: str = Field(min_length=1, max_length=160)
    observation: ObservationCreate


class ConnectorIngestRequest(BaseModel):
    consent_receipt: str = Field(min_length=8, max_length=240)
    observations: list[ConnectorObservation] = Field(min_length=1, max_length=500)


class ConnectorIngestResponse(BaseModel):
    connector_id: ConnectorId
    accepted: int
    skipped: int
    records: list[ObservationRecord]


SUPPORTED_KINDS = [
    "water_ml",
    "steps",
    "sleep_minutes",
    "weight_kg",
    "waist_cm",
    "resting_heart_rate",
    "mood_score",
]

CONNECTORS = [
    HealthConnector(
        id="apple_healthkit",
        label="Apple 健康",
        status="requires_native_bridge",
        authorization="自动同步需要 iPhone 原生授权；网页可手动导入 Apple 健康 XML",
        transport="Apple 健康 XML 手动导入，或 iOS HealthKit 原生桥接",
        docs_url="https://developer.apple.com/documentation/healthkit",
        supported_kinds=SUPPORTED_KINDS,
    ),
    HealthConnector(
        id="android_health_connect",
        label="Android Health Connect",
        status="requires_native_bridge",
        authorization="需要用户在 Android 应用内授权读取范围",
        transport="Android Health Connect SDK → 服务端导入接口",
        docs_url="https://developer.android.com/health-and-fitness/health-connect",
        supported_kinds=SUPPORTED_KINDS,
    ),
    HealthConnector(
        id="huawei_health_kit",
        label="华为运动健康",
        status="requires_credentials",
        authorization="需要 Health Kit 开发者配置和用户授权",
        transport="华为 Health Kit 适配器 → 服务端导入接口",
        docs_url="https://developer.huawei.com/consumer/en/hms/huaweihealth/",
        supported_kinds=SUPPORTED_KINDS,
    ),
    HealthConnector(
        id="generic_import",
        label="通用数据导入",
        status="available",
        authorization="调用方必须提交用户同意回执",
        transport="HTTPS JSON 批量导入",
        docs_url="/docs#/default/ingest_health_observations_api_v1_health_connectors__connector_id__ingest_post",
        supported_kinds=SUPPORTED_KINDS,
    ),
]


def get_connector(connector_id: str) -> HealthConnector | None:
    return next((item for item in CONNECTORS if item.id == connector_id), None)
