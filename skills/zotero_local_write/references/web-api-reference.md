# Zotero Web API — Field Reference

Reference for metadata fields that can be read and updated via the
`zotero_update.py` CLI using the Zotero Web API.

## Simple Text Fields

These fields accept plain string values via `--value "text"`:

| Field | Description | Example |
|---|---|---|
| `title` | Item title | `"Manual of Tree Statics"` |
| `date` | Publication date | `"2016"` or `"2016-03-15"` |
| `DOI` | Digital Object Identifier | `"10.1234/example"` |
| `abstractNote` | Abstract text | `"This paper presents..."` |
| `url` | URL | `"https://example.com/paper"` |
| `volume` | Volume number | `"42"` |
| `issue` | Issue number | `"3"` |
| `pages` | Page range | `"123-456"` |
| `publisher` | Publisher name | `"Patzer Verlag"` |
| `place` | Publication place | `"Berlin"` |
| `language` | Language code | `"en"` or `"de"` |
| `ISBN` | International Standard Book Number | `"978-3-87617-143-2"` |
| `ISSN` | International Standard Serial Number | `"1234-5678"` |
| `series` | Series title | `"Springer Series in Wood Science"` |
| `edition` | Edition | `"2nd"` |
| `numPages` | Number of pages | `"342"` |
| `shortTitle` | Short title | `"Tree Statics"` |
| `archive` | Archive name | `"Internet Archive"` |
| `archiveLocation` | Archive identifier | `"ia:treestatics2016"` |
| `rights` | Copyright/license | `"CC BY 4.0"` |
| `extra` | Extra metadata (free text) | `"Original date: 2014"` |

## Complex Fields (JSON)

These fields require valid JSON via `--value 'JSON'`:

### `creators`

Array of creator objects. Each object must have `creatorType`, `firstName`,
`lastName`:

```json
[
  {"creatorType": "author", "firstName": "Lothar", "lastName": "Wessolly"},
  {"creatorType": "author", "firstName": "Martin", "lastName": "Erb"},
  {"creatorType": "editor", "firstName": "Hans", "lastName": "Schmidt"}
]
```

Valid `creatorType` values: `author`, `editor`, `translator`, `seriesEditor`,
`contributor`, `bookAuthor`, `reviewedAuthor`.

### `tags`

Array of tag objects. Each object has a `tag` field:

```json
[
  {"tag": "citable"},
  {"tag": "tree statics"},
  {"tag": "arboriculture"}
]
```

## Item Types

Common Zotero item types and their specific fields:

| Item Type | Extra Fields |
|---|---|
| `book` | `publisher`, `place`, `edition`, `numPages`, `ISBN`, `series` |
| `journalArticle` | `publicationTitle`, `volume`, `issue`, `pages`, `ISSN`, `DOI` |
| `conferencePaper` | `conferenceName`, `proceedingsTitle`, `pages`, `DOI` |
| `bookSection` | `bookTitle`, `publisher`, `pages`, `ISBN` |
| `thesis` | `university`, `thesisType` |
| `report` | `institution`, `reportNumber`, `reportType` |
| `webpage` | `websiteTitle`, `url`, `accessDate` |

## API Constraints

- **One field per update call**: The CLI updates one field at a time.
- **Version tracking**: The Web API uses optimistic locking. The CLI handles
  version tracking automatically (reads current version, sends with update).
- **Rate limit**: The Zotero Web API allows ~50 requests per minute. The CLI
  does not enforce rate limiting, so avoid rapid successive calls.
- **Sync delay**: After updating via Web API, remind the user to sync Zotero
  (`Ctrl+Shift+S`) so the local database reflects the changes.
