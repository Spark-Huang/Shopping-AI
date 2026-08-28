# QA Findings

This document records verification results that remain useful while their
corresponding changes are being prepared for release.

## 2026-08-28 08:37:02 +0800 — revision `0d62e3f` (baseline)

### QA-001 — Memory cart migration failures

- **Timestamp:** 2026-08-28 08:37:02 +0800
- **Revision:** `0d62e3f`; affected service files were workspace changes at verification time.
- **Command:** `python3 -m pytest -c tests/pytest.ini tests`
- **Result:** 67 selected; 64 passed; 3 failed.
- **Service/module:** memory / cart schema migration.
- **Location:** `tests/unit/memory/test_api.py:52` rebinds `memory.app.main.engine` for the isolated test engine, while `memory/app/database.py:24` and `memory/app/database.py:60` continue to use the module-level `database.engine`.
- **Observed behavior:** `TestCartMigration.test_cart_columns_migrate_idempotently[price]` and `[url]` report missing `price`/`url` columns after calling `_ensure_cart_columns()`; `TestCartMigration.test_cart_duplicates_are_removed_and_unique_index_is_idempotent` reports that `ux_cart_items_user_item` is absent. The tested isolated schema is not updated by those helper calls.

## 2026-08-28 08:49:12 +0800 — revision `aba04d8` (round 2)

The baseline-to-round-2 comparison found `0d62e3f` → `aba04d8`, memory/safety/search changes, and concurrently added orchestrator and web workspace files. Memory and safety passed their service suites: memory 44 passed; safety 23 passed.

Recheck at 2026-08-28 08:49:44 +0800, after concurrent workspace updates, reran `python -m pytest -c tests/pytest.ini tests/unit/orchestrator`: 413 selected; 411 passed; 2 failed. The cart compatibility and local-rule failures were no longer reproduced; the two remaining failures are the stream/language cases recorded in QA-004.

## 2026-08-28 09:02:21 +0800 — revision `371707a` (round 3)

The round-2-to-round-3 comparison found `aba04d8` → `371707a`. The diff affected the web module only, so no pytest run was triggered by that revision. Workspace orchestrator source and tests changed concurrently, so the orchestrator service suite was rerun.

- **Initial run:** `python -m pytest -c tests/pytest.ini tests/unit/orchestrator` — 413 selected; 409 passed; 4 failed. Failures covered the parallel language merge and API stream/timing expectations.
- **Concurrent-update recheck:** the same command at 2026-08-28 09:00:56 +0800 — 413 selected; 409 passed; 4 failed.
- **Updated test recheck:** the same command at 2026-08-28 09:02:21 +0800 — 413 selected; 412 passed; 1 failed. The API failures no longer reproduced.

### QA-005 — Parallel language update remains unresolved

- **Timestamp:** 2026-08-28 09:02:21 +0800
- **Revision:** `371707a` (HEAD during verification); affected graph/state tests were workspace changes.
- **Command:** `python -m pytest -c tests/pytest.ini tests/unit/orchestrator`
- **Result:** 413 selected; 412 passed; 1 failed.
- **Service/module:** orchestrator / graph language merge.
- **Location:** `orchestrator/app/agents/state.py:13` defines the language reducer, and `tests/unit/orchestrator/graph/test_nodes.py:684` asserts the expected final value.
- **Observed behavior:** The parallel language test receives `en` where `zh` is expected after planner and input-safety nodes provide concurrent language updates.

### QA-002 — Orchestrator cart compatibility shim failures

- **Timestamp:** 2026-08-28 08:49:12 +0800
- **Revision:** `aba04d8` (HEAD during verification); orchestrator changes were workspace changes.
- **Command:** `python -m pytest -c tests/pytest.ini tests/unit/orchestrator`
- **Result:** 413 selected; 352 passed; 61 failed (33 of the failures fall under this entry).
- **Service/module:** orchestrator / cart agent compatibility surface.
- **Location:** `orchestrator/app/agents/cart.py:5` re-exports the `cartops` package and `orchestrator/app/agents/cartops/memory_client.py:9` imports `requests` without exposing it through the compatibility module.
- **Observed behavior:** Tests report `AttributeError: module 'orchestrator.app.agents.cart' has no attribute 'requests'` while attempting to patch the cart compatibility surface. The failing cases cover catalog lookup, add/remove/view operations, invoke paths, and override contracts.

### QA-003 — Orchestrator safety local rules failure during verification

- **Timestamp:** 2026-08-28 08:49:12 +0800
- **Revision:** `aba04d8` (HEAD during verification); orchestrator changes were workspace changes.
- **Command:** `python -m pytest -c tests/pytest.ini tests/unit/orchestrator`
- **Result:** 413 selected; 352 passed; 61 failed (25 of the failures fall under this entry).
- **Service/module:** orchestrator / input and output local safety rules.
- **Location:** traceback reported `orchestrator/app/graph/local_rules.py:24` at the time of execution; the file at post-test inspection used a filesystem path at `orchestrator/app/graph/local_rules.py:24`.
- **Observed behavior:** Twenty-five safety tests failed with `NameError: name 'files' is not defined` when loading local unsafe rules. The source changed concurrently during the verification interval, so the traceback text no longer matches the inspected post-test file contents.

### QA-004 — Orchestrator stream and language behavior failures

- **Timestamp:** 2026-08-28 08:49:12 +0800
- **Revision:** `aba04d8` (HEAD during verification); orchestrator changes were workspace changes.
- **Command:** `python -m pytest -c tests/pytest.ini tests/unit/orchestrator`
- **Result:** 413 selected; 352 passed; 61 failed (3 failures fall under this entry).
- **Locations:** `orchestrator/app/agents/chatter.py:163`; `orchestrator/app/main.py:155`; graph behavior exercised by `tests/unit/orchestrator/graph/test_nodes.py:668`.
- **Observed behavior:** Two chatter buffering tests fail with `NameError: name 'time' is not defined` at `orchestrator/app/agents/chatter.py:163`. The image-only stream test records no calls to the compiled graph stub after handling the request at `orchestrator/app/main.py:155`. The parallel language-update test receives `en` where `zh` is expected.
