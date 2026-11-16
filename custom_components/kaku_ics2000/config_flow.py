"""Config flow: log in with the KlikAanKlikUit account, pick the home, find the hub."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import Home, Ics2000AuthError, Ics2000Client, Ics2000Error
from .discovery import async_discover
from .const import (
    CONF_AES_KEY, CONF_HOME_ID, CONF_MAC, CONF_SCAN_INTERVAL, CONF_TRIES,
    DEFAULT_SCAN_INTERVAL, DEFAULT_TRIES, DOMAIN, MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema({vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str})


class Ics2000ConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._email = ""
        self._password = ""
        self._homes: list[Home] = []
        self._home: Home | None = None

    async def _login(self, email: str, password: str) -> tuple[list[Home], dict[str, str]]:
        client = Ics2000Client(async_get_clientsession(self.hass), email, password)
        try:
            return await client.login(), {}
        except Ics2000AuthError:
            return [], {"base": "invalid_auth"}
        except Ics2000Error:
            return [], {"base": "cannot_connect"}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            homes, errors = await self._login(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            if not errors and not homes:
                errors = {"base": "no_homes"}
            if not errors:
                self._email, self._password, self._homes = (
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD], homes,
                )
                if len(homes) == 1:
                    return await self._async_finish_home(homes[0])
                return await self.async_step_home()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, {CONF_EMAIL: user_input[CONF_EMAIL]} if user_input else None
            ),
            errors=errors,
        )

    async def async_step_home(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            home = next(h for h in self._homes if h.home_id == user_input[CONF_HOME_ID])
            return await self._async_finish_home(home)
        return self.async_show_form(
            step_id="home",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOME_ID): vol.In({h.home_id: h.name for h in self._homes})}
            ),
        )

    async def _async_finish_home(self, home: Home) -> ConfigFlowResult:
        self._home = home
        await self.async_set_unique_id(home.mac)
        self._abort_if_unique_id_configured()
        return await self.async_step_host()

    async def async_step_host(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._home is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._home.name,
                data={
                    CONF_EMAIL: self._email,
                    CONF_PASSWORD: self._password,
                    CONF_HOME_ID: self._home.home_id,
                    CONF_MAC: self._home.mac,
                    CONF_AES_KEY: self._home.aes_key,
                    CONF_HOST: user_input.get(CONF_HOST) or None,
                },
            )
        found = await async_discover(self.hass)
        host = found.get(self._home.mac)
        if host:
            # Found on the LAN: no need to ask anything.
            return await self.async_step_host({CONF_HOST: host})
        return self.async_show_form(
            step_id="host",
            data_schema=vol.Schema({vol.Optional(CONF_HOST): str}),
            description_placeholders={"mac": self._home.mac},
        )

    # ------------------------------------------------------------- reauth
    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        self._email = entry_data[CONF_EMAIL]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            homes, errors = await self._login(self._email, user_input[CONF_PASSWORD])
            home = next((h for h in homes if h.mac == entry.unique_id), None)
            if not errors and home is None:
                errors = {"base": "no_homes"}
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD], CONF_AES_KEY: home.aes_key},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={"email": self._email},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return Ics2000OptionsFlow()


class Ics2000OptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL, default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=3600)),
                    vol.Required(CONF_TRIES, default=opts.get(CONF_TRIES, DEFAULT_TRIES)): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=5)
                    ),
                }
            ),
        )
