# Test and Demo Isolation Review — 2026-11-24

## Configuration reviewed

- Normal application database: `instance/consentx.sqlite3`, unless `CONSENTX_DB` explicitly selects another path.
- Test fixture: `tests/test_ps002.py` creates a unique `TemporaryDirectory` for every test and patches the app's `DB_PATH` to a SQLite file within it.
- Flask `TESTING` configuration is enabled for each fixture and restored to its previous value during teardown.
- The application has no test-only authorization bypass route or flag; tests use the same routes as the demo.

## Verification

- Added T-25, `test_fixture_isolated_from_demo_database`, which asserts testing mode is active in the fixture, the configured database is its temporary file, and that path is not the normal demo database.
- Full command: `.venv/bin/python -m unittest discover -s tests -v`
- Result: **25 tests passed**. Exact output: `test-results.txt`.

## Scope

This verifies local test/demo database separation and the absence of an explicit bypass in the inspected app. It is not a deployment security audit.
