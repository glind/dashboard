"""Task sync helpers for external task providers."""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from database import get_credentials

logger = logging.getLogger(__name__)

SUPPORTED_TASK_SYNC_PROVIDERS = ("ticktick", "apple_reminders", "todoist")
TASK_SYNC_PROVIDER_ALIASES = {
    "apple": "apple_reminders",
    "apple reminders": "apple_reminders",
    "applereminders": "apple_reminders",
    "reminders": "apple_reminders",
}


def normalize_task_sync_provider(provider: Optional[str]) -> Optional[str]:
    """Normalize provider names from UI and config input."""
    if not provider:
        return None

    normalized = str(provider).strip().lower().replace("-", "_")
    return TASK_SYNC_PROVIDER_ALIASES.get(normalized, normalized)


def normalize_task_sync_order(
    preferred_provider: Optional[str] = None,
    provider_order: Optional[List[str]] = None,
    fallback_order: Optional[List[str]] = None,
) -> List[str]:
    """Build a de-duplicated provider order with defaults appended."""
    ordered: List[str] = []

    for raw_provider in [preferred_provider, *(provider_order or []), *(fallback_order or []), *SUPPORTED_TASK_SYNC_PROVIDERS]:
        provider = normalize_task_sync_provider(raw_provider)
        if provider in SUPPORTED_TASK_SYNC_PROVIDERS and provider not in ordered:
            ordered.append(provider)

    return ordered


class TaskSyncService:
    """Push tasks to supported external task providers."""

    def __init__(self, settings: Any = None):
        self.settings = settings

    def get_default_provider_order(self) -> List[str]:
        """Return configured provider order or the built-in default."""
        task_sync_settings = getattr(self.settings, "task_sync", None)
        configured_order = getattr(task_sync_settings, "provider_order", None)
        default_provider = getattr(task_sync_settings, "default_provider", None)
        return normalize_task_sync_order(default_provider, configured_order, ["ticktick", "apple_reminders", "todoist"])

    async def sync_task(
        self,
        task: Dict[str, Any],
        preferred_provider: Optional[str] = None,
        provider_order: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Sync one task to the first available provider in order."""
        order = normalize_task_sync_order(
            preferred_provider=preferred_provider,
            provider_order=provider_order,
            fallback_order=self.get_default_provider_order(),
        )

        attempts: List[Dict[str, Any]] = []
        for provider in order:
            result = await self.sync_task_to_provider(provider, task)
            attempts.append(result)
            if result.get("success"):
                return {
                    "success": True,
                    "provider": provider,
                    "provider_order": order,
                    "attempts": attempts,
                    "result": result,
                }

        return {
            "success": False,
            "provider_order": order,
            "attempts": attempts,
            "error": "No task sync provider accepted the task",
        }

    async def sync_task_to_provider(self, provider: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch task sync to a concrete provider."""
        normalized_provider = normalize_task_sync_provider(provider)

        if normalized_provider == "ticktick":
            return await self._sync_to_ticktick(task)
        if normalized_provider == "apple_reminders":
            return await self._sync_to_apple_reminders(task)
        if normalized_provider == "todoist":
            return await self._sync_to_todoist(task)

        return {
            "success": False,
            "provider": normalized_provider or provider,
            "error": "Unsupported task sync provider",
        }

    async def _sync_to_ticktick(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Create a task in TickTick using the existing collector."""
        try:
            from collectors.ticktick_collector import TickTickCollector

            collector = TickTickCollector(self.settings)
            if not await collector.is_authenticated():
                return {
                    "success": False,
                    "provider": "ticktick",
                    "error": "TickTick not authenticated",
                }

            priority_map = {"low": 1, "medium": 3, "high": 5}
            created_task = await collector.create_task(
                title=task.get("title", ""),
                content=task.get("description") or "",
                due_date=self._parse_due_date(task.get("due_date")),
                priority=priority_map.get(str(task.get("priority", "medium")).lower(), 3),
                tags=["dashboard-sync", task.get("category", "general")],
            )

            if not created_task:
                return {
                    "success": False,
                    "provider": "ticktick",
                    "error": "TickTick did not create the task",
                }

            return {
                "success": True,
                "provider": "ticktick",
                "external_id": created_task.get("id"),
            }
        except Exception as exc:
            logger.error(f"Error syncing task to TickTick: {exc}")
            return {
                "success": False,
                "provider": "ticktick",
                "error": str(exc),
            }

    async def _sync_to_todoist(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Create a task in Todoist using the REST API."""
        token = self._get_todoist_token()
        if not token:
            return {
                "success": False,
                "provider": "todoist",
                "error": "Todoist API token not configured",
            }

        payload: Dict[str, Any] = {
            "content": task.get("title", ""),
            "description": task.get("description") or "",
            "priority": self._map_todoist_priority(task.get("priority")),
        }

        due_date = self._parse_due_date(task.get("due_date"))
        if due_date:
            if due_date.time().hour == 0 and due_date.time().minute == 0 and due_date.time().second == 0:
                payload["due_date"] = due_date.date().isoformat()
            else:
                payload["due_datetime"] = due_date.isoformat()

        try:
            response = await asyncio.to_thread(
                requests.post,
                "https://api.todoist.com/rest/v2/tasks",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=15,
            )
            if response.status_code >= 400:
                return {
                    "success": False,
                    "provider": "todoist",
                    "error": f"Todoist API error {response.status_code}: {response.text[:200]}",
                }

            created_task = response.json() if response.content else {}
            return {
                "success": True,
                "provider": "todoist",
                "external_id": created_task.get("id"),
            }
        except Exception as exc:
            logger.error(f"Error syncing task to Todoist: {exc}")
            return {
                "success": False,
                "provider": "todoist",
                "error": str(exc),
            }

    async def _sync_to_apple_reminders(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Create a reminder on macOS using AppleScript."""
        if sys.platform != "darwin":
            return {
                "success": False,
                "provider": "apple_reminders",
                "error": "Apple Reminders sync is only available on macOS",
            }

        reminders_list = self._get_apple_reminders_list()
        script = self._build_apple_reminders_script(task, reminders_list)

        try:
            process = await asyncio.create_subprocess_exec(
                "osascript",
                "-e",
                script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_text = stderr.decode().strip() or stdout.decode().strip() or "AppleScript failed"
                return {
                    "success": False,
                    "provider": "apple_reminders",
                    "error": error_text,
                }

            return {
                "success": True,
                "provider": "apple_reminders",
                "external_id": stdout.decode().strip() or None,
            }
        except Exception as exc:
            logger.error(f"Error syncing task to Apple Reminders: {exc}")
            return {
                "success": False,
                "provider": "apple_reminders",
                "error": str(exc),
            }

    def _get_todoist_token(self) -> Optional[str]:
        """Resolve Todoist token from environment or stored credentials."""
        token = os.getenv("TODOIST_API_TOKEN")
        if token:
            return token

        creds = get_credentials("todoist") or {}
        token = creds.get("api_token")
        if token and "YOUR_TODOIST" not in str(token):
            return token
        return None

    def _get_apple_reminders_list(self) -> Optional[str]:
        """Resolve Apple Reminders list name from config or credentials."""
        task_sync_settings = getattr(self.settings, "task_sync", None)
        configured_list = getattr(task_sync_settings, "apple_reminders_list", None)
        if configured_list:
            return configured_list

        apple_creds = get_credentials("apple") or {}
        list_name = apple_creds.get("reminders_list") or apple_creds.get("list")
        if list_name:
            return str(list_name)

        return None

    def _build_apple_reminders_script(self, task: Dict[str, Any], reminders_list: Optional[str]) -> str:
        """Build AppleScript to insert a reminder."""
        title = self._apple_script_string(task.get("title", "Untitled task"))
        description = self._apple_script_string(task.get("description") or "")
        due_date = self._parse_due_date(task.get("due_date"))
        due_date_literal = self._apple_script_string(
            due_date.strftime("%A, %B %d, %Y at %I:%M:%S %p") if due_date else ""
        )
        reminders_list_literal = self._apple_script_string(reminders_list or "")

        lines = [
            'tell application "Reminders"',
            f"set listName to {reminders_list_literal}",
            'if listName is not "" then',
            'set targetList to list listName',
            'else',
            'set targetList to default list',
            'end if',
            f"set newReminder to make new reminder at end of reminders of targetList with properties {{name:{title}}}",
        ]

        if description != '""':
            lines.append(f"set body of newReminder to {description}")
        if due_date:
            lines.append(f"set due date of newReminder to date {due_date_literal}")

        lines.extend([
            'return id of newReminder',
            'end tell',
        ])
        return "\n".join(lines)

    def _parse_due_date(self, due_date: Any) -> Optional[datetime]:
        """Parse supported due date inputs into a datetime."""
        if not due_date:
            return None
        if isinstance(due_date, datetime):
            return due_date

        due_date_str = str(due_date).strip()
        if not due_date_str:
            return None

        try:
            return datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))
        except ValueError:
            try:
                return datetime.fromisoformat(f"{due_date_str}T00:00:00")
            except ValueError:
                logger.warning(f"Unable to parse due date for task sync: {due_date_str}")
                return None

    def _map_todoist_priority(self, priority: Any) -> int:
        """Convert internal priority strings to Todoist priority values."""
        normalized = str(priority or "medium").lower()
        if normalized == "high":
            return 4
        if normalized == "low":
            return 1
        return 3

    def _apple_script_string(self, value: str) -> str:
        """Escape strings for AppleScript literals."""
        return json.dumps(str(value or ""))