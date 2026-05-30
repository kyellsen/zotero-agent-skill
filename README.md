# zotero-agent-skill

Platform-agnostic AI agent skills for local Zotero library access. Works natively
with **Antigravity**, **Claude Code**, **Codex**, and **Cursor**.

## Skills

| Skill | Purpose | Access Level |
|---|---|---|
| `zotero_local_read` | Search, fulltext retrieval & metadata | Read-only (REST API + SQLite + filesystem) |
| `zotero_local_write` | Metadata corrections | Read+Write (Web API via `pyzotero`) |

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   AI Agent                       │
├──────────────────┬──────────────────────────────┤
│ zotero_local_read│ zotero_local_write           │
│ (search, text,   │ (metadata correct)           │
│  metadata, API   │                              │
│  recipes)        │                              │
├──────────────────┼──────────────────────────────┤
│ Local REST API   │ Zotero Web API               │
│ :23119/api/      │ api.zotero.org (R/W)         │
│ READ-ONLY        │ pyzotero + ZOTERO_API_KEY    │
├──────────────────┴──────────────────────────────┤
│            Zotero Desktop App                    │
│            SQLite DB (fallback, read-only)       │
│            Storage: PDFs, HTML, ft-cache          │
└─────────────────────────────────────────────────┘
```

## Prerequisites

- **`uv`** — Python package manager (resolves inline script dependencies)
- **`sqlite3`** — Available on all Linux/macOS systems
- **`~/Zotero/`** — Local Zotero data directory (configurable via `--zotero-dir`)
- **`pdftotext`** — Optional, for PDF text extraction fallback (`poppler-utils`)

For write access only:
- **`ZOTERO_API_KEY`** — In `~/.env` (obtain from https://www.zotero.org/settings/keys)
- **`ZOTERO_LIBRARY_ID`** — In `~/.env` (your personal library ID)

## Installation

### Antigravity (via Ansible symlink)

```bash
# Managed by linux_aurora_dx Ansible — automatic via `just setup`
# Manual: ln -s ~/code/infra/zotero-agent-skill ~/.gemini/config/plugins/zotero-local
```

### Claude Code

```bash
git clone https://github.com/kyellsen/zotero-agent-skill.git ~/.claude/skills/zotero-local
```

### Codex

```bash
git clone https://github.com/kyellsen/zotero-agent-skill.git ~/.agents/skills/zotero-local
```

### Cursor

```bash
git clone https://github.com/kyellsen/zotero-agent-skill.git .cursor/skills/zotero-local
```

## Quick Start

```bash
cd /path/to/this/repo

# Search for literature
uv run skills/zotero_local_read/scripts/zotero_search.py search "Wessolly"

# Search inside PDF content (fulltext)
uv run skills/zotero_local_read/scripts/zotero_search.py search "Windlast" --fulltext

# Get fulltext of an item
uv run skills/zotero_local_read/scripts/zotero_search.py get-text "YVHV6XLI"

# Get item metadata (local, no API key needed)
uv run skills/zotero_local_read/scripts/zotero_search.py get-metadata "YVHV6XLI"

# Read item metadata via Web API (write skill)
uv run skills/zotero_local_write/scripts/zotero_update.py read "YVHV6XLI"
```

## License

MIT
