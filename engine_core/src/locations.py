from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LocationRecord:
    city: str
    latitude: float
    longitude: float
    baseline_epw: Path
    wmo: str = ""
    station: str = ""
    coordinate_source: str = "epw"
    baseline_latitude: float | None = None
    baseline_longitude: float | None = None


def load_location_spec(path: Path | str) -> list[LocationRecord]:
    p = Path(path)
    payload = json.loads(p.read_text(encoding="utf-8"))
    items = payload.get("locations")
    if not isinstance(items, list) or not items:
        raise ValueError("location spec must contain a non-empty 'locations' list")
    records: list[LocationRecord] = []
    seen: set[str] = set()
    for item in items:
        city = str(item.get("city", "")).strip()
        if not city:
            raise ValueError("location spec city must be non-empty")
        if city in seen:
            raise ValueError(f"duplicate city in location spec: {city}")
        seen.add(city)
        lat = float(item["latitude"])
        lon = float(item["longitude"])
        if not -90.0 <= lat <= 90.0:
            raise ValueError(f"{city}: latitude out of range: {lat}")
        if not -180.0 <= lon <= 180.0:
            raise ValueError(f"{city}: longitude out of range: {lon}")
        baseline = Path(item["baseline_epw"]).expanduser().resolve()
        if not baseline.is_file():
            raise FileNotFoundError(f"{city}: baseline EPW not found: {baseline}")
        records.append(
            LocationRecord(
                city=city,
                latitude=lat,
                longitude=lon,
                baseline_epw=baseline,
                wmo=str(item.get("wmo", "")).strip(),
                station=str(item.get("station", "")).strip(),
                coordinate_source=str(item.get("coordinate_source", "epw")).strip() or "epw",
                baseline_latitude=(float(item["baseline_latitude"]) if item.get("baseline_latitude") is not None else None),
                baseline_longitude=(float(item["baseline_longitude"]) if item.get("baseline_longitude") is not None else None),
            )
        )
    return records


def locations_from_spec(path: Path | str, cities=None) -> dict[str, tuple[float, float]]:
    records = load_location_spec(path)
    mapping = {r.city: (r.latitude, r.longitude) for r in records}
    if cities is None:
        return mapping
    requested = list(map(str, cities))
    missing = [city for city in requested if city not in mapping]
    if missing:
        raise ValueError(f"location spec missing requested city/cities: {missing}")
    return {city: mapping[city] for city in requested}


def baselines_from_spec(path: Path | str, cities=None) -> dict[str, Path]:
    records = load_location_spec(path)
    mapping = {r.city: r.baseline_epw for r in records}
    if cities is None:
        return mapping
    requested = list(map(str, cities))
    missing = [city for city in requested if city not in mapping]
    if missing:
        raise ValueError(f"location spec missing requested baseline(s): {missing}")
    return {city: mapping[city] for city in requested}


def location_summary(path: Path | str, cities=None) -> list[dict]:
    records = load_location_spec(path)
    if cities is not None:
        wanted = set(map(str, cities))
        records = [r for r in records if r.city in wanted]
    return [
        {
            "city": r.city,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "wmo": r.wmo,
            "station": r.station,
            "coordinate_source": r.coordinate_source,
            "baseline_epw": str(r.baseline_epw),
        }
        for r in records
    ]
