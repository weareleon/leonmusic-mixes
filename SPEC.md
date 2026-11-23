# Mix hub format, version 1

This is an open format (MIT licence): anyone can host a hub, and anything can read one. leon.music is one client.

A hub is a static website with a **`hub.json`** file. A client is given the hub's address (`https://host/path/`). It reads
`https://host/path/hub.json`, shows the mixes, and downloads the ones its admin picks.

## hub.json

UTF-8 JSON, at most 5 MB.

| Field | Type | |
|---|---|---|
| `format` | integer | `1`. Clients refuse hubs with a higher number than they understand. |
| `name` | string | Hub name, at most 80 characters. |
| `description` | string | Optional. |
| `apply` | URL | Optional page where creators can submit mixes. |
| `curators` | array | People, festivals, radio shows or labels that publish mixes. |
| `mixes` | array | The mixes. |

### Curator

| Field | Type | |
|---|---|---|
| `id` | string | **Required.** `^[a-z0-9][a-z0-9-]{0,79}$`, unique in the hub. |
| `name` | string | Display name. |
| `bio` | string | Optional, plain text. |
| `url` | URL | Optional website. |
| `color` | `#rrggbb` | Optional brand colour. |
| `avatar` | URL | Optional square image (JPEG/PNG). |
| `banner` | URL | Optional wide image, about 4:1. |

### Mix

| Field | Type | |
|---|---|---|
| `id` | string | **Required.** Same rules as curator ids, unique in the hub. Changing it makes it a new mix. |
| `title` | string | **Required.** |
| `dj` | string | The mix's artist. Defaults to the CUE sheet's top-level `PERFORMER`, then the curator's name. |
| `curator` | string | **Required.** A curator `id` from this hub. |
| `collection` | string | Optional grouping on the curator's page, e.g. `"Summer Festival 2026"`. |
| `year` | integer | Optional. |
| `genre` | string | Optional, defaults to `"Dance"`. |
| `explicit` | boolean | Optional, defaults to `false`. |
| `description` | string | Optional, plain text. |
| `color` | `#rrggbb` | Optional page colour. Clients may derive one from the cover. |
| `cover` | URL | Optional square cover. |
| `cue` | URL | **Required.** The CUE sheet. |
| `audio.url` | URL | **Required.** The full mix (MP3, M4A/AAC, FLAC, OGG, Opus or WAV). |
| `audio.size` | integer | Size in bytes. |
| `audio.sha256` | hex string | Clients should refuse a download that doesn't match. |
| `duration` | number | Length in seconds. |
| `tracks` | integer | Number of songs in the CUE sheet, for display. |

**URLs** may be absolute (`https://…`) or relative to `hub.json`. Only `http` and `https` are allowed.

### CUE sheet

A standard CUE sheet. Clients use the top-level `PERFORMER`/`TITLE` and, for each `TRACK`, its `TITLE`, `PERFORMER` and
`INDEX 01 mm:ss:ff` (75 frames per second). A song runs from its `INDEX 01` to the next song's `INDEX 01`, and the last
one to the end of the file. The first song always starts at 0:00. Encoding: UTF-8 (Windows-1252 is accepted).

## Compatibility

New optional fields can be added without changing `format`, so clients must ignore fields they don't know. Anything a
version-1 client would misread gets a new `format` number.

## Example

```json
{
  "format": 1,
  "name": "Example Mixes",
  "curators": [{"id": "example-fest", "name": "Example Fest", "avatar": "curators/example-fest/avatar.jpg"}],
  "mixes": [{
    "id": "ef26-someone", "title": "Example Fest 2026: Someone (DJ Mix)", "dj": "Someone", "curator": "example-fest",
    "collection": "Example Fest 2026", "year": 2026, "cover": "mixes/ef26-someone/cover.jpg",
    "cue": "mixes/ef26-someone/mix.cue",
    "audio": {"url": "https://example.com/files/ef26-someone.mp3", "size": 145000000, "sha256": "…"},
    "duration": 3621.4, "tracks": 22
  }]
}
```
