# Changelog

## 1.9.0 (unreleased)

This series improves the custom integration against Home Assistant's Integration Quality Scale. The checklist is a project self-assessment; it does not represent an official Home Assistant tier award.

### Compatibility and upgrade notes

- Supports Home Assistant **2026.1 and newer**. HACS declares 2026.1.0 as the minimum, and CI checks January and September releases. Home Assistant provides the required Python runtime.
- Existing entity unique IDs, registry entity IDs, and names customized in Home Assistant are preserved for entities that retain their platform. Default names now follow device-relative naming and translated fixed labels.
- Writable numeric temperature points without minimum or maximum bounds, including iGate 2.0 heat/cool setpoints, now become number controls. Their default range is 0–100 in the native temperature unit, rather than manufacturer-specified limits. Reload to discover them; an existing sensor may remain unavailable, and automations referring to it need the new number entity.
- Notification sensors are diagnostic and disabled by default when newly created. Existing enabled entities retain their setting. Enable a new notification entity manually if wanted.
- Recognized duration and flow-rate unit aliases are normalized. Ambiguous manufacturer units such as **Ws** remain unclassified. Previously, Ws points were labelled as W power measurements; 1.9 retains Ws and does not generate new long-term statistics for those points until their meaning is established. Existing recorded statistics are not converted or deleted.
- Raw parameter and zone actions require an administrator when called by a signed-in user. Home Assistant automations can still call them.
- Failed writes now raise translated errors instead of silently appearing successful.

### Reliability and controls

- Register administrator actions when the integration loads, including when an account cannot load, and keep them available after account unload.
- Retry network and server failures, honor quota headers and Retry-After, and start reauthentication for expired authorization.
- Keep working point reads and known subscription permissions during temporary subscription lookup failures, including HTTP 5xx, connection errors, timeouts, and invalid JSON; warn once per outage. Authentication errors and quota limits still trigger reauthentication or backoff.
- Cache subscription metadata for 15 minutes and firmware metadata for one hour to reduce cloud requests.
- Add newly discovered devices, points, and zones after a successful refresh. Missing data makes existing entities unavailable; returning data restores them.
- Keep a point's initially chosen platform until reload, combine duplicate API points by ID, and use indexed coordinator lookups.
- Use the heating, cooling, or shared setpoint for the active thermostat mode, clear missing readings, and report unsupported command-only zone writes.
- Retain the select fix released in 1.8.5: match raw values to enum labels when the API's display text includes units or uses a different numeric format. Regression tests cover integer-valued floats and fallback display text.
- Port the temperature-discovery fix from contributor PR #270 into this series, preserving platform overrides, write permissions, and existing switch/select detection. Leave #270 independent for its separate 1.8.x merge.
- Protect supported water-heater controls when required points disappear.
- Keep account collections and flow data isolated per instance, and publish only complete account snapshots.
- Normalize malformed expert-option structures safely and omit an unset country from the API language header.

### Diagnostics, documentation, and development

- Provide cached, redacted diagnostics without additional cloud calls and allow manual removal of devices absent from the account.
- Improve device classes, categories, translated names and exceptions, and icons. Retain manufacturer-provided parameter names and enum values.
- Preserve the German and Norwegian translations for existing API enum labels, including the historical text aliases.
- Document account setup, every option and raw action, supported models and functions, polling, limitations, use cases, removal, and troubleshooting.
- Disclose AI assistance in the README and PR template while retaining maintainer responsibility and review before merging.
- Add a locked development environment, strict mypy typing, lint/format checks, translation synchronization, and network-isolated tests.
- Require above 95% statement and branch coverage in every integration module and 100% config-flow coverage in CI. The release candidate has 345 tests, run against both supported test environments.
- Review all 54 closed issues and 23 merged pull requests from other authors. Record the results and unresolved cloud or hardware cases in the release checklist, with regression tests for historical controls, metadata, translations, and API failures.

Automated tests use synthetic API data. Device-specific behavior still requires validation on supported hardware and subscriptions before release.
