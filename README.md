# MyUpLink integration for Home Assistant
Custom Home Assistant integration for devices and sensors in [myUplink](https://myuplink.com/) account.

This integration should work with most smart devices from brands listed [here](https://myuplink.com/legal/works-with/en).

![example view](example-device-view.png)

## Intstall
### HACS
The easiest way to install this component is using HACS.

Open HACS > Integrations. Click the three dots top right, and select custom repos. Paste the link to this repo and select "Integration" as category.

### Configuration

To use this integration, you need to make an application at [dev.myuplink.com](https://dev.myuplink.com/).  
_Remember to set a valid Callback Url. It might be easiest to use `https://my.home-assistant.io/redirect/oauth`. You have to make a new application in order to change it._

Start the myUplink integration setup, and copy the Client Identifier and Client Secret into the OAuth text fields.

Approve access via OAuth pop-up and you should be good to go!
