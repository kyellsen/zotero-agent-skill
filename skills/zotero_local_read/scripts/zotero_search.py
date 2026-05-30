#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Zotero Local Search — Read-only search, metadata, and fulltext retrieval.

A platform-agnostic CLI tool for AI agents to search a local Zotero library,
read item metadata, and extract fulltext content. Uses the Zotero Local REST
API when available, with automatic fallback to direct SQLite and filesystem
access.

Usage:
    uv run zotero_search.py search "QUERY" [--limit N] [--fulltext] [--zotero-dir PATH]
    uv run zotero_search.py get-text "KEY" [--zotero-dir PATH]
    uv run zotero_search.py get-metadata "KEY" [--zotero-dir PATH]
"""

import argparse
import json
import re
import sqlite3
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# Zotero Local REST API configuration
ZOTERO_PORT = 23119
ZOTERO_HOST = "localhost"

# SQLite schema constants (Zotero 7.x)
ITEM_TYPE_ATTACHMENT = 1
ITEM_TYPE_NOTE = 14


def _default_zotero_dir() -> Path:
    """Returns the default Zotero data directory.

    Returns:
        Path to ~/Zotero.
    """
    return Path.home() / "Zotero"


def is_api_running() -> bool:
    """Checks whether the Zotero Local REST API is reachable.

    Returns:
        True if the local API responds to a health check, False otherwise.
    """
    try:
        url = f"http://{ZOTERO_HOST}:{ZOTERO_PORT}/api/users/0/items?limit=1"
        with urllib.request.urlopen(url, timeout=1) as response:
            return response.status == 200
    except Exception:
        return False


def search_api(
    query: str, limit: int = 15, fulltext: bool = False
) -> list[dict]:
    """Queries the Zotero Local REST API for items matching the search query.

    Args:
        query: Search term (author name, part of title, year, etc.).
        limit: Maximum number of search results to return.
        fulltext: If True, searches inside PDF content (qmode=everything).
            If False, searches only title/creator/year.

    Returns:
        List of matching items with keys: key, title, citationKey, creators,
        date, attachmentKey.
    """
    q = urllib.parse.quote(query)
    qmode = "everything" if fulltext else "titleCreatorYear"
    url = (
        f"http://{ZOTERO_HOST}:{ZOTERO_PORT}/api/users/0/items"
        f"?q={q}&qmode={qmode}&limit={limit}&format=json"
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            items = json.loads(response.read().decode("utf-8"))
            results = []
            for item in items:
                data = item.get("data", {})
                if data.get("itemType") in ("attachment", "note"):
                    continue

                attachment_key = None
                attachment_info = item.get("links", {}).get("attachment", {})
                if attachment_info:
                    href = attachment_info.get("href", "")
                    if href:
                        attachment_key = href.split("/")[-1]

                creators_list = data.get("creators", [])
                creators_str = ", ".join(
                    c.get("lastName", "")
                    for c in creators_list
                    if "lastName" in c
                )

                results.append(
                    {
                        "key": item.get("key"),
                        "title": data.get("title"),
                        "citationKey": data.get("citationKey"),
                        "creators": creators_str,
                        "date": data.get("date"),
                        "attachmentKey": attachment_key,
                    }
                )
            return results
    except Exception as e:
        print(f"REST API search failed: {e}", file=sys.stderr)
        return []


def search_sqlite(
    query: str, sqlite_path: Path, limit: int = 15
) -> list[dict]:
    """Queries the local Zotero SQLite database for matching items.

    Uses a read-only, immutable database connection to guarantee safety.

    Args:
        query: Search term matching title, creators, or date.
        sqlite_path: Absolute path to the zotero.sqlite file.
        limit: Maximum number of search results to return.

    Returns:
        List of matching items with keys: key, title, citationKey, creators,
        date, attachmentKey.
    """
    if not sqlite_path.exists():
        print(f"SQLite DB not found: {sqlite_path}", file=sys.stderr)
        return []

    conn_str = f"file:{sqlite_path}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(conn_str, uri=True)
        cursor = conn.cursor()

        sql = """
        SELECT DISTINCT i.key, i.itemID
        FROM items i
        LEFT JOIN itemData id ON i.itemID = id.itemID
        LEFT JOIN itemDataValues v ON id.valueID = v.valueID
        LEFT JOIN itemCreators ic ON i.itemID = ic.itemID
        LEFT JOIN creators c ON ic.creatorID = c.creatorID
        WHERE i.itemTypeID NOT IN (?, ?)
          AND (
            v.value LIKE ? OR
            c.lastName LIKE ? OR
            c.firstName LIKE ?
          )
        LIMIT ?
        """
        like_query = f"%{query}%"
        cursor.execute(
            sql,
            (
                ITEM_TYPE_ATTACHMENT,
                ITEM_TYPE_NOTE,
                like_query,
                like_query,
                like_query,
                limit,
            ),
        )
        rows = cursor.fetchall()

        results = []
        for key, item_id in rows:
            results.append(_fetch_item_summary(cursor, key, item_id))

        conn.close()
        return results
    except Exception as e:
        print(f"SQLite search failed: {e}", file=sys.stderr)
        return []


def _fetch_item_summary(cursor, key: str, item_id: int) -> dict:
    """Fetches a summary dict for a single item from SQLite.

    Args:
        cursor: Active SQLite cursor.
        key: The Zotero item key.
        item_id: The internal SQLite item ID.

    Returns:
        Dict with key, title, citationKey, creators, date, attachmentKey.
    """
    cursor.execute(
        """
        SELECT f.fieldName, v.value
        FROM itemData id
        JOIN fields f ON id.fieldID = f.fieldID
        JOIN itemDataValues v ON id.valueID = v.valueID
        WHERE id.itemID = ?
        """,
        (item_id,),
    )
    meta = dict(cursor.fetchall())

    cursor.execute(
        """
        SELECT c.firstName, c.lastName
        FROM itemCreators ic
        JOIN creators c ON ic.creatorID = c.creatorID
        WHERE ic.itemID = ?
        ORDER BY ic.orderIndex
        """,
        (item_id,),
    )
    creators_str = ", ".join(
        last for _first, last in cursor.fetchall() if last
    )

    cursor.execute(
        """
        SELECT att_item.key
        FROM itemAttachments att
        JOIN items att_item ON att.itemID = att_item.itemID
        WHERE att.parentItemID = ?
          AND att.contentType = 'application/pdf'
        LIMIT 1
        """,
        (item_id,),
    )
    att_row = cursor.fetchone()

    return {
        "key": key,
        "title": meta.get("title"),
        "citationKey": meta.get("citationKey"),
        "creators": creators_str,
        "date": meta.get("date"),
        "attachmentKey": att_row[0] if att_row else None,
    }


def get_metadata_api(key: str) -> dict | None:
    """Reads full item metadata via the Zotero Local REST API.

    Args:
        key: The 8-character Zotero item key.

    Returns:
        The item's data dict, or None on failure.
    """
    url = (
        f"http://{ZOTERO_HOST}:{ZOTERO_PORT}"
        f"/api/users/0/items/{key}?format=json"
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            item = json.loads(response.read().decode("utf-8"))
            return item.get("data", {})
    except Exception as e:
        print(f"REST API metadata read failed: {e}", file=sys.stderr)
        return None


def get_metadata_sqlite(key: str, sqlite_path: Path) -> dict | None:
    """Reads item metadata from the local SQLite database.

    Args:
        key: The 8-character Zotero item key.
        sqlite_path: Absolute path to the zotero.sqlite file.

    Returns:
        Dict with all metadata fields, or None on failure.
    """
    if not sqlite_path.exists():
        return None

    conn_str = f"file:{sqlite_path}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(conn_str, uri=True)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT itemID, itemTypeID FROM items WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        item_id, item_type_id = row

        # Get item type name
        cursor.execute(
            "SELECT typeName FROM itemTypes WHERE itemTypeID = ?",
            (item_type_id,),
        )
        type_row = cursor.fetchone()

        # Get all metadata fields
        cursor.execute(
            """
            SELECT f.fieldName, v.value
            FROM itemData id
            JOIN fields f ON id.fieldID = f.fieldID
            JOIN itemDataValues v ON id.valueID = v.valueID
            WHERE id.itemID = ?
            """,
            (item_id,),
        )
        meta = dict(cursor.fetchall())

        # Get creators
        cursor.execute(
            """
            SELECT ct.creatorType, c.firstName, c.lastName
            FROM itemCreators ic
            JOIN creators c ON ic.creatorID = c.creatorID
            JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
            WHERE ic.itemID = ?
            ORDER BY ic.orderIndex
            """,
            (item_id,),
        )
        creators = [
            {
                "creatorType": ctype,
                "firstName": fname or "",
                "lastName": lname or "",
            }
            for ctype, fname, lname in cursor.fetchall()
        ]

        # Get tags
        cursor.execute(
            """
            SELECT t.name
            FROM itemTags it
            JOIN tags t ON it.tagID = t.tagID
            WHERE it.itemID = ?
            """,
            (item_id,),
        )
        tags = [{"tag": name} for (name,) in cursor.fetchall()]

        # Get attachment keys
        cursor.execute(
            """
            SELECT att_item.key, att.contentType, att.path
            FROM itemAttachments att
            JOIN items att_item ON att.itemID = att_item.itemID
            WHERE att.parentItemID = ?
            """,
            (item_id,),
        )
        attachments = [
            {"key": akey, "contentType": ctype, "path": path}
            for akey, ctype, path in cursor.fetchall()
        ]

        conn.close()

        result = {
            "key": key,
            "itemType": type_row[0] if type_row else "unknown",
            "creators": creators,
            "tags": tags,
            "attachments": attachments,
        }
        result.update(meta)
        return result
    except Exception as e:
        print(f"SQLite metadata read failed: {e}", file=sys.stderr)
        return None


def get_text_api(attachment_key: str) -> str | None:
    """Retrieves fulltext for a Zotero attachment via the Local REST API.

    Args:
        attachment_key: The 8-character Zotero key of the attachment.

    Returns:
        The fulltext content if available, None otherwise.
    """
    url = (
        f"http://{ZOTERO_HOST}:{ZOTERO_PORT}"
        f"/api/users/0/items/{attachment_key}/fulltext"
    )
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("content")
    except Exception as e:
        print(f"REST API fulltext failed: {e}", file=sys.stderr)
        return None


def get_text_local(attachment_key: str, zotero_dir: Path) -> str | None:
    """Retrieves fulltext locally from the Zotero storage directory.

    Tries multiple methods in order:
    1. Plaintext cache (.zotero-ft-cache)
    2. PDF text extraction (pdftotext)
    3. HTML snapshot plain text

    Args:
        attachment_key: The 8-character Zotero key of the attachment.
        zotero_dir: Path to the Zotero data directory (e.g. ~/Zotero).

    Returns:
        Fulltext content if successfully extracted, None otherwise.
    """
    attach_dir = zotero_dir / "storage" / attachment_key
    if not attach_dir.exists():
        print(f"Attachment dir not found: {attach_dir}", file=sys.stderr)
        return None

    # 1. Plaintext cache (.zotero-ft-cache)
    cache_file = attach_dir / ".zotero-ft-cache"
    if cache_file.exists():
        try:
            return cache_file.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"Error reading .zotero-ft-cache: {e}", file=sys.stderr)

    # 2. PDF text extraction (pdftotext)
    pdf_files = list(attach_dir.glob("*.pdf"))
    if pdf_files:
        try:
            result = subprocess.run(
                ["pdftotext", str(pdf_files[0]), "-"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout
        except Exception as e:
            print(f"pdftotext failed: {e}", file=sys.stderr)

    # 3. HTML snapshot plain text
    html_files = list(attach_dir.glob("*.html"))
    if html_files:
        try:
            content = html_files[0].read_text(
                encoding="utf-8", errors="replace"
            )
            import html as html_module

            text = re.sub(r"<[^>]+>", " ", content)
            text = html_module.unescape(text)
            return re.sub(r"\s+", " ", text).strip()
        except Exception as e:
            print(f"HTML parsing failed: {e}", file=sys.stderr)

    return None


def _is_valid_zotero_key(key: str) -> bool:
    """Checks if a string looks like a standard 8-char Zotero key.

    Args:
        key: The string to validate.

    Returns:
        True if the key matches the Zotero key pattern.
    """
    return bool(re.match(r"^[A-Z0-9]{8}$", key))


def resolve_citation_key(citation_key: str, sqlite_path: Path) -> str | None:
    """Resolves a Better BibTeX citation key to a Zotero parent item key.

    Args:
        citation_key: The Better BibTeX citation key.
        sqlite_path: Absolute path to the zotero.sqlite file.

    Returns:
        The resolved 8-char Zotero key, or None if not found.
    """
    if not sqlite_path.exists():
        return None

    conn_str = f"file:{sqlite_path}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(conn_str, uri=True)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT i.key
            FROM items i
            JOIN itemData id ON i.itemID = id.itemID
            JOIN fields f ON id.fieldID = f.fieldID
            JOIN itemDataValues v ON id.valueID = v.valueID
            WHERE f.fieldName = 'citationKey' AND v.value = ?
            LIMIT 1
            """,
            (citation_key,),
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print(f"Citation key resolution failed: {e}", file=sys.stderr)
        return None


def resolve_attachment_key(parent_key: str, sqlite_path: Path) -> str | None:
    """Finds the primary attachment key for a parent item.

    Args:
        parent_key: 8-character Zotero key of the parent item.
        sqlite_path: Absolute path to the zotero.sqlite file.

    Returns:
        The attachment's Zotero key, or None if not found.
    """
    if not sqlite_path.exists():
        return None

    conn_str = f"file:{sqlite_path}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(conn_str, uri=True)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT att_item.key
            FROM items i
            JOIN itemAttachments att ON i.itemID = att.parentItemID
            JOIN items att_item ON att.itemID = att_item.itemID
            WHERE i.key = ?
            LIMIT 1
            """,
            (parent_key,),
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print(f"Attachment key lookup failed: {e}", file=sys.stderr)
        return None


def _resolve_key(identifier: str, sqlite_path: Path) -> str:
    """Resolves any identifier (Zotero key or citation key) to a Zotero key.

    Args:
        identifier: A Zotero key or citation key.
        sqlite_path: Path to the zotero.sqlite file.

    Returns:
        The resolved Zotero key.

    Raises:
        SystemExit: If the citation key cannot be resolved.
    """
    if _is_valid_zotero_key(identifier):
        return identifier

    resolved = resolve_citation_key(identifier, sqlite_path)
    if resolved:
        return resolved

    print(
        f"Could not resolve citation key: {identifier}",
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> None:
    """CLI entry point for search, metadata, and fulltext retrieval."""
    parser = argparse.ArgumentParser(
        description="Zotero local read — search, metadata, and fulltext."
    )
    parser.add_argument(
        "--zotero-dir",
        type=Path,
        default=None,
        help="Path to Zotero data directory (default: ~/Zotero)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # search command
    sp_search = subparsers.add_parser(
        "search", help="Search for literature items."
    )
    sp_search.add_argument(
        "query", type=str, help="Search query (author, title, year)"
    )
    sp_search.add_argument(
        "--limit", type=int, default=15, help="Max results (default: 15)"
    )
    sp_search.add_argument(
        "--fulltext",
        action="store_true",
        help="Search inside PDF/fulltext content (qmode=everything)",
    )

    # get-text command
    sp_text = subparsers.add_parser(
        "get-text", help="Retrieve fulltext for an item."
    )
    sp_text.add_argument(
        "identifier",
        type=str,
        help="Zotero key (YVHV6XLI) or citation key (wessolly2014Baumstatik)",
    )

    # get-metadata command
    sp_meta = subparsers.add_parser(
        "get-metadata", help="Read full item metadata (local, no API key)."
    )
    sp_meta.add_argument(
        "identifier",
        type=str,
        help="Zotero key (YVHV6XLI) or citation key (wessolly2014Baumstatik)",
    )

    args = parser.parse_args()
    zotero_dir = args.zotero_dir or _default_zotero_dir()
    sqlite_path = zotero_dir / "zotero.sqlite"
    api_active = is_api_running()

    if args.command == "search":
        if api_active:
            results = search_api(
                args.query, limit=args.limit, fulltext=args.fulltext
            )
        else:
            if args.fulltext:
                print(
                    "Warning: --fulltext requires Zotero running (REST API). "
                    "Falling back to title/creator/year search via SQLite.",
                    file=sys.stderr,
                )
            results = search_sqlite(args.query, sqlite_path, limit=args.limit)
        print(json.dumps(results, indent=2, ensure_ascii=False))

    elif args.command == "get-text":
        parent_key = _resolve_key(args.identifier, sqlite_path)

        # Find attachment key
        attachment_key = None
        if api_active and _is_valid_zotero_key(parent_key):
            try:
                url = (
                    f"http://{ZOTERO_HOST}:{ZOTERO_PORT}"
                    f"/api/users/0/items/{parent_key}?format=json"
                )
                with urllib.request.urlopen(url, timeout=3) as response:
                    item_data = json.loads(response.read().decode("utf-8"))
                    href = (
                        item_data.get("links", {})
                        .get("attachment", {})
                        .get("href", "")
                    )
                    if href:
                        attachment_key = href.split("/")[-1]
            except Exception:
                pass

        if not attachment_key:
            attachment_key = resolve_attachment_key(parent_key, sqlite_path)
        if not attachment_key:
            attachment_key = parent_key

        text = None
        if api_active:
            text = get_text_api(attachment_key)
        if not text:
            text = get_text_local(attachment_key, zotero_dir)

        if text:
            print(text)
        else:
            print(
                f"Could not retrieve fulltext for '{args.identifier}' "
                f"(attachment key: '{attachment_key}'). "
                f"Try using the agent's view_file tool on the PDF directly.",
                file=sys.stderr,
            )
            sys.exit(1)

    elif args.command == "get-metadata":
        parent_key = _resolve_key(args.identifier, sqlite_path)

        metadata = None
        if api_active:
            metadata = get_metadata_api(parent_key)
        if not metadata:
            metadata = get_metadata_sqlite(parent_key, sqlite_path)

        if metadata:
            print(json.dumps(metadata, indent=2, ensure_ascii=False))
        else:
            print(
                f"Could not read metadata for '{args.identifier}'.",
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
