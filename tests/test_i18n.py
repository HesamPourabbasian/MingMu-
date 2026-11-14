"""
Unit tests for MingMu internationalization (i18n) module.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from mingmu.i18n import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    detect_system_language,
    get_language,
    init_language,
    load_language_preference,
    save_language_preference,
    set_language,
    t,
)
from mingmu.i18n.translations import TRANSLATIONS
from mingmu.display.colors import overall_badge, status_badge
from mingmu.utils.thresholds import Status
from mingmu.utils.user_info import UserDeviceInfo


def test_supported_languages_list() -> None:
    """Verify that all 8 requested languages are present."""
    expected_codes = {"en", "es", "ja", "ru", "fr", "de", "zh", "tr"}
    assert set(SUPPORTED_LANGUAGES.keys()) == expected_codes


def test_translation_dictionaries_completeness() -> None:
    """Verify that every supported language dictionary has all keys and no empty strings."""
    en_keys = set(TRANSLATIONS["en"].keys())
    assert len(en_keys) >= 90

    for lang_code, translations in TRANSLATIONS.items():
        missing_keys = en_keys - set(translations.keys())
        assert not missing_keys, f"Language '{lang_code}' missing keys: {missing_keys}"

        for key, val in translations.items():
            assert isinstance(val, str), f"Value for '{key}' in '{lang_code}' is not a string"
            assert val.strip(), f"Value for '{key}' in '{lang_code}' is empty"


def test_translation_function_basic() -> None:
    """Test t() helper in English."""
    set_language("en")
    assert get_language() == "en"
    assert t("col_metric") == "Metric"
    assert t("status_good") == "Good"
    assert t("sec_battery") == "BATTERY"


def test_translation_switching() -> None:
    """Test switching languages and getting translated values."""
    # Spanish
    set_language("es")
    assert get_language() == "es"
    assert t("col_metric") == "Métrica"
    assert t("status_good") == "Correcto"
    assert t("sec_battery") == "BATERÍA"

    # Japanese
    set_language("ja")
    assert get_language() == "ja"
    assert t("col_metric") == "項目"
    assert t("status_good") == "正常"
    assert t("sec_battery") == "バッテリー"

    # Russian
    set_language("ru")
    assert get_language() == "ru"
    assert t("col_metric") == "Метрика"
    assert t("status_good") == "Отлично"
    assert t("sec_battery") == "БАТАРЕЯ"

    # French
    set_language("fr")
    assert get_language() == "fr"
    assert t("col_metric") == "Métrique"
    assert t("status_good") == "Bon"
    assert t("sec_battery") == "BATTERIE"

    # German
    set_language("de")
    assert get_language() == "de"
    assert t("col_metric") == "Metrik"
    assert t("status_good") == "Gut"
    assert t("sec_battery") == "AKKU / BATTERIE"

    # Chinese
    set_language("zh")
    assert get_language() == "zh"
    assert t("col_metric") == "监控指标"
    assert t("status_good") == "良好"
    assert t("sec_battery") == "电池状态"

    # Turkish
    set_language("tr")
    assert get_language() == "tr"
    assert t("col_metric") == "Metrik"
    assert t("status_good") == "İyi"
    assert t("sec_battery") == "PİL"

    # Reset back to English
    set_language("en")
    assert get_language() == "en"


def test_translation_formatting() -> None:
    """Test interpolation of variables in translation strings."""
    set_language("en")
    msg_en = t("welcome", user="Hesam", model="MacBook Air M1")
    assert "Hello Hesam" in msg_en
    assert "MacBook Air M1" in msg_en

    set_language("es")
    msg_es = t("welcome", user="Hesam", model="MacBook Air M1")
    assert "Hola Hesam" in msg_es
    assert "MacBook Air M1" in msg_es

    set_language("zh")
    msg_zh = t("welcome", user="Hesam", model="MacBook Air M1")
    assert "你好 Hesam" in msg_zh
    assert "MacBook Air M1" in msg_zh

    set_language("en")


def test_fallback_behavior() -> None:
    """Test fallback when key is not found."""
    set_language("es")
    # Non-existent key with default
    assert t("non_existent_key_xyz", default="Fallback Text") == "Fallback Text"
    # Non-existent key without default returns the key itself
    assert t("non_existent_key_xyz") == "non_existent_key_xyz"

    # Setting unsupported language falls back to English
    set_language("invalid_lang_code")
    assert get_language() == "en"


def test_status_badges_localization() -> None:
    """Test localized status badge strings."""
    set_language("en")
    assert "Good" in status_badge(Status.GOOD)
    assert "[GOOD]" in overall_badge(Status.GOOD)

    set_language("es")
    assert "Correcto" in status_badge(Status.GOOD)
    assert "[CORRECTO]" in overall_badge(Status.GOOD)

    set_language("ja")
    assert "正常" in status_badge(Status.GOOD)
    assert "[正常]" in overall_badge(Status.GOOD)

    set_language("en")


def test_welcome_message_localization() -> None:
    """Test UserDeviceInfo welcome greeting localization."""
    info = UserDeviceInfo(
        username="hesam",
        display_name="Hesam Pourabbasain",
        device_model="MacBook Air (Apple M1)",
    )

    set_language("en")
    assert info.welcome_message() == "Hello Hesam Pourabbasain (hesam), you are using MacBook Air (Apple M1)."

    set_language("es")
    assert info.welcome_message() == "Hola Hesam Pourabbasain (hesam), estás utilizando MacBook Air (Apple M1)."

    set_language("de")
    assert info.welcome_message() == "Hallo Hesam Pourabbasain (hesam), Sie verwenden MacBook Air (Apple M1)."

    set_language("en")


def test_save_and_load_preference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test saving and loading user language preference."""
    fake_config_file = tmp_path / "config.json"
    fake_config_dir = tmp_path

    import mingmu.i18n
    monkeypatch.setattr(mingmu.i18n, "CONFIG_FILE", fake_config_file)
    monkeypatch.setattr(mingmu.i18n, "CONFIG_DIR", fake_config_dir)

    # Initial load should be None
    assert load_language_preference() is None

    # Save preference for Japanese
    assert save_language_preference("ja") is True
    assert fake_config_file.exists()

    # Verify JSON content
    with open(fake_config_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data == {"language": "ja"}

    # Load should now return "ja"
    assert load_language_preference() == "ja"

    # Invalid language code should not be saved
    assert save_language_preference("invalid") is False


def test_init_language_hierarchy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test initialization hierarchy: CLI override > Config file > Default."""
    fake_config_file = tmp_path / "config.json"
    fake_config_dir = tmp_path

    import mingmu.i18n
    monkeypatch.setattr(mingmu.i18n, "CONFIG_FILE", fake_config_file)
    monkeypatch.setattr(mingmu.i18n, "CONFIG_DIR", fake_config_dir)

    # 1. CLI override has highest priority
    lang = init_language(cli_override="fr")
    assert lang == "fr"
    assert get_language() == "fr"

    # 2. Config file when CLI override is None
    save_language_preference("de")
    lang = init_language(cli_override=None)
    assert lang == "de"
    assert get_language() == "de"

    # Reset
    set_language("en")


def test_help_view_localization() -> None:
    """Test localized rendering of the help & documentation manual."""
    from mingmu.display.help_view import render_help_view

    # English
    set_language("en")
    view_en = render_help_view(width=80)
    assert "HELP & DOCUMENTATION GUIDE" in view_en
    assert "STATUS INDICATORS" in view_en
    assert "COMMAND-LINE SHORTCUTS" in view_en

    # Spanish
    set_language("es")
    view_es = render_help_view(width=80)
    assert "GUÍA DE AYUDA Y DOCUMENTACIÓN" in view_es
    assert "INDICADORES DE ESTADO" in view_es
    assert "ATAJOS DE LÍNEA DE COMANDOS" in view_es

    # Japanese
    set_language("ja")
    view_ja = render_help_view(width=80)
    assert "ヘルプ＆ドキュメントガイド" in view_ja
    assert "ステータスインジケーター" in view_ja

    # Russian
    set_language("ru")
    view_ru = render_help_view(width=80)
    assert "РУКОВОДСТВО ПО ПОМОЩИ И ДОКУМЕНТАЦИЯ" in view_ru
    assert "ИНДИКАТОРЫ СОСТОЯНИЯ" in view_ru

    # German
    set_language("de")
    view_de = render_help_view(width=80)
    assert "HILFE- & DOKUMENTATIONSHANDBUCH" in view_de
    assert "STATUSINDIKATOREN" in view_de

    # French
    set_language("fr")
    view_fr = render_help_view(width=80)
    assert "GUIDE D'AIDE ET DE DOCUMENTATION" in view_fr
    assert "INDICATEURS D'ÉTAT" in view_fr

    # Chinese
    set_language("zh")
    view_zh = render_help_view(width=80)
    assert "帮助与完整技术文档指南" in view_zh
    assert "状态指示器" in view_zh

    # Turkish
    set_language("tr")
    view_tr = render_help_view(width=80)
    assert "YARDIM VE BELGE KILAVUZU" in view_tr
    assert "DURUM GÖSTERGELERİ" in view_tr

    set_language("en")
