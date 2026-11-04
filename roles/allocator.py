import random
from typing import List, Optional, Set
from config import MIN_PLAYERS, MAX_PLAYERS, ROLES, ROLE_ORDER, REPEATABLE_ROLES

def choose_roles(n: int, disabled: Optional[Set[str]] = None) -> Optional[List[str]]:
    """Strict, balanced, dependency-safe role allocator for 4 to 100+ players.

    Formulas & Guarantees:
      - Length: always returns a valid list of length n for 4 <= n <= MAX_PLAYERS.
      - Mafia count: red_count = max(1, n // 5)
          * n = 4..9: 1 mafia (Boshliq / Don)
          * n = 10..14: 2 mafia (Boshliq + Qotil / Mafia)
          * n = 15..19: 3 mafia
          * n = 20..24: 4 mafia
          * n = 25..29: 5 mafia
          * n = 30..34: 6 mafia
          * n = 35..100: max(1, n // 5) mafia
      - Solo count:
          * n < 7: 0
          * 7 <= n <= 11: 1 (e.g. n=10 -> 7 Tinch, 2 Mafia, 1 Yakkaxon)
          * 12 <= n <= 17: 2
          * 18 <= n <= 24: 3
          * n >= 25: 4
      - Town (Blue) count: blue_count = n - red_count - solo_count
      - Dependencies:
          * Sherif NEVER appears without Detektiv.
          * Qotil NEVER appears without Boshliq.
    """
    if n < MIN_PLAYERS or n > MAX_PLAYERS:
        return None

    # Calculate exact team distribution
    red_count = max(1, n // 5)
    if n < 7:
        solo_count = 0
    elif 7 <= n <= 11:
        solo_count = 1
    elif 12 <= n <= 17:
        solo_count = 2
    elif 18 <= n <= 24:
        solo_count = 3
    else:
        solo_count = 4

    blue_count = n - red_count - solo_count

    disabled_set = set(disabled) if disabled else set()
    enabled = [r for r in ROLE_ORDER if r not in disabled_set]
    if not enabled:
        enabled = list(ROLE_ORDER)

    blue = [r for r in enabled if ROLES.get(r) == "blue"]
    red = [r for r in enabled if ROLES.get(r) == "red"]
    solo = [r for r in enabled if ROLES.get(r) == "solo"]

    # Minimum safety fallbacks
    if not blue:
        blue = ["Fuqaro", "Detektiv", "Doktor"]
    if not red:
        red = ["Boshliq", "Qotil"]
    if not solo:
        solo = ["Firibgar", "Joker", "Maniak"]

    result: List[str] = []

    # 1. RED TEAM (Mafia)
    # Don (Boshliq) is always the foundation
    if "Boshliq" in red and red_count >= 1:
        result.append("Boshliq")
    elif red:
        result.append(red[0])

    if red_count >= 2:
        if "Qotil" in red:
            result.append("Qotil")
        else:
            other_red = [r for r in red if r not in result]
            if other_red:
                result.append(random.choice(other_red))
            else:
                result.append("Boshliq")

    # Fill remaining red slots
    while sum(1 for r in result if ROLES.get(r) == "red") < red_count:
        candidates = [
            r for r in red
            if (r not in result or r in REPEATABLE_ROLES)
            and not (r == "Qotil" and "Boshliq" not in result)
        ]
        unselected = [c for c in candidates if c not in result]
        if unselected:
            random.shuffle(unselected)
            result.append(unselected[0])
        elif candidates:
            result.append(random.choice(candidates))
        else:
            result.append("Qotil" if "Boshliq" in result else "Boshliq")

    # 2. BLUE TEAM (Shahar / Town)
    # Detective foundation
    if "Detektiv" in blue and blue_count >= 1:
        result.append("Detektiv")
    # Doctor foundation
    if "Doktor" in blue and blue_count >= 2:
        result.append("Doktor")
    # Sheriff only if Detective is present and enough room (e.g. blue_count >= 3) and n >= 7
    if "Sherif" in blue and "Detektiv" in result and blue_count >= 3 and n >= 7:
        result.append("Sherif")

    # Fill remaining blue slots
    while sum(1 for r in result if ROLES.get(r) == "blue") < blue_count:
        candidates = [
            r for r in blue
            if (r not in result or r in REPEATABLE_ROLES)
            and not (r == "Sherif" and ("Detektiv" not in result or n < 7))
        ]
        unselected = [c for c in candidates if c not in result]
        if unselected:
            random.shuffle(unselected)
            result.append(unselected[0])
        elif candidates:
            result.append(random.choice(candidates))
        else:
            result.append("Fuqaro")

    # 3. SOLO TEAM (Yakkaxonlar)
    if solo_count > 0:
        solo_candidates = [r for r in solo if r not in result]
        random.shuffle(solo_candidates)
        for r in solo_candidates:
            if sum(1 for x in result if ROLES.get(x) == "solo") >= solo_count:
                break
            result.append(r)

        while sum(1 for r in result if ROLES.get(r) == "solo") < solo_count:
            cand = [r for r in solo if r not in result or r in REPEATABLE_ROLES]
            if not cand:
                cand = ["Firibgar", "Joker", "Qasoskor"]
            result.append(random.choice(cand))

    # Adjust exact length if any rounding / condition mismatch
    while len(result) < n:
        result.append("Fuqaro")
    while len(result) > n:
        popped = False
        for i in range(len(result) - 1, -1, -1):
            if result[i] in REPEATABLE_ROLES and result[i] != "Boshliq":
                result.pop(i)
                popped = True
                break
        if not popped:
            result.pop()

    # Final dependency guarantee
    if "Qotil" in result and "Boshliq" not in result:
        idx = result.index("Qotil")
        result[idx] = "Boshliq"
    while "Sherif" in result and (n < 7 or "Detektiv" not in result):
        idx = result.index("Sherif")
        result[idx] = "Detektiv" if ("Detektiv" not in result and n >= 7 and "Detektiv" not in disabled_set) else "Fuqaro"

    # Strictly guarantee at most 1 Sheriff
    while result.count("Sherif") > 1:
        idx = result.index("Sherif")
        result[idx] = "Fuqaro"

    random.shuffle(result)
    return result
