import pytest
from core.storyteller import (
    TEMPLATES, generate_morning_story, generate_verdict_story
)
from core.clues import generate_forensic_clue
from core.weather import roll_weather

def test_template_catalog_count():
    total_templates = sum(len(templates) for templates in TEMPLATES.values())
    assert total_templates >= 60, f"Expected at least 60 templates, found {total_templates}"

def test_generate_morning_story_mafia_hit():
    clue = generate_forensic_clue("Boshliq", "Alisher")
    weather = roll_weather()
    story = generate_morning_story(
        victim_name="Alisher",
        killer_role="Boshliq",
        clue=clue,
        weather_info=weather
    )
    assert story is not None
    assert "Alisher" in story
    assert len(story) > 30

def test_generate_morning_story_serial_killer():
    clue = generate_forensic_clue("Maniak", "Botir")
    weather = roll_weather()
    story = generate_morning_story(
        victim_name="Botir",
        killer_role="Maniak",
        clue=clue,
        weather_info=weather
    )
    assert story is not None
    assert "Botir" in story

def test_generate_morning_story_peaceful_night():
    weather = roll_weather()
    story = generate_morning_story(
        victim_name=None,
        killer_role=None,
        clue=None,
        weather_info=weather
    )
    assert story is not None
    assert len(story) > 20

def test_generate_morning_story_doctor_saved():
    story = generate_morning_story(
        victim_name=None,
        killer_role=None,
        doctor_saved_name="Jasur"
    )
    assert story is not None
    assert "Jasur" in story

def test_generate_verdict_story():
    for _ in range(10):
        story = generate_verdict_story("Sobir", "Qotil")
        assert "Sobir" in story
        assert "Qotil" in story
