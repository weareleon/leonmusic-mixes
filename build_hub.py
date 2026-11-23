"""Build hub.json for a leon.music DJ mix hub.

Folder layout (everything except the audio can live in the repo / on GitHub Pages):

    hub.config.json                 {"name": "...", "description": "...", "apply": "https://.../issues/new?template=submit-a-mix.yml"}
    curators/<curator-id>/curator.json   {"name": "Tomorrowland", "bio": "...", "url": "https://...", "color": "#7b2cff"}
    curators/<curator-id>/avatar.jpg     square logo (optional)
    curators/<curator-id>/banner.jpg     wide banner, about 4:1 (optional)
    mixes/<mix-id>/mix.json         {"title": "...", "dj": "Alesso", "curator": "<curator-id>", "collection": "Tomorrowland 2026",
                                     "year": 2026, "genre": "Dance", "explicit": false, "description": "..."}
    mixes/<mix-id>/cover.jpg        square cover
    mixes/<mix-id>/mix.cue          CUE sheet: TRACK / TITLE / PERFORMER / INDEX 01 mm:ss:ff
    mixes/<mix-id>/mix.mp3          the mix (or .m4a/.flac/.ogg/.opus); not committed if you host audio elsewhere

Usage:
    python build_hub.py                                   # audio served next to hub.json (Cloudflare tunnel, any web server)
    python build_hub.py --audio-base https://github.com/<you>/<repo>/releases/download/mixes/
                                                          # audio uploaded as GitHub release assets (up to 2 GB each)
Ids are lowercase letters, numbers and dashes. Re-run after adding or editing a mix.
"""
import argparse, hashlib, json, re, sys
from pathlib import Path

AUDIO = (".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wav")
ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")

def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def duration(p: Path) -> float:
    try:
        from mutagen import File
        return round(float(File(p).info.length), 3)
    except Exception:
        return 0.0

def cue_tracks(p: Path) -> int:
    return sum(1 for line in p.read_text(encoding="utf-8-sig", errors="replace").splitlines() if line.strip().upper().startswith("TRACK "))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="hub folder (default: here)")
    ap.add_argument("--audio-base", default="", help="URL the audio files are uploaded to; the file name is added to it")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    cfg = json.loads((root / "hub.config.json").read_text(encoding="utf-8")) if (root / "hub.config.json").exists() else {}
    hub = {"format": 1, "name": cfg.get("name", "DJ Mixes"), "description": cfg.get("description", ""),
           "apply": cfg.get("apply", ""), "curators": [], "mixes": []}
    problems = []
    for d in sorted((root / "curators").glob("*/")):
        if not ID.match(d.name):
            problems.append(f"curator id '{d.name}' must be lowercase letters, numbers and dashes"); continue
        c = json.loads((d / "curator.json").read_text(encoding="utf-8"))
        c["id"] = d.name
        for img in ("avatar", "banner"):
            if (d / f"{img}.jpg").exists():
                c[img] = f"curators/{d.name}/{img}.jpg"
        hub["curators"].append(c)
    curator_ids = {c["id"] for c in hub["curators"]}
    for d in sorted((root / "mixes").glob("*/")):
        if not ID.match(d.name):
            problems.append(f"mix id '{d.name}' must be lowercase letters, numbers and dashes"); continue
        meta = json.loads((d / "mix.json").read_text(encoding="utf-8"))
        audio = next((f for f in sorted(d.iterdir()) if f.suffix.lower() in AUDIO), None)
        cue = d / "mix.cue"
        if meta.get("curator") not in curator_ids:
            problems.append(f"{d.name}: curator '{meta.get('curator')}' doesn't exist"); continue
        if not audio or not cue.exists():
            problems.append(f"{d.name}: needs an audio file and mix.cue"); continue
        name = f"{d.name}{audio.suffix.lower()}"
        url = (a.audio_base.rstrip("/") + "/" + name) if a.audio_base else f"mixes/{d.name}/{audio.name}"
        m = {"id": d.name, **meta, "cue": f"mixes/{d.name}/mix.cue",
             "audio": {"url": url, "size": audio.stat().st_size, "sha256": sha256(audio)},
             "duration": duration(audio), "tracks": cue_tracks(cue)}
        if (d / "cover.jpg").exists():
            m["cover"] = f"mixes/{d.name}/cover.jpg"
        hub["mixes"].append(m)
        if a.audio_base:
            print(f"  upload {audio}  as  {name}")
    hub["mixes"].sort(key=lambda m: (-(m.get("year") or 0), m["title"].lower()))
    (root / "hub.json").write_text(json.dumps(hub, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"hub.json: {len(hub['curators'])} curators, {len(hub['mixes'])} mixes")
    for p in problems:
        print("  ! " + p)
    return 1 if problems else 0

if __name__ == "__main__":
    sys.exit(main())
