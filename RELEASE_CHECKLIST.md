# 1.9.x release preparation

The series develops on **release/1.9.x**, initially created from the **1.8.5** baseline (`490085d`). Native stack **#271** replaces the former grouping #262 and contains the same PRs in order: **#259 → #260 → #261 → #263 → #264 → #265 → #266**. Its destination is **release/1.9.x**; upper PRs retain their preceding branches as comparison bases. The existing **release/1.9.0** branch remains the source of preparation PR #266.

Merge reviewed work into **release/1.9.x** and publish prereleases from validated commits there. Promote the completed series to **main** through a separate reviewed release PR. Maintainer review and hardware validation remain part of release preparation.

## Development and prereleases

- [x] Review and understand the original quality-scale PRs and their AI assistance disclosures (maintainer confirmed on 2026-10-05).
- [ ] Review and understand the follow-up PR #270 port and the PR #268 regression tests.
- [ ] Verify all stack layers pass Tests, hassfest, and HACS validation.
- [ ] Verify the release passes the full test and quality checks on Home Assistant 2026.1.0 and 2026.9.4.
- [ ] Review the historical regression audit below and validate the remaining cloud and hardware cases.
- [ ] Verify a real account can authorize, configure options, reload, unload, and reauthenticate.
- [ ] Check existing entity IDs and user-customized names after upgrading from 1.8.x, including the sensor-to-number change for unbounded writable temperatures.
- [ ] Check new-device discovery, disconnected availability, and return of missing device data.
- [ ] Validate representative number, select, switch, thermostat, and supported water-heater writes with available account permissions.
- [ ] Verify an invalid or rejected write reports an error without displaying a successful target.
- [ ] Inspect downloaded diagnostics for identifying information before sharing.
- [ ] Confirm the Home Assistant 2026.1.0 minimum and documented upgrade behavior.
- [ ] Merge the reviewed stack into **release/1.9.x** using GitHub's native stack merge and the merge-commit method to retain commit history.
- [ ] Set the next prerelease version, such as **1.9.0-rc1**, in **custom_components/myuplink/manifest.json** and **pyproject.toml**, regenerate **uv.lock** with `uv lock`, and record the prerelease notes in **CHANGELOG.md**.
- [ ] Run the complete checks below on the versioned prerelease commit in both supported environments.
- [ ] Create the prerelease tag from that validated **release/1.9.x** commit, using the project's existing tag style, for example **1.9.0-rc1**.
- [ ] Publish the GitHub release with **Set as a pre-release** enabled and leave the current stable latest release selected; verify HACS users can opt into the prerelease.

## Stable release

- [ ] Set the final **1.9.0** version in the manifest and project metadata on **release/1.9.x**, and regenerate **uv.lock**.
- [ ] Update the changelog's unreleased heading with the release date.
- [ ] Validate **release/1.9.x** and review the complete promotion diff against **main**.
- [ ] Merge a reviewed release PR from **release/1.9.x** into **main** with a merge commit.
- [ ] Run the complete test, typing, translation, coverage, and lint checks on the merged release commit.
- [ ] Create tag **1.9.0** from that validated **main** commit, following the existing tag naming convention.
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

## Recent issues and contributor pull requests

Review date: **2026-10-05**. The rebased stack is based on **1.8.5** (`490085d`), which includes contributor [PR #268](https://github.com/jaroschek/home-assistant-myuplink/pull/268). All seven existing stack PRs passed Tests, hassfest, and HACS validation at their current published tips.

### PR #270 and the 1.8.6 candidate

[PR #270](https://github.com/jaroschek/home-assistant-myuplink/pull/270) is a narrow correction suitable for a **1.8.6** release: writable, finite numeric °C/°F points without bounds become number controls. Existing overrides, permissions, switch/select rules, native write values, and scaled steps retain priority. It directly addresses the reported iGate 2.0 heat/cool payloads in [#234](https://github.com/jaroschek/home-assistant-myuplink/issues/234). The original 28 tests pass on both Home Assistant 2026.1.0/Python 3.13.2 and 2026.9.4/Python 3.14.5 with network sockets blocked. Pending fork hassfest/HACS runs were approved during this review and passed.

The PR remains draft, awaiting real-device feedback. Its branch, contents, and draft state were left unchanged. Before releasing 1.8.6, review the documented **0–100 native-unit default range**, reload/discovery behavior, and the change from sensor to number entity. The old sensor can remain unavailable and its automation references need updating. API acceptance of physical iGate writes remains a device-validation item.

The fix is ported independently into the final **1.9 release layer (#266)**. Its tests use the 1.9 fixtures and coordinator, have annotated parameters, and cover invalid readings, permissions, overrides, platform priority, scaled steps, discovery without duplicates, and native writes. Five tests failed against the existing 1.9 classifier before the port. The contributor's original commit is not merged into the stack, keeping #270 independent for its later 1.8.x merge. Follow-up commits preserve all published stack history.

PR #268 already reaches every stack layer through the 1.8.5 baseline. Additional select regressions check mismatched display text, integer-valued floats, string enum codes, the first enum option, and fallback values. No 1.8.6 merge, version bump, tag, release, or public issue/PR comment was made during this review.

The updated 1.9 candidate passes **345 tests in each supported environment**. Combined statement/branch coverage is **99.68%** on 2026.1.0 and **99.67%** on 2026.9.4; every integration module exceeds 95%, and API/config-flow coverage is 100%. Strict mypy passes in both environments. Repository-wide lint/format hooks and translation synchronization also pass.

### Current issue coverage

| Issue | 1.9 assessment | Evidence and remaining work |
| --- | --- | --- |
| [#234](https://github.com/jaroschek/home-assistant-myuplink/issues/234) — iGate setpoints without bounds | Addressed by this port in #266 | The supplied heat/cool metadata now discovers number controls; [temperature regressions](tests/test_unbounded_temperature.py) verify classification, permissions, values, steps and writes. Validate accepted temperatures on the reporter's hardware before calling the physical controls confirmed. |
| [#267](https://github.com/jaroschek/home-assistant-myuplink/issues/267) — five-minute unavailability after a write | Partly addressed; faster retry remains open | #261 removes the whole-account 30-second timeout and retains per-request timeouts; #265 reduces requests through metadata caches. Entity writes already request a coordinator refresh. A genuine timeout/network/5xx failure still raises UpdateFailed without retry_after and waits for the configured scan interval, normally 300 seconds. No delayed retry or stale-success fallback is implemented; authoritative refreshes can still make entities unavailable after a write. |
| [#254](https://github.com/jaroschek/home-assistant-myuplink/issues/254), [#241](https://github.com/jaroschek/home-assistant-myuplink/issues/241) — polling dropouts | Mitigated; cloud recovery unconfirmed | #261 provides per-request timeouts, quota backoff and reauthentication; #265 caches metadata; #266 isolates optional subscription outages. The disconnected-device option only changes availability after a successful cloud refresh. It does not mask failed account polls or prove the reported outages resolved. |
| [#255](https://github.com/jaroschek/home-assistant-myuplink/issues/255) — polling, reconfigure callback 500, reload hang | Partly addressed | Polling benefits from #261/#265/#266. Normal OAuth reconfigure and cancellation/unload paths are tested, but the UnknownFlow exception in Home Assistant's callback handler and the reported reload during setup_retry are not reproduced or specifically corrected. Capture the original callback/reload sequence before claiming either solved. |
| [#253](https://github.com/jaroschek/home-assistant-myuplink/issues/253) — simultaneous timeout outage | External or unconfirmed | Several reporters recovered on the same day without an integration change. The 1.9 reliability changes mitigate request failures; the discussion does not establish a code defect or verified permanent fix. |
| [#256](https://github.com/jaroschek/home-assistant-myuplink/issues/256) — missing schedule-blocking settings | Not specifically solved | No schedule editor or model-specific schedule mapping is added. Generic discovery, additional point IDs, overrides and raw actions remain available when the public API exposes the settings. A redacted point payload and expected IDs are needed to identify a concrete integration fix. |
| [#220](https://github.com/jaroschek/home-assistant-myuplink/issues/220) — pool reading/control; latest comment 2026-09-29 | Not specifically solved | The recent SMO40/AMS10 report confirms readable state but rejected writes. #261 reports failures explicitly; it does not add a pool-specific endpoint or overcome cloud permissions. Obtain the point ID, metadata and write response. The provider's web portal may use a different API contract. |
| [#245](https://github.com/jaroschek/home-assistant-myuplink/issues/245) — deprecated update listener | Already addressed in 1.8.4 and retained | Maintainer PR #257 migrated option reloads to OptionsFlowWithReload. [Options and OAuth update tests](tests/test_config_flow.py) retain reload-on-change and token-refresh-without-reload behavior throughout the rebased stack. |
| [#242](https://github.com/jaroschek/home-assistant-myuplink/issues/242) — device-relative names after migration | Naming addressed by #260/#263/#264; migration caveat | Device-relative names and registry customizations are covered by [discovery tests](tests/test_discovery.py). The built-in integration uses device-point unique IDs while this custom integration retains myuplink_device_point IDs; there is no migration that reconnects old built-in registry entries automatically. |
| [#222](https://github.com/jaroschek/home-assistant-myuplink/issues/222) — zone setpoints sent to the points endpoint | Zone controls already supported; retained and improved | Zone climate entities and the raw zone action use devices/{deviceId}/zones/{zoneId}, introduced in 1.8. #264 selects the correct heating/cooling/shared field and [climate tests](tests/test_climate.py) protect writes and failed-state preservation. Generic parameter actions still use the points endpoint; there is no automatic rerouting of arbitrary point writes. |

Do not close the partially addressed or unconfirmed reports solely because the 1.9 tests pass. The next reliability change for #267 should use a bounded early retry that respects API backoff; it is separate from the temperature-discovery port.

## Historical regression audit

Audit date: **2026-10-02**. Reviewed every closed issue and every merged pull request authored by someone other than the maintainer in [jaroschek/home-assistant-myuplink](https://github.com/jaroschek/home-assistant-myuplink). The inventory contains **54 closed issues** and **23 merged contributor PRs**: 19 from people and 4 from Dependabot, selected from 129 merged PRs in total. Review included reports, resolution comments, linked fixes, PR discussion and patches. Maintainer PRs were traced where they explain a resolution or supersede contributor changes.

The comparison uses the **1.8.4 main baseline** (`5a62a3b`) and the **1.9 release candidate before this audit** (`6d5d0d5`), followed by the corrections in [release PR #266](https://github.com/jaroschek/home-assistant-myuplink/pull/266). Closed does not necessarily mean fixed: #106 was closed as not planned, and several reports have no confirmed resolution.

Two regressions introduced during the 1.9 changes were corrected:

1. Subscription lookup had been narrowed to tolerating HTTP 500 alone. Other 5xx responses, connection errors, timeouts and invalid JSON/content type could invalidate otherwise healthy point reads, weakening [PR #213](https://github.com/jaroschek/home-assistant-myuplink/pull/213). These failures now retain known permissions, leave failures uncached for retry, and warn once. Authentication failures, quota backoff and cancellation still propagate. New tests reproduced the failures before the correction.
2. Translation cleanup removed **69 existing API-label aliases**, 46 Norwegian and 23 German. Because entity states still use API text, these aliases are required to display the old localized labels. They have been restored without changing states, options or unique IDs. All historical numeric enum codes were also compared against contributor merge commits; none were removed.

### Meaning of the outcomes

**Covered** means the relevant integration behavior is retained and covered by automated tests or a direct comparison, as described in the row. **Corrected** marks behavior restored during this audit. **Documented** means the documented remedy or repository setup remains available. **External** means the resolution or limitation belongs to cloud data, firmware, hardware or another integration. **Unconfirmed** means the closed discussion does not establish a reproducible fix; any passing substitute scenario is named explicitly. Automated tests use mocked cloud responses and reported metadata, with synthetic values where a complete original payload is unavailable. They do not certify the current behavior of a physical device or subscription.

### Validation references

| Reference | Evidence |
| --- | --- |
| H | [Historical regression tests](tests/test_historical_regressions.py): subscription faults, unchanged readings, statistics metadata, CTC partial enums, scaled bounds/writes, NIBE/Høiax overrides, subscription controls, translation keys/labels, startup pacing, two-system ownership and cancellation. |
| A | [API snapshot and cache tests](tests/test_api.py): complete snapshots, name cleanup, optional endpoint opt-outs, whitelist/additional IDs, caches and account isolation. |
| E | [API error tests](tests/test_api_errors.py): quota headers/backoff, request timeouts, authentication, failed writes, permissions during subscription outages and recovery. |
| C | [Coordinator tests](tests/test_coordinator.py): polling failures, backoff, reauthentication and recovery logging. |
| D | [Discovery](tests/test_discovery.py), [optional discovery](tests/test_optional_discovery.py) and [point discovery](tests/test_point_discovery.py): disappearing/returning data, new entities and custom registry names/IDs. |
| P | [Point discovery tests](tests/test_point_discovery.py): exact and renamed duplicate points within a response and across additional-point requests, normalized integer/string IDs, and platform stability until reload. |
| M | [Sensor tests](tests/test_sensor.py) and translation synchronization: normalized units, statistics metadata, API enum states and localized names. Historical numeric state keys were compared against merged contributor versions and the 1.8.4 baseline. |
| N | [Entity tests](tests/test_entity.py) and [registry customization test](tests/test_discovery.py): stable unique IDs, relative names and user customizations. |
| O | [Initial OAuth flows](tests/test_initial_flow.py), [configuration/OAuth updates](tests/test_config_flow.py) and [setup tests](tests/test_init.py): scopes, reauth, reconfigure, options, token refresh without reload and unload. |
| R | [Raw action tests](tests/test_services.py): registry/account routing, IDs independent of fetched point lists, administrator enforcement and registration lifecycle. |
| T | [Control tests](tests/test_controls.py), [thermostat tests](tests/test_climate.py) and [action tests](tests/test_actions.py): number/select/switch, smart-home modes, water-heater bounds/operations and failed writes. |

### Closed issues

| Issue | Outcome | Assessment and evidence |
| --- | --- | --- |
| [#247](https://github.com/jaroschek/home-assistant-myuplink/issues/247) | Covered | The fixed 2.4-second startup delay stays removed with quota headroom. A six-device, 22-request snapshot does not sleep; quota backoff remains tested. H, E, C. |
| [#246](https://github.com/jaroschek/home-assistant-myuplink/issues/246) | Covered | Same startup family as #247; the smart-home-zone opt-out remains available and skips the endpoint. H, A. |
| [#238](https://github.com/jaroschek/home-assistant-myuplink/issues/238) | Covered | W and kW power measurements retain a measurement state class. The reported 25165 ID is included in a synthetic kW case; its real-device metadata still needs validation. H, M. See the separate Ws upgrade caveat below. |
| [#218](https://github.com/jaroschek/home-assistant-myuplink/issues/218) | Unconfirmed | Closure has no resolution discussion. Default writable controls and platform stability pass tests, but the original account and missing controls cannot be certified. H, P. |
| [#212](https://github.com/jaroschek/home-assistant-myuplink/issues/212) | Corrected | The reported HTTP 500 case remained handled. The 1.9 changes had narrowed PR #213 and made other temporary subscription failures invalidate healthy readings; the broader fallback is restored. H, E, A. |
| [#203](https://github.com/jaroschek/home-assistant-myuplink/issues/203) | Covered | The removed homeassistant.backports.enum import is absent. Standard-library StrEnum imports succeed in both supported environments. |
| [#196](https://github.com/jaroschek/home-assistant-myuplink/issues/196) | Covered | Writable-without-subscription remains enabled by default and actual writable-point requests succeed without Manage in the mocked API. H. |
| [#191](https://github.com/jaroschek/home-assistant-myuplink/issues/191) | Covered | The subscription override remains available; rejected writes report an error without invalidating other sensor readings. Actual cloud permission still depends on the account. H, E. |
| [#189](https://github.com/jaroschek/home-assistant-myuplink/issues/189) | Documented | The report used an obsolete 1.1.4 install. The supported 1.9 environment uses standard-library StrEnum; upgrade requirements are documented. Both supported test environments import successfully. |
| [#186](https://github.com/jaroschek/home-assistant-myuplink/issues/186) | Covered | Raw services use config-entry runtime_data after the 1.6 migration, select the owning account, and remain registered after unload. R. |
| [#185](https://github.com/jaroschek/home-assistant-myuplink/issues/185) | Unconfirmed | The only resolution is that entities came back online. No reproducible cause or integration fix was recorded; simulated disappearance and recovery pass. D, C. |
| [#183](https://github.com/jaroschek/home-assistant-myuplink/issues/183) | Unconfirmed | Closed without a resolution or reproducible crash report. Setup failures and authentication handling are covered, but this particular failure is unverified. O, C. |
| [#169](https://github.com/jaroschek/home-assistant-myuplink/issues/169) | External | The Manage subscription had expired. The integration cannot renew it or guarantee cloud permission; write failures are now visible. H, E. |
| [#166](https://github.com/jaroschek/home-assistant-myuplink/issues/166) | Covered | Manufacturer kWH is normalized to kWh with ENERGY/TOTAL metadata and the supplied reading is not rescaled. H, M. |
| [#161](https://github.com/jaroschek/home-assistant-myuplink/issues/161) | External | Discussion identified an old backup using the different Nibe Uplink integration. The custom myUplink reading for point 40004 is preserved without double scaling. H. |
| [#159](https://github.com/jaroschek/home-assistant-myuplink/issues/159) | Covered | The raw parameter action still sends an ID without requiring that point to be in the fetched parameter list. API requests and account routing remain covered. R. |
| [#153](https://github.com/jaroschek/home-assistant-myuplink/issues/153) | Covered | All existing smart-home modes, system/device association, and mode writes remain supported. Manufacturer acceptance and the reported cloud delay require a real account. H, T, A. |
| [#147](https://github.com/jaroschek/home-assistant-myuplink/issues/147) | External | Discussion traced the 0.1 A values to hardware/current-probe data. The integration preserves that API reading and does not multiply it by scaleValue. H. |
| [#139](https://github.com/jaroschek/home-assistant-myuplink/issues/139) | Unconfirmed | Closed without a resolution for replacement credentials. Current reconfiguration and the Application credentials procedure are documented and tested where automated. O. |
| [#124](https://github.com/jaroschek/home-assistant-myuplink/issues/124) | Covered | The parameter whitelist still limits requests; additional IDs are combined into a single filtered request. The API determines how many points exist. A. |
| [#122](https://github.com/jaroschek/home-assistant-myuplink/issues/122) | Covered | The 11 NIBE switch overrides from PR #125 still work with empty enums and absent min/max metadata, including 47669 and 47771. H. |
| [#120](https://github.com/jaroschek/home-assistant-myuplink/issues/120) | External | Firmware/cloud data changed; no integration correction was recorded. Dynamic discovery handles newly returned points, but the historical manufacturer payload cannot be reproduced. D. |
| [#115](https://github.com/jaroschek/home-assistant-myuplink/issues/115) | Covered | The deprecated Home Assistant StrEnum dependency stays replaced with enum.StrEnum; the entire suite imports on both supported runtimes. |
| [#111](https://github.com/jaroschek/home-assistant-myuplink/issues/111) | External | Empty systems and MHI/Hydrolution public-API restrictions remained unresolved by integration code. Firmware updates and alternate Modbus solutions in the discussion are not evidence of a myUplink fix. D covers empty/returning snapshots only. |
| [#106](https://github.com/jaroschek/home-assistant-myuplink/issues/106) | Unconfirmed | Closed as not planned after an apparent local Home Assistant problem. Stable IDs, renamed-point deduplication, and repeated discovery pass; closure is not proof of a code fix. P, D. |
| [#105](https://github.com/jaroschek/home-assistant-myuplink/issues/105) | Covered | The API later exposed the missing points. Additional point requests, overrides, and discovery remain functional, but unavailable cloud points cannot be invented. A, D, H. |
| [#98](https://github.com/jaroschek/home-assistant-myuplink/issues/98) | External | The supply-air point was not exposed by the manufacturer API. This remains a documented API limitation rather than a fixed integration defect. |
| [#97](https://github.com/jaroschek/home-assistant-myuplink/issues/97) | Unconfirmed | Closed without discussion. A new two-system test verifies distinct ownership for identical point IDs on different devices, but the original two-location account is unverified. H. |
| [#96](https://github.com/jaroschek/home-assistant-myuplink/issues/96) | Covered | The historical generic entry-update listener caused hourly OAuth reloads. It remains removed; the real OAuth2Session refresh updates the stored token without reloading. O. |
| [#84](https://github.com/jaroschek/home-assistant-myuplink/issues/84) | Covered | Rate-limit pacing no longer shares a global 30-second poll timeout. Shutdown cancellation propagates and releases the request lock; it is not silently swallowed. H, E, C. |
| [#77](https://github.com/jaroschek/home-assistant-myuplink/issues/77) | Covered | Lowercase off/on labels on point 50005 still produce a switch, preserving PR #78 after its original NameError was fixed. H. |
| [#62](https://github.com/jaroschek/home-assistant-myuplink/issues/62) | Covered | CTC point 62004 with minute units and a partial Blocked enum remains a numeric duration at 180 minutes; no enum-state exception occurs. H. |
| [#55](https://github.com/jaroschek/home-assistant-myuplink/issues/55) | Covered | The same CTC point remains numeric at zero minutes even when the enum only contains Blocked. H. |
| [#51](https://github.com/jaroschek/home-assistant-myuplink/issues/51) | Unconfirmed | Closed without a resolution. Credential replacement remains documented through Home Assistant Application credentials and reconfiguration. O. |
| [#50](https://github.com/jaroschek/home-assistant-myuplink/issues/50) | Documented | The reporter recovered SMO20 data by clearing obsolete credentials and authorizing again. The documented cleanup/reauthorization route is retained; cloud recovery is not simulated. O. |
| [#49](https://github.com/jaroschek/home-assistant-myuplink/issues/49) | Documented | Removing stale application credentials and entering the correct Client Identifier/Secret remains documented. Account login and application credentials are distinguished. |
| [#40](https://github.com/jaroschek/home-assistant-myuplink/issues/40) | Covered | The 44703 binary override and frequency metadata remain present; a synthetic reported frequency point retains statistics. Missing cloud points are discovered when returned. H, D, M. |
| [#39](https://github.com/jaroschek/home-assistant-myuplink/issues/39) | Documented | The working Application credentials cleanup procedure remains documented. Explicit account reconfiguration and reauthentication flows are covered. O. |
| [#38](https://github.com/jaroschek/home-assistant-myuplink/issues/38) | Documented | The resolution was the callback URL rather than the application name. The exact required callback remains in the setup instructions. |
| [#37](https://github.com/jaroschek/home-assistant-myuplink/issues/37) | External | F730 writable metadata and API support were restricted upstream. Expert overrides and raw actions remain available, but they cannot force the cloud to accept a write. H, R. |
| [#32](https://github.com/jaroschek/home-assistant-myuplink/issues/32) | Documented | Setup still requires the exact https://my.home-assistant.io/redirect/oauth callback; it is not described as optional. |
| [#30](https://github.com/jaroschek/home-assistant-myuplink/issues/30) | Documented | Stored credentials can be removed through Home Assistant Application credentials; the troubleshooting procedure remains in the README. |
| [#24](https://github.com/jaroschek/home-assistant-myuplink/issues/24) | Documented | The original unsupported Python 3.10/StrEnum problem is superseded by the declared Home Assistant 2026.1 minimum. Both supported Python/HA combinations pass. |
| [#23](https://github.com/jaroschek/home-assistant-myuplink/issues/23) | Documented | The confirmed callback/credentials cleanup procedure remains explicit in the README. |
| [#21](https://github.com/jaroschek/home-assistant-myuplink/issues/21) | Covered | Reported 47753 bounds 50–300 and step 5 with scale 0.1 become 5–30 °C and step 0.5. A write sends 18.5 directly, without double scaling. H. |
| [#20](https://github.com/jaroschek/home-assistant-myuplink/issues/20) | Documented | The restored-installation problem was resolved by removing stale integration/application credentials and reauthorizing. Reauth/reconfigure are covered, but a real restore is not reproduced. O. |
| [#19](https://github.com/jaroschek/home-assistant-myuplink/issues/19) | Covered | offline_access remains a required scope, startup validates scopes, and the real Home Assistant OAuth refresh path updates the token without reloading. O. |
| [#18](https://github.com/jaroschek/home-assistant-myuplink/issues/18) | External | Stale heat-meter timestamps were corrected by manufacturer firmware 9586R4. The integration preserves energy values; it cannot refresh stale cloud measurements. H, M. |
| [#15](https://github.com/jaroschek/home-assistant-myuplink/issues/15) | Covered | The unused zone-call fix is superseded by configurable, functional zone support; disabling it skips requests. Quota headroom avoids per-request sleep and network timeouts apply to individual requests. H, A, E. |
| [#14](https://github.com/jaroschek/home-assistant-myuplink/issues/14) | Documented | The official HACS default integration registry still lists jaroschek/home-assistant-myuplink on the audit date. HACS installation and validation remain configured. |
| [#12](https://github.com/jaroschek/home-assistant-myuplink/issues/12) | Documented | Invalid application credentials/callback were resolved by cleanup and replacement; both steps remain documented. |
| [#10](https://github.com/jaroschek/home-assistant-myuplink/issues/10) | Covered | The historical fix removed soft hyphens and used string translation keys. Both remain: all 13 known enum IDs have string keys, and API-name cleanup is covered. H, A. |
| [#9](https://github.com/jaroschek/home-assistant-myuplink/issues/9) | External | The myUplink developer portal once rejected the callback because of its own URL validation. That was corrected upstream; current portal behavior requires manual registration. |
| [#1](https://github.com/jaroschek/home-assistant-myuplink/issues/1) | Documented | The confirmed new-application/credential cleanup uses the exact callback and remains documented. Later thermostat support is separately covered; original account setup still needs real authorization. O, T. |

### Merged pull requests from other authors

| Pull request | Author | Outcome | Assessment and evidence |
| --- | --- | --- | --- |
| [#249](https://github.com/jaroschek/home-assistant-myuplink/pull/249) | dependabot[bot] | Covered | actions/checkout@v7 remains in HACS and hassfest workflows; the CI runs validate these workflows. |
| [#248](https://github.com/jaroschek/home-assistant-myuplink/pull/248) | lbjordan | Covered | Quota-headroom pacing and tolerant partial/header parsing remain. The multi-device startup, low-quota pacing, and retry-window tests protect the fix. H, E, C. |
| [#219](https://github.com/jaroschek/home-assistant-myuplink/pull/219) | backisen | Covered | All original numeric state codes for CTC 62005, 62017, and 62246 remain in strings.json and synchronized English translations. API text states and string translation keys remain stable. H, M. |
| [#213](https://github.com/jaroschek/home-assistant-myuplink/pull/213) | jgmGit | Corrected | Restore optional subscription fault isolation for all 5xx responses, transport/timeouts, invalid JSON and content type. Keep authentication, rate limits and cancellation visible. H, E, A. |
| [#210](https://github.com/jaroschek/home-assistant-myuplink/pull/210) | dependabot[bot] | Covered | The checkout v6 bump is superseded by the contributor/bot update to v7, which remains installed. |
| [#207](https://github.com/jaroschek/home-assistant-myuplink/pull/207) | astrandb | Covered | The temporary brands exemption was superseded by maintainer PR #250 adding local brand assets and restoring validation. Those assets remain; HACS validation is enabled. |
| [#205](https://github.com/jaroschek/home-assistant-myuplink/pull/205) | dependabot[bot] | Covered | The checkout v5 bump is superseded by v7; its dependency-update intent remains satisfied. |
| [#193](https://github.com/jaroschek/home-assistant-myuplink/pull/193) | ak6i | Covered | The writable-without-subscription option, enabled default, read-only opt-out, and localized option labels remain. H, O, T. |
| [#192](https://github.com/jaroschek/home-assistant-myuplink/pull/192) | ak6i | Covered | Manage subscription detection and HTTP 204 behavior remain. PR #193 and the later maintainer fix permit writes without a subscription where the API supports them. H, A. |
| [#165](https://github.com/jaroschek/home-assistant-myuplink/pull/165) | dependabot[bot] | Covered | The checkout v4 bump is superseded by v7. |
| [#125](https://github.com/jaroschek/home-assistant-myuplink/pull/125) | woopstar | Covered | All 11 added NIBE switch overrides and Danish state codes remain. Legacy read-only overrides, localized option support, and API text states are retained. H, M, O. |
| [#108](https://github.com/jaroschek/home-assistant-myuplink/pull/108) | elden1337 | Covered | Device-relative names and stable myuplink_device_point IDs remain. A dictionary keyed by normalized point ID replaces the old seen set keyed by (ID, name), matching the entity unique ID. Exact/renamed duplicates and duplicate IDs across additional-point requests produce one point. Real registry tests preserve the entity ID and custom name after an API rename. P, D, N. |
| [#102](https://github.com/jaroschek/home-assistant-myuplink/pull/102) | thytterdal | Covered | Text-valued non-enum point 513 (model_id) is still skipped while other Høiax sensors load. H. |
| [#78](https://github.com/jaroschek/home-assistant-myuplink/pull/78) | grumlu | Covered | Off/on classification ignores label capitalization and uses enum codes. The historical lowercase 50005 case stays a switch. H. |
| [#66](https://github.com/jaroschek/home-assistant-myuplink/pull/66) | imsh | Covered | Temperature sensors retain MEASUREMENT and long-term-statistics eligibility. Numeric readings are not double scaled. H, M. |
| [#57](https://github.com/jaroschek/home-assistant-myuplink/pull/57) | 7RST1 | Documented | README troubleshooting still covers invalid_request, unauthorized_client, stale credentials, callback setup and inspection of raw point data through Swagger. |
| [#13](https://github.com/jaroschek/home-assistant-myuplink/pull/13) | 7RST1 | Documented | The contributed example-device-view.png remains unchanged from 1.8.4 and is still embedded in the README. |
| [#11](https://github.com/jaroschek/home-assistant-myuplink/pull/11) | 7RST1 | Covered | Number/select/switch and 18760NE water-heater controls remain, including scaled bounds, modes, read-only overrides and all required heater points. Unsupported/missing readings fail safely. H, T, D. |
| [#7](https://github.com/jaroschek/home-assistant-myuplink/pull/7) | 7RST1 | Covered | All contributed Høiax numeric state codes and English/Norwegian labels remain. 1.8 text aliases used for existing API labels were restored after the 1.9 cleanup. H, M. |
| [#5](https://github.com/jaroschek/home-assistant-myuplink/pull/5) | 7RST1 | Covered | A one-word Høiax device name remains a model with manufacturer=None. H. |
| [#4](https://github.com/jaroschek/home-assistant-myuplink/pull/4) | 7RST1 | Covered | Høiax 505/506 remain binary sensors and writable 600 remains a switch when provided boolean enum metadata. H. |
| [#3](https://github.com/jaroschek/home-assistant-myuplink/pull/3) | 7RST1 | Covered | Norwegian config text and all original numeric NIBE state codes remain in the modern translation files. Existing API-label translations are restored. H, M, O. |
| [#2](https://github.com/jaroschek/home-assistant-myuplink/pull/2) | 7RST1 | Documented | The custom_components/myuplink layout, installation instructions, callback guidance and HACS configuration remain; documentation has been expanded. |

### Remaining release validation

On 2026-10-02, the audited candidate passed **310 tests in each environment**: Home Assistant 2026.1.0/Python 3.13.2 and Home Assistant 2026.9.4/Python 3.14.5. Combined statement/branch coverage was **99.68%** and **99.67%**, respectively; every integration module exceeded 95%, and API and config-flow coverage were 100%. Strict mypy, translation synchronization, lint/format hooks and local hassfest also passed. GitHub repeats the release checks on PR #266; the current candidate's validation is recorded in the recent-review section above.

The confirmed manufacturer/cloud limitations in #111, #98, #37, #147 and #18 cannot be established as currently solved without their real accounts, API access or hardware. Likewise, closed reports #218, #185, #183, #139, #106, #97 and #51 lack a confirmed historical fix. Their automated substitute scenarios are identified above; these reports should not be advertised as verified hardware fixes.

There is one deliberate upgrade change with a statistics consequence: **Ws points were previously labelled as W power measurements**, including a measurement state class. The 1.9 candidate keeps the manufacturer unit Ws and leaves its quantity/state class unclassified. It therefore **does not produce new long-term statistics for those points**. Existing records are not converted or deleted. Power points with W/kW units and temperature points covered by #238 and PR #66 retain their statistics metadata, as do recognized energy points. Validate the affected device's actual quantity before choosing a conversion or a statistics migration; the compatibility notes now state this consequence explicitly.

The [official HACS default registry](https://github.com/hacs/default/blob/master/integration) still contains this custom repository on the audit date, confirming the continuing result of #14. Current HACS/hassfest workflows retain checkout v7 and validate the local brand assets supplied after PR #207.

The release checklist above remains the place to record real-account authorization, supported-device writes, upgrade behavior and maintainer review before release. This audit does not mark those manual checks complete.
