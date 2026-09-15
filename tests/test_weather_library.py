from pathlib import Path
import json
import zipfile

from future_epw_demo.weather_library import WeatherCatalog, WeatherLibrary, WeatherRecord
from tests.test_functional_backend import make_epw


def test_bundled_weather_catalog_has_at_least_40_major_cities():
    catalog = WeatherCatalog()
    assert len(catalog.records) >= 40
    cities = {r.city for r in catalog.records}
    assert {"Tokyo", "Singapore", "London", "New York", "Beijing", "Sydney"}.issubset(cities)
    assert catalog.search("tokyo")[0].wmo == "476710"
    assert catalog.search("羽田") or catalog.search("Haneda")


def test_weather_library_downloads_validates_and_reuses_cached_epw(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    epw = make_epw(source / "Tokyo.epw", wmo="476710", lat=35.5533, lon=139.7811)
    lines = epw.read_text(encoding="utf-8").splitlines()
    lines[0] = "LOCATION,Tokyo.Intl.AP-Haneda.AP,TK,JPN,SRC-TMYx,476710,35.5533,139.7811,9.0,10.7"
    epw.write_text("\n".join(lines) + "\n", encoding="utf-8")
    archive = source / "tokyo.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(epw, arcname="JPN_TK_Tokyo.Intl.AP-Haneda.AP.476710_TMYx.2009-2023.epw")
    record = WeatherRecord(
        id="tokyo-test", city="Tokyo", country="Japan", country_code="JPN", region="Tokyo",
        station="Tokyo Intl AP - Haneda", wmo="476710", latitude=35.5533, longitude=139.7811,
        elevation_m=10.7, dataset="TMYx", period="2009-2023", source="test",
        download_url=archive.as_uri(), preferred_epw_name="JPN_TK_Tokyo.Intl.AP-Haneda.AP.476710_TMYx.2009-2023.epw",
        aliases=("东京", "羽田"),
    )
    library = WeatherLibrary(cache_root=tmp_path / "cache")
    downloaded = library.download_and_validate(record)
    assert downloaded.is_file()
    assert library.cached_epw(record) == downloaded
    metadata = json.loads((downloaded.parent / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["wmo"] == "476710"
    assert metadata["downloaded_at"]
    assert metadata["archive_url"].endswith("tokyo.zip")


def test_project_persists_weather_library_origin(tmp_path: Path):
    from future_epw_demo.project_workspace import ProjectWorkspace
    source = tmp_path / "Tokyo.epw"
    make_epw(source, wmo="476710", lat=35.5533, lon=139.7811)
    ws = ProjectWorkspace.create(
        root=tmp_path / "project",
        project_name="Tokyo_Future_EPW",
        baseline_source=source,
        city_name="Tokyo",
        scenarios=["ssp126"], periods=["2040"], gcms=["ACCESS-CM2"], climate_mode="advanced",
        baseline_origin={"type": "weather_library", "catalog_id": "tokyo-haneda", "source": "Climate.OneBuilding.org"},
    )
    payload = json.loads(ws.project_file.read_text(encoding="utf-8"))
    assert payload["baseline"]["origin"]["catalog_id"] == "tokyo-haneda"
    reopened = ProjectWorkspace.load(ws.root)
    assert reopened.baseline_origin["type"] == "weather_library"


def test_weather_library_rejects_cached_epw_with_changed_sha(tmp_path: Path):
    source = tmp_path / "source_sha"; source.mkdir()
    epw = make_epw(source / "Tokyo.epw", wmo="476710", lat=35.5533, lon=139.7811)
    archive = source / "tokyo_sha.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(epw, arcname="Tokyo.epw")
    record = WeatherRecord(
        id="tokyo-sha-test", city="Tokyo", country="Japan", country_code="JPN", region="Tokyo",
        station="Tokyo Intl AP - Haneda", wmo="476710", latitude=35.5533, longitude=139.7811,
        elevation_m=10.7, dataset="TMYx", period="2009-2023", source="test",
        download_url=archive.as_uri(), preferred_epw_name="Tokyo.epw", aliases=(),
    )
    library = WeatherLibrary(cache_root=tmp_path / "cache_sha")
    downloaded = library.download_and_validate(record)
    original = downloaded.read_text(encoding="utf-8")
    downloaded.write_text(original + "\n", encoding="utf-8")
    assert library.cached_epw(record) is None


def test_weather_catalog_can_resolve_canonical_city_by_wmo():
    catalog = WeatherCatalog()
    record = catalog.by_wmo("476710")
    assert record is not None
    assert record.city == "Tokyo"
    assert record.station == "Tokyo Intl AP - Haneda"


def test_weather_library_raises_typed_validation_error_for_wmo_mismatch(tmp_path: Path):
    from future_epw_demo.errors import WeatherValidationError
    epw = make_epw(tmp_path / "wrong.epw", wmo="999999", lat=35.5533, lon=139.7811)
    record = WeatherRecord(
        id="tokyo-wmo-test", city="Tokyo", country="Japan", country_code="JPN", region="Tokyo",
        station="Tokyo Intl AP - Haneda", wmo="476710", latitude=35.5533, longitude=139.7811,
        elevation_m=10.7, dataset="TMYx", period="2009-2023", source="test",
        download_url="file:///unused.zip", preferred_epw_name="wrong.epw", aliases=(),
    )
    library = WeatherLibrary(cache_root=tmp_path / "cache_validation")
    import pytest
    with pytest.raises(WeatherValidationError):
        library._validate_epw(epw, record)


def test_weather_library_windows_default_uses_localappdata():
    from future_epw_demo.weather_library import default_weather_library_root
    root = default_weather_library_root(platform_name="nt", env={"LOCALAPPDATA": r"C:\Users\Test\AppData\Local"})
    assert str(root).replace("\\", "/").endswith("AppData/Local/FutureEPWGenerator/weather_library")
