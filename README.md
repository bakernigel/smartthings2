# smartthings2
New version of my Smartthings integration using OAuth. Replaces the core Smartthings integration.

<b> Previously installed versions of Smartthings integration must be deleted before installing this integration <b>

![logo](https://brands.home-assistant.io/_/smartthings/logo@2x.png)

__A Home Assistant custom Integration for SmartThings.__

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&repository=smartthings2&owner=bakernigel)

## __Installation Using HACS__
- Backup your existing HA
- Delete any existing Smarthings integration
- Delete any custom Smarthings installations from HACS
- Restart Home Assistant
- Download the custom SmartThings integration from the HACS custom repository using the button above
- Restart Home Assistant
- Install the Smartthings integration using Settings -> Devices and Services -> Add Integration
- Configure the Smartthings integration the same as for the core integration. 
- See https://www.home-assistant.io/integrations/smartthings for full instructions. 

## __𝐅𝐞𝐚𝐭𝐮𝐫𝐞𝐬__
- Added some missing sensors & controls 
- More capabilities are available than core Smartthings integration
- Only tested with Samsung Fridge Family Hub Model 24K_REF_LCD_FHUB9.0, Samsung Dishwasher Model DA_DW_TP1_21_COMMON and Samsung Wall Oven Model LCD_S905D3_OV_P_US_23K. <b>May not work with other devices.</b>
- Integration may add unwanted sensors/controls for your device. Simply disable the unwanted ones in Home Assistant.
- Integration reports the raw state for sensors from Samsung. Adjust the values using HA templates. e.g Family Hub Power {{(states('sensor.fridge_family_hub_power_meter')) | int /10}}

Based on: Core Smartthings 2025.3.4
