# Zotero Local REST API — Direct Access Recipes

The Zotero Local REST API runs on `http://localhost:23119` when Zotero Desktop
is open. It is **physically read-only** — there is no risk of data corruption.

Use these recipes when the CLI commands (`search`, `get-text`, `get-metadata`)
don't cover your use case.

## API Base URL

```
http://localhost:23119/api/users/0/
```

## Check if API is Running

```bash
curl -s "http://localhost:23119/api/users/0/items?limit=1" > /dev/null 2>&1 && echo "Running" || echo "Not running"
```

---

## Search

### Title / Creator / Year Search

```bash
curl -s "http://localhost:23119/api/users/0/items?q=QUERY&qmode=titleCreatorYear&limit=25&format=json" | jq '.[].data | {key, title, citationKey, date}'
```

### Fulltext Search (Inside PDFs and Documents)

```bash
curl -s "http://localhost:23119/api/users/0/items?q=QUERY&qmode=everything&limit=25&format=json" | jq '.[].data | {key, title, citationKey}'
```

### Filter by Tag

```bash
curl -s "http://localhost:23119/api/users/0/items?tag=TAG_NAME&format=json&limit=50" | jq '.[].data | {key, title, date}'
```

### Filter by Item Type

```bash
curl -s "http://localhost:23119/api/users/0/items?itemType=book&format=json&limit=50" | jq '.[].data | {key, title}'
```

### Sort by Date (Newest First)

```bash
curl -s "http://localhost:23119/api/users/0/items?sort=date&direction=desc&limit=10&format=json" | jq '.[].data | {key, title, date}'
```

### Recently Added Items

```bash
curl -s "http://localhost:23119/api/users/0/items?sort=dateAdded&direction=desc&limit=10&format=json" | jq '.[].data | {key, title, dateAdded}'
```

---

## Item Metadata

### Read Full Metadata for One Item

```bash
curl -s "http://localhost:23119/api/users/0/items/KEY?format=json" | jq '.data'
```

### Export as BibTeX

```bash
curl -s "http://localhost:23119/api/users/0/items/KEY?format=bibtex"
```

### Export Multiple Items as BibTeX

```bash
curl -s "http://localhost:23119/api/users/0/items?tag=citable&format=bibtex&limit=100"
```

---

## Collections

### List All Collections

```bash
curl -s "http://localhost:23119/api/users/0/collections?format=json" | jq '.[].data | {key, name, parentCollection}'
```

### Get Items in a Collection

```bash
curl -s "http://localhost:23119/api/users/0/collections/COLLECTION_KEY/items?format=json" | jq '.[].data | {key, title}'
```

### Get Subcollections

```bash
curl -s "http://localhost:23119/api/users/0/collections/COLLECTION_KEY/collections?format=json" | jq '.[].data | {key, name}'
```

---

## Fulltext

### Get Fulltext for an Attachment

```bash
curl -s "http://localhost:23119/api/users/0/items/ATTACHMENT_KEY/fulltext" | jq -r '.content' | head -100
```

### Get Attachment Info for a Parent Item

```bash
curl -s "http://localhost:23119/api/users/0/items/PARENT_KEY/children?format=json" | jq '.[].data | {key, itemType, contentType, filename}'
```

---

## Direct Filesystem Access

### Find PDF Path

```bash
ls ~/Zotero/storage/ATTACHMENT_KEY/*.pdf
```

### Read Fulltext Cache

```bash
cat ~/Zotero/storage/ATTACHMENT_KEY/.zotero-ft-cache | head -100
```

### Extract Text from PDF (pdftotext)

```bash
pdftotext ~/Zotero/storage/ATTACHMENT_KEY/*.pdf - | head -100
```

---

## SQLite Offline Access

Always open with **read-only** and **immutable** flags:

```bash
sqlite3 "file:$HOME/Zotero/zotero.sqlite?mode=ro&immutable=1"
```

### Search by Title

```bash
sqlite3 "file:$HOME/Zotero/zotero.sqlite?mode=ro&immutable=1" \
  "SELECT i.key, v.value AS title
   FROM items i
   JOIN itemData id ON i.itemID = id.itemID
   JOIN fields f ON id.fieldID = f.fieldID AND f.fieldName = 'title'
   JOIN itemDataValues v ON id.valueID = v.valueID
   WHERE i.itemTypeID NOT IN (1, 14) AND v.value LIKE '%QUERY%'
   LIMIT 20"
```

### Search by Author

```bash
sqlite3 "file:$HOME/Zotero/zotero.sqlite?mode=ro&immutable=1" \
  "SELECT DISTINCT i.key, c.lastName, c.firstName
   FROM items i
   JOIN itemCreators ic ON i.itemID = ic.itemID
   JOIN creators c ON ic.creatorID = c.creatorID
   WHERE c.lastName LIKE '%QUERY%'
   LIMIT 20"
```

### Resolve Citation Key to Zotero Key

```bash
sqlite3 "file:$HOME/Zotero/zotero.sqlite?mode=ro&immutable=1" \
  "SELECT i.key
   FROM items i
   JOIN itemData id ON i.itemID = id.itemID
   JOIN fields f ON id.fieldID = f.fieldID AND f.fieldName = 'citationKey'
   JOIN itemDataValues v ON id.valueID = v.valueID
   WHERE v.value = 'CITATION_KEY'"
```

### Find Items by Tag

```bash
sqlite3 "file:$HOME/Zotero/zotero.sqlite?mode=ro&immutable=1" \
  "SELECT i.key, v.value AS title
   FROM items i
   JOIN itemTags it ON i.itemID = it.itemID
   JOIN tags t ON it.tagID = t.tagID
   JOIN itemData id ON i.itemID = id.itemID
   JOIN fields f ON id.fieldID = f.fieldID AND f.fieldName = 'title'
   JOIN itemDataValues v ON id.valueID = v.valueID
   WHERE t.name = 'TAG_NAME'
   LIMIT 20"
```

### Find Attachment Key for a Parent Item

```bash
sqlite3 "file:$HOME/Zotero/zotero.sqlite?mode=ro&immutable=1" \
  "SELECT att_item.key, att.contentType, att.path
   FROM items i
   JOIN itemAttachments att ON i.itemID = att.parentItemID
   JOIN items att_item ON att.itemID = att_item.itemID
   WHERE i.key = 'PARENT_KEY'"
```

### Schema Overview (Zotero 7.x)

| Table | Purpose |
|---|---|
| `items` | All items (key, itemTypeID) |
| `itemTypes` | Type names (book, journalArticle, etc.) |
| `itemData` / `fields` / `itemDataValues` | Metadata key-value pairs |
| `itemCreators` / `creators` / `creatorTypes` | Author information |
| `itemTags` / `tags` | Tag assignments |
| `itemAttachments` | Attachment links (PDF, HTML) |
| `fulltextWords` / `fulltextItems` | Fulltext index |
| `collections` / `collectionItems` | Collection membership |

Item type IDs to exclude from searches: `1` (attachment), `14` (note).
