# 1.9.0 release preparation

The release files are prepared on a draft PR. Complete the maintainer review and hardware validation before merging and publishing.

- [ ] Review and understand each quality-scale PR and its AI assistance disclosure.
- [ ] Verify all stack layers pass Tests, hassfest, and HACS validation.
- [ ] Verify the release passes the full test and quality checks on Home Assistant 2026.1.0 and 2026.9.4.
- [ ] Verify a real account can authorize, configure options, reload, unload, and reauthenticate.
- [ ] Check existing entity IDs and user-customized names after upgrading from 1.8.4.
- [ ] Check new-device discovery, disconnected availability, and return of missing device data.
- [ ] Validate representative number, select, switch, thermostat, and supported water-heater writes with available account permissions.
- [ ] Verify an invalid or rejected write reports an error without displaying a successful target.
- [ ] Inspect downloaded diagnostics for identifying information before sharing.
- [ ] Confirm the Home Assistant 2026.1.0 minimum and documented upgrade behavior.
- [ ] Merge the reviewed stack from the bottom up.
- [ ] Update the changelog's unreleased heading with the release date.
- [ ] Run the complete test, typing, translation, coverage, and lint checks on the merged release commit.
- [ ] Create tag **1.9.0** from that validated commit, following the existing tag naming convention.
- [ ] Publish the GitHub release with the changelog notes and confirm HACS offers the new version.

Local automated checks:

~~~sh
script/setup
uv run --no-sync prek run --all-files
uv run --no-sync mypy
uv run --no-sync python3 script/sync_translations.py --check
uv run --no-sync pytest tests --cov --cov-report=term-missing --cov-report=xml --cov-report=json
uv run --no-sync python3 script/check_coverage.py
~~~
