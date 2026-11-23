"""Publish a DJ mix to your leon.music mix hub in one go.

Double-click "Publish a mix.cmd" (or run: python publish_mix.py). Pick the mix's audio and CUE sheet, check the
details, press Publish. The publisher:
  1. copies the files into the hub (and makes a cover if you don't have one),
  2. uploads the audio to the hub's GitHub release,
  3. updates hub.json, commits and pushes, so GitHub Pages shows the mix a minute later.

Needs git and the GitHub CLI (gh), signed in with an account that can push to the hub repo.
"""
import json, os, re, shutil, subprocess, sys, threading, random
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

HERE = Path(__file__).resolve().parent
CONF = Path.home() / ".leon-music" / "mixhub-publisher.json"
DEFAULT_REPO = "weareleon/leonmusic-mixes"
AUDIO = (".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wav")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

def slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return (s[:70].rstrip("-") or "mix")

def parse_cue(text: str) -> dict:
    top, tracks, cur = {"title": "", "performer": ""}, [], None
    for raw in text.splitlines():
        cmd, _, rest = raw.strip().partition(" ")
        cmd, rest = cmd.upper(), rest.strip()
        val = rest[1:-1] if len(rest) >= 2 and rest[0] == rest[-1] == '"' else rest
        if cmd == "TRACK":
            cur = {"title": "", "performer": "", "start": None}; tracks.append(cur)
        elif cmd in ("TITLE", "PERFORMER"):
            (cur if cur is not None else top)[cmd.lower()] = val
        elif cmd == "INDEX" and cur is not None and rest.split()[0].lstrip("0") == "1":
            try:
                mm, ss, ff = (int(x) for x in rest.split()[1].split(":")); cur["start"] = mm * 60 + ss + ff / 75
            except (ValueError, IndexError):
                pass
    top["tracks"] = [t for t in tracks if t["start"] is not None]
    return top

def read_text(p: Path) -> str:
    b = p.read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try: return b.decode(enc)
        except UnicodeDecodeError: pass
    return b.decode("latin-1")

def run(cmd, cwd=None, log=None):
    if log: log("$ " + " ".join(str(c) for c in cmd))
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, creationflags=NO_WINDOW)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or f"{cmd[0]} failed").strip()[-600:])
    return r.stdout.strip()

def make_cover(path: Path, dj: str, sub: str, color: str):
    """A simple cover: colour blobs + the DJ's name, like the demo covers."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    def font(sz):
        for n in ("ariblk.ttf", "Arial Black.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
            try: return ImageFont.truetype(n, sz)
            except Exception: pass
        return ImageFont.load_default()
    c = tuple(int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) if re.match(r"^#[0-9a-fA-F]{6}$", color or "") else (210, 30, 140)
    c2 = (min(255, c[2] + 90), min(255, c[0] // 2 + 60), min(255, c[1] + 40))
    S = 1000; rng = random.Random(dj); im = Image.new("RGB", (S, S), c); d = ImageDraw.Draw(im)
    for k in range(9):
        x, y, r = rng.randint(0, S), rng.randint(0, S), rng.randint(S // 4, int(S / 1.5))
        d.ellipse((x - r, y - r, x + r, y + r), fill=c2 if k % 2 else tuple(min(255, v + 40) for v in c))
    im = im.filter(ImageFilter.GaussianBlur(S // 10)); d = ImageDraw.Draw(im)
    name = dj.upper(); size = 150
    while size > 50 and d.textlength(name, font=font(size)) > S * .9: size -= 8
    d.text((50, S - 70 - size - 60), name, font=font(size), fill="white")
    d.text((54, S - 110), sub.upper()[:40], font=font(44), fill="white")
    im.save(path, quality=90)

class App:
    def __init__(self, root):
        self.root = root
        root.title("Publish a mix")
        root.geometry("640x720")
        self.conf = json.loads(CONF.read_text()) if CONF.exists() else {}
        self.v = {k: tk.StringVar() for k in ("audio", "cue", "cover", "title", "dj", "curator", "new_name", "collection",
                                               "year", "genre", "desc", "repo", "logo", "banner", "bio", "url")}
        self.v["repo"].set(self.conf.get("repo", DEFAULT_REPO))
        self.v["genre"].set("Dance"); self.v["year"].set(str(__import__("datetime").date.today().year))
        self.explicit = tk.BooleanVar()
        f = ttk.Frame(root, padding=16); f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)
        row = [0]
        def add(label, widget, browse=None):
            ttk.Label(f, text=label).grid(row=row[0], column=0, sticky="w", pady=3, padx=(0, 10))
            widget.grid(row=row[0], column=1, sticky="ew", pady=3)
            if browse:
                ttk.Button(f, text="Browse…", command=browse).grid(row=row[0], column=2, padx=(6, 0))
            row[0] += 1
        def head(t):
            ttk.Label(f, text=t, font=("Segoe UI", 11, "bold")).grid(row=row[0], column=0, columnspan=3, sticky="w", pady=(12, 4)); row[0] += 1
        head("1. The files")
        add("Mix audio", ttk.Entry(f, textvariable=self.v["audio"]), lambda: self.pick("audio", [("Audio", " ".join("*" + e for e in AUDIO))]))
        add("CUE sheet", ttk.Entry(f, textvariable=self.v["cue"]), lambda: self.pick("cue", [("CUE sheet", "*.cue"), ("All files", "*.*")]))
        add("Cover (optional)", ttk.Entry(f, textvariable=self.v["cover"]), lambda: self.pick("cover", [("Images", "*.jpg *.jpeg *.png")]))
        head("2. About the mix")
        add("Title", ttk.Entry(f, textvariable=self.v["title"]))
        add("DJ", ttk.Entry(f, textvariable=self.v["dj"]))
        self.cur_box = ttk.Combobox(f, textvariable=self.v["curator"], state="readonly")
        add("Curator", self.cur_box)
        self.cur_box.bind("<<ComboboxSelected>>", lambda e: self.toggle_new())
        self.new_frame = ttk.Frame(f); self.new_frame.columnconfigure(1, weight=1)
        for i, (lab, key, br) in enumerate((("New curator name", "new_name", None), ("Bio (optional)", "bio", None),
                                             ("Website (optional)", "url", None),
                                             ("Logo (optional)", "logo", lambda: self.pick("logo", [("Images", "*.jpg *.jpeg *.png")])),
                                             ("Banner (optional)", "banner", lambda: self.pick("banner", [("Images", "*.jpg *.jpeg *.png")])))):
            ttk.Label(self.new_frame, text=lab).grid(row=i, column=0, sticky="w", pady=2, padx=(0, 10))
            ttk.Entry(self.new_frame, textvariable=self.v[key]).grid(row=i, column=1, sticky="ew", pady=2)
            if br: ttk.Button(self.new_frame, text="Browse…", command=br).grid(row=i, column=2, padx=(6, 0))
        self.new_frame.grid(row=row[0], column=0, columnspan=3, sticky="ew", padx=(20, 0)); self.new_row = row[0]; row[0] += 1
        add("Collection", ttk.Entry(f, textvariable=self.v["collection"]))
        add("Genre", ttk.Entry(f, textvariable=self.v["genre"]))
        add("Year", ttk.Entry(f, textvariable=self.v["year"], width=8))
        add("Description", ttk.Entry(f, textvariable=self.v["desc"]))
        ttk.Checkbutton(f, text="Contains explicit language", variable=self.explicit).grid(row=row[0], column=1, sticky="w"); row[0] += 1
        head("3. Publish")
        add("Hub repo", ttk.Entry(f, textvariable=self.v["repo"]))
        self.btn = ttk.Button(f, text="Publish", command=self.publish); self.btn.grid(row=row[0], column=1, sticky="w", pady=8); row[0] += 1
        self.bar = ttk.Progressbar(f, maximum=100); self.bar.grid(row=row[0], column=0, columnspan=3, sticky="ew"); row[0] += 1
        self.log_box = tk.Text(f, height=8, wrap="word", font=("Consolas", 9)); self.log_box.grid(row=row[0], column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        f.rowconfigure(row[0], weight=1)
        self.curators = {}
        threading.Thread(target=self.prepare, daemon=True).start()

    # ── helpers ──
    def log(self, msg):
        self.root.after(0, lambda: (self.log_box.insert("end", msg + "\n"), self.log_box.see("end")))
    def step(self, pct, msg):
        self.root.after(0, lambda: self.bar.configure(value=pct)); self.log(msg)
    def pick(self, key, types):
        p = filedialog.askopenfilename(filetypes=types)
        if not p: return
        self.v[key].set(p)
        if key == "cue":
            cue = parse_cue(read_text(Path(p)))
            if cue["title"] and not self.v["title"].get(): self.v["title"].set(cue["title"])
            if cue["performer"] and not self.v["dj"].get(): self.v["dj"].set(cue["performer"])
            self.log(f"CUE sheet: {len(cue['tracks'])} songs")
        if key == "audio":
            cue = Path(p).with_suffix(".cue")
            if cue.exists() and not self.v["cue"].get(): self.v["cue"].set(str(cue)); self.pick_cue_info(cue)
    def pick_cue_info(self, p):
        cue = parse_cue(read_text(p))
        if cue["title"] and not self.v["title"].get(): self.v["title"].set(cue["title"])
        if cue["performer"] and not self.v["dj"].get(): self.v["dj"].set(cue["performer"])
        self.log(f"Found {p.name}: {len(cue['tracks'])} songs")
    def toggle_new(self):
        if self.v["curator"].get() == "+ New curator…": self.new_frame.grid()
        else: self.new_frame.grid_remove()
    def repo_dir(self) -> Path:
        return Path.home() / ".leon-music" / "mixhub-repo"

    def prepare(self):
        """Get a fresh copy of the hub repo and list its curators."""
        try:
            run(["gh", "--version"]); run(["git", "--version"])
        except Exception:
            self.log("! Install git and the GitHub CLI (https://cli.github.com), then run: gh auth login"); return
        try:
            self.sync()
        except Exception as e:
            self.log(f"! Couldn't get the hub repo: {e}"); return
        d = self.repo_dir() / "curators"
        self.curators = {}
        for c in sorted(d.glob("*/curator.json")):
            try: self.curators[json.loads(c.read_text(encoding="utf-8"))["name"]] = c.parent.name
            except Exception: pass
        opts = list(self.curators) + ["+ New curator…"]
        def ui():
            self.cur_box["values"] = opts
            self.v["curator"].set(self.conf.get("last_curator") if self.conf.get("last_curator") in self.curators else opts[0])
            self.toggle_new()
        self.root.after(0, ui)
        self.log(f"Ready. Hub has {len(self.curators)} curator(s).")

    def sync(self):
        d, repo = self.repo_dir(), self.v["repo"].get().strip()
        if (d / ".git").exists():
            run(["git", "-C", d, "pull", "--ff-only", "-q"])
        else:
            d.parent.mkdir(parents=True, exist_ok=True)
            run(["gh", "repo", "clone", repo, d, "--", "-q"])

    # ── publish ──
    def publish(self):
        g = {k: v.get().strip() for k, v in self.v.items()}
        audio, cue = Path(g["audio"]), Path(g["cue"])
        errs = []
        if not audio.is_file() or audio.suffix.lower() not in AUDIO: errs.append("Pick the mix audio (MP3, M4A, FLAC, OGG, Opus or WAV).")
        elif audio.stat().st_size > 2 * 1024 ** 3: errs.append("The audio is over 2 GB, GitHub's limit. Export it as a 320 kbps MP3.")
        if not cue.is_file(): errs.append("Pick the CUE sheet.")
        elif len(parse_cue(read_text(cue))["tracks"]) < 1: errs.append("The CUE sheet has no songs with INDEX 01 times.")
        if not g["title"]: errs.append("Give the mix a title.")
        if not g["dj"]: errs.append("Who's the DJ?")
        new = g["curator"] == "+ New curator…"
        if new and not g["new_name"]: errs.append("Name the new curator.")
        if not g["year"].isdigit(): errs.append("Year should be a number like 2026.")
        if errs:
            messagebox.showerror("Publish a mix", "\n".join(errs)); return
        self.btn.configure(state="disabled")
        threading.Thread(target=self._publish, args=(g, audio, cue, new), daemon=True).start()

    def _publish(self, g, audio, cue, new):
        try:
            repo, d = g["repo"], self.repo_dir()
            self.step(5, "Updating the hub…"); self.sync()
            if new:
                cid = slug(g["new_name"]); base = cid; n = 2
                while (d / "curators" / cid).exists(): cid = f"{base}-{n}"; n += 1
                cdir = d / "curators" / cid; cdir.mkdir(parents=True)
                (cdir / "curator.json").write_text(json.dumps({"name": g["new_name"], "bio": g["bio"], "url": g["url"]},
                                                              indent=1, ensure_ascii=False), encoding="utf-8")
                from PIL import Image, ImageOps
                for key, name, size in (("logo", "avatar.jpg", (400, 400)), ("banner", "banner.jpg", (2400, 600))):
                    if g[key]:
                        ImageOps.fit(Image.open(g[key]).convert("RGB"), size, Image.LANCZOS).save(cdir / name, quality=88)
                self.log(f"New curator: {g['new_name']}")
            else:
                cid = self.curators[g["curator"]]
            mid = slug(g["title"]); base = mid; n = 2
            while (d / "mixes" / mid).exists(): mid = f"{base}-{n}"; n += 1
            mdir = d / "mixes" / mid; mdir.mkdir(parents=True)
            self.step(15, f"Copying files for {mid}…")
            ext = audio.suffix.lower()
            shutil.copyfile(audio, mdir / f"{mid}{ext}")
            (mdir / "mix.cue").write_text(read_text(cue), encoding="utf-8")
            if g["cover"]:
                from PIL import Image, ImageOps
                ImageOps.fit(Image.open(g["cover"]).convert("RGB"), (1000, 1000), Image.LANCZOS).save(mdir / "cover.jpg", quality=90)
            else:
                color = ""
                cj = d / "curators" / cid / "curator.json"
                if cj.exists(): color = json.loads(cj.read_text(encoding="utf-8")).get("color", "")
                make_cover(mdir / "cover.jpg", g["dj"], g["collection"] or g["genre"], color)
                self.log("Made a cover (pick one next time if you have one)")
            (mdir / "mix.json").write_text(json.dumps({"title": g["title"], "dj": g["dj"], "curator": cid,
                "collection": g["collection"], "year": int(g["year"]), "genre": g["genre"] or "Dance",
                "explicit": self.explicit.get(), "description": g["desc"]}, indent=1, ensure_ascii=False), encoding="utf-8")
            self.step(25, f"Uploading the audio ({audio.stat().st_size // (1 << 20)} MB)… this can take a while")
            try:
                run(["gh", "release", "view", "mixes", "--repo", repo])
            except RuntimeError:
                run(["gh", "release", "create", "mixes", "--repo", repo, "--title", "Mix audio", "--notes", "Audio files for the hub's mixes."], log=self.log)
            run(["gh", "release", "upload", "mixes", mdir / f"{mid}{ext}", "--repo", repo, "--clobber"], log=self.log)
            self.step(80, "Updating hub.json…")
            out = run([sys.executable, d / "build_hub.py", "--root", d,
                       "--audio-base", f"https://github.com/{repo}/releases/download/mixes/"])
            self.log(out.splitlines()[0] if out else "hub.json updated")
            self.step(90, "Publishing…")
            run(["git", "-C", d, "add", "-A"])
            run(["git", "-C", d, "commit", "-q", "-m", f"Add mix: {g['title']}"])
            run(["git", "-C", d, "push", "-q"], log=self.log)
            try: (mdir / f"{mid}{ext}").unlink()            # it's on GitHub now; hub.json remembers its size and checksum
            except OSError: pass
            self.conf.update(repo=repo, last_curator=g["new_name"] if new else g["curator"])
            CONF.parent.mkdir(parents=True, exist_ok=True); CONF.write_text(json.dumps(self.conf))
            owner, name = repo.split("/")
            self.step(100, f"Done! It's on https://{owner.lower()}.github.io/{name}/ in a minute or two.")
            self.root.after(0, lambda: messagebox.showinfo("Publish a mix", f"Published “{g['title']}”.\n\nServers can add it from Admin → DJ Mixes in a minute or two."))
            self.root.after(0, lambda: [self.v[k].set("") for k in ("audio", "cue", "cover", "title", "desc", "new_name", "bio", "url", "logo", "banner")])
            threading.Thread(target=self.prepare, daemon=True).start()
        except Exception as e:
            self.log(f"! {e}")
            try:                                        # leave the local copy clean so a half-finished mix isn't published later
                run(["git", "-C", self.repo_dir(), "reset", "-q", "--hard", "@{u}"]); run(["git", "-C", self.repo_dir(), "clean", "-fdxq"])
            except Exception:
                pass
            msg = str(e)
            self.root.after(0, lambda: messagebox.showerror("Publish a mix", f"Something went wrong:\n\n{msg}"))
        finally:
            self.root.after(0, lambda: self.btn.configure(state="normal"))

if __name__ == "__main__":
    root = tk.Tk()
    try: ttk.Style().theme_use("vista")
    except Exception: pass
    App(root)
    root.mainloop()
