# Changelog

## 1.9.0 (unreleased)

This series improves the custom integration against Home Assistant's Integration Quality Scale. The checklist is a project self-assessment; it does not represent an official Home Assistant tier award.

### Compatibility and upgrade notes

- Home Assistant **2026.9.4 or newer** is required and declared in the HACS manifest. Development uses Python 3.14.2 or newer; CI tests Python 3.14.5.
- Existing entity unique IDs, registry entity IDs, and names customized in Home Assistant are preserved. Default names now follow device-relative naming and translated fixed labels.
- Notification sensors are diagnostic and disabled by default when newly created. Existing enabled entities retain their setting. Enable a new notification entity manually if wanted.
- Recognized duration and flow-rate unit aliases are normalized. Ambiguous manufacturer units such as **Ws** remain unclassified.
- Raw parameter and zone actions require an administrator when called by a signed-in user. Home Assistant automations can still call them.
- Failed writes now raise translated errors instead of silently appearing successful.

### Reliability and controls

- Register administrator actions when the integration loads, including when an account cannot load, and keep them available after account unload.
- Retry network and server failures, honor quota headers and Retry-After, and start reauthentication for expired authorization.
- Retain known subscription permissions when the optional endpoint returns HTTP 500; warn once per outage.
- Cache subscription metadata for 15 minutes and firmware metadata for one hour to reduce cloud requests.
- Add newly discovered devices, points, and zones after a successful refresh. Missing data makes existing entities unavailable; returning data restores them.
- Keep a point's initially chosen platform until reload, combine duplicate API points by ID, and use indexed coordinator lookups.
- Use the heating, cooling, or shared setpoint for the active thermostat mode, clear missing readings, and report unsupported command-only zone writes.
- Protect supported water-heater controls when required points disappear.
- Keep account collections and flow data isolated per instance, and publish only complete account snapshots.
- Normalize malformed expert-option structures safely and omit an unset country from the API language header.

### Diagnostics, documentation, and development

- Provide cached, redacted diagnostics without additional cloud calls and allow manual removal of devices absent from the account.
- Improve device classes, categories, translated names and exceptions, and icons. Retain manufacturer-provided parameter names and enum values.
- Document account setup, every option and raw action, supported models and functions, polling, limitations, use cases, removal, and troubleshooting.
- Disclose AI assistance in the README and PR template while retaining maintainer responsibility and review before merging.
- Add a locked development environment, strict mypy typing, lint/format checks, translation synchronization, and network-isolated tests.
- Require above 95% statement and branch coverage in every integration module and 100% config-flow coverage in CI. The release candidate has 234 passing tests and 99.61% overall coverage.

Automated tests use synthetic API data. Device-specific behavior still requires validation on supported hardware and subscriptions before release.
