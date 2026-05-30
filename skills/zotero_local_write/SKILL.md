---
name: zotero_local_write
description: >-
  Correct metadata for a single Zotero item via the Zotero Web API. Use when
  the user asks to fix, update, or correct Zotero metadata (title, authors,
  date, DOI, etc.). Requires ZOTERO_API_KEY and ZOTERO_LIBRARY_ID in ~/.env.
  Always shows a diff and waits for explicit user approval before writing.
  Trigger on: Zotero fix, metadata correction, update Zotero, fix title, fix
  author, fix DOI, zotero-fix.
---

# Zotero Local Write

Controlled metadata corrections for a single Zotero item via the Zotero Web API.

## Prerequisites

1.  **`uv`**: Read the `uv` skill and follow its setup instructions to ensure
    `uv` is installed and on PATH.
2.  **`.env` file**: Make sure `~/.env` exists. Create one if it does not exist.
3.  **`ZOTERO_API_KEY`**: Must be set in `~/.env`. Obtain from
    https://www.zotero.org/settings/keys (requires "Allow write access").
4.  **`ZOTERO_LIBRARY_ID`**: Must be set in `~/.env`. Find your library ID at
    https://www.zotero.org/settings/keys (shown as "Your userID for use in API
    calls").

If the variables are missing from `~/.env`, do NOT ask the user to paste them
into the chat (this would leak keys into the agent's context). Instead, give the
user these commands:

```bash
printf "Enter Zotero API key (typing hidden): " && read -s key && echo && echo "ZOTERO_API_KEY=$key" >> ~/.env && echo "Saved."
```

```bash
printf "Enter Zotero Library ID: " && read lib_id && echo "ZOTERO_LIBRARY_ID=$lib_id" >> ~/.env && echo "Saved."
```

The scripts load credentials automatically via `dotenv`. **NEVER** read, print,
or inspect the `~/.env` file or its variables (e.g. no `cat`, `grep`, `echo`,
`printenv`, or `os.environ.get` on keys). Credentials must stay out of the
agent's context.

## Structure of the Skill Folder

-   `SKILL.md` — This file
-   `scripts/zotero_update.py` — CLI tool (read, update)
-   `references/web-api-reference.md` — Zotero Web API field reference

## Core Rules

-   🚨 **ONE item per invocation** — never batch-update multiple items.
-   🚨 **NEVER use `delete_item()`** — only `update_item()` is permitted.
-   🚨 **NEVER modify attachments or files** — only metadata fields.
-   🚨 **ALWAYS show the diff and WAIT for explicit user approval** before
    writing.
-   **No fabrication**: Never invent metadata values. Extract correct data from
    the actual document using the `zotero_local_read` skill's `get-text` command.

## CLI Usage

```bash
uv run scripts/zotero_update.py <command> [args]
```

All commands are run from **this skill's directory**.

### Commands

#### `read` — Read current metadata for an item

```bash
uv run scripts/zotero_update.py read "ZOTERO_KEY"
```

**Arguments:**

-   `ZOTERO_KEY` (str, required) — The 8-character Zotero item key.

**Output:** JSON object with all Zotero metadata fields (title, creators, date,
DOI, tags, collections, etc.).

**Recipes:**
```bash
# Read and extract key fields
uv run scripts/zotero_update.py read "P3XQNZ6V" | jq '{title, date, DOI, creators: [.creators[] | "\(.firstName) \(.lastName)"]}'

# Read and show all tags
uv run scripts/zotero_update.py read "P3XQNZ6V" | jq '.tags'
```

---

#### `update` — Update a single metadata field (REQUIRES USER APPROVAL)

```bash
uv run scripts/zotero_update.py update "ZOTERO_KEY" --field FIELD --value "NEW_VALUE"
```

**Arguments:**

-   `ZOTERO_KEY` (str, required) — The 8-character Zotero item key.
-   `--field FIELD` (str, required) — Metadata field name. Supported fields:
    `title`, `date`, `DOI`, `abstractNote`, `url`, `volume`, `issue`, `pages`,
    `publisher`, `place`, `language`, `ISBN`, `ISSN`, `series`, `edition`,
    `numPages`, `shortTitle`, `archive`, `archiveLocation`, `rights`, `extra`,
    `creators`, `tags`.
-   `--value "VALUE"` (str, required) — New value. For complex fields
    (`creators`, `tags`), pass valid JSON.

**Output:** JSON confirmation with old and new values:

```json
{
  "status": "updated",
  "key": "P3XQNZ6V",
  "field": "title",
  "old_value": "Manual of tree statics...",
  "new_value": "Manual of Tree Statics and Tree Inspection"
}
```

**Recipes:**
```bash
# Update a simple text field
uv run scripts/zotero_update.py update "P3XQNZ6V" --field title --value "Manual of Tree Statics and Tree Inspection"

# Update creators (JSON format)
uv run scripts/zotero_update.py update "P3XQNZ6V" --field creators --value '[{"creatorType": "author", "firstName": "Lothar", "lastName": "Wessolly"}, {"creatorType": "author", "firstName": "Martin", "lastName": "Erb"}]'

# Add a DOI
uv run scripts/zotero_update.py update "P3XQNZ6V" --field DOI --value "10.1234/example"
```

---

## Mandatory Workflow

When correcting metadata, agents MUST follow this exact workflow:

### 1. Read Current Metadata

```bash
uv run scripts/zotero_update.py read "ZOTERO_KEY" | jq '{title, date, DOI, creators, publisher, ISBN}'
```

Display all fields to the user in a readable table.

### 2. Read the Source Document

Use the `zotero_local_read` skill to extract correct metadata from the actual
document (title page, DOI, authors, year, journal):

```bash
uv run /path/to/zotero_local_read/scripts/zotero_search.py get-text "ZOTERO_KEY" | head -500
```

### 3. Show a Diff

Compare current Zotero metadata vs. proposed corrections:

```
Field        | Current (Zotero)       | Proposed (from source)
-------------|------------------------|------------------------
title        | "Grundlagen der KS..." | "Grundlagen der Kronensicherung..."
date         | 2019                   | 2019 ✓
creators[0]  | Detter, A.             | Detter, Andreas
DOI          | (empty)                | 10.xxxx/example
```

### 4. STOP — Wait for User Approval

Do NOT proceed without explicit user approval.

### 5. Apply and Verify

```bash
# Apply the correction
uv run scripts/zotero_update.py update "KEY" --field title --value "Grundlagen der Kronensicherung..."

# Verify the change
uv run scripts/zotero_update.py read "KEY" | jq '{title}'
```

Remind the user to **sync Zotero** (`Ctrl+Shift+S` or green sync button)
so the Local API reflects the changes.

## Error Handling

| Situation | Behavior | Action |
|---|---|---|
| `ZOTERO_API_KEY` missing | Exit code 1, error on stderr | Follow prerequisite setup |
| `ZOTERO_LIBRARY_ID` missing | Exit code 1, error on stderr | Follow prerequisite setup |
| Item key not found (404) | Exit code 1, pyzotero exception | Verify key with `search` first |
| Network error | Exit code 1, pyzotero exception | Check internet connection |
| Version conflict (412) | Exit code 1, pyzotero exception | Re-read item and retry |
| Invalid JSON for complex field | Exit code 1, parse error | Fix JSON syntax in `--value` |
