from pathlib import Path


def test_requirements_pin_numexpr_warning_floor():
    root=Path(__file__).resolve().parents[1]
    text=(root/'requirements.txt').read_text(encoding='utf-8')
    assert 'numexpr>=2.10.2' in text


def test_requirements_include_s3fs_for_aws_fallback():
    root=Path(__file__).resolve().parents[1]
    text=(root/'requirements.txt').read_text(encoding='utf-8')
    assert 's3fs' in text
