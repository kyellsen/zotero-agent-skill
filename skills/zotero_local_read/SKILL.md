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

## Structure of the Skill Folder

-   `SKILL.md` — This file
-   `scripts/zotero_search.py` — CLI tool (search, get-text, get-metadata, status)
-   `references/api-recipes.md` — Direct curl and sqlite3 recipes for advanced queries

## Core Rules

-   🚨 **READ-ONLY**: NEVER write to, modify, or delete any file in the Zotero
    storage directory or database.
-   **SQLite safety**: NEVER open the database without `?mode=ro&immutable=1`.
-   **Prefer the CLI** (`scripts/zotero_search.py`) for standard operations.
    For advanced queries not covered by the CLI, use the direct API recipes
    in `references/api-recipes.md`.
-   **JSON processing**: Use `jq` to filter and transform JSON output to prevent
    context overflow.
-   **Citation output**: Always return the `citationKey` field alongside results
    so the user can reference sources in their documents (e.g. `@citationKey`).
-   **No fabrication**: Never invent Zotero keys or citation keys. Use `search`
    to look them up. Report empty results accurately.

## Context Management

-   **Slim fulltext output**: Fulltext can be 100k+ characters. Always pipe
    through `head -500` for preview, or use `grep -i "KEYWORD"` to extract
    relevant passages. Never read raw fulltext into context without truncation.
-   **Limit search results**: Use `--limit 10` for overview queries. Only
    increase when explicitly searching for completeness.
-   **Filter early**: Use `jq` to extract only needed fields before reading
    JSON into context (e.g. `jq '.[] | {key, title, citationKey}'`).
-   **Search termination**: If 3 varied search queries return no results,
    conclude that no items match rather than continuing to iterate.

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

**Arguments:**

-   `QUERY` (str, required) — Search term (author name, title fragment, year).
-   `--limit N` (int, default 15) — Maximum number of results.
-   `--fulltext` (flag) — Search inside PDF/document content instead of
    title/creator/year. Requires Zotero running (REST API). Falls back to
    title/creator/year via SQLite with a warning if Zotero is not running.
-   `--zotero-dir PATH` (Path, optional) — Override Zotero data directory.

**Output:** JSON array of matching items:

```json
[
  {
    "key": "P3XQNZ6V",
    "title": "Manual of tree statics and tree inspection",
    "citationKey": "wessolly2016ManualTreeStatics",
    "creators": "Wessolly, Erb",
    "date": "2016",
    "attachmentKey": "QMZB6VWH"
  }
]
```

**Recipes:**
```bash
# Basic search — slim output
uv run scripts/zotero_search.py search "Wessolly" | jq '.[] | {key, title, citationKey}'

# Search INSIDE document content (PDFs, HTML snapshots)
uv run scripts/zotero_search.py search "Windlast" --fulltext --limit 20

# Search with higher limit
uv run scripts/zotero_search.py search "Kronensicherung" --limit 30
```

---

#### `get-text` — Retrieve fulltext for an item

```bash
uv run scripts/zotero_search.py get-text "KEY_OR_CITATION_KEY" [--zotero-dir PATH]
```

**Arguments:**

-   `KEY_OR_CITATION_KEY` (str, required) — Either an 8-char Zotero key
    (`YVHV6XLI`) or a Better BibTeX citation key (`wessolly2014Baumstatik`).
    Citation keys are automatically resolved via SQLite.
-   `--zotero-dir PATH` (Path, optional) — Override Zotero data directory.

**Output:** Plain text on stdout. Can be very large (100k+ chars for books).

**Fulltext priority chain:**
1. REST API `/fulltext` endpoint (Zotero running, item indexed)
2. `.zotero-ft-cache` plaintext file (fastest offline method)
3. `pdftotext` extraction from PDF (requires `poppler-utils`)
4. HTML snapshot text extraction (for web page snapshots)

If all methods fail, exit code 1 with diagnostic on stderr. In this case, use
the agent's `view_file` tool directly on the PDF for built-in OCR.

**Recipes:**
```bash
# Preview first 500 lines (ALWAYS do this first)
uv run scripts/zotero_search.py get-text "YVHV6XLI" | head -500

# Search for specific content within a document
uv run scripts/zotero_search.py get-text "wessolly2014Baumstatik" | grep -i "kronensicherung" -A 5

# Search then get text for the first result
KEY=$(uv run scripts/zotero_search.py search "Wessolly" | jq -r '.[0].key')
uv run scripts/zotero_search.py get-text "$KEY" | head -500
```

---

#### `get-metadata` — Read full item metadata (local, no API key needed)

```bash
uv run scripts/zotero_search.py get-metadata "KEY_OR_CITATION_KEY" [--zotero-dir PATH]
```

**Arguments:**

-   `KEY_OR_CITATION_KEY` (str, required) — Zotero key or citation key.
-   `--zotero-dir PATH` (Path, optional) — Override Zotero data directory.

**Output:** JSON object with all metadata fields:

```json
{
  "key": "P3XQNZ6V",
  "itemType": "book",
  "title": "Manual of tree statics and tree inspection",
  "creators": [{"creatorType": "author", "firstName": "Lothar", "lastName": "Wessolly"}, ...],
  "date": "2016",
  "publisher": "Patzer Verlag",
  "ISBN": "978-3-87617-143-2",
  "citationKey": "wessolly2016ManualTreeStatics",
  "tags": [{"tag": "citable"}, ...],
  "attachments": [{"key": "QMZB6VWH", "contentType": "application/pdf", "path": "storage:...pdf"}]
}
```

**Recipes:**
```bash
# Get compact metadata
uv run scripts/zotero_search.py get-metadata "P3XQNZ6V" | jq '{title, date, DOI, citationKey, creators: [.creators[] | "\(.firstName) \(.lastName)"]}'

# Get metadata for a citation key
uv run scripts/zotero_search.py get-metadata "wessolly2016ManualTreeStatics"

# Find the PDF path for an item
uv run scripts/zotero_search.py get-metadata "P3XQNZ6V" | jq '.attachments[] | select(.contentType == "application/pdf") | .path'
```

---

#### `status` — Check Zotero availability and library stats

```bash
uv run scripts/zotero_search.py status [--zotero-dir PATH]
```

**Arguments:**

-   `--zotero-dir PATH` (Path, optional) — Override Zotero data directory.

**Output:** JSON object with availability info:

```json
{
  "rest_api": true,
  "sqlite": true,
  "zotero_dir": "/home/user/Zotero",
  "item_count": 3600,
  "attachment_count": 4200
}
```

---

## Common Workflows

### Find a Source and Read It

```bash
# 1. Search for the item
uv run scripts/zotero_search.py search "Wessolly Baumstatik" | jq '.[] | {key, title, citationKey}'

# 2. Read the fulltext (preview first 500 lines)
uv run scripts/zotero_search.py get-text "wessolly2016ManualTreeStatics" | head -500

# 3. Search for specific content within the document
uv run scripts/zotero_search.py get-text "wessolly2016ManualTreeStatics" | grep -i "kronensicherung" -A 10
```

### Look Up a Citation Key for Typst/LaTeX

```bash
# Search → extract citation key → use in document as @citationKey
uv run scripts/zotero_search.py search "Detter Zugversuch" | jq -r '.[0].citationKey'
# Output: detter2025AktuelleEntwicklungenZur → use as @detter2025AktuelleEntwicklungenZur
```

### Check Metadata Before Citing

```bash
# Verify metadata is correct before citing
uv run scripts/zotero_search.py get-metadata "P3XQNZ6V" | jq '{title, date, creators, DOI, ISBN}'
```

### Find All Items by Tag

```bash
# Direct API recipe (not covered by CLI)
curl -s "http://localhost:23119/api/users/0/items?tag=citable&format=json&limit=100" \
  | jq '[.[].data | {key, title, citationKey, date}]'
```

## Error Handling

| Situation | Behavior | Action |
|---|---|---|
| Zotero not running | Falls back to SQLite + filesystem | No action needed — automatic |
| `--fulltext` without Zotero | Warning on stderr, falls back to title/creator search | Start Zotero for fulltext search |
| Citation key not found | Exit code 1, error on stderr | Verify key with `search` first |
| No attachment found | Exit code 1, diagnostic on stderr | Use `get-metadata` to check attachments |
| PDF not text-indexed | `get-text` fails, suggests `view_file` | Use agent's `view_file` tool on the PDF directly |
| SQLite DB not found | Error on stderr, empty results | Check `--zotero-dir` path |

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

# Find PDF path for an attachment key
ls ~/Zotero/storage/ATTACHMENT_KEY/*.pdf

# Read fulltext cache directly
cat ~/Zotero/storage/ATTACHMENT_KEY/.zotero-ft-cache | head -500
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
