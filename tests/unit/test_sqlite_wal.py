"""SQLite access must see writes that still sit in Zotero's WAL file.

Zotero runs its database in WAL mode with an exclusive lock and may go days
without a checkpoint. The fixture reproduces that on-disk state: the main file
holds one item, the WAL holds a second one that the main file does not.
"""

import hashlib
import io
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

import zotero_search as zs

OLD_KEY, OLD_CITEKEY = "OLDITEM1", "old2020Checkpointed"
NEW_KEY, NEW_CITEKEY = "NEWITEM1", "dee2026CorrigendumComparativeEffects"
NEW_ATTACHMENT_KEY = "NEWATT01"

SCHEMA = """
CREATE TABLE items (itemID INTEGER PRIMARY KEY, itemTypeID INT, key TEXT);
CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
CREATE TABLE itemData (itemID INT, fieldID INT, valueID INT);
CREATE TABLE itemAttachments (
    itemID INT, parentItemID INT, contentType TEXT, path TEXT
);
INSERT INTO fields VALUES (1, 'title'), (2, 'citationKey');
"""


def _add_item(conn: sqlite3.Connection, item_id: int, key: str, citekey: str):
    conn.execute("INSERT INTO items VALUES (?, 2, ?)", (item_id, key))
    conn.execute(
        "INSERT INTO itemDataValues VALUES (?, ?)", (item_id, citekey)
    )
    conn.execute("INSERT INTO itemData VALUES (?, 2, ?)", (item_id, item_id))


def _digest(directory: Path) -> dict[str, str]:
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(directory.iterdir())
    }


@pytest.fixture
def zotero_dir(tmp_path: Path) -> Path:
    """A Zotero data dir whose newest item exists only in zotero.sqlite-wal."""
    live = tmp_path / "live"
    live.mkdir()
    conn = sqlite3.connect(live / "zotero.sqlite")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA locking_mode=EXCLUSIVE")  # as Zotero does: no -shm
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.executescript(SCHEMA)
    _add_item(conn, 1, OLD_KEY, OLD_CITEKEY)
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    _add_item(conn, 2, NEW_KEY, NEW_CITEKEY)
    conn.execute("INSERT INTO items VALUES (3, 1, ?)", (NEW_ATTACHMENT_KEY,))
    conn.execute(
        "INSERT INTO itemAttachments VALUES (3, 2, 'application/pdf', '')"
    )
    conn.commit()

    # Freeze the files while the writer is still open, as they look while
    # Zotero runs; closing the writer would checkpoint and delete the WAL.
    frozen = tmp_path / "Zotero"
    frozen.mkdir()
    for name in ("zotero.sqlite", "zotero.sqlite-wal"):
        shutil.copyfile(live / name, frozen / name)
    conn.close()
    return frozen


@pytest.fixture(autouse=True)
def _isolated_snapshots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(zs, "SNAPSHOT_PARENT", tmp_path)
    zs._sqlite_uri.cache_clear()
    yield
    zs._sqlite_uri.cache_clear()


@pytest.mark.unit
def test_fixture_reproduces_immutable_blind_spot(zotero_dir: Path):
    sqlite_path = zotero_dir / "zotero.sqlite"
    assert (zotero_dir / "zotero.sqlite-wal").stat().st_size > 0

    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro&immutable=1", uri=True)
    keys = {k for (k,) in conn.execute("SELECT key FROM items")}
    conn.close()

    assert keys == {OLD_KEY}


@pytest.mark.unit
def test_citation_key_in_wal_resolves(zotero_dir: Path):
    sqlite_path = zotero_dir / "zotero.sqlite"

    assert zs.resolve_citation_key(NEW_CITEKEY, sqlite_path) == NEW_KEY
    assert zs.resolve_citation_key(OLD_CITEKEY, sqlite_path) == OLD_KEY


@pytest.mark.unit
def test_attachment_in_wal_resolves(zotero_dir: Path):
    sqlite_path = zotero_dir / "zotero.sqlite"

    assert zs.resolve_attachment_key(NEW_KEY, sqlite_path) == NEW_ATTACHMENT_KEY


@pytest.mark.unit
def test_status_counts_wal_items(zotero_dir: Path):
    status = zs.get_status(zotero_dir, zotero_dir / "zotero.sqlite")

    assert status["item_count"] == 2
    assert status["attachment_count"] == 1


@pytest.mark.unit
def test_zotero_files_are_never_touched(zotero_dir: Path):
    before = _digest(zotero_dir)

    zs.resolve_citation_key(NEW_CITEKEY, zotero_dir / "zotero.sqlite")
    zs.get_status(zotero_dir, zotero_dir / "zotero.sqlite")

    assert _digest(zotero_dir) == before  # no -shm, no checkpoint, no edits


@pytest.mark.unit
def test_snapshot_is_taken_once_per_process(zotero_dir: Path):
    sqlite_path = zotero_dir / "zotero.sqlite"

    first = zs._sqlite_uri(sqlite_path)
    second = zs._sqlite_uri(sqlite_path)

    assert first == second
    assert str(zotero_dir) not in first  # the copy, not the original


@pytest.mark.unit
def test_without_wal_the_original_is_opened_immutable(zotero_dir: Path):
    (zotero_dir / "zotero.sqlite-wal").unlink()
    sqlite_path = zotero_dir / "zotero.sqlite"

    assert zs._sqlite_uri(sqlite_path) == (
        f"file:{sqlite_path}?mode=ro&immutable=1"
    )
    assert zs.resolve_citation_key(OLD_CITEKEY, sqlite_path) == OLD_KEY


@pytest.mark.unit
def test_api_citation_key_needs_exact_match(monkeypatch: pytest.MonkeyPatch):
    payload = [
        {"key": "AAAAAAAA", "data": {"citationKey": NEW_CITEKEY + "A"}},
        {"key": "DEFNE2UU", "data": {"itemType": "attachment"}},
        {"key": "2MCM9PVA", "data": {"citationKey": NEW_CITEKEY}},
    ]
    seen_urls = []

    def fake_urlopen(url, timeout):
        seen_urls.append(url)
        return io.BytesIO(json.dumps(payload).encode())

    monkeypatch.setattr(zs.urllib.request, "urlopen", fake_urlopen)

    assert zs.resolve_citation_key_api(NEW_CITEKEY) == "2MCM9PVA"
    assert zs.resolve_citation_key_api("missing2026Key") is None
    assert f"q={NEW_CITEKEY}" in seen_urls[0]
