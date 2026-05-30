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
2.  **`ZOTERO_API_KEY`**: Must be set in `~/.env`. Obtain from
    https://www.zotero.org/settings/keys (requires "Allow write access").
3.  **`ZOTERO_LIBRARY_ID`**: Must be set in `~/.env`. Find your library ID at
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
or inspect the `~/.env` file or its variables.

## Core Rules

-   🚨 **ONE item per invocation** — never batch-update multiple items.
-   🚨 **NEVER use `delete_item()`** — only `update_item()` is permitted.
-   🚨 **NEVER modify attachments or files** — only metadata fields.
-   🚨 **ALWAYS show the diff and WAIT for explicit user approval** before
    writing.

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

**Output:** JSON object with all metadata fields for the item.

**Recipes:**
```bash
# Read and format as table
uv run scripts/zotero_update.py read "YVHV6XLI" | jq '{title, date, DOI, creators: [.creators[] | "\(.firstName) \(.lastName)"]}'
```

#### `update` — Update a single metadata field (REQUIRES USER APPROVAL)

```bash
uv run scripts/zotero_update.py update "ZOTERO_KEY" --field FIELD --value "NEW_VALUE"
```

Supports all standard Zotero metadata fields: `title`, `date`, `DOI`,
`abstractNote`, `url`, `volume`, `issue`, `pages`, `publisher`, etc.

For creator updates, use JSON format:
```bash
uv run scripts/zotero_update.py update "YVHV6XLI" --field creators --value '[{"creatorType": "author", "firstName": "Lothar", "lastName": "Wessolly"}]'
```

## Mandatory Workflow

When correcting metadata, agents MUST follow this exact workflow:

1.  **Read current metadata** using `read` command.
    Display all fields to the user in a readable table.

2.  **Read the source attachment** using the `zotero_local_read` skill
    (`get-text` command). Extract the correct metadata from the actual document
    (title page, DOI, authors, year, journal, etc.).

3.  **Show a diff** comparing current Zotero metadata vs. proposed corrections:
    ```
    Field        | Current (Zotero)       | Proposed (from source)
    -------------|------------------------|------------------------
    title        | "Grundlagen der KS..." | "Grundlagen der Kronensicherung..."
    date         | 2019                   | 2019 ✓
    creators[0]  | Detter, A.             | Detter, Andreas
    DOI          | (empty)                | 10.xxxx/example
    ```

4.  **STOP and wait for explicit user approval.** Do NOT proceed without
    approval.

5.  **Apply the correction** using the `update` command.

6.  **Verify the change.** Re-read the item via `read` command and confirm the
    update was applied correctly. Show the user the updated metadata.
    Remind the user to **sync Zotero** (`Ctrl+Shift+S` or green sync button)
    so the Local API reflects the changes.
