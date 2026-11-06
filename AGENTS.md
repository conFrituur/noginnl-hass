# Repository Guidelines

## Project Structure & Module Organization

This repository contains the Nogin.nl Home Assistant custom integration. Implementation lives in `custom_components/nogin_nl/`: `api.py` handles API access, `coordinator.py` coordinates polling, `config_flow.py` manages setup, and `switch.py` exposes switch entities. Shared entity behavior, runtime data, and constants live in their respective modules. Integration metadata is in `manifest.json`; user-facing strings are in `translations/en.json`.

`config/configuration.yaml` configures the local Home Assistant instance. Development helpers live in `scripts/`, and GitHub Actions workflows live in `.github/workflows/`. No test directory or brand assets are currently included. Some documentation and configuration retain blueprint placeholders; use the actual domain `nogin_nl` for new integration code.

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
- `bash scripts/develop`: start Home Assistant with the repository's configuration and debug mode enabled.
- `bash scripts/lint`: format Python files and automatically fix lint findings; review the resulting diff.
- `python3 -m ruff check .`: run CI's lint checks without modifying files.
- `python3 -m ruff format . --check`: verify formatting without modifying files.

There is no separate build step. CI also runs Hassfest and HACS integration validation.

## Coding Style & Naming Conventions

Use four-space Python indentation, type annotations, and descriptive docstrings. Follow existing `snake_case` module/function names, `NoginNL` class prefixes, and uppercase constants. Preserve Home Assistant's asynchronous API and coordinator patterns.

`.ruff.toml` defines the active lint rules and formatter target. Use Ruff for formatting; the Black reference in `CONTRIBUTING.md` predates the current tooling.

## Testing Guidelines

No automated test suite, test runner dependency, or coverage threshold is configured. Validate changes in the local Home Assistant instance, exercising relevant setup, switch behavior, and API error handling. Record checks performed in the pull request. If adding automated tests, use `tests/test_*.py` and document the chosen runner and installation requirements.

## Commit & Pull Request Guidelines

Git history currently contains only `Initial commit`, so no established commit convention exists. Use concise, imperative subjects describing the change. Branch from `main`, update affected documentation, and submit a focused pull request explaining behavior changes, related issues, and validation results. Include screenshots when changing user-visible setup flows. Ensure lint, formatting, and integration validation pass.
