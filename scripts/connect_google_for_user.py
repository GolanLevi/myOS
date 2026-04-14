from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utils.gmail_connector import connect_google_account, get_google_connection_status


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an interactive Google OAuth flow and store encrypted credentials for a specific myOS user."
    )
    parser.add_argument("--user-id", required=True, help="myOS user id or 'admin'")
    args = parser.parse_args()

    before = get_google_connection_status(args.user_id)
    result = connect_google_account(args.user_id)
    after = get_google_connection_status(args.user_id)

    print(
        json.dumps(
            {
                "before": before,
                "result": result,
                "after": after,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
