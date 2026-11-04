import pytest
from core.i18n import t
from core.logging_config import setup_logging

def test_i18n_translations():
    assert t("role_fuqaro") == "Fuqaro"
    assert t("role_detektiv") == "Detektiv"
    assert "Assalomu alaykum" in t("welcome_private", name="Azimjon")
    # Missing key fallback
    assert t("non_existent_key_123") == "non_existent_key_123"

def test_setup_logging_idempotent():
    setup_logging(default_level="DEBUG")
    setup_logging(default_level="INFO")
