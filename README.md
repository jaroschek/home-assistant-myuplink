# MyUpLink integration for Home Assistant
Custom Home Assistant integration for devices and sensors in myUplink account.

## Intstall
### HACS
The easiest way to install this component is using HACS.

Open HACS > Integrations. Click the three dots top right, and select custom repos. Paste the link to this repo and select "Integration" as category.

### Configuration

To use this integration, you need to make an application at [dev.myuplink.com](https://dev.myuplink.com/).  
_Remember to set a valid Callback Url. It might be easiest to use `https://my.home-assistant.io/redirect/oauth`. You can't change this in the future, even though the GUI makes you think you can._

Start the myUplink integration setup, and copy the Client Identifier and Client Secret into the OAuth text fields.

Approve access via OAuth pop-up and you should be good to go!
