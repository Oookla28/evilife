from pathlib import Path

from app.apple_health_import import parse_apple_health_xml
from app.lifestyle import LifestyleStore


APPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData locale="zh_CN">
  <Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone" unit="count" value="100" startDate="2026-08-10 08:00:00 +0800" endDate="2026-08-10 09:00:00 +0800"/>
  <Record type="HKQuantityTypeIdentifierStepCount" sourceName="iPhone" unit="count" value="200" startDate="2026-08-10 10:00:00 +0800" endDate="2026-08-10 11:00:00 +0800"/>
  <Record type="HKQuantityTypeIdentifierStepCount" sourceName="Watch" unit="count" value="400" startDate="2026-08-10 08:00:00 +0800" endDate="2026-08-10 11:00:00 +0800"/>
  <Record type="HKQuantityTypeIdentifierDietaryWater" sourceName="Health" unit="L" value="0.5" startDate="2026-08-10 12:00:00 +0800" endDate="2026-08-10 12:00:00 +0800"/>
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Watch" value="HKCategoryValueSleepAnalysisAsleepCore" startDate="2026-08-10 00:00:00 +0800" endDate="2026-08-10 05:00:00 +0800"/>
  <Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="Watch" value="HKCategoryValueSleepAnalysisAsleepREM" startDate="2026-08-10 05:00:00 +0800" endDate="2026-08-10 06:30:00 +0800"/>
  <Record type="HKQuantityTypeIdentifierBodyMass" sourceName="Scale" unit="kg" value="69.2" startDate="2026-08-10 07:00:00 +0800" endDate="2026-08-10 07:00:00 +0800"/>
  <Record type="HKQuantityTypeIdentifierRestingHeartRate" sourceName="Watch" unit="count/min" value="60" startDate="2026-08-10 07:00:00 +0800" endDate="2026-08-10 07:00:00 +0800"/>
  <Record type="HKQuantityTypeIdentifierRestingHeartRate" sourceName="Watch" unit="count/min" value="70" startDate="2026-08-10 08:00:00 +0800" endDate="2026-08-10 08:00:00 +0800"/>
  <Record type="HKQuantityTypeIdentifierHeartRate" sourceName="Watch" unit="count/min" value="100" startDate="2026-08-10 08:00:00 +0800" endDate="2026-08-10 08:00:00 +0800"/>
</HealthData>"""


def test_streaming_parser_aggregates_supported_types_without_source_double_count(tmp_path: Path) -> None:
    export = tmp_path / "export.xml"
    export.write_text(APPLE_XML, encoding="utf-8")
    parsed = parse_apple_health_xml(export)
    values = {request.kind: request.value for _, request in parsed.observations}

    assert parsed.processed_records == 10
    assert values == {
        "steps": 400,
        "water_ml": 500,
        "sleep_minutes": 390,
        "weight_kg": 69.2,
        "resting_heart_rate": 65.0,
    }


def test_bulk_insert_persists_once_and_deduplicates_reimport(tmp_path: Path) -> None:
    export = tmp_path / "export.xml"
    export.write_text(APPLE_XML, encoding="utf-8")
    parsed = parse_apple_health_xml(export)
    store = LifestyleStore(tmp_path / "lifestyle.json")

    first = store.add_device_observations_bulk(parsed.observations, connector_id="apple_healthkit")
    second = store.add_device_observations_bulk(parsed.observations, connector_id="apple_healthkit")

    assert first == (5, 0)
    assert second == (0, 5)
    assert len(store.list_observations(limit=20)) == 5
