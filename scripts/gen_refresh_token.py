#!/usr/bin/env python3
"""Generate a YouTube OAuth refresh token using google_auth_oauthlib."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the OAuth device flow for the configured client and print the "
            "generated refresh token."
        )
    )
    parser.add_argument(
        "--client-secrets",
        "-c",
        required=True,
        help="Path to the OAuth client JSON downloaded from Google Cloud Console.",
    )
    parser.add_argument(
        "--scopes",
        nargs="+",
        default=DEFAULT_SCOPES,
        help=(
            "OAuth scopes to request. Defaults to the repository's upload/read scopes. "
            "If you change YT_SCOPES in the workflow, pass the same values here."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    client_path = Path(args.client_secrets).expanduser().resolve()
    if not client_path.exists():
        raise SystemExit(f"Client secrets file not found: {client_path}")

    flow = InstalledAppFlow.from_client_secrets_file(str(client_path), scopes=args.scopes)
    creds = flow.run_console(prompt="consent")

    refresh_token = getattr(creds, "refresh_token", None)
    if not refresh_token:
        raise SystemExit(
            "No refresh_token was returned. Double-check the scopes and make sure "
            "offline access is granted."
        )

    print(refresh_token)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user.", file=sys.stderr)
        raise SystemExit(1)
