import pytest
from core.will import format_will_announcement
from core.clues import generate_forensic_clue
from core.weather import roll_weather

def test_will_formatting_with_text():
    formatted = format_will_announcement("Dilshod", "1-tun: Nodirni tekshirdim — Mafiya!")
    assert "Dilshod" in formatted
    assert "Nodirni tekshirdim — Mafiya!" in formatted
    assert "Vasiyatnomasi" in formatted

def test_will_formatting_empty():
    formatted = format_will_announcement("Dilshod", None)
    assert "vasiyatnoma qoldirmagan" in formatted

    formatted_blank = format_will_announcement("Dilshod", "   ")
    assert "vasiyatnoma qoldirmagan" in formatted_blank

def test_forensic_clue_generation():
    clue = generate_forensic_clue("Qotil", "Zafar")
    assert "weapon" in clue
    assert "fabric" in clue
    assert "footprint" in clue
    assert "time" in clue
    assert "summary" in clue
    assert "🔍 Dalil:" in clue["summary"]

def test_weather_roll_fields():
    w = roll_weather()
    assert "id" in w
    assert "name" in w
    assert "icon" in w
    assert "desc" in w
