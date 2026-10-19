"""Shared personal assistant runtime for the local core-workspace apps."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEMORY_ROOT = PROJECT_ROOT / "data" / "assistant_memory"
SHORT_MEMORY = MEMORY_ROOT / "SHORT_TERM.md"
LONG_MEMORY = MEMORY_ROOT / "LONG_TERM.md"
TASK_LOG = MEMORY_ROOT / "HERMES_TASKS.jsonl"
HERMES_BIN = Path.home() / ".local" / "bin" / "hermes"

APP_ROOTS = {
    "dashboard": PROJECT_ROOT,
    "yavin": Path("/Users/greglind/Projects/Yavin.Home"),
    "focus": Path("/Users/greglind/Projects/buildly/THEFORGE/focus"),
    "launchpad": Path("/Users/greglind/Projects/buildly/launchpad"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PersonalAssistantRuntime:
    def __init__(self, ai_service_factory: Callable[[], Any]):
        self.ai_service_factory = ai_service_factory
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.task_queue: queue.Queue = queue.Queue(maxsize=8)
        self.lock = threading.RLock()
        self._ensure_memory_files()
        self.worker = threading.Thread(target=self._task_worker, name="hermes-task-worker", daemon=True)
        self.worker.start()

    def _ensure_memory_files(self) -> None:
        MEMORY_ROOT.mkdir(parents=True, exist_ok=True)
        if not SHORT_MEMORY.exists():
            SHORT_MEMORY.write_text(
                "# Short-term memory\n\nRecent conversations and active context. This file is automatically compacted.\n\n",
                encoding="utf-8",
            )
        if not LONG_MEMORY.exists():
            LONG_MEMORY.write_text(
                "# Long-term memory\n\nStable facts and preferences explicitly saved by the user.\n\n",
                encoding="utf-8",
            )

    def read_memory(self) -> Dict[str, str]:
        self._ensure_memory_files()
        return {
            "short_term": SHORT_MEMORY.read_text(encoding="utf-8")[-24000:],
            "long_term": LONG_MEMORY.read_text(encoding="utf-8")[-32000:],
        }

    def remember(self, content: str, kind: str = "long_term", source: str = "dashboard") -> Dict[str, Any]:
        text = " ".join((content or "").strip().split())
        if not text:
            raise ValueError("Memory content is required")
        target = LONG_MEMORY if kind == "long_term" else SHORT_MEMORY
        with self.lock:
            with target.open("a", encoding="utf-8") as handle:
                handle.write(f"- {_now()} [{source}] {text[:4000]}\n")
            if target == SHORT_MEMORY and target.stat().st_size > 40000:
                body = target.read_text(encoding="utf-8")
                target.write_text("# Short-term memory\n\n" + body[-26000:], encoding="utf-8")
        return {"success": True, "kind": kind, "path": str(target)}

    def speak(self, text: str) -> bool:
        """Speak through the lightweight native macOS voice without blocking."""
        say_bin = Path("/usr/bin/say")
        cleaned = " ".join((text or "").replace("`", "").split())[:5000]
        if not say_bin.exists() or not cleaned:
            return False
        subprocess.Popen(
            [str(say_bin), "-r", "185", cleaned],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True

    async def chat(self, message: str, app_context: Dict[str, Any], conversation_id: Optional[str] = None) -> Dict[str, Any]:
        memory = self.read_memory()
        app = str(app_context.get("app") or "dashboard")
        view = str(app_context.get("view") or app_context.get("title") or "unknown")
        url = str(app_context.get("url") or "")
        # AIService already assembles current dashboard data and Markdown memory.
        # Passing a second full memory dump as the user message made intent
        # detection match old conversations (for example "priorities") and could
        # trigger a second model generation. Keep the current turn authoritative.
        contextual_message = f"[Current app: {app}; view: {view}]\n{message}"
        service = self.ai_service_factory()
        result = await service.chat(
            message=contextual_message,
            conversation_id=conversation_id,
            include_context=True,
        )
        if result.get("success"):
            response = str(result.get("response") or "")
            self.remember(f"User: {message[:1200]} | Assistant: {response[:1800]}", "short_term", app)
            if message.strip().lower().startswith(("remember that", "remember this", "please remember")):
                self.remember(message, "long_term", app)
        return result

    def hermes_status(self) -> Dict[str, Any]:
        executable = HERMES_BIN.exists() or shutil.which("hermes") is not None
        provider_ready = False
        detail = "Hermes is not installed"
        if executable:
            try:
                completed = subprocess.run(
                    [str(HERMES_BIN if HERMES_BIN.exists() else "hermes"), "status"],
                    capture_output=True,
                    text=True,
                    timeout=8,
                    env={**os.environ, "NO_COLOR": "1"},
                )
                output = f"{completed.stdout}\n{completed.stderr}"
                provider_ready = "not logged in" not in output.lower() and completed.returncode == 0
                detail = "Ready" if provider_ready else "Installed; inference provider login required"
            except Exception as exc:
                detail = f"Status unavailable: {exc}"
        with self.lock:
            running = sum(1 for task in self.tasks.values() if task["status"] == "running")
            queued = sum(1 for task in self.tasks.values() if task["status"] == "queued")
        return {
            "installed": executable,
            "provider_ready": provider_ready,
            "detail": detail,
            "running": running,
            "queued": queued,
            "max_concurrent": 1,
            "max_queue": 8,
        }

    def enqueue_task(self, prompt: str, app: str = "dashboard") -> Dict[str, Any]:
        prompt = (prompt or "").strip()
        if not prompt:
            raise ValueError("Task prompt is required")
        if app not in APP_ROOTS:
            raise ValueError("Unknown app context")
        task_id = f"hermes_{uuid.uuid4().hex[:10]}"
        task = {
            "id": task_id,
            "prompt": prompt[:12000],
            "app": app,
            "cwd": str(APP_ROOTS[app]),
            "status": "queued",
            "created_at": _now(),
            "started_at": None,
            "finished_at": None,
            "output": "",
            "error": "",
        }
        with self.lock:
            self.tasks[task_id] = task
        try:
            self.task_queue.put_nowait(task_id)
        except queue.Full:
            with self.lock:
                self.tasks.pop(task_id, None)
            raise
        self._record_task(task)
        return dict(task)

    def list_tasks(self) -> list[Dict[str, Any]]:
        with self.lock:
            return [dict(task) for task in reversed(list(self.tasks.values()))][:30]

    def _record_task(self, task: Dict[str, Any]) -> None:
        MEMORY_ROOT.mkdir(parents=True, exist_ok=True)
        with TASK_LOG.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(task, ensure_ascii=False) + "\n")

    def _task_worker(self) -> None:
        while True:
            task_id = self.task_queue.get()
            with self.lock:
                task = self.tasks.get(task_id)
                if not task:
                    self.task_queue.task_done()
                    continue
                task["status"] = "running"
                task["started_at"] = _now()
            try:
                command = [
                    str(HERMES_BIN if HERMES_BIN.exists() else "hermes"),
                    "--safe-mode",
                    "--oneshot",
                    task["prompt"],
                ]
                completed = subprocess.run(
                    command,
                    cwd=task["cwd"],
                    capture_output=True,
                    text=True,
                    timeout=600,
                    env={**os.environ, "NO_COLOR": "1"},
                )
                with self.lock:
                    task["output"] = completed.stdout[-16000:].strip()
                    task["error"] = completed.stderr[-4000:].strip()
                    task["status"] = "complete" if completed.returncode == 0 else "failed"
            except subprocess.TimeoutExpired:
                with self.lock:
                    task["status"] = "timed_out"
                    task["error"] = "Hermes task exceeded the 10-minute limit"
            except Exception as exc:
                with self.lock:
                    task["status"] = "failed"
                    task["error"] = str(exc)
            finally:
                with self.lock:
                    task["finished_at"] = _now()
                    self._record_task(task)
                self.task_queue.task_done()
