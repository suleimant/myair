"""MyAir climate integration."""

import logging
import json
import asyncio
from datetime import timedelta
from aiohttp import request, ClientError

from .const import *

from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
)

from homeassistant.helpers import device_registry, collection, entity_component
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry):
    #config[DOMAIN]
    url = config_entry.data.get('url')

    async def async_update_data():
        data = {}
        count = 0
        while True:      
            try:
                async with request('GET', f"{url}/getSystemData") as resp:
                    assert resp.status == 200
                    data = await resp.json(content_type=None)
            except ConnectionResetError:
                continue
            except ClientError as err:
                raise UpdateFailed(err)

            if('aircons' in data):
                return data

            if(count > 5):
                raise UpdateFailed("Tried too many times to get MyAir data") 
            else:
                count+=1
                _LOGGER.debug(f"Waiting a second and then retrying, Try: {count}")
                await asyncio.sleep(1)

    async def async_set_data(change):
        try:
            async with request('GET', f"{url}/setAircon", params={'json':json.dumps(change)}) as resp:
                assert resp.status == 200
                data = await resp.json(content_type=None)
        except ClientError as err:
            raise UpdateFailed(err)

        if(data['ack'] == False):
            raise UpdateFailed(data['reason'])

        await asyncio.sleep(1) #Give it time to make the change
        return data['ack']

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="MyAir",
        update_method=async_update_data,
        update_interval=timedelta(seconds=30),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    if('system' in coordinator.data):
        device = {
            "identifiers": {(DOMAIN,coordinator.data['system'].get('rid',"0"))},
            "name": coordinator.data['system'].get('name'),
            "manufacturer": "Advantage Air",
            "model": coordinator.data['system'].get('sysType'),
            "sw_version": coordinator.data['system'].get('myAppRev'),
        }
    else:
        device = None

    hass.data[DOMAIN] = {
        'coordinator': coordinator,
        'async_set_data': async_set_data,
        'device': device,
    }
    
    # Load Platforms
    for platform in MYAIR_PLATFORMS:
        hass.async_create_task(
            hass.helpers.discovery.async_load_platform(platform, DOMAIN, {}, config_entry.data)
        )

    return True