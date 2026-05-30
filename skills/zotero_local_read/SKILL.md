---
name: zotero_local_read
description: >-
  Search and retrieve fulltext from a local Zotero library. Use when the user
  asks to find references, search for papers by author/title/year, read PDF
  content, or extract text from Zotero items. Supports REST API (Zotero
  running), SQLite fallback (offline), and filesystem cache access. Trigger on:
  Zotero, literature search, reference lookup, citation key, fulltext, paper,
  PDF content, BibTeX key, bibliography.
---

# Zotero Local Read

Read-only search, metadata, and fulltext retrieval from a local Zotero library.

## Prerequisites

1.  **`uv`**: Read the `uv` skill and follow its setup instructions to ensure
    `uv` is installed and on PATH.
2.  **Zotero data directory**: `~/Zotero/` must exist with `zotero.sqlite` and
    `storage/` subdirectory. Override with `--zotero-dir` if non-standard.
3.  **`pdftotext`** (optional): Install `poppler-utils` for PDF text extraction
    fallback. Not required if Zotero's fulltext cache (`.zotero-ft-cache`) is
    populated.

## Core Rules

-   🚨 **READ-ONLY**: NEVER write to, modify, or delete any file in the Zotero
    storage directory or database.
-   **SQLite safety**: NEVER open the database without `?mode=ro&immutable=1`.
-   **Prefer the CLI** (`scripts/zotero_search.py`) for standard operations
    (search, get-text, get-metadata). For advanced queries not covered by the
    CLI, use the direct API recipes documented below or in `references/`.
-   **JSON processing**: Use `jq` to filter and transform JSON output to prevent
    context overflow.

## CLI Usage

```bash
uv run scripts/zotero_search.py <command> [args]
```

All commands are run from **this skill's directory**.

### Commands

#### `search` — Find items by author, title, year, or keyword

```bash
uv run scripts/zotero_search.py search "QUERY" [--limit N] [--fulltext] [--zotero-dir PATH]
```

- Default: Searches title, creator, year only.
- `--fulltext`: Searches inside PDF/document content (requires Zotero running).

**Recipes:**
```bash
# Basic search
uv run scripts/zotero_search.py search "Wessolly" | jq '.[] | {key, title}'

# Search INSIDE document content (PDFs, HTML snapshots)
uv run scripts/zotero_search.py search "Windlast" --fulltext --limit 20

# Search with higher limit
uv run scripts/zotero_search.py search "Kronensicherung" --limit 30
```

#### `get-text` — Retrieve fulltext for an item

```bash
uv run scripts/zotero_search.py get-text "KEY_OR_CITATION_KEY" [--zotero-dir PATH]
```

Accepts both 8-char Zotero keys (`YVHV6XLI`) and Better BibTeX citation keys
(`wessolly2014Baumstatik`). Automatically resolves citation keys via SQLite.

**Fulltext priority chain:**
1. REST API `/fulltext` endpoint (Zotero running, item indexed)
2. `.zotero-ft-cache` plaintext file (fastest offline method)
3. `pdftotext` extraction from PDF (requires `poppler-utils`)
4. HTML snapshot text extraction (for web page snapshots)

If all methods fail, use the agent's `view_file` tool directly on the PDF for
built-in OCR.

**Recipes:**
```bash
# Get text and pipe to head for preview
uv run scripts/zotero_search.py get-text "YVHV6XLI" | head -100

# Get text for a citation key
uv run scripts/zotero_search.py get-text "wessolly2014Baumstatik"

# Search then get text for the first result
KEY=$(uv run scripts/zotero_search.py search "Wessolly" | jq -r '.[0].key')
uv run scripts/zotero_search.py get-text "$KEY" | head -50
```

#### `get-metadata` — Read full item metadata (local, no API key needed)

```bash
uv run scripts/zotero_search.py get-metadata "KEY_OR_CITATION_KEY" [--zotero-dir PATH]
```

Returns complete metadata including title, creators, date, DOI, tags,
collections, and attachment info. Uses REST API when available, SQLite fallback
otherwise. **No Web API key required.**

**Recipes:**
```bash
# Get metadata for a specific item
uv run scripts/zotero_search.py get-metadata "P3XQNZ6V" | jq '{title, date, DOI, creators}'

# Get metadata for a citation key
uv run scripts/zotero_search.py get-metadata "wessolly2016ManualTreeStatics"
```

## Advanced Recipes (Direct API Access)

For operations not covered by the CLI, agents can use `curl` and `sqlite3`
directly. The Zotero Local REST API (port 23119) is **physically read-only** —
there is no risk of data corruption.

> ⚠️ Read the full reference: **[references/api-recipes.md](references/api-recipes.md)**

### Quick Reference

```bash
# List all collections
curl -s "http://localhost:23119/api/users/0/collections?format=json" | jq '.[].data | {key, name}'

# Export item as BibTeX
curl -s "http://localhost:23119/api/users/0/items/KEY?format=bibtex"

# Filter items by tag
curl -s "http://localhost:23119/api/users/0/items?tag=citable&format=json&limit=50" | jq '.[].data | {key, title}'

# Get all items in a collection
curl -s "http://localhost:23119/api/users/0/collections/COLL_KEY/items?format=json" | jq '.[].data | {key, title}'

# Read raw item metadata via REST API
curl -s "http://localhost:23119/api/users/0/items/KEY?format=json" | jq '.data'

# Find PDF path for an attachment key
ls ~/Zotero/storage/ATTACHMENT_KEY/*.pdf

# Read fulltext cache directly
cat ~/Zotero/storage/ATTACHMENT_KEY/.zotero-ft-cache | head -50

# SQLite: Find items by tag (offline)
sqlite3 "file:$HOME/Zotero/zotero.sqlite?mode=ro&immutable=1" \
  "SELECT i.key, v.value FROM items i
   JOIN itemTags it ON i.itemID = it.itemID
   JOIN tags t ON it.tagID = t.tagID
   JOIN itemData id ON i.itemID = id.itemID
   JOIN fields f ON id.fieldID = f.fieldID AND f.fieldName = 'title'
   JOIN itemDataValues v ON id.valueID = v.valueID
   WHERE t.name = 'citable' LIMIT 10"
```

## How It Works

The CLI automatically detects whether the Zotero Local REST API is running
and falls back to direct SQLite + filesystem access if not:

| Method | Requires Zotero? | Speed | Scope |
|---|---|---|---|
| REST API search | ✅ Yes | Fast | Full Zotero search |
| REST API fulltext search | ✅ Yes | Fast | PDF/document content |
| SQLite search | ❌ No | Fast | Title/creator/date only |
| REST API fulltext retrieval | ✅ Yes | Fast | Pre-indexed content |
| `.zotero-ft-cache` | ❌ No | Instant | Cached plaintext |
| `pdftotext` | ❌ No | Medium | PDF text layer |
| HTML parsing | ❌ No | Fast | Web snapshots |
