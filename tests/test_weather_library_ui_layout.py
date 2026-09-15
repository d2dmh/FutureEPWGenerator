from pathlib import Path

from future_epw_demo.project_workspace import ProjectWorkspace


def _make_epw(path: Path, *, station: str = "Tokyo.Intl.AP-Haneda.AP", wmo: str = "476710") -> Path:
    header = [
        f"LOCATION,{station},TK,JPN,SRC-TMYx,{wmo},35.5533,139.7811,9.0,10.7",
        "DESIGN CONDITIONS,0",
        "TYPICAL/EXTREME PERIODS,0",
        "GROUND TEMPERATURES,0",
        "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
        "COMMENTS 1,",
        "COMMENTS 2,",
        "DATA PERIODS,1,1,Data,Sunday,1/1,12/31",
    ]
    rows = ["2020,1,1,1,60,0,25,20,50,101325,0,0,0,0,0,0,0,0,0,0,180,2,5,5,20,7777,0,999999999,10,0.1,0,0.1,0,0" for _ in range(8760)]
    path.write_text("\n".join(header + rows) + "\n", encoding="utf-8")
    return path


def test_weather_library_selector_uses_search_and_bounded_result_list_not_combo_box():
    source = Path("future_epw_demo/pages/project_page.py").read_text(encoding="utf-8")
    assert "QListWidget" in source
    assert "self.library_search" in source
    assert "self.library_results" in source
    assert "setMaximumHeight" in source
    assert "QComboBox" not in source
    assert "self.library_combo" not in source


def test_workspace_display_city_uses_catalog_city_without_changing_cache_identity(tmp_path: Path):
    epw = _make_epw(tmp_path / "tokyo.epw")
    ws = ProjectWorkspace.create(
        root=tmp_path / "project",
        project_name="Tokyo_Future_EPW",
        city_name="Tokyo.Intl.AP-Haneda.AP",
        baseline_source=epw,
        scenarios=["ssp126"],
        periods=["2040"],
        gcms=["ACCESS-CM2"],
        climate_mode="advanced",
        baseline_origin={"type": "local"},
    )
    original_key = ws.location_key
    assert ws.city == "Tokyo.Intl.AP-Haneda.AP"
    assert ws.display_city == "Tokyo"
    assert ws.location_key == original_key


def test_project_page_uses_display_city_for_opened_workspace():
    source = Path("future_epw_demo/pages/project_page.py").read_text(encoding="utf-8")
    assert "display_city = ws.display_city" in source
    assert "self.city.setText(display_city)" in source
    assert "labels[2].setText(display_city)" in source


def test_main_window_propagates_display_city_to_ui_state():
    source = Path("future_epw_demo/main_window.py").read_text(encoding="utf-8")
    assert "ws.display_city" in source


def test_weather_library_search_labels_exist_in_both_languages():
    from future_epw_demo.i18n import Translator
    for language in ["en", "zh-CN"]:
        tr = Translator(language)
        assert tr.text("project.weather_library.search_label") != "project.weather_library.search_label"
        assert tr.text("project.weather_library.results") != "project.weather_library.results"
        assert tr.text("project.station") != "project.station"


def test_project_page_is_scrollable_for_weather_library_and_large_text():
    source = Path("future_epw_demo/main_window.py").read_text(encoding="utf-8")
    assert "self.stack.addWidget(self._wrap_scrollable(self.project_page))" in source
