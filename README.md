# leon.music mix hub

A **mix hub** is a small static website that shares DJ mixes with leon.music servers. Server admins add the hub in
**Admin panel → DJ Mixes**, browse it, and press **Add** on a mix. leon.music downloads the mix and its CUE sheet, cuts it
into songs, and creates a curator page for whoever published it. Listeners find it under **Search → DJ Mixes**.

Only the hub owner can publish to this hub. Anyone else applies through the **Submit a DJ mix** issue form, and each
submission is reviewed by hand.

## Open source: host your own hub

The hub format and these tools are open source under the [MIT licence](LICENSE). The format is described in
[SPEC.md](SPEC.md). Anyone can run a hub, for a festival, a radio show, a label or just their own mixes, and every
leon.music server can add as many hubs as it likes.

1. Press **Use this template** on GitHub, or copy this folder.
2. Edit `hub.config.json` (name, description, your own `apply` link) and delete the example content.
3. Turn on GitHub Pages (Settings → Pages → Deploy from branch → `main`, `/`), or serve the folder any other way.
4. Add mixes as described below. Your hub's address is the Pages URL, e.g. `https://you.github.io/your-hub/`.

The licence covers the code, the website and the format. The mixes, covers and CUE sheets on a hub belong to their
creators. Only publish mixes you made or have permission to share.

## How it's hosted

| Part | Where | Why |
|---|---|---|
| `hub.json`, `index.html`, covers, CUE sheets, curator images | **GitHub Pages** (this repo) | Small files, free, versioned |
| The mix audio (50 MB to 2 GB each) | **GitHub Releases** of this repo, one asset per mix | Pages and git can't hold files over 100 MB; release assets can be up to 2 GB and are free to download |

Prefer to host it yourself? Serve this folder from any web server, for example behind a Cloudflare Tunnel, and leave the
audio next to `hub.json`. Then build without `--audio-base`.

## Adding a mix

1. Create `mixes/<mix-id>/` (lowercase letters, numbers and dashes, e.g. `tl26-alesso-w1`) with:
   - `mix.json`
     ```json
     {"title": "Sunset Festival 2026: Nova Lane at Mainstage (DJ Mix)", "dj": "Nova Lane", "curator": "sunset-festival",
      "collection": "Sunset Festival 2026", "year": 2026, "genre": "Dance", "explicit": false,
      "description": "Recorded live at the Mainstage."}
     ```
   - `mix.cue` is the CUE sheet. Each song needs `TRACK`, `TITLE`, `PERFORMER` and `INDEX 01 mm:ss:ff` (75 frames per second).
   - `cover.jpg` is a square cover.
   - the audio, named after the mix id, e.g. `tl26-alesso-w1.mp3`. It stays out of git (see `.gitignore`).
2. If the curator is new, create `curators/<curator-id>/curator.json` (`name`, `bio`, `url`, `color`), plus `avatar.jpg`
   (square) and `banner.jpg` (about 4:1).
3. Build the catalogue and upload the audio:
   ```powershell
   python build_hub.py --audio-base https://github.com/<owner>/<repo>/releases/download/mixes/
   gh release upload mixes mixes/<mix-id>/<mix-id>.mp3 --clobber
   ```
   Make the `mixes` release once with `gh release create mixes --title "Mix audio" --notes "Audio files for the hub"`.
4. Commit and push. GitHub Pages publishes the new `hub.json`, and servers see the mix the next time they browse the hub.

To fix a CUE sheet, edit it, rebuild and push. Admins then press **Update** on the mix, and plays and likes are kept.

## `hub.json` (format 1)

```json
{
  "format": 1, "name": "...", "description": "...", "apply": "https://...",
  "curators": [{"id": "sunset-festival", "name": "...", "bio": "...", "url": "...", "color": "#c8147a",
                "avatar": "curators/sunset-festival/avatar.jpg", "banner": "curators/sunset-festival/banner.jpg"}],
  "mixes": [{"id": "sf26-nova-lane", "title": "...", "dj": "...", "curator": "sunset-festival", "collection": "...",
             "year": 2026, "genre": "Dance", "explicit": false, "description": "...",
             "cover": "mixes/sf26-nova-lane/cover.jpg", "cue": "mixes/sf26-nova-lane/mix.cue",
             "audio": {"url": "https://...", "size": 123456789, "sha256": "..."}, "duration": 3601.2, "tracks": 24}]
}
```

Links can be relative to `hub.json` or absolute. leon.music checks each download against `sha256` before importing it.
