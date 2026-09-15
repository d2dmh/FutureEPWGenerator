from __future__ import annotations

from future_epw_demo.i18n import Translator, text_scale_factor
from future_epw_demo.theme import APP_STYLE, scaled_app_style


def test_translator_switches_english_and_chinese_and_formats_parameters():
    tr = Translator("en")
    assert tr.text("nav.project") == "Project"
    assert tr.text("cmip6.progress.assets_cached", complete=12, total=200) == "12 / 200 assets cached"
    tr.set_language("zh_CN")
    assert tr.text("nav.project") == "项目"
    assert tr.text("cmip6.progress.assets_cached", complete=12, total=200) == "已完成 12 / 200 个资产"


def test_missing_chinese_key_falls_back_to_english_and_unknown_key_is_safe():
    tr = Translator("zh_CN")
    assert tr.text("app.name") == "Future EPW Generator"
    assert tr.text("missing.semantic.key") == "missing.semantic.key"


def test_text_scale_presets_and_stylesheet_scaling():
    assert text_scale_factor("small") == 0.90
    assert text_scale_factor("standard") == 1.00
    assert text_scale_factor("large") == 1.15
    assert scaled_app_style("standard") == APP_STYLE
    small = scaled_app_style("small")
    large = scaled_app_style("large")
    assert small != APP_STYLE
    assert large != APP_STYLE
    assert "font-size: 9px" in small  # 10 px -> 9 px
    assert "font-size: 12px" in large  # 10 px -> 11.5 -> 12 px


def test_preflight_failure_messages_exist_in_both_languages():
    for language in ["en", "zh_CN"]:
        tr = Translator(language)
        for key in ["project", "baseline", "location", "protocol", "manifest", "cache", "output", "idle"]:
            message = tr.text(f"preflight.{key}.fail", detail="12/200")
            recovery = tr.text(f"preflight.{key}.recovery")
            assert not message.startswith("preflight.")
            assert not recovery.startswith("preflight.")


def test_v091_catalog_covers_dynamic_ui_guidance_in_both_languages():
    keys = [
        "climate.strip.scenarios.value", "climate.strip.scenarios.detail",
        "climate.strip.time_slices.detail", "climate.strip.ensemble.value",
        "climate.strip.ensemble.detail", "climate.strip.expected.detail",
        "climate.method.future.value", "climate.method.ensemble.value",
        "cmip6.strip.assets.detail", "cmip6.strip.city_slots.detail",
        "cmip6.strip.provider.detail", "cmip6.message.busy.text",
        "cmip6.message.failure.preserved", "generate.stop.tooltip",
    ]
    for language in ["en", "zh_CN"]:
        tr = Translator(language)
        for key in keys:
            value = tr.text(key)
            assert value != key


def test_chinese_catalog_covers_all_translatable_english_keys():
    from future_epw_demo.i18n import EN, ZH_CN
    intentionally_shared = {"app.name", "app.version", "settings.language.en", "settings.language.zh_CN"}
    assert set(EN) - set(ZH_CN) == intentionally_shared


def test_v092_dynamic_preflight_copy_has_no_fixed_200_requirement():
    from future_epw_demo.i18n import Translator
    en = Translator('en')
    zh = Translator('zh_CN')
    assert '200/200' not in en.text('preflight.cache.recovery')
    assert '200/200' not in zh.text('preflight.cache.recovery')
    assert 'climate selection' in en.text('preflight.cache.recovery')
    assert '当前气候选择' in zh.text('preflight.cache.recovery')
