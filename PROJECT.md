# Project: Telegram Mafia ("Detektiv") Bot Overhaul

## Architecture
- **Application Engine (`core/`, `phases/`, `roles/`)**: State machines for Lobby, Night, Day, Voting, and Verdict phases. Player roles, dossiers, and distribution. In-memory `games` and `lobbies` managed under per-chat `asyncio.Lock` serialization.
- **Presentation & UI System (`core/ui.py`, `core/emojis.py`, `core/visuals.py`, `locales/`)**: HTML component-based message renderer. Throttled in-place game board editing (3-5s). Custom emoji capability probe with unicode fallbacks. Multi-channel animations (`sendDice`, reactions, animated stickers). Centralized i18n (`t(key, lang, **vars)`).
- **Handler Layer (`bot.py`, `handlers/`)**: Dispatches commands and callbacks. Two-tier slash/exact command dispatcher in private chats. Modularized handlers (`deep_link.py`, `cb_night.py`, `cb_voting.py`, `settings.py`, `admin_panel.py`). Scope-based Telegram command menus.
- **Data & Persistence Layer (`database/db.py`, `database/models.py`)**: SQLite with WAL mode, atomic SQL transactions (`UPDATE ... WHERE balance + ? >= 0`), strict column whitelisting, user migration tracking, in-memory TTL caching for hot reads and `track_group_user`.
- **Infrastructure & Quality (`Dockerfile`, `docker-compose.yml`, CI, tests)**: Non-root container, port 8000 healthcheck server, pinned dependencies, ruff/black/mypy, extensive automated test suite, load benchmark simulation.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Fail-Fast BOT_TOKEN | Raise immediate error on missing/empty BOT_TOKEN | M1 | R0 §13 |
| 2 | Numeric Admin Authorization | Restrict admin permissions strictly to numeric IDs with safe parsing | M1 | R0 §14 |
| 3 | Env-configurable DB_PATH | Dynamic path resolution with parent directory creation | M1 | R0 §14 |
| 4 | Atomic Balance Updates | Balance modifications use atomic SQL with column whitelisting | M1 | R0 §15 |
| 5 | Atomic Inventory Debits | Item consumption uses atomic SQL with field whitelisting | M1 | R0 §15 |
| 6 | Clan Balance Atomic Helper | Clan treasury modifications use atomic SQL checks | M1 | R0 / Survey 1 |
| 7 | Fail-Closed lobby_stop | Terminate lobby only on verified admin permissions; fail closed on errors | M1 | R0 §16 |
| 8 | Phase Timer Cancellation | Ensure all timers pop and cancel on abort, finish, or phase advance | M1 | R0 §16 |
| 9 | Callback Actor & Target Auth | Validate actor ID, role eligibility, life state, target existence & life | M1 | R0 §17 |
| 10 | Stale Button Graceful Rejection | User-friendly alert when clicking outdated or mismatched buttons | M1 | R0 §17 |
| 11 | Startup Orphan Game Cleanup | Reconcile active SQLite games to aborted on bot launch | M1 | R0 §18 |
| 12 | Git & Secrets Hygiene | Untrack and ignore .env, *.db, *.log, *.zip | M1 | R0 §13 |
| 13 | Comprehensive COMMANDS.md | Document 100% of commands, aliases, scopes, permissions, args, replies | M2 | R1 §21 |
| 14 | Fix send_cmd UnboundLocalError | Fix undefined sender_name crash in /send command | M2 | R1 / Survey 2 |
| 15 | Fix PM_DISPATCH_TABLE Collision | Prevent coin and gold commands from colliding with balance aliases | M2 | R1 / Survey 2 |
| 16 | NoneType Guarding | Guard against None effective_user / effective_message in all handlers | M2 | R1 / Survey 2 |
| 17 | HTML Dynamic Escaping | Replace unescaped Markdown with clean HTML (html.escape dynamic variables) | M2 | R1 §23 |
| 18 | Two-Tier PM Command Dispatcher | Whole-word and slash dispatcher preserving Last Words and Will input flows | M2 | R1 §24 |
| 19 | Telegram Command Scopes | Register commands for default, private, group, group admins, and bot admins | M2 | R1 §25 |
| 20 | Modularize start_cmd | Separate deep linking (join, act, role views) into handlers/deep_link.py | M2 | R1 §26 |
| 21 | Modularize callback_router | Implement clean fallback answers and validation wrappers | M2 | R1 §26 |
| 22 | Modularize resolve_night | Decompose priority action chain into testable sub-functions | M2 | R1 §26 |
| 23 | Modularize resolve_verdict | Decompose vote tally, interventions, and execution into sub-functions | M2 | R1 §26 |
| 24 | Centralized UI Message System | Component templates in core/ui.py (group ≤8 lines, rich PMs) | M3 | R2 §29 |
| 25 | Throttled Game Board Editing | In-place message updates throttled to 3-5 seconds per chat | M3 | R2 §30 |
| 26 | Custom Emoji Capability Probe | Proactive startup probe (getCustomEmojiStickers) with unicode fallback | M3 | R2 §31 |
| 27 | Animation & Emoji Registry | Distinct visual assets for all roles, phases, shop, social features | M3 | R2 §32 |
| 28 | Image Asset Caching | Cache Telegram file_id for hayrli_kun.jpg and osuda_tun.jpg | M3 | R2 §33 |
| 29 | Multi-Channel Animations | Integrate sendDice, setMessageReaction, and animated stickers | M3 | R2 §33 |
| 30 | Rich Onboarding & Guides | Role encyclopedia, breadcrumb navigation, group-add guide & checklist | M3 | R2 §34 |
| 31 | Centralized Locales (i18n) | locales/uz.json, ru.json, en.json with t(key, lang, **vars) | M3 | R2 §35 |
| 32 | Concurrent Updates & Chat Locks | Enable concurrent_updates with per-chat asyncio locks for state mutations | M4 | R3 §38 |
| 33 | Rate Limiter & Tracked Timers | AIORateLimiter and tracked tasks with reliable cancellation | M4 | R3 §39 |
| 34 | TTL Cache for track_group_user | In-memory cache skipping redundant SQLite writes for active users | M4 | R3 §40 |
| 35 | Hot Read Caching | Cache settings, badges, admin status, role info without N+1 queries | M4 | R3 §41 |
| 36 | Specific Exceptions & Logging | Replace broad exception blocks with structured logging | M4 | R3 §42 |
| 37 | Concurrency Benchmark Script | scripts/benchmark_simulation.py (10 groups × 15 players) | M4 | R3 §43 |
| 38 | Pinned Dependencies | Pin exact versions in requirements.txt and requirements-dev.txt | M5 | R4 §46 |
| 39 | Tooling & CI Pipeline | ruff, black, mypy/pyright, and GitHub Actions CI workflow | M5 | R4 §46 |
| 40 | Production Docker & Compose | Non-root Dockerfile, persistent /app/data, HEALTHCHECK, docker-compose | M5 | R4 §47 |
| 41 | Documentation & Quickstart | Comprehensive README.md with 5-step quickstart, env vars, test guide | M5 | R4 §48 |
| 42 | E2E Test Suite Creation | Opaque-box 4-tier test suite (Tiers 1-4) by E2E Testing Track | M_E2E | Project Dual Track |
| 43 | Final E2E Test Pass (Tiers 1-4) | Pass 100% of E2E tests before project completion | M6 | Project Dual Track |
| 44 | Adversarial Hardening (Tier 5) | White-box stress testing and gap hardening with Challengers | M6 | Project Dual Track |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M_E2E | E2E Testing Track | Design test infra and 4-tier test suite (Tiers 1-4), publish TEST_READY.md | none | DONE |
| M1 | R0 Security & DB Hygiene | Fail-fast config, numeric admin auth, atomic queries, timer cancels, startup cleanup | none | DONE |
| M2 | R1 Command Matrix & Hardening | COMMANDS.md, fix crashes, HTML escaping, two-tier dispatcher, command scopes, modularize handlers | M1 | DONE |
| M3 | R2 UI/UX, Animations & Locales | core/ui.py, game board throttling, emoji probe, asset caching, multi-channel visuals, locales | M2 | DONE |
| M4 | R3 Concurrency & Performance | concurrent_updates, per-chat locks, TTL caching, hot reads, structured logs, benchmark | M1, M3 | DONE |
| M5 | R4 Quality Gates & Packaging | Pinned deps, ruff/black/mypy, Dockerfile & compose, README.md | M1-M4 | DONE |
| M6 | Final Verification & Hardening | Pass 100% of E2E test suite (Tiers 1-4) then Adversarial Coverage Hardening (Tier 5) | M_E2E, M5 | DONE |

## Interface Contracts
### core.ui ↔ phases & handlers
- `async def update_game_board(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, reply_markup=None, photo_key: str = None) -> None`:
  Updates the in-place game board message with 3-5s throttle debounce. If no existing board message ID in `game["board_msg_id"]`, sends message and stores ID.
- `def format_html(template_key: str, lang: str = "uz", **kwargs) -> str`:
  Returns escaped HTML formatted string based on centralized locale keys.

### core.i18n ↔ system
- `def t(key: str, lang: str = "uz", **vars: Any) -> str`:
  Resolves dot-notated key in `locales/{lang}.json`, falling back to `uz`, formatting with `vars`.

### core.engine ↔ handlers (Concurrency)
- `def get_chat_lock(chat_id: int) -> asyncio.Lock`:
  Returns unique per-chat `asyncio.Lock` instance stored in `_chat_locks[chat_id]`.
- All game and lobby mutations must acquire `async with get_chat_lock(chat_id):`.

### database.models ↔ database.db
- `async def change_clan_balance(clan_id: int, amount: int) -> bool`:
  Atomic SQL update `UPDATE clans SET coins = coins + ? WHERE clan_id = ? AND (coins + ?) >= 0`. Returns `True` if row count > 0.

## Code Layout
- `bot.py`: Main entry point, application builder, scope setup, startup cleanup. Owned by M1, M2, M4.
- `config.py`: Environment configuration and validation. Owned by M1.
- `database/`: SQLite connections, migrations, models, queries. Owned by M1, M4.
- `core/ui.py`: UI system and throttled game board manager. Owned by M3.
- `core/i18n.py` & `locales/`: Internationalization system and locale files. Owned by M3.
- `core/emojis.py` & `core/visuals.py`: Emoji registry, probe, and animation effects. Owned by M3.
- `core/rate_limiter.py` & `core/engine.py`: Chat locks, rate limiting, and timers. Owned by M1, M4.
- `handlers/`: Command and callback handlers. Owned by M1, M2, M3.
- `phases/`: Phase state machines. Owned by M1, M2, M3, M4.
- `roles/`: Role definitions and dossier formatting. Owned by M2, M3.
- `scripts/`: Benchmark simulation and maintenance scripts. Owned by M4.
- `tests/`: Unit and integration tests. Owned by M1-M5, and `tests/e2e/` owned by M_E2E.
- `Dockerfile`, `docker-compose.yml`, `requirements*.txt`, `README.md`, `COMMANDS.md`: Owned by M2, M5.
