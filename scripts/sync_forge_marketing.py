"""Import ForgeMarketing actions into Yavin suggested todos."""

from __future__ import annotations

import os
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from database import DATABASE_PATH, DatabaseManager  # noqa: E402
from services.forge_marketing_connector import (  # noqa: E402
    ForgeMarketingTodoConnector,
    load_checkpoint,
    sync_forge_marketing_todos,
)
from services.connector_run_history import connector_health, run_with_retries  # noqa: E402


def main() -> None:
    base_url = os.environ.get("FORGE_MARKETING_URL", "").strip()
    token = os.environ.get("FORGE_MARKETING_TOKEN", "").strip()
    if not base_url or not token:
        raise SystemExit("Set FORGE_MARKETING_URL and FORGE_MARKETING_TOKEN")
    DatabaseManager(DATABASE_PATH)
    def job():
        connector = ForgeMarketingTodoConnector(
            base_url=base_url, bearer_token=token, cursor=load_checkpoint(DATABASE_PATH)
        )
        return sync_forge_marketing_todos(DATABASE_PATH, connector)
    attempts = int(os.environ.get("FORGE_MARKETING_SYNC_ATTEMPTS", "3"))
    result = run_with_retries(DATABASE_PATH, job, max_attempts=attempts)
    print(json.dumps({"result": result, "health": connector_health(DATABASE_PATH)}, sort_keys=True))


if __name__ == "__main__":
    main()
