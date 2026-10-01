# MyUplink integration for Home Assistant

[![Version](https://img.shields.io/github/v/release/jaroschek/home-assistant-myuplink?label=version)](https://github.com/jaroschek/home-assistant-myuplink/releases/latest)
[![Validate for HACS](https://github.com/jaroschek/home-assistant-myuplink/workflows/Validate%20for%20HACS/badge.svg)](https://github.com/jaroschek/home-assistant-myuplink/actions/workflows/hacs.yaml)
[![Validate with hassfest](https://github.com/jaroschek/home-assistant-myuplink/workflows/Validate%20with%20hassfest/badge.svg)](https://github.com/jaroschek/home-assistant-myuplink/actions/workflows/hassfest.yaml)

Custom Home Assistant integration for devices and sensors in [myUplink](https://myuplink.com/) account.

This integration should work with most smart devices from brands listed [here](https://myuplink.com/legal/works-with/en).

![example view](example-device-view.png)

## Install
### HACS
The easiest way to install this component is by clicking the badge below, which adds this repo as a custom repo in your HASS instance.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=Integration&owner=jaroschek&repository=home-assistant-myuplink)

You can also add the integration manually by copying `custom_components/myuplink` into `<HASS config directory>/custom_components`
### Configuration

To use this integration, you need to make an application at [dev.myuplink.com](https://dev.myuplink.com/). 

Remember to set a valid Callback Url. Make sure you use `https://my.home-assistant.io/redirect/oauth`, as HA currently uses that callback URL by default for the Oauth2 config flow.

_Note: You cannot edit the Callback Url after the application has been created, even though the GUI makes you think so. Create a new one if you want to change it._

Start the myUplink integration setup and copy the Client Identifier and Client Secret from your myUplink-application into the OAuth text fields.

Next, approve access via the OAuth pop-up and you should be good to go!

## Troubleshooting

Reading this might help if you run into issues

### "Sorry, there was an error : invalid_request"

This often means that the Callback URL provided is invalid or unreachable.

Double-check that the Callback URL saved in the myUpLink application is correct.

### "Sorry, there was an error : unauthorized_client"

This means that the credentials used by the integration is invalid. This often occurs when the myuplink-application is deleted and recreated, without deleting the old credentials from Home Assistant.

You can delete the old credentials stored in Home Assistant by going to the Devices & Services page, clicking the three dots top right and selecting "Application Credentials". Delete the one originating from myuplink, and you'll be prompted for new credentials next time you set up the integration.

### Some entities don't look right

This can happen when the device is integrated poorly with the myUpLink-API, or it's implemented in a way this integration cannot handle yet.

See the debugging section below to find some useful info about the offending data point.

## Debugging misbehaving entities

If the your entities are malformed, it's often caused by the manufacturer's implementation of the myUpLink-API. The easiest way to check this is by getting the raw data points from the Swagger client.

1. Take note of the entity's name, and open [myUpLink's Swagger](https://api.myuplink.com/swagger/index.html).
2. Click Authorize and paste your application credentials. Make sure to check the READSYSTEM box.
3. Find your device ID by querying ​`/v2​/systems​/me`, and enter it when querying `/v2/devices/{deviceId}/points`.
4. Find the relevant data points and post them in an issue.

## Development

The 1.9.x series is improving this custom integration against the [Home Assistant Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/). Progress and exemptions are tracked in `custom_components/myuplink/quality_scale.yaml`. This checklist is a self-assessment; the integration remains a custom integration.

Install [uv](https://docs.astral.sh/uv/) and use Python 3.14.2 or newer, then run:

```sh
script/setup
uv run --no-sync pytest tests --cov --cov-report=term-missing
uv run --no-sync prek run --all-files
```

Setup creates the project's `.venv` and installs Git hooks. If your IDE sets `UV_PROJECT_ENVIRONMENT` to a shared environment, set it to `.venv` when running these commands so this project uses its own environment.

CI checks formatting, lint, and tests, including 100% coverage of the config flow. The Silver target is above 95% coverage of every integration module; the checklist records this rule as pending until measured coverage meets that target.

### Actions and entity names in 1.9

The `myuplink.set_device_parameter_value` and `myuplink.set_device_zone_property_value` actions are registered when the integration loads. They remain available when an account is unloaded, and report an unavailable-device error until the selected account is loaded. Raw parameter and zone writes require an administrator when called by a signed-in user; Home Assistant automations can continue to call them.

Entity names are relative to their device. Existing unique IDs are retained, so existing entity IDs and names customized in Home Assistant remain associated with the same entities. Newly added entities include their device name in Home Assistant's generated name.

### Runtime failures in 1.9

Expired or revoked authorization starts Home Assistant's reauthentication flow. Network failures and API outages make coordinator-backed entities unavailable until polling succeeds again. Repeated polling failures are logged once, followed by recovery when data returns.

HTTP 429 responses use `Retry-After` (seconds or an HTTP date), falling back to `RateLimit-Reset` and then 60 seconds. Home Assistant schedules the next poll after this delay. Each token or HTTP request has a 30-second timeout; intentional request pacing is outside that timeout. Writes report rejected requests and read-only points as action errors. A successful write needs a 2xx response, and smart-home-mode responses must confirm success when they return a command payload.

The optional subscription endpoint's HTTP 500 response retains known manage permissions and logs one warning per outage. Authentication failures from that endpoint still start reauthentication.

### Discovery, removal, and diagnostics in 1.9

New devices, parameters, and smart-home zones are discovered after a successful refresh. A parameter retains its initial Home Assistant platform until account reload, preventing duplicate entities if its writable flag changes. Duplicate point responses are combined by parameter ID. Zero-valued zone measurements are included.

Missing systems, devices, points, and zones make their existing entities unavailable. They become available again when data returns. The disconnected-availability option keeps cached device readings available, while a failed cloud refresh still makes them unavailable. The connection diagnostic remains available to report an offline device.

Devices are not deleted automatically because a temporary absence from the cloud does not confirm permanent removal. After a device disappears, remove its registry entry from **Settings → Devices & services → Devices**. Devices still present in the account are protected from manual removal through this integration. Unloaded accounts allow manual cleanup.

Download diagnostics from the integration's entry in **Settings → Devices & services**. Diagnostics use cached metadata without making API requests. Account credentials, entry identity, cloud system and device IDs, serial numbers, and system/device/zone names are redacted; notification text is omitted.

### AI assistance

AI tools assist with code, tests, and documentation in this project. AI-assisted changes require maintainer review, understanding, and passing automated checks before merging. Pull requests describe the AI assistance and validation performed; the maintainer remains responsible for the changes.
