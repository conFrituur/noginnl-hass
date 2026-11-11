# Nogin.nl bruur switches

Create switch entities for bruurs from Nogin.nl. Each switch shows
whether that person is still in the Netherlands; changing it updates their status
on Nogin.nl.

Requires Home Assistant **2026.3.0 or newer**.

<!-- ha-marketplace:exclude-start -->

## Install from GitHub (Home Assistant Marketplace)

[![Open this repository in Home Assistant Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=conFrituur&repository=noginnl-hass&category=integration)

1. Open **Settings → Marketplace → Add from link**.
2. Enter `https://github.com/conFrituur/noginnl-hass` and select **Add**.
   Connect your GitHub account when prompted. If asked for a type, select **Integration**.
3. Open **Nogin.nl** in the Marketplace and select **Install**.
4. Follow any restart prompt, then configure the integration below.


<!-- ha-marketplace:exclude-end -->

## Configuration

Add the Nogin.nl integration under **Settings → Devices & services → Add integration**.
Setup fetches the available people from the API and lets you tick which people
should have switches. Everyone is selected by default during initial setup; untick anyone you do not want to add.

To add or remove people later, open **Settings → Devices & services → Nogin.nl**
and choose **Configure** (the options/gear button). Review the checkboxes and save.
The integration reloads automatically: selected people get switches, and deselected
people's switches are removed. Selecting nobody removes all person switches.
Removing and later re-adding a switch may reset its custom entity settings.

New API people are available in the options form but are never added automatically.
Selected people temporarily missing from the API remain unavailable until they return.
Existing installations from before person selection must choose their people in
Configure after updating; previously automatic switches are removed unless selected.