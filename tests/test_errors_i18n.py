from future_epw_demo.errors import ProjectConflictError, InvalidBaselineError
from future_epw_demo.i18n import Translator


def test_workflow_user_error_can_render_localized_generic_message():
    tr = Translator("zh_CN")
    error = ProjectConflictError("This folder already contains a Future EPW project.", recovery="Open the existing project.")
    text = error.user_text(tr)
    assert "项目" in text
    assert "打开" in text or "文件夹" in text
    assert "This folder" not in text


def test_workflow_user_error_keeps_original_text_without_translator():
    error = InvalidBaselineError("Invalid baseline", recovery="Choose another file")
    assert error.user_text() == "Invalid baseline\n\nChoose another file"


def test_weather_library_validation_error_localizes_in_chinese():
    from future_epw_demo.errors import WeatherValidationError
    tr = Translator("zh_CN")
    error = WeatherValidationError("Downloaded EPW WMO mismatch", recovery="Do not use this file")
    text = error.user_text(tr)
    assert "气象" in text or "EPW" in text
    assert "Downloaded EPW" not in text
