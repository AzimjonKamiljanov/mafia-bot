import pytest
from core.i18n import t
from core.logging_config import setup_logging

def test_i18n_translations():
    # Uzbek (default)
    assert t("role_fuqaro") == "Fuqaro"
    assert t("role_detektiv") == "Detektiv"
    assert "Assalomu alaykum" in t("welcome_private", name="Azimjon")

    # Russian
    assert t("role_fuqaro", lang="ru") == "Мирный житель"
    assert t("role_detektiv", lang="ru") == "Детектив"
    assert "Здравствуйте" in t("welcome_private", lang="ru", name="Азим")

    # English
    assert t("role_fuqaro", lang="en") == "Civilian"
    assert t("role_detektiv", lang="en") == "Detective"
    assert "Hello" in t("welcome_private", lang="en", name="Azim")

    # Missing key fallback
    assert t("non_existent_key_123") == "non_existent_key_123"
    assert t("non_existent_key_123", default="DefaultVal") == "DefaultVal"

def test_setup_logging_idempotent():
    setup_logging(default_level="DEBUG")
    setup_logging(default_level="INFO")
