#!/usr/bin/env python3
"""Sound Pack Maker: download audio from one video and package a sound pack."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

try:
    import tkinter.font as tkfont
except ImportError:  # pragma: no cover - tkinter ships with supported Python builds
    tkfont = None

APP_NAME = "Sound Pack Maker"
CONFIG_PATH = Path.home() / ".soundpack_maker.json"
AUDIO_NAME = "menu_music.mp3"

# Three intentionally distinct visual packs. They affect presentation only.
STYLE_PACKS: dict[str, dict[str, str | int]] = {
    "Basic": {
        "description": "Clean, bright, familiar",
        "background": "#F3F5F8",
        "surface": "#FFFFFF",
        "surface_alt": "#EDF1F6",
        "border": "#DCE3EC",
        "text": "#1C2735",
        "muted": "#687789",
        "accent": "#356AE6",
        "accent_hover": "#2457C8",
        "accent_text": "#FFFFFF",
        "field": "#FBFCFE",
        "selection": "#D8E5FF",
        "trough": "#E2E8F0",
        "success": "#16845B",
        "danger": "#C44750",
        "font": "TkDefaultFont",
        "mono": "TkFixedFont",
        "font_size": 10,
        "title_size": 22,
        "console": 0,
    },
    "Signal": {
        "description": "A little more character, still restrained",
        "background": "#11161D",
        "surface": "#19212B",
        "surface_alt": "#202B37",
        "border": "#2C3948",
        "text": "#E9EEF5",
        "muted": "#99A9BC",
        "accent": "#D7A957",
        "accent_hover": "#EAC078",
        "accent_text": "#171A1F",
        "field": "#121A23",
        "selection": "#34485D",
        "trough": "#293746",
        "success": "#83C6A2",
        "danger": "#E08A83",
        "font": "TkDefaultFont",
        "mono": "TkFixedFont",
        "font_size": 10,
        "title_size": 22,
        "console": 0,
    },
    "Half-Life 1 Console": {
        "description": "GoldSrc-inspired green phosphor console",
        "background": "#050B07",
        "surface": "#07130A",
        "surface_alt": "#0D1D11",
        "border": "#244B2B",
        "text": "#A5DDA8",
        "muted": "#5F9666",
        "accent": "#63F078",
        "accent_hover": "#9BFFA5",
        "accent_text": "#031006",
        "field": "#020704",
        "selection": "#1C4D27",
        "trough": "#142A18",
        "success": "#7DFF8F",
        "danger": "#DBA36E",
        "font": "TkFixedFont",
        "mono": "TkFixedFont",
        "font_size": 10,
        "title_size": 18,
        "console": 1,
    },
}


def resource_path(name: str) -> Path | None:
    """Find a bundled resource in a PyInstaller one-file or one-folder build."""
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidate = Path(bundle_dir) / name
        if candidate.is_file():
            return candidate
    return None


def prepare_bundled_runtime() -> None:
    """Make bundled Deno visible to yt-dlp's JavaScript runtime discovery."""
    executable = "deno.exe" if os.name == "nt" else "deno"
    bundled_deno = resource_path(executable)
    if bundled_deno:
        os.environ["PATH"] = str(bundled_deno.parent) + os.pathsep + os.environ.get("PATH", "")


def load_config() -> dict:
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def save_config(cfg: dict) -> None:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as handle:
            json.dump(cfg, handle, indent=2)
    except OSError:
        # Settings persistence is optional; it must never block pack creation.
        pass


def slugify(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_\- ]+", "", text).strip().replace(" ", "_")
    return text.lower() or "soundpack"


def find_ffmpeg() -> str | None:
    """Return the bundled imageio-ffmpeg executable, or a system ffmpeg path."""
    try:
        import imageio_ffmpeg

        executable = imageio_ffmpeg.get_ffmpeg_exe()
        if executable and os.path.isfile(executable):
            return executable
    except Exception:
        pass
    return shutil.which("ffmpeg")


def download_mp3(url: str, dest_dir: str, progress_cb: Callable[[float], None]) -> str:
    prepare_bundled_runtime()
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError(
            "yt-dlp is missing from this build. Rebuild with requirements-build.txt."
        ) from exc

    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise RuntimeError(
            "FFmpeg was not found. The packaged build should include it; "
            "for a source run, install FFmpeg or imageio-ffmpeg."
        )

    def hook(data: dict) -> None:
        if data.get("status") == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            if total:
                downloaded = data.get("downloaded_bytes", 0)
                progress_cb(min(90.0, max(0.0, downloaded / total * 90.0)))
        elif data.get("status") == "finished":
            progress_cb(92.0)

    options = {
        "format": "bestaudio/best",
        "outtmpl": str(Path(dest_dir) / "menu_music.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "ffmpeg_location": ffmpeg,
    }

    with yt_dlp.YoutubeDL(options) as downloader:
        result = downloader.download([url])
    if result:
        raise RuntimeError(f"yt-dlp exited with status {result}.")

    audio_path = Path(dest_dir) / AUDIO_NAME
    if not audio_path.is_file():
        raise RuntimeError("Download finished, but no MP3 file was produced.")
    return str(audio_path)


def build_zip(mp3_path: str, pack_json: dict, folder_name: str, out_dir: str) -> str:
    output_dir = Path(out_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"{folder_name}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{folder_name}/", "")
        archive.write(mp3_path, f"{folder_name}/{AUDIO_NAME}")
        archive.writestr(
            f"{folder_name}/pack.json",
            json.dumps(pack_json, indent=2, ensure_ascii=False),
        )
    return str(zip_path)


class App(tk.Tk):
    """Minimal Tk interface with switchable style packs."""

    def __init__(self) -> None:
        super().__init__()
        self.cfg = load_config()
        self.out_dir = self.cfg.get("output_dir") or str(Path.home())
        saved_pack = self.cfg.get("style_pack", "Basic")
        self.style_pack = saved_pack if saved_pack in STYLE_PACKS else "Basic"
        self.palette = STYLE_PACKS[self.style_pack]
        self._status_kind = "neutral"
        self.style = ttk.Style(self)
        self._font_family = self._resolve_font(str(self.palette["font"]))
        self._mono_family = self._resolve_font(str(self.palette["mono"]))

        self.title(APP_NAME)
        self.geometry("720x760")
        self.minsize(620, 680)
        self._build_ui()
        self._install_context_menus()
        self._apply_theme(persist=False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _resolve_font(self, requested: str) -> str:
        """Use a sensible platform font, falling back to Tk's built-in fonts."""
        if requested in ("TkDefaultFont", "TkFixedFont"):
            try:
                base = tkfont.nametofont(requested) if tkfont else None
                return str(base.actual("family")) if base else "TkDefaultFont"
            except tk.TclError:
                return "TkDefaultFont"

        try:
            available = set(tkfont.families(self)) if tkfont else set()
        except tk.TclError:
            available = set()
        candidates = (
            ["Consolas", "DejaVu Sans Mono", "Liberation Mono", "Courier New"]
            if requested == "TkFixedFont"
            else ["Segoe UI", "Inter", "DejaVu Sans", "Arial"]
        )
        for family in candidates:
            if family in available:
                return family
        try:
            base_name = "TkFixedFont" if requested == "TkFixedFont" else "TkDefaultFont"
            return str(tkfont.nametofont(base_name).actual("family")) if tkfont else "TkDefaultFont"
        except tk.TclError:
            return "TkDefaultFont"

    def _build_ui(self) -> None:
        self.style.theme_use("clam")
        self.shell = ttk.Frame(self, style="App.TFrame", padding=(18, 8, 18, 8))
        self.shell.pack(fill="both", expand=True)
        self.shell.columnconfigure(0, weight=1)

        # Header: title on the left, compact style selector and output action on the right.
        header = ttk.Frame(self.shell, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        header.columnconfigure(0, weight=1)
        brand = ttk.Frame(header, style="App.TFrame")
        brand.grid(row=0, column=0, sticky="w")
        self.kicker = ttk.Label(brand, text="AUDIO TOOLKIT  /  01", style="Kicker.TLabel")
        self.kicker.pack(anchor="w")
        self.brand_title = ttk.Label(brand, text=APP_NAME, style="Title.TLabel")
        self.brand_title.pack(anchor="w", pady=(2, 1))
        self.subtitle = ttk.Label(
            brand,
            text="Turn one video into a ready-to-install sound pack.",
            style="Muted.TLabel",
        )
        self.subtitle.pack(anchor="w")

        controls = ttk.Frame(header, style="App.TFrame")
        controls.grid(row=0, column=1, sticky="e", padx=(18, 0))
        self.style_label = ttk.Label(controls, text="STYLE PACK", style="Kicker.TLabel")
        self.style_label.grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.style_var = tk.StringVar(value=self.style_pack)
        self.style_combo = ttk.Combobox(
            controls,
            textvariable=self.style_var,
            values=list(STYLE_PACKS.keys()),
            state="readonly",
            width=21,
        )
        self.style_combo.grid(row=1, column=0, sticky="ew")
        self.style_combo.bind("<<ComboboxSelected>>", self._on_style_selected)
        self.style_hint = ttk.Label(controls, text=str(self.palette["description"]), style="Muted.TLabel")
        self.style_hint.grid(row=2, column=0, sticky="w", pady=(3, 0))

        self.source_card = ttk.Frame(self.shell, style="Card.TFrame", padding=10)
        self.source_card.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.source_card.columnconfigure(0, weight=1)
        source_head = ttk.Frame(self.source_card, style="CardInner.TFrame")
        source_head.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        source_head.columnconfigure(0, weight=1)
        self.source_heading = ttk.Label(source_head, text="01  /  SOURCE", style="Section.TLabel")
        self.source_heading.grid(row=0, column=0, sticky="w")
        self.source_note = ttk.Label(source_head, text="ONE VIDEO  ·  NO PLAYLIST", style="CardMuted.TLabel")
        self.source_note.grid(row=0, column=1, sticky="e")
        self.url_label = ttk.Label(self.source_card, text="YouTube link", style="FieldLabel.TLabel")
        self.url_label.grid(row=1, column=0, sticky="w", pady=(0, 2))
        self.url = ttk.Entry(self.source_card)
        self.url.grid(row=2, column=0, sticky="ew")

        self.details_card = ttk.Frame(self.shell, style="Card.TFrame", padding=10)
        self.details_card.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        self.details_card.columnconfigure(0, weight=1)
        details_head = ttk.Frame(self.details_card, style="CardInner.TFrame")
        details_head.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        details_head.columnconfigure(0, weight=1)
        self.details_heading = ttk.Label(details_head, text="02  /  PACK DETAILS", style="Section.TLabel")
        self.details_heading.grid(row=0, column=0, sticky="w")
        self.details_note = ttk.Label(details_head, text="EDITABLE MANIFEST", style="CardMuted.TLabel")
        self.details_note.grid(row=0, column=1, sticky="e")

        self.name_label = ttk.Label(self.details_card, text="Pack name", style="FieldLabel.TLabel")
        self.name_label.grid(row=1, column=0, sticky="w", pady=(0, 2))
        self.name = ttk.Entry(self.details_card)
        self.name.grid(row=2, column=0, sticky="ew", pady=(0, 4))

        self.desc_label = ttk.Label(self.details_card, text="Description", style="FieldLabel.TLabel")
        self.desc_label.grid(row=3, column=0, sticky="w", pady=(0, 2))
        self.desc = tk.Text(
            self.details_card,
            height=3,
            wrap="word",
            undo=True,
            borderwidth=1,
            relief="solid",
            padx=8,
            pady=5,
            highlightthickness=1,
        )
        self.desc.grid(row=4, column=0, sticky="ew", pady=(0, 4))

        metadata = ttk.Frame(self.details_card, style="CardInner.TFrame")
        metadata.grid(row=5, column=0, sticky="ew", pady=(0, 4))
        metadata.columnconfigure(0, weight=1)
        metadata.columnconfigure(1, weight=1)
        self.author_label = ttk.Label(metadata, text="Author", style="FieldLabel.TLabel")
        self.author_label.grid(row=0, column=0, sticky="w", pady=(0, 2))
        self.version_label = ttk.Label(metadata, text="Version", style="FieldLabel.TLabel")
        self.version_label.grid(row=0, column=1, sticky="w", padx=(10, 0), pady=(0, 2))
        self.author = ttk.Entry(metadata)
        self.author.grid(row=1, column=0, sticky="ew")
        self.version = ttk.Entry(metadata)
        self.version.insert(0, "v1.0")
        self.version.grid(row=1, column=1, sticky="ew", padx=(10, 0))

        footer_fields = ttk.Frame(self.details_card, style="CardInner.TFrame")
        footer_fields.grid(row=6, column=0, sticky="ew")
        footer_fields.columnconfigure(0, weight=1)
        folder_box = ttk.Frame(footer_fields, style="CardInner.TFrame")
        folder_box.grid(row=0, column=0, sticky="ew", padx=(0, 14))
        folder_box.columnconfigure(0, weight=1)
        self.folder_label = ttk.Label(
            folder_box,
            text="Folder / ZIP name  ·  blank uses pack name",
            style="FieldLabel.TLabel",
        )
        self.folder_label.grid(row=0, column=0, sticky="w", pady=(0, 2))
        self.folder = ttk.Entry(folder_box)
        self.folder.grid(row=1, column=0, sticky="ew")

        options = ttk.Frame(footer_fields, style="CardInner.TFrame")
        options.grid(row=0, column=1, sticky="e")
        self.music = tk.BooleanVar(value=True)
        self.music_check = ttk.Checkbutton(options, text='"music": true', variable=self.music)
        self.music_check.grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.manifest_label = ttk.Label(options, text="MANIFEST VERSION", style="FieldLabel.TLabel")
        self.manifest_label.grid(row=1, column=0, sticky="w", pady=(0, 2))
        self.manifest = ttk.Spinbox(options, from_=1, to=9, width=5, justify="center")
        self.manifest.set("2")
        self.manifest.grid(row=2, column=0, sticky="w")

        self.action_card = ttk.Frame(self.shell, style="Card.TFrame", padding=10)
        self.action_card.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        self.action_card.columnconfigure(0, weight=1)
        action_top = ttk.Frame(self.action_card, style="CardInner.TFrame")
        action_top.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        action_top.columnconfigure(0, weight=1)
        self.action_heading = ttk.Label(action_top, text="03  /  BUILD PACK", style="Section.TLabel")
        self.action_heading.grid(row=0, column=0, sticky="w")
        self.action_note = ttk.Label(action_top, text="MP3  ·  192 KBPS  ·  ZIP", style="CardMuted.TLabel")
        self.action_note.grid(row=0, column=1, sticky="e")
        self.go_btn = ttk.Button(
            self.action_card,
            text="Download & Pack",
            command=self.start,
            style="Primary.TButton",
            takefocus=True,
        )
        self.go_btn.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        self.bar = ttk.Progressbar(self.action_card, maximum=100, mode="determinate")
        self.bar.grid(row=2, column=0, sticky="ew", pady=(0, 5))
        self._status_text = "Ready when you are."
        self.status = tk.StringVar(value=self._status_text)
        self.status_label = ttk.Label(
            self.action_card,
            textvariable=self.status,
            style="Status.TLabel",
            wraplength=620,
        )
        self.status_label.grid(row=3, column=0, sticky="w")

        bottom = ttk.Frame(self.shell, style="App.TFrame")
        bottom.grid(row=4, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        self.out_label = tk.StringVar(value="")
        self.output_label = ttk.Label(bottom, textvariable=self.out_label, style="Muted.TLabel", wraplength=440, justify="left")
        self.output_label.grid(row=0, column=0, sticky="w")
        self.output_button = ttk.Button(
            bottom,
            text="Choose output folder",
            command=self.choose_output,
            style="Quiet.TButton",
        )
        self.output_button.grid(row=0, column=1, sticky="e", padx=(8, 4))
        self.open_button = ttk.Button(
            bottom,
            text="Open",
            command=self.open_output_folder,
            style="Quiet.TButton",
        )
        self.open_button.grid(row=0, column=2, sticky="e")
        self._refresh_out_label()

    def _apply_theme(self, persist: bool = True) -> None:
        """Apply a complete visual pack without recreating widgets or losing input."""
        self.palette = STYLE_PACKS[self.style_pack]
        p = self.palette
        console = bool(p["console"])
        family = self._resolve_font(str(p["font"]))
        mono = self._resolve_font(str(p["mono"]))
        self._font_family = family
        self._mono_family = mono
        size = int(p["font_size"])
        title_size = int(p["title_size"])

        self.configure(background=str(p["background"]))
        self.style.theme_use("clam")
        self.style.configure(".", font=(family, size), background=str(p["background"]), foreground=str(p["text"]))
        self.style.configure("TFrame", background=str(p["background"]))
        self.style.configure("App.TFrame", background=str(p["background"]))
        self.style.configure("CardInner.TFrame", background=str(p["surface"]))
        self.style.configure(
            "Card.TFrame",
            background=str(p["surface"]),
            bordercolor=str(p["border"]),
            relief="solid" if console else "flat",
            borderwidth=1 if console else 0,
        )
        self.style.configure("TLabel", background=str(p["background"]), foreground=str(p["text"]))
        self.style.configure("Muted.TLabel", background=str(p["background"]), foreground=str(p["muted"]), font=(family, max(8, size - 1)))
        self.style.configure("CardMuted.TLabel", background=str(p["surface"]), foreground=str(p["muted"]), font=(mono if console else family, max(8, size - 1)))
        self.style.configure("Kicker.TLabel", background=str(p["background"]), foreground=str(p["accent"]), font=(mono if console else family, max(8, size - 1), "bold"))
        self.style.configure("Title.TLabel", background=str(p["background"]), foreground=str(p["text"]), font=(family, title_size, "bold"))
        self.style.configure("Section.TLabel", background=str(p["surface"]), foreground=str(p["accent"]), font=(mono if console else family, max(9, size - 1), "bold"))
        self.style.configure("FieldLabel.TLabel", background=str(p["surface"]), foreground=str(p["muted"]), font=(mono if console else family, max(8, size - 1), "bold" if console else "normal"))
        self.style.configure("Status.TLabel", background=str(p["surface"]), foreground=str(p["text"]), font=(mono if console else family, size))

        self.style.configure(
            "TEntry",
            fieldbackground=str(p["field"]),
            foreground=str(p["text"]),
            insertcolor=str(p["accent"]),
            bordercolor=str(p["border"]),
            lightcolor=str(p["border"]),
            darkcolor=str(p["border"]),
            padding=(9, 4),
            relief="flat",
            borderwidth=1,
            font=(mono if console else family, size),
        )
        self.style.map(
            "TEntry",
            bordercolor=[("focus", str(p["accent"]))],
            lightcolor=[("focus", str(p["accent"]))],
            darkcolor=[("focus", str(p["accent"]))],
        )
        self.style.configure(
            "TSpinbox",
            fieldbackground=str(p["field"]),
            foreground=str(p["text"]),
            background=str(p["surface_alt"]),
            arrowcolor=str(p["muted"]),
            bordercolor=str(p["border"]),
            padding=(6, 2),
            font=(mono if console else family, size),
        )
        self.style.map("TSpinbox", bordercolor=[("focus", str(p["accent"]))])
        self.style.configure(
            "TCombobox",
            fieldbackground=str(p["field"]),
            foreground=str(p["text"]),
            background=str(p["surface_alt"]),
            arrowcolor=str(p["accent"]),
            bordercolor=str(p["border"]),
            padding=(8, 4),
            font=(mono if console else family, max(9, size - 1)),
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", str(p["field"]))],
            foreground=[("readonly", str(p["text"]))],
            selectbackground=[("readonly", str(p["selection"]))],
            selectforeground=[("readonly", str(p["text"]))],
            bordercolor=[("focus", str(p["accent"]))],
        )
        self.style.configure(
            "TButton",
            background=str(p["surface_alt"]),
            foreground=str(p["text"]),
            bordercolor=str(p["border"]),
            lightcolor=str(p["border"]),
            darkcolor=str(p["border"]),
            padding=(10, 5),
            relief="flat",
            borderwidth=1,
            font=(mono if console else family, size, "bold" if console else "normal"),
        )
        self.style.map(
            "TButton",
            background=[("pressed", str(p["border"])), ("active", str(p["surface_alt"]))],
            foreground=[("disabled", str(p["muted"]))],
        )
        self.style.configure(
            "Quiet.TButton",
            background=str(p["background"]),
            foreground=str(p["muted"]),
            bordercolor=str(p["border"]),
            padding=(8, 5),
            font=(mono if console else family, max(8, size - 1)),
        )
        self.style.map("Quiet.TButton", background=[("active", str(p["surface_alt"]))], foreground=[("active", str(p["accent"]))])
        self.style.configure(
            "Primary.TButton",
            background=str(p["accent"]),
            foreground=str(p["accent_text"]),
            bordercolor=str(p["accent"]),
            lightcolor=str(p["accent"]),
            darkcolor=str(p["accent"]),
            padding=(12, 7),
            font=(mono if console else family, size + (0 if console else 1), "bold"),
        )
        self.style.map(
            "Primary.TButton",
            background=[("pressed", str(p["accent_hover"])), ("active", str(p["accent_hover"]))],
            foreground=[("disabled", str(p["muted"]))],
        )
        self.style.configure("TCheckbutton", background=str(p["surface"]), foreground=str(p["text"]), indicatorcolor=str(p["surface_alt"]), font=(mono if console else family, max(8, size - 1)))
        self.style.map("TCheckbutton", foreground=[("disabled", str(p["muted"]))], background=[("active", str(p["surface"]))], indicatorcolor=[("selected", str(p["accent"])), ("active", str(p["surface_alt"]))])
        self.style.configure(
            "Horizontal.TProgressbar",
            troughcolor=str(p["trough"]),
            background=str(p["accent"]),
            bordercolor=str(p["border"]),
            lightcolor=str(p["accent"]),
            darkcolor=str(p["accent"]),
            thickness=5 if not console else 4,
        )

        # tk.Text and tk.Menu are classic Tk widgets, so theme them separately.
        self.desc.configure(
            background=str(p["field"]),
            foreground=str(p["text"]),
            insertbackground=str(p["accent"]),
            selectbackground=str(p["selection"]),
            selectforeground=str(p["text"]),
            highlightbackground=str(p["border"]),
            highlightcolor=str(p["accent"]),
            font=(mono if console else family, size),
            relief="solid" if console else "flat",
            borderwidth=1 if console else 0,
        )
        self._edit_menu.configure(
            background=str(p["surface_alt"]),
            foreground=str(p["text"]),
            activebackground=str(p["accent"]),
            activeforeground=str(p["accent_text"]),
            disabledforeground=str(p["muted"]),
            selectcolor=str(p["accent"]),
            font=(mono if console else family, max(9, size - 1)),
            borderwidth=1,
            relief="solid",
        )

        # Console pack deliberately uses the restrained terminal vocabulary and caps.
        if console:
            self.title("SOUND PACK MAKER  //  CONSOLE")
            self.kicker.configure(text="GOLDSRC AUDIO TOOL  /  01")
            self.subtitle.configure(text="] source audio  ->  sound pack")
            self.style_label.configure(text="STYLE PRESET")
            self.source_heading.configure(text="01  /  SOURCE INPUT")
            self.source_note.configure(text="SINGLE URL  ·  PLAYLISTS OFF")
            self.url_label.configure(text="YOUTUBE URL")
            self.details_heading.configure(text="02  /  PACK MANIFEST")
            self.details_note.configure(text="PACK.JSON")
            self.name_label.configure(text="PACK NAME")
            self.desc_label.configure(text="DESCRIPTION")
            self.author_label.configure(text="AUTHOR")
            self.version_label.configure(text="VERSION")
            self.folder_label.configure(text="OUTPUT FOLDER NAME  ·  EMPTY = PACK NAME")
            self.music_check.configure(text='"MUSIC": TRUE')
            self.manifest_label.configure(text="MANIFEST VERSION")
            self.action_heading.configure(text="03  /  EXECUTE")
            self.action_note.configure(text="MP3  ·  192 KBPS  ·  ZIP")
            self.go_btn.configure(text="[ DOWNLOAD  &  PACK ]")
            self.output_button.configure(text="SET OUTPUT")
            self.out_label.set(f"OUTPUT: {self.out_dir}")
            self.open_button.configure(text="OPEN")
        else:
            self.title(APP_NAME)
            self.kicker.configure(text="AUDIO TOOLKIT  /  01")
            self.subtitle.configure(text="Turn one video into a ready-to-install sound pack.")
            self.style_label.configure(text="STYLE PACK")
            self.source_heading.configure(text="01  /  SOURCE")
            self.source_note.configure(text="ONE VIDEO  ·  NO PLAYLIST")
            self.url_label.configure(text="YouTube link")
            self.details_heading.configure(text="02  /  PACK DETAILS")
            self.details_note.configure(text="EDITABLE MANIFEST")
            self.name_label.configure(text="Pack name")
            self.desc_label.configure(text="Description")
            self.author_label.configure(text="Author")
            self.version_label.configure(text="Version")
            self.folder_label.configure(text="Folder / ZIP name  ·  blank uses pack name")
            self.music_check.configure(text='"music": true')
            self.manifest_label.configure(text="MANIFEST VERSION")
            self.action_heading.configure(text="03  /  BUILD PACK")
            self.action_note.configure(text="MP3  ·  192 KBPS  ·  ZIP")
            self.go_btn.configure(text="Download & Pack")
            self.output_button.configure(text="Choose output folder")
            self.open_button.configure(text="Open")

        self.style_hint.configure(text=str(p["description"]))
        self.status.set(f"] {self._status_text}" if console else self._status_text)
        status_color = p["text"] if self._status_kind == "neutral" else p["success"] if self._status_kind == "success" else p["danger"]
        self.status_label.configure(foreground=str(status_color))
        if persist:
            self.cfg["style_pack"] = self.style_pack
            self.cfg["output_dir"] = self.out_dir
            save_config(self.cfg)

    def _on_style_selected(self, _event: tk.Event | None = None) -> None:
        selected = self.style_var.get()
        if selected not in STYLE_PACKS:
            return
        self.style_pack = selected
        self._apply_theme(persist=True)

    def _install_context_menus(self) -> None:
        """Add Cut/Copy/Paste/Select All to every editable text control."""
        self._context_widget: tk.Widget | None = None
        self._edit_menu = tk.Menu(self, tearoff=False)
        self._edit_menu.add_command(label="Cut", command=lambda: self._edit_action("<<Cut>>"))
        self._edit_menu.add_command(label="Copy", command=lambda: self._edit_action("<<Copy>>"))
        self._edit_menu.add_command(label="Paste", command=lambda: self._edit_action("<<Paste>>"))
        self._edit_menu.add_separator()
        self._edit_menu.add_command(label="Select All", command=lambda: self._edit_action("<<SelectAll>>"))

        editable_widgets = (
            self.url,
            self.name,
            self.desc,
            self.author,
            self.version,
            self.folder,
            self.manifest,
        )
        for widget in editable_widgets:
            widget.bind("<Button-3>", self._show_edit_menu, add="+")
            widget.bind("<Shift-F10>", self._show_edit_menu, add="+")
            if sys.platform == "darwin":
                widget.bind("<Button-2>", self._show_edit_menu, add="+")
                widget.bind("<Control-Button-1>", self._show_edit_menu, add="+")

    @staticmethod
    def _has_text_selection(widget: tk.Widget) -> bool:
        try:
            if isinstance(widget, tk.Text):
                return bool(widget.tag_ranges("sel"))
            return bool(widget.selection_present())
        except (AttributeError, tk.TclError):
            return False

    @staticmethod
    def _is_editable(widget: tk.Widget) -> bool:
        try:
            return str(widget.cget("state")) not in ("disabled", "readonly")
        except tk.TclError:
            return False

    @staticmethod
    def _has_text(widget: tk.Widget) -> bool:
        try:
            if isinstance(widget, tk.Text):
                return bool(widget.get("1.0", "end-1c"))
            return bool(widget.get())
        except (AttributeError, tk.TclError):
            return False

    def _show_edit_menu(self, event: tk.Event) -> str:
        widget = event.widget
        self._context_widget = widget
        widget.focus_set()
        selected = self._has_text_selection(widget)
        editable = self._is_editable(widget)
        try:
            self.clipboard_get()
            clipboard_has_text = True
        except tk.TclError:
            clipboard_has_text = False

        self._edit_menu.entryconfigure("Cut", state="normal" if selected and editable else "disabled")
        self._edit_menu.entryconfigure("Copy", state="normal" if selected else "disabled")
        self._edit_menu.entryconfigure("Paste", state="normal" if editable and clipboard_has_text else "disabled")
        self._edit_menu.entryconfigure("Select All", state="normal" if self._has_text(widget) else "disabled")
        try:
            self._edit_menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self._edit_menu.grab_release()
            except tk.TclError:
                pass
        return "break"

    def _edit_action(self, virtual_event: str) -> None:
        widget = self._context_widget
        if widget is None:
            return
        try:
            widget.focus_set()
            widget.event_generate(virtual_event)
        except tk.TclError:
            self._context_widget = None

    def _refresh_out_label(self) -> None:
        prefix = "OUTPUT:" if bool(self.palette.get("console")) else "Output:"
        self.out_label.set(f"{prefix} {self.out_dir}")

    def _on_close(self) -> None:
        self.cfg["style_pack"] = self.style_pack
        self.cfg["output_dir"] = self.out_dir
        save_config(self.cfg)
        self.destroy()

    def choose_output(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.out_dir, title="Choose output folder")
        if selected:
            self.out_dir = selected
            self._refresh_out_label()
            self.cfg["output_dir"] = selected
            save_config(self.cfg)

    def open_output_folder(self) -> None:
        folder = Path(self.out_dir).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except (OSError, AttributeError) as exc:
            messagebox.showerror("Could not open folder", str(exc), parent=self)

    def _set_status_display(self, text: str, kind: str = "neutral") -> None:
        self._status_text = text
        self._status_kind = kind
        self.status.set(f"] {text}" if bool(self.palette.get("console")) else text)
        key = "text" if kind == "neutral" else "success" if kind == "success" else "danger"
        self.status_label.configure(foreground=str(self.palette[key]))

    def set_status(self, text: str) -> None:
        self.after(0, lambda: self._set_status_display(text))

    def set_progress(self, value: float) -> None:
        self.after(0, lambda: self.bar.configure(value=value))

    def _finish(self, ok: bool, message: str) -> None:
        self.go_btn.configure(state="normal")
        self._set_status_display(message, "success" if ok else "danger")
        if ok:
            self.bar.configure(value=100)
        else:
            self.bar.configure(value=0)
            messagebox.showerror("Download failed", message, parent=self)

    def start(self) -> None:
        url = self.url.get().strip()
        name = self.name.get().strip()
        if not url:
            messagebox.showwarning("Missing link", "Paste a YouTube link first.", parent=self)
            self.url.focus_set()
            return
        if not name:
            messagebox.showwarning("Missing name", "Enter a name for the pack.", parent=self)
            self.name.focus_set()
            return

        try:
            manifest_version = int(self.manifest.get())
        except ValueError:
            manifest_version = 2

        pack_json = {
            "name": name,
            "description": self.desc.get("1.0", "end-1c").strip(),
            "author": self.author.get().strip(),
            "version": self.version.get().strip(),
            "manifest_version": manifest_version,
            "music": bool(self.music.get()),
            "ignore": [],
            "mappings": {},
        }
        folder = slugify(self.folder.get().strip() or name)
        output_dir = self.out_dir

        self.go_btn.configure(state="disabled")
        self.bar.configure(value=0)
        self._set_status_display("Downloading audio…")
        threading.Thread(
            target=self.worker,
            args=(url, pack_json, folder, output_dir),
            daemon=True,
            name="soundpack-download",
        ).start()

    def worker(self, url: str, pack_json: dict, folder: str, out_dir: str) -> None:
        temporary_dir = tempfile.mkdtemp(prefix="soundpack_")
        try:
            audio = download_mp3(url, temporary_dir, self.set_progress)
            self.set_status("Building ZIP…")
            zip_path = build_zip(audio, pack_json, folder, out_dir)
            self.after(0, lambda: self._finish(True, f"Created: {zip_path}"))
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            self.after(0, lambda message=message: self._finish(False, message))
        finally:
            shutil.rmtree(temporary_dir, ignore_errors=True)


if __name__ == "__main__":
    App().mainloop()
