"""Shared pytest setup: markers and import path for the skill scripts."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "skills" / "zotero_local_read" / "scripts"))


def pytest_configure(config):
    """Registers the canon test markers."""
    config.addinivalue_line("markers", "unit: fast, no network, local I/O < 1 MB")
    config.addinivalue_line("markers", "integration: real filesystem, no network")
    config.addinivalue_line("markers", "system: needs a running Zotero")
