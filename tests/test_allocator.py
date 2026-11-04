import pytest
from roles.allocator import choose_roles
from config import MIN_PLAYERS, MAX_PLAYERS, ROLES

def test_choose_roles_all_player_counts():
    """Verify that choose_roles generates a valid, properly sized team for 4 to 100 players."""
    for n in range(MIN_PLAYERS, MAX_PLAYERS + 1):
        for trial in range(10):
            roles = choose_roles(n)
            assert roles is not None, f"choose_roles({n}) returned None on trial {trial}"
            assert len(roles) == n, f"Expected {n} roles, got {len(roles)}"

            # Dependency constraints
            if "Qotil" in roles:
                assert "Boshliq" in roles, f"Qotil appeared without Boshliq for n={n}"
            if "Sherif" in roles:
                assert "Detektiv" in roles, f"Sherif appeared without Detektiv for n={n}"
                assert n >= 7, f"Sherif appeared for n={n} which is < 7!"
            if n < 7:
                assert "Sherif" not in roles, f"Sherif must never appear for n={n} < 7!"

            # Team presence
            red_count = sum(1 for r in roles if ROLES.get(r) == "red")
            blue_count = sum(1 for r in roles if ROLES.get(r) == "blue")
            assert red_count >= 1, f"No red roles for n={n}"
            assert blue_count >= 1, f"No blue roles for n={n}"

def test_choose_roles_boundaries():
    assert choose_roles(3) is None
    assert choose_roles(MAX_PLAYERS + 1) is None
    assert choose_roles(36) is not None

def test_choose_roles_with_disabled():
    disabled = {"Maniak", "Pirotexnik"}
    for _ in range(20):
        roles = choose_roles(15, disabled=disabled)
        assert roles is not None
        assert "Maniak" not in roles
        assert "Pirotexnik" not in roles

def test_choose_roles_mafia_ratio():
    """Verify that choose_roles strictly allocates 1 mafia per 5 players."""
    for n in range(MIN_PLAYERS, MAX_PLAYERS + 1):
        expected_red = max(1, n // 5)
        for _ in range(10):
            roles = choose_roles(n)
            red_count = sum(1 for r in roles if ROLES.get(r) == "red")
            assert red_count == expected_red, f"For n={n}, expected {expected_red} red roles, got {red_count}"

def test_choose_roles_sheriff_strict_uniqueness():
    """Verify that Sherif NEVER appears more than once and NEVER for n < 7."""
    for n in range(MIN_PLAYERS, MAX_PLAYERS + 1):
        for _ in range(50):
            roles = choose_roles(n)
            sheriff_count = roles.count("Sherif")
            assert sheriff_count <= 1, f"Sherif duplicated ({sheriff_count} times) for n={n}"
            if n < 7:
                assert sheriff_count == 0, f"Sherif appeared for n={n} < 7"

def test_choose_roles_disabled_detective_not_reintroduced():
    """Verify that if Detektiv is disabled, it is never reintroduced by Sheriff fallback."""
    for _ in range(50):
        roles = choose_roles(10, disabled={"Detektiv"})
        assert "Detektiv" not in roles
        assert "Sherif" not in roles


