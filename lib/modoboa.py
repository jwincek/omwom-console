"""
Modoboa REST API client.

In production, connects to mail.omwom.com. In local dev, returns mock responses.

Modoboa API docs: https://mail.omwom.com/docs/openapi/

Usage:
    client = get_modoboa_client()
    domains = client.list_domains()
    accounts = client.list_accounts("clientsite.com")
    client.create_account("info@clientsite.com", "password", quota=0)
    client.delete_account("info@clientsite.com")
"""

import os
from datetime import datetime, timezone
from dataclasses import dataclass

import requests
import streamlit as st


@dataclass
class ModoboaConfig:
    base_url: str
    api_token: str
    mock_mode: bool = False


def get_config() -> ModoboaConfig:
    base_url = os.environ.get("MODOBOA_URL", "")
    api_token = os.environ.get("MODOBOA_TOKEN", "")

    mock_mode = not base_url or not api_token

    return ModoboaConfig(
        base_url=base_url.rstrip("/"),
        api_token=api_token,
        mock_mode=mock_mode,
    )


class ModoboaClient:
    def __init__(self, config: ModoboaConfig):
        self.config = config
        self.base_url = f"{config.base_url}/api/v1"
        self.headers = {
            "Authorization": f"Token {config.api_token}",
            "Content-Type": "application/json",
        }

    @property
    def mock_mode(self) -> bool:
        return self.config.mock_mode

    def _get(self, path: str) -> dict | list:
        try:
            resp = requests.get(
                f"{self.base_url}{path}",
                headers=self.headers,
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Modoboa API error: {e.response.status_code} on {path}") from None
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Modoboa connection error on {path}: {type(e).__name__}") from None

    def _post(self, path: str, data: dict) -> dict:
        try:
            resp = requests.post(
                f"{self.base_url}{path}",
                headers=self.headers,
                json=data,
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Modoboa API error: {e.response.status_code} on {path}") from None
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Modoboa connection error on {path}: {type(e).__name__}") from None

    def _delete(self, path: str) -> bool:
        try:
            resp = requests.delete(
                f"{self.base_url}{path}",
                headers=self.headers,
                timeout=15,
            )
            resp.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Modoboa API error: {e.response.status_code} on {path}") from None
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Modoboa connection error on {path}: {type(e).__name__}") from None

    def list_domains(self) -> list[dict]:
        return self._get("/domains/")

    def get_domain(self, domain_name: str) -> dict | None:
        domains = self.list_domains()
        for d in domains:
            if d.get("name") == domain_name:
                return d
        return None

    def list_accounts(self, domain: str = "") -> list[dict]:
        path = "/accounts/"
        if domain:
            path += f"?domain={domain}"
        return self._get(path)

    def create_account(
        self,
        email: str,
        password: str,
        first_name: str = "",
        last_name: str = "",
        quota: int = 0,
        role: str = "SimpleUsers",
    ) -> dict:
        local_part, domain = email.split("@", 1)
        payload = {
            "username": email,
            "role": role,
            "password": password,
            "first_name": first_name or local_part.title(),
            "last_name": last_name,
            "is_active": True,
            "mailbox": {
                "full_address": email,
                "quota": quota,
                "use_domain_quota": quota == 0,
            },
        }
        return self._post("/accounts/", payload)

    def delete_account(self, email: str) -> bool:
        accounts = self.list_accounts()
        for acct in accounts:
            if acct.get("username") == email:
                return self._delete(f"/accounts/{acct['pk']}/")
        return False

    def create_default_accounts(self, domain: str, password: str) -> list[dict]:
        defaults = [
            {"address": f"postmaster@{domain}", "first_name": "Postmaster"},
            {"address": f"info@{domain}", "first_name": "Info"},
        ]
        created = []
        for acct in defaults:
            result = self.create_account(
                email=acct["address"],
                password=password,
                first_name=acct["first_name"],
            )
            created.append(result)
        return created


class MockModoboaClient:
    """Returns realistic mock data for local development."""

    _mock_accounts = {
        "omwom.com": [
            {"pk": 1, "username": "admin@omwom.com", "first_name": "Admin", "last_name": "",
             "role": "DomainAdmins", "is_active": True,
             "mailbox": {"full_address": "admin@omwom.com", "quota": 0}},
            {"pk": 2, "username": "noreply@omwom.com", "first_name": "No Reply", "last_name": "",
             "role": "SimpleUsers", "is_active": True,
             "mailbox": {"full_address": "noreply@omwom.com", "quota": 0}},
            {"pk": 3, "username": "postmaster@omwom.com", "first_name": "Postmaster", "last_name": "",
             "role": "SimpleUsers", "is_active": True,
             "mailbox": {"full_address": "postmaster@omwom.com", "quota": 0}},
        ],
        "slowbirdbread.com": [
            {"pk": 4, "username": "admin@slowbirdbread.com", "first_name": "Admin", "last_name": "",
             "role": "SimpleUsers", "is_active": True,
             "mailbox": {"full_address": "admin@slowbirdbread.com", "quota": 0}},
            {"pk": 5, "username": "info@slowbirdbread.com", "first_name": "Info", "last_name": "",
             "role": "SimpleUsers", "is_active": True,
             "mailbox": {"full_address": "info@slowbirdbread.com", "quota": 0}},
        ],
        "clientsite2.com": [
            {"pk": 6, "username": "contact@clientsite2.com", "first_name": "Contact", "last_name": "",
             "role": "SimpleUsers", "is_active": True,
             "mailbox": {"full_address": "contact@clientsite2.com", "quota": 0}},
        ],
    }

    @property
    def mock_mode(self) -> bool:
        return True

    def list_domains(self) -> list[dict]:
        return [
            {"pk": 1, "name": "omwom.com", "quota": 0, "enabled": True},
            {"pk": 2, "name": "slowbirdbread.com", "quota": 0, "enabled": True},
            {"pk": 3, "name": "clientsite2.com", "quota": 0, "enabled": True},
        ]

    def get_domain(self, domain_name: str) -> dict | None:
        for d in self.list_domains():
            if d["name"] == domain_name:
                return d
        return None

    def list_accounts(self, domain: str = "") -> list[dict]:
        if domain:
            return self._mock_accounts.get(domain, [])
        all_accounts = []
        for accts in self._mock_accounts.values():
            all_accounts.extend(accts)
        return all_accounts

    def create_account(
        self,
        email: str,
        password: str,
        first_name: str = "",
        last_name: str = "",
        quota: int = 0,
        role: str = "SimpleUsers",
    ) -> dict:
        local_part, domain = email.split("@", 1)
        return {
            "pk": 100,
            "username": email,
            "first_name": first_name or local_part.title(),
            "last_name": last_name,
            "role": role,
            "is_active": True,
            "mailbox": {"full_address": email, "quota": quota},
        }

    def delete_account(self, email: str) -> bool:
        return True

    def create_default_accounts(self, domain: str, password: str) -> list[dict]:
        return [
            self.create_account(f"postmaster@{domain}", password, first_name="Postmaster"),
            self.create_account(f"info@{domain}", password, first_name="Info"),
        ]


@st.cache_resource
def get_modoboa_client() -> ModoboaClient | MockModoboaClient:
    config = get_config()
    if config.mock_mode:
        return MockModoboaClient()
    return ModoboaClient(config)
