"""
Semaphore API client.

In production, connects to ops.omwom.com. In local dev, returns mock responses.

Semaphore API docs: https://docs.semaphoreui.com/administration-guide/api

Usage:
    client = get_client()
    templates = client.get_templates()
    task = client.run_task(template_id=5, extra_vars={"wp_name": "slowbread", ...})
    status = client.get_task(task["id"])
    output = client.get_task_output(task["id"])
"""

import os
import time
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

import requests
import streamlit as st


@dataclass
class SemaphoreConfig:
    base_url: str
    api_token: str
    project_id: int
    mock_mode: bool = False


def get_config() -> SemaphoreConfig:
    base_url = os.environ.get("SEMAPHORE_URL", "")
    api_token = os.environ.get("SEMAPHORE_TOKEN", "")
    project_id = int(os.environ.get("SEMAPHORE_PROJECT_ID", "1"))

    mock_mode = not base_url or not api_token

    return SemaphoreConfig(
        base_url=base_url.rstrip("/"),
        api_token=api_token,
        project_id=project_id,
        mock_mode=mock_mode,
    )


class SemaphoreClient:
    def __init__(self, config: SemaphoreConfig):
        self.config = config
        self.base_url = f"{config.base_url}/api"
        self.headers = {
            "Authorization": f"Bearer {config.api_token}",
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
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Semaphore API error: {e.response.status_code} on {path}") from None
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Semaphore connection error on {path}: {type(e).__name__}") from None

    def _post(self, path: str, data: dict) -> dict:
        try:
            resp = requests.post(
                f"{self.base_url}{path}",
                headers=self.headers,
                json=data,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Semaphore API error: {e.response.status_code} on {path}") from None
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Semaphore connection error on {path}: {type(e).__name__}") from None

    def ping(self) -> bool:
        try:
            resp = requests.get(
                f"{self.base_url}/ping",
                headers=self.headers,
                timeout=5,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def get_templates(self) -> list[dict]:
        path = f"/project/{self.config.project_id}/templates"
        return self._get(path)

    def get_template(self, template_id: int) -> dict:
        path = f"/project/{self.config.project_id}/templates/{template_id}"
        return self._get(path)

    def run_task(self, template_id: int, extra_vars: dict | None = None) -> dict:
        path = f"/project/{self.config.project_id}/tasks"
        payload = {"template_id": template_id}

        if extra_vars:
            import json
            payload["environment"] = json.dumps(extra_vars)

        return self._post(path, payload)

    def find_template_by_playbook(self, playbook: str) -> dict | None:
        templates = self.get_templates()
        bare = playbook.split("/")[-1]
        for t in templates:
            tp = t.get("playbook", "")
            if tp == playbook or tp == f"playbooks/{playbook}" or tp.endswith(f"/{bare}"):
                return t
        return None

    def run_playbook(self, playbook: str, extra_vars: dict | None = None) -> dict:
        template = self.find_template_by_playbook(playbook)
        if template is None:
            raise RuntimeError(f"No Semaphore template found for playbook: {playbook}")
        return self.run_task(template["id"], extra_vars=extra_vars)

    def get_task(self, task_id: int) -> dict:
        path = f"/project/{self.config.project_id}/tasks/{task_id}"
        return self._get(path)

    def get_task_output(self, task_id: int) -> list[dict]:
        path = f"/project/{self.config.project_id}/tasks/{task_id}/output"
        return self._get(path)

    def get_tasks(self, limit: int = 20) -> list[dict]:
        path = f"/project/{self.config.project_id}/tasks?count={limit}"
        return self._get(path)

    def wait_for_task(self, task_id: int, poll_interval: float = 3.0, timeout: float = 600.0) -> dict:
        start = time.time()
        while time.time() - start < timeout:
            task = self.get_task(task_id)
            if task.get("status") in ("success", "error", "stopped"):
                return task
            time.sleep(poll_interval)
        return self.get_task(task_id)


class MockSemaphoreClient:
    """Returns realistic mock data for local development."""

    @property
    def mock_mode(self) -> bool:
        return True

    def ping(self) -> bool:
        return True

    def get_templates(self) -> list[dict]:
        return [
            {"id": 1, "name": "Add WordPress Site", "playbook": "wordpress-add.yml"},
            {"id": 2, "name": "Remove WordPress Site", "playbook": "wordpress-remove.yml"},
            {"id": 3, "name": "Add Odoo Instance", "playbook": "odoo-add.yml"},
            {"id": 4, "name": "Remove Odoo Instance", "playbook": "odoo-remove.yml"},
            {"id": 5, "name": "Add Mail Domain", "playbook": "mail-add-domain.yml"},
            {"id": 6, "name": "Remove Mail Domain", "playbook": "mail-remove-domain.yml"},
            {"id": 7, "name": "Server Health", "playbook": "health.yml"},
            {"id": 8, "name": "WordPress Restore", "playbook": "wordpress-restore.yml"},
            {"id": 9, "name": "WordPress PHP Change", "playbook": "wordpress-php-change.yml"},
            {"id": 10, "name": "WordPress Toggle", "playbook": "wordpress-toggle.yml"},
            {"id": 11, "name": "Odoo Toggle", "playbook": "odoo-toggle.yml"},
            {"id": 12, "name": "Run Backup", "playbook": "backup-run.yml"},
            {"id": 13, "name": "Verify Backups", "playbook": "backup-verify.yml"},
        ]

    def get_template(self, template_id: int) -> dict:
        templates = {t["id"]: t for t in self.get_templates()}
        return templates.get(template_id, {"id": template_id, "name": "Unknown"})

    def run_task(self, template_id: int, extra_vars: dict | None = None) -> dict:
        return {
            "id": 42,
            "template_id": template_id,
            "status": "waiting",
            "created": datetime.now(timezone.utc).isoformat(),
        }

    def find_template_by_playbook(self, playbook: str) -> dict | None:
        for t in self.get_templates():
            if t.get("playbook") == playbook:
                return t
        return None

    def run_playbook(self, playbook: str, extra_vars: dict | None = None) -> dict:
        template = self.find_template_by_playbook(playbook)
        if template is None:
            raise RuntimeError(f"No Semaphore template found for playbook: {playbook}")
        return self.run_task(template["id"], extra_vars=extra_vars)

    def get_task(self, task_id: int) -> dict:
        return {
            "id": task_id,
            "template_id": 7,
            "status": "success",
            "start": (datetime.now(timezone.utc) - timedelta(seconds=45)).isoformat(),
            "end": datetime.now(timezone.utc).isoformat(),
            "created": (datetime.now(timezone.utc) - timedelta(seconds=50)).isoformat(),
        }

    def get_task_output(self, task_id: int) -> list[dict]:
        now = datetime.now(timezone.utc)
        return [
            {"task_id": task_id, "time": (now - timedelta(seconds=40)).isoformat(),
             "output": "PLAY [omwom] *****"},
            {"task_id": task_id, "time": (now - timedelta(seconds=38)).isoformat(),
             "output": "TASK [Run health-check.sh] *****"},
            {"task_id": task_id, "time": (now - timedelta(seconds=35)).isoformat(),
             "output": "=== System Health Report ==="},
            {"task_id": task_id, "time": (now - timedelta(seconds=34)).isoformat(),
             "output": f"Uptime:     47 days, 12:34:56"},
            {"task_id": task_id, "time": (now - timedelta(seconds=33)).isoformat(),
             "output": f"Load:       1.24, 0.98, 0.87"},
            {"task_id": task_id, "time": (now - timedelta(seconds=32)).isoformat(),
             "output": f"CPU:        23% used"},
            {"task_id": task_id, "time": (now - timedelta(seconds=31)).isoformat(),
             "output": f"RAM:        8.8 GB / 12.0 GB (73%)"},
            {"task_id": task_id, "time": (now - timedelta(seconds=30)).isoformat(),
             "output": f"Disk:       77 GB / 240 GB (32%)"},
            {"task_id": task_id, "time": (now - timedelta(seconds=29)).isoformat(),
             "output": f"Swap:       124 MB / 2048 MB (6%)"},
            {"task_id": task_id, "time": (now - timedelta(seconds=28)).isoformat(),
             "output": ""},
            {"task_id": task_id, "time": (now - timedelta(seconds=27)).isoformat(),
             "output": "=== Service Status ==="},
            {"task_id": task_id, "time": (now - timedelta(seconds=26)).isoformat(),
             "output": "nginx              active (running)"},
            {"task_id": task_id, "time": (now - timedelta(seconds=25)).isoformat(),
             "output": "mariadb            active (running)"},
            {"task_id": task_id, "time": (now - timedelta(seconds=24)).isoformat(),
             "output": "postgresql         active (running)"},
            {"task_id": task_id, "time": (now - timedelta(seconds=23)).isoformat(),
             "output": "php8.3-fpm         active (running)"},
            {"task_id": task_id, "time": (now - timedelta(seconds=22)).isoformat(),
             "output": "postfix            active (running)"},
            {"task_id": task_id, "time": (now - timedelta(seconds=21)).isoformat(),
             "output": "dovecot            active (running)"},
            {"task_id": task_id, "time": (now - timedelta(seconds=20)).isoformat(),
             "output": "semaphore          active (running)"},
            {"task_id": task_id, "time": (now - timedelta(seconds=19)).isoformat(),
             "output": "fail2ban           active (running)"},
            {"task_id": task_id, "time": (now - timedelta(seconds=18)).isoformat(),
             "output": ""},
            {"task_id": task_id, "time": (now - timedelta(seconds=17)).isoformat(),
             "output": "=== Docker Containers ==="},
            {"task_id": task_id, "time": (now - timedelta(seconds=16)).isoformat(),
             "output": "portainer          running (Up 47 days)"},
            {"task_id": task_id, "time": (now - timedelta(seconds=15)).isoformat(),
             "output": "uptime-kuma        running (Up 47 days)"},
            {"task_id": task_id, "time": (now - timedelta(seconds=14)).isoformat(),
             "output": ""},
            {"task_id": task_id, "time": (now - timedelta(seconds=13)).isoformat(),
             "output": "=== SSL Certificates ==="},
            {"task_id": task_id, "time": (now - timedelta(seconds=12)).isoformat(),
             "output": "omwom.com                62 days remaining  OK"},
            {"task_id": task_id, "time": (now - timedelta(seconds=11)).isoformat(),
             "output": "mail.omwom.com           62 days remaining  OK"},
            {"task_id": task_id, "time": (now - timedelta(seconds=10)).isoformat(),
             "output": "ops.omwom.com            62 days remaining  OK"},
            {"task_id": task_id, "time": (now - timedelta(seconds=9)).isoformat(),
             "output": "slowbirdbread.com        12 days remaining  WARNING"},
            {"task_id": task_id, "time": (now - timedelta(seconds=8)).isoformat(),
             "output": "clientsite3.com           5 days remaining  CRITICAL"},
            {"task_id": task_id, "time": (now - timedelta(seconds=7)).isoformat(),
             "output": ""},
            {"task_id": task_id, "time": (now - timedelta(seconds=6)).isoformat(),
             "output": "=== Backup Status ==="},
            {"task_id": task_id, "time": (now - timedelta(seconds=5)).isoformat(),
             "output": "Last backup:  2026-04-11 02:00:03  SUCCESS"},
            {"task_id": task_id, "time": (now - timedelta(seconds=4)).isoformat(),
             "output": "Last verify:  2026-04-11 05:00:12  PASSED"},
            {"task_id": task_id, "time": (now - timedelta(seconds=3)).isoformat(),
             "output": "Providers:    backblaze(synced) hetzner(synced)"},
            {"task_id": task_id, "time": (now - timedelta(seconds=2)).isoformat(),
             "output": ""},
            {"task_id": task_id, "time": (now - timedelta(seconds=1)).isoformat(),
             "output": "PLAY RECAP *****"},
            {"task_id": task_id, "time": now.isoformat(),
             "output": "omwom : ok=4    changed=0    unreachable=0    failed=0"},
        ]

    def get_tasks(self, limit: int = 20) -> list[dict]:
        now = datetime.now(timezone.utc)
        return [
            {"id": 42, "template_id": 7, "status": "success",
             "start": (now - timedelta(minutes=5)).isoformat(),
             "end": (now - timedelta(minutes=4, seconds=15)).isoformat(),
             "created": (now - timedelta(minutes=5, seconds=5)).isoformat()},
            {"id": 41, "template_id": 1, "status": "success",
             "start": (now - timedelta(hours=3)).isoformat(),
             "end": (now - timedelta(hours=2, minutes=57)).isoformat(),
             "created": (now - timedelta(hours=3, seconds=10)).isoformat()},
            {"id": 40, "template_id": 5, "status": "success",
             "start": (now - timedelta(hours=6)).isoformat(),
             "end": (now - timedelta(hours=5, minutes=59)).isoformat(),
             "created": (now - timedelta(hours=6, seconds=5)).isoformat()},
            {"id": 39, "template_id": 7, "status": "success",
             "start": (now - timedelta(days=1)).isoformat(),
             "end": (now - timedelta(days=1) + timedelta(seconds=45)).isoformat(),
             "created": (now - timedelta(days=1, seconds=5)).isoformat()},
            {"id": 38, "template_id": 8, "status": "error",
             "start": (now - timedelta(days=2)).isoformat(),
             "end": (now - timedelta(days=2) + timedelta(minutes=3)).isoformat(),
             "created": (now - timedelta(days=2, seconds=5)).isoformat()},
        ]

    def wait_for_task(self, task_id: int, poll_interval: float = 3.0, timeout: float = 600.0) -> dict:
        return self.get_task(task_id)


@st.cache_resource
def get_client() -> SemaphoreClient | MockSemaphoreClient:
    config = get_config()
    if config.mock_mode:
        return MockSemaphoreClient()
    return SemaphoreClient(config)
