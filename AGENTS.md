# Repository Guidelines

## Project Structure & Module Organization

This repository contains the Nogin.nl Home Assistant custom integration. Implementation lives in `custom_components/nogin_nl/`: `api.py` handles API access, `coordinator.py` coordinates polling, `config_flow.py` manages setup, and `switch.py` exposes switch entities. Shared entity behavior, runtime data, and constants live in their respective modules. Integration metadata is in `manifest.json`; user-facing strings are in `translations/en.json`.

`config/configuration.yaml` configures the local Home Assistant instance. Development helpers live in `scripts/`, tests in `tests/`, brand assets in `custom_components/nogin_nl/brand/`, and GitHub Actions workflows in `.github/workflows/`. Some documentation and configuration retain blueprint placeholders; use the actual domain `nogin_nl` for new integration code.

# API nogin.nl

The REST Api is at `api.nogin.nl`

it has 3 endpoints

GET /persons
which returns all persons with status:

`
[
  {"name": "sjaak", "isNogInNL": true},
  {"name": "harrie", "isNogInNL": false}
]
`
GET /persons/{name}
which returns a single person
`
{"name": "sjaak", "isNogInNL": true}
`

PATCH /persons/{name}
to update the `isNogInNL` bool of a person

request body:
`{"isNogInNL": false}`
response:
`{"name": "sjaak", "isNogInNL": false}`

## Build, Test, and Development Commands

Use Python 3.14, matching CI and the Ruff target. From the repository root, with a virtual environment activated:

- `bash scripts/setup`: install common and development requirements, including Home Assistant and Ruff.
- `python3 -m pip install -r requirements_test.txt`: install development and test dependencies.
- `python3 -m pytest`: run the full test suite with integration coverage.
- `python3 -m pytest tests/test_config_flow.py`: run configuration flow tests only.
- `bash scripts/develop`: start Home Assistant with the repository's configuration and debug mode enabled.
- `bash scripts/lint`: format Python files and automatically fix lint findings; review the resulting diff.
- `python3 -m ruff check .`: run CI's lint checks without modifying files.
- `python3 -m ruff format . --check`: verify formatting without modifying files.

There is no separate build step. CI runs pytest, Ruff, Hassfest, and HACS integration validation.

## Coding Style & Naming Conventions

Use four-space Python indentation, type annotations, and descriptive docstrings. Follow existing `snake_case` module/function names, `NoginNL` class prefixes, and uppercase constants. Preserve Home Assistant's asynchronous API and coordinator patterns.

`.ruff.toml` defines the active lint rules, test-specific exceptions, and formatter target. Use Ruff for formatting.

## Testing Guidelines

Use pytest with `pytest-homeassistant-custom-component`. Keep its pinned version (`0.13.340`) aligned with Home Assistant (`2026.6.4`); upgrade them together. Newer Home Assistant releases use the official `pytest-homeassistant` package, which must not be installed alongside the older plugin.

Name tests `tests/test_*.py`. Shared fixtures in `tests/conftest.py` enable custom integrations, create mock configuration entries, and mock API clients. Cover setup/options flows, selection changes, switch writes, polling/unload, and API error recovery through Home Assistant's fixtures. Mock all external requests; never change real API statuses in tests.

`pytest.ini` enables async tests, disables network sockets except Unix sockets, and reports integration line coverage. Maintain the current full line coverage when changing behavior; no minimum threshold is enforced automatically. `.github/workflows/test.yml` runs the suite on pushes and pull requests to `main`. Supplement automated tests with local Home Assistant checks when UI behavior changes, and record validation in the pull request.

## Commit & Pull Request Guidelines

Git history currently contains only `Initial commit`, so no established commit convention exists. Use concise, imperative subjects describing the change. Branch from `main`, update affected documentation, and submit a focused pull request explaining behavior changes, related issues, and validation results. Include screenshots when changing user-visible setup flows. Ensure tests, lint, formatting, and integration validation pass.
