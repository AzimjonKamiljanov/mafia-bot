# Telegram Mafia ("Detektiv") Bot — E2E Test Infrastructure & Philosophy

## 1. Test Philosophy & Principles

The End-to-End (E2E) Test Suite for the Uzbek-language Telegram Mafia ("Detektiv") Bot provides an opaque-box, requirement-driven verification harness designed to validate all 41 project features, state machines, handlers, and security contracts under realistic Telegram client interactions.

### Core Principles
1. **Requirement-Driven**: Every test case is derived strictly from `ORIGINAL_REQUEST.md` and `PROJECT.md` § Feature Inventory (Features 1 to 41), rather than coupling to internal private methods.
2. **Opaque-Box Protocol Simulation**: The bot is exercised through external entry points (`Update`, `Message`, `CallbackQuery`, `Application`) simulating real Telegram update streams without depending on real Telegram network calls.
3. **Progressive Testability**: Tests are built to verify features incrementally without requiring unimplemented milestone features, providing explicit expectations (`xfail` annotations) when upstream implementation gaps are detected.
4. **Adversarial Verification**:
   - **Encoding & Escaping Integrity**: Dynamic user input (`<script>`, HTML tags, unicode emojis, zero-width characters) is tested against XSS and template injection.
   - **Invalid Combinations**: Concurrent clicks, non-digit IDs, negative currency transfers, out-of-order callbacks.
   - **Resource & Concurrency Stress**: Race condition prevention across simultaneous database writes and timer task lifecycle cancellations.

---

## 2. 4-Tier Test Design Methodology

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Tier 4: Real-World Scenarios                   │
│   Complete multi-turn match simulations (Lobby -> Night -> Day -> Vote │
│   -> Verdict -> Win condition & reward persistence)                    │
├────────────────────────────────────────────────────────────────────────┤
│                    Tier 3: Cross-Feature Combinations                  │
│   Pairwise interactions (Lobby join + stop, Night attack + Doctor save, │
│   Mayor 3x voting + Extra vote item, Shop purchase + item use)          │
├────────────────────────────────────────────────────────────────────────┤
│                    Tier 2: Boundary & Corner Cases                     │
│   Empty inputs, None updates, non-digit IDs, negative currency,        │
│   XSS escaping, burst rate limit thresholds, malformed callbacks       │
├────────────────────────────────────────────────────────────────────────┤
│                       Tier 1: Feature Coverage                         │
│   Isolated happy-path verification of all 41 features from PROJECT.md   │
└────────────────────────────────────────────────────────────────────────┘
```

- **Tier 1 — Feature Coverage (`test_tier1_features.py`)**: Individual, isolated validation of every feature in the Feature Inventory (F1 to F41), ensuring baseline operational contracts are fulfilled.
- **Tier 2 — Boundary & Corner Cases (`test_tier2_boundaries.py`)**: Strict input validation, zero/negative bounds, non-digit ID rejection, XSS defense, rate limit sliding windows, NoneType handling, and malformed callback payloads.
- **Tier 3 — Cross-Feature Combinations (`test_tier3_combinations.py`)**: Integration across distinct subsystems (economy ↔ inventory, lobby ↔ timers, night actions ↔ doctor/bodyguard protection, voting ↔ mayor roles ↔ items).
- **Tier 4 — Real-World Scenarios (`test_tier4_scenarios.py`)**: Full end-to-end game lifecycle simulations verifying complete match progression from `/game` through endgame win conditions and coin/rating payouts.

---

## 3. Comprehensive Feature Inventory Matrix (Features 1–41)

| Feature ID | Feature Name | Milestone | Target Module | Tier | Test Function | Authoritative Specification & Expected Output |
|:----------:|:-------------|:---------:|:--------------|:----:|:--------------|:-----------------------------------------------|
| **1** | Fail-Fast BOT_TOKEN | M1 | `bot.py`, `config.py` | Tier 1 | `test_feature_01_fail_fast_bot_token` | `create_bot_app()` raises `ValueError("BOT_TOKEN is missing or empty")` when token is absent. |
| **2** | Numeric Admin Auth | M1 | `config.py`, `database/models.py` | Tier 1 | `test_feature_02_numeric_admin_authorization` | `is_admin` returns `True` for numeric `ADMIN_IDS` and strictly `False` for unauthorized IDs. |
| **3** | Env-configurable DB_PATH | M1 | `config.py`, `database/db.py` | Tier 1 | `test_feature_03_env_configurable_db_path` | `config.DB_PATH` resolves dynamically from environment. |
| **4** | Atomic Balance Updates | M1 | `database/models.py` | Tier 1 | `test_feature_04_atomic_balance_updates` | `change_balance` executes atomic check `balance + ? >= 0`, rejecting negative balances & invalid columns. |
| **5** | Atomic Inventory Debits | M1 | `database/models.py` | Tier 1 | `test_feature_05_atomic_inventory_debits` | `take_item` verifies atomic inventory deduction, preventing negative counts. |
| **6** | Clan Balance Atomic Helper | M1 | `database/models.py` | Tier 1 | `test_feature_06_clan_balance_atomic_helper` | `change_clan_balance` modifies clan treasury atomically. |
| **7** | Fail-Closed lobby_stop | M1 | `handlers/callbacks.py` | Tier 1 | `test_feature_07_fail_closed_lobby_stop` | Exceptions during admin verification preserve lobby state and prevent unauthorized stopping. |
| **8** | Phase Timer Cancellation | M1 | `core/engine.py` | Tier 1 | `test_feature_08_phase_timer_cancellation` | `cancel_game_timer` & `cancel_lobby_timer` safely cancel attached asyncio background tasks. |
| **9** | Callback Actor/Target Auth | M1 | `handlers/callbacks.py` | Tier 1 | `test_feature_09_callback_actor_target_auth` | Callback routing rejects unauthorized or dead players attempting game phase actions. |
| **10** | Stale Button Rejection | M1 | `handlers/callbacks.py` | Tier 1 | `test_feature_10_stale_button_graceful_rejection` | Outdated callback queries answer user cleanly without raising unhandled exceptions. |
| **11** | Startup Orphan Game Cleanup | M1 | `bot.py` | Tier 1 | `test_feature_11_startup_orphan_cleanup` | `cleanup_orphaned_games` reconciles active games in SQLite to 'aborted' state on launch. |
| **12** | Git & Secrets Hygiene | M1 | `.gitignore` | Tier 1 | `test_feature_12_git_secrets_hygiene` | `.gitignore` strictly ignores `.env`, `*.db`, `*.log`, and `*.zip`. |
| **13** | Comprehensive COMMANDS.md | M2 | `COMMANDS.md`, `bot.py` | Tier 1 | `test_feature_13_commands_matrix_coverage` | Registered PM and group commands are mapped in the command dispatch system. |
| **14** | Fix send_cmd UnboundLocalError | M2 | `handlers/social.py` | Tier 1 | `test_feature_14_send_cmd_boundary_and_validation` | `/send` validates positive amounts, private chat restrictions, and argument count. |
| **15** | Fix PM Dispatch Collision | M2 | `bot.py` | Tier 1 | `test_feature_15_pm_dispatch_table_collision` | `coin` and `gold` commands map to transfer handlers, not `balance_cmd`. |
| **16** | NoneType Guarding | M2 | Handlers, `bot.py` | Tier 1 | `test_feature_16_nonetype_guarding` | Handlers guard against `update.message is None` and `effective_user is None`. |
| **17** | HTML Dynamic Escaping | M2 | Core visuals, phases | Tier 1 | `test_feature_17_html_dynamic_escaping` | Dynamic strings containing HTML tags are escaped via `html.escape`. |
| **18** | Two-Tier PM Dispatcher | M2 | `bot.py` | Tier 1 | `test_feature_18_two_tier_pm_dispatcher` | Whole-word and slash commands route correctly; unknown inputs receive fallback menu. |
| **19** | Telegram Command Scopes | M2 | `bot.py` | Tier 1 | `test_feature_19_telegram_command_scopes` | `post_init` registers `BotCommandScopeDefault`, `AllGroupChats`, `AllPrivateChats`, and Admin scopes. |
| **20** | Modularize start_cmd | M2 | `handlers/commands.py` | Tier 1 | `test_feature_20_modularize_start_cmd` | Deep links (`act_*`, `join_*`) route user directly to active game actions. |
| **21** | Modularize callback_router | M2 | `handlers/callbacks.py` | Tier 1 | `test_feature_21_modularize_callback_router` | Callback routing cleanly dispatches to settings, admin, lobby, night, and voting sub-handlers. |
| **22** | Modularize resolve_night | M2 | `phases/night.py` | Tier 1 | `test_feature_22_modularize_resolve_night` | Night priority chain accurately resolves attacks, heals, blocks, and clue generation. |
| **23** | Modularize resolve_verdict | M2 | `phases/verdict.py` | Tier 1 | `test_feature_23_modularize_resolve_verdict` | Verdict tallies QATL vs AFV votes and handles execution or survival. |
| **24** | Centralized UI Message System | M3 | `phases/lobby.py`, UI | Tier 1 | `test_feature_24_centralized_ui_message_formatting` | Group messages are formatted concisely (<= 8 lines) with clear instructions. |
| **25** | Throttled Game Board Editing | M3 | `core/rate_limiter.py` | Tier 1 | `test_feature_25_throttled_game_board_editing` | Rate limiting throttles rapid consecutive edits within 3-5s window. |
| **26** | Custom Emoji Capability Probe | M3 | `bot.SafeExtBot`, `core/emojis.py` | Tier 1 | `test_feature_26_custom_emoji_fallback` | `SafeExtBot` adapts custom emojis and falls back cleanly on parsing errors. |
| **27** | Animation & Emoji Registry | M3 | `core/emojis.py` | Tier 1 | `test_feature_27_animation_emoji_registry` | `tg_emoji` returns configured visual assets with unicode fallbacks. |
| **28** | Image Asset Caching | M3 | `config.py` | Tier 1 | `test_feature_28_image_asset_resolution` | Daytime and nighttime image assets exist at configured filesystem paths. |
| **29** | Multi-Channel Animations | M3 | `core/visuals.py` | Tier 1 | `test_feature_29_multi_channel_animations` | `send_animated_dice_effect` triggers Telegram native 3D dice in private chats. |
| **30** | Rich Onboarding & Guides | M3 | `handlers/commands.py` | Tier 1 | `test_feature_30_rich_onboarding_and_guides` | `/guide` displays complete role dossiers, win conditions, and team affiliations. |
| **31** | Centralized Locales (i18n) | M3 | `core/i18n.py`, `locales/` | Tier 1 | `test_feature_31_centralized_locales` | `t(key, lang)` translates across `uz`, `ru`, `en` with `uz` fallback. |
| **32** | Concurrent Updates & Chat Locks | M4 | `database/models.py` | Tier 1 | `test_feature_32_concurrent_updates_chat_locks` | Concurrent state mutations execute atomically without data corruption. |
| **33** | Rate Limiter & Tracked Timers | M4 | `core/rate_limiter.py` | Tier 1 | `test_feature_33_rate_limiter_and_tracked_timers` | Sliding window rate limiter enforces maximum actions within time window. |
| **34** | TTL Cache for track_group_user | M4 | `bot.py` | Tier 1 | `test_feature_34_ttl_cache_track_group_user` | Rapid message tracking does not throw database or constraint errors. |
| **35** | Hot Read Caching | M4 | `database/models.py` | Tier 1 | `test_feature_35_hot_read_caching` | Settings reads return consistent values across repeated calls. |
| **36** | Specific Exceptions & Logging | M4 | `core/logging_config.py` | Tier 1 | `test_feature_36_specific_exceptions_and_logging` | Structured logger `detektiv` is initialized and operational. |
| **37** | Concurrency Benchmark Script | M4 | `core/engine.py` | Tier 1 | `test_feature_37_concurrency_benchmark_simulation` | Multi-group concurrent lobbies execute without deadlock. |
| **38** | Pinned Dependencies | M5 | `requirements.txt` | Tier 1 | `test_feature_38_pinned_dependencies` | Dependencies in `requirements.txt` specify pinned versions (`==`). |
| **39** | Tooling & CI Pipeline | M5 | `.github/workflows/ci.yml` | Tier 1 | `test_feature_39_ci_tooling_pipeline` | CI workflow config exists and includes linting, type-checking, and tests. |
| **40** | Production Docker & Compose | M5 | `Dockerfile`, `docker-compose.yml` | Tier 1 | `test_feature_40_production_docker_compose` | Dockerfile specifies non-root user `appuser` and persistent volume `/app/data`. |
| **41** | Documentation & Quickstart | M5 | `README.md` | Tier 1 | `test_feature_41_documentation_quickstart` | `README.md` documents environment variables and setup instructions. |

---

## 4. Test Infrastructure Architecture

### Directory Layout
```
tests/
├── conftest.py                      # Global teardown fixture & environment defaults
├── e2e/                             # Opaque-Box E2E Test Suite (Tiers 1-4)
│   ├── __init__.py                  # Shared mocks, Update factories, and state reset utilities
│   ├── test_tier1_features.py       # Tier 1: Feature Coverage (Features 1-41)
│   ├── test_tier2_boundaries.py     # Tier 2: Boundary & Corner Cases
│   ├── test_tier3_combinations.py   # Tier 3: Cross-Feature Combinations
│   └── test_tier4_scenarios.py      # Tier 4: Real-World Scenarios
└── ...                              # Unit and subsystem integration tests
```

### Shared Mock & Factory Specifications
- `MockUser(uid, full_name, username, is_premium, is_bot)`: Spec-conforming Telegram user representation.
- `MockChat(chat_id, chat_type, title)`: Simulates `private`, `group`, and `supergroup` chats.
- `make_pm_update(...)`: Constructs incoming text message updates in private chats.
- `make_group_message_update(...)`: Constructs group discussion and command updates.
- `make_callback_update(...)`: Constructs inline keyboard button callback queries with `answer()` and `edit_message_text()`.
- `make_e2e_context()`: Instantiates full mock Telegram `ContextTypes.DEFAULT_TYPE` with all bot async methods mocked.
- `reset_runtime_state()`: Reinitializes `games`, `lobbies`, cancels dangling asyncio tasks, and flushes rate limit buckets between tests.

---

## 5. Coverage Thresholds & Quality Gates

1. **Pass Rate**: 100% of non-deferred tests must pass cleanly.
2. **Execution Time**: The complete E2E test suite must execute in **under 2.0 seconds** (current benchmark: ~0.80s).
3. **Zero Resource Leaks**: Every background timer task created during testing must be popped and cancelled upon completion.
4. **Adversarial Resiliency**: Malicious HTML input must never be reflected as executable markup.
