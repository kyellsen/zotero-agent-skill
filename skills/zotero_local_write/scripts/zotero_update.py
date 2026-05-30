#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyzotero", "python-dotenv"]
# ///
"""Zotero Local Write — Controlled metadata corrections via Web API.

A platform-agnostic CLI tool for AI agents to read and update Zotero item
metadata through the Zotero Web API. Requires ZOTERO_API_KEY and
ZOTERO_LIBRARY_ID environment variables set in ~/.env.

Usage:
    uv run zotero_update.py read "ZOTERO_KEY"
    uv run zotero_update.py update "ZOTERO_KEY" --field FIELD --value "VALUE"
"""

import argparse
import json
import sys
from pathlib import Path


def _load_credentials() -> tuple[str, str]:
    """Loads Zotero API credentials from ~/.env.

    Returns:
        Tuple of (library_id, api_key).

    Raises:
        SystemExit: If credentials are missing.
    """
    from dotenv import dotenv_values

    env_path = Path.home() / ".env"
    if not env_path.exists():
        print(
            "Error: ~/.env not found. Create it with ZOTERO_API_KEY and "
            "ZOTERO_LIBRARY_ID.",
            file=sys.stderr,
        )
        sys.exit(1)

    values = dotenv_values(env_path)
    api_key = values.get("ZOTERO_API_KEY")
    library_id = values.get("ZOTERO_LIBRARY_ID")

    if not api_key:
        print("Error: ZOTERO_API_KEY not found in ~/.env.", file=sys.stderr)
        sys.exit(1)
    if not library_id:
        print(
            "Error: ZOTERO_LIBRARY_ID not found in ~/.env.", file=sys.stderr
        )
        sys.exit(1)

    return library_id, api_key


def _get_zotero_client():
    """Creates an authenticated Zotero API client.

    Returns:
        A pyzotero.zotero.Zotero client instance.
    """
    from pyzotero import zotero

    library_id, api_key = _load_credentials()
    return zotero.Zotero(library_id, "user", api_key)


def cmd_read(key: str) -> None:
    """Reads and prints metadata for a single Zotero item.

    Args:
        key: The 8-character Zotero item key.
    """
    zot = _get_zotero_client()
    try:
        item = zot.item(key)
    except Exception as e:
        print(f"Error reading item {key}: {e}", file=sys.stderr)
        sys.exit(1)

    data = item.get("data", {})
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_update(key: str, field: str, value: str) -> None:
    """Updates a single metadata field on a Zotero item.

    Args:
        key: The 8-character Zotero item key.
        field: The metadata field name (e.g. 'title', 'date', 'DOI').
        value: The new value. For complex fields like 'creators', pass JSON.
    """
    zot = _get_zotero_client()
    try:
        item = zot.item(key)
    except Exception as e:
        print(f"Error reading item {key}: {e}", file=sys.stderr)
        sys.exit(1)

    data = item.get("data", {})
    old_value = data.get(field, "(not set)")

    # Parse JSON value for complex fields (creators, tags, etc.)
    parsed_value = value
    if field in ("creators", "tags", "relations", "collections"):
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            print(
                f"Error: Field '{field}' requires valid JSON. "
                f"Got: {value}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Apply the change
    data[field] = parsed_value

    try:
        zot.update_item(item)
    except Exception as e:
        print(f"Error updating item {key}: {e}", file=sys.stderr)
        sys.exit(1)

    print(
        json.dumps(
            {
                "status": "updated",
                "key": key,
                "field": field,
                "old_value": old_value,
                "new_value": parsed_value,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def main() -> None:
    """CLI entry point for Zotero metadata read and update."""
    parser = argparse.ArgumentParser(
        description="Zotero local write — metadata read and update."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # read command
    sp_read = subparsers.add_parser(
        "read", help="Read metadata for a Zotero item."
    )
    sp_read.add_argument("key", type=str, help="Zotero item key")

    # update command
    sp_update = subparsers.add_parser(
        "update", help="Update a metadata field (requires approval)."
    )
    sp_update.add_argument("key", type=str, help="Zotero item key")
    sp_update.add_argument(
        "--field",
        type=str,
        required=True,
        help="Metadata field to update (e.g. title, date, DOI)",
    )
    sp_update.add_argument(
        "--value",
        type=str,
        required=True,
        help="New value for the field (use JSON for complex fields)",
    )

    args = parser.parse_args()

    if args.command == "read":
        cmd_read(args.key)
    elif args.command == "update":
        cmd_update(args.key, args.field, args.value)


if __name__ == "__main__":
    main()
