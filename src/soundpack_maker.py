#!/usr/bin/env python3
"""Sound Pack Maker: download a video's audio and package it as a sound pack."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import threading
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable

APP_NAME = "Sound Pack Maker"
CONFIG_PATH = Path.home() / ".soundpack_maker.json"
AUDIO_NAME = "menu_music.mp3"


def resource_path(name: str) -> Path | None:
    """Find a bundled resource in a PyInstaller one-file or one-folder build."""
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidate = Path(bundle_dir) / name
        if candidate.is_file():
            return candidate
    return None


def prepare_bundled_runtime() -> None:
    """Make a bundled Deno runtime visible to yt-dlp's JS runtime discovery."""
    executable = "deno.exe" if os.name == "nt" else "deno"
    bundled_deno = resource_path(executable)
    if bundled_deno:
        # yt-dlp discovers Deno from PATH. Keep the user's existing PATH intact.
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
        # Config persistence is optional; do not interrupt pack creation.
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
    # Set this before importing/initializing yt-dlp so its runtime discovery sees Deno.
    prepare_bundled_runtime()

    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("yt-dlp is missing from this build. Rebuild with requirements-build.txt.") from exc

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
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("540x540")
        self.minsize(490, 500)

        self.cfg = load_config()
        self.out_dir = self.cfg.get("output_dir") or str(Path.home())
        self._build_ui()
        self._install_context_menus()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 4}
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True, padx=8, pady=8)
        root.columnconfigure(0, weight=1)

        top = ttk.Frame(root)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)
        ttk.Label(top, text="YouTube link").grid(row=0, column=0, sticky="w", **pad)
        ttk.Button(top, text="⚙", width=3, command=self.choose_output).grid(
            row=0, column=1, sticky="e", padx=10
        )

        self.url = ttk.Entry(root)
        self.url.grid(row=1, column=0, sticky="ew", **pad)

        ttk.Label(root, text="Name").grid(row=2, column=0, sticky="w", **pad)
        self.name = ttk.Entry(root)
        self.name.grid(row=3, column=0, sticky="ew", **pad)

        ttk.Label(root, text="Description").grid(row=4, column=0, sticky="w", **pad)
        self.desc = tk.Text(root, height=4, wrap="word")
        self.desc.grid(row=5, column=0, sticky="ew", **pad)

        author_version = ttk.Frame(root)
        author_version.grid(row=6, column=0, sticky="ew", **pad)
        author_version.columnconfigure(0, weight=1)
        author_version.columnconfigure(1, weight=1)
        ttk.Label(author_version, text="Author").grid(row=0, column=0, sticky="w")
        ttk.Label(author_version, text="Version").grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.author = ttk.Entry(author_version)
        self.author.grid(row=1, column=0, sticky="ew")
        self.version = ttk.Entry(author_version)
        self.version.insert(0, "v1.0")
        self.version.grid(row=1, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(root, text="Folder / zip name (blank = from Name)").grid(
            row=7, column=0, sticky="w", **pad
        )
        self.folder = ttk.Entry(root)
        self.folder.grid(row=8, column=0, sticky="ew", **pad)

        options = ttk.Frame(root)
        options.grid(row=9, column=0, sticky="w", **pad)
        self.music = tk.BooleanVar(value=True)
        ttk.Checkbutton(options, text='"music": true', variable=self.music).pack(side="left")
        ttk.Label(options, text="   manifest_version").pack(side="left")
        self.manifest = ttk.Spinbox(options, from_=1, to=9, width=3)
        self.manifest.set("2")
        self.manifest.pack(side="left", padx=4)

        self.go_btn = ttk.Button(root, text="Download & Pack", command=self.start)
        self.go_btn.grid(row=10, column=0, sticky="ew", padx=10, pady=(10, 4))

        self.bar = ttk.Progressbar(root, maximum=100)
        self.bar.grid(row=11, column=0, sticky="ew", **pad)

        self.status = tk.StringVar(value="Ready")
        ttk.Label(root, textvariable=self.status, wraplength=490).grid(
            row=12, column=0, sticky="w", **pad
        )

        self.out_label = tk.StringVar()
        self._refresh_out_label()
        ttk.Label(root, textvariable=self.out_label, foreground="gray", wraplength=490).grid(
            row=13, column=0, sticky="w", **pad
        )

    def _install_context_menus(self) -> None:
        """Add a familiar edit context menu to every editable text control."""
        self._context_widget: tk.Widget | None = None
        self._edit_menu = tk.Menu(self, tearoff=False)
        self._edit_menu.add_command(label="Cut", command=lambda: self._edit_action("<<Cut>>"))
        self._edit_menu.add_command(label="Copy", command=lambda: self._edit_action("<<Copy>>"))
        self._edit_menu.add_command(label="Paste", command=lambda: self._edit_action("<<Paste>>"))
        self._edit_menu.add_separator()
        self._edit_menu.add_command(
            label="Select All", command=lambda: self._edit_action("<<SelectAll>>")
        )

        # Include both Entry and Text controls. On SteamOS/Linux and Windows,
        # right-click is Button-3. macOS also commonly uses Button-2 or
        # Control-click, so support those without changing other platforms.
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

        has_selection = self._has_text_selection(widget)
        editable = self._is_editable(widget)
        try:
            self.clipboard_get()
            clipboard_has_text = True
        except tk.TclError:
            clipboard_has_text = False

        self._edit_menu.entryconfigure("Cut", state="normal" if has_selection and editable else "disabled")
        self._edit_menu.entryconfigure("Copy", state="normal" if has_selection else "disabled")
        self._edit_menu.entryconfigure("Paste", state="normal" if editable and clipboard_has_text else "disabled")
        self._edit_menu.entryconfigure(
            "Select All", state="normal" if self._has_text(widget) else "disabled"
        )

        try:
            self._edit_menu.tk_popup(event.x_root, event.y_root)
        finally:
            # tk_popup takes a temporary grab; always release it to avoid
            # leaving the application or touchpad input stuck after dismissal.
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
            # A widget may have been destroyed while its context menu was open.
            self._context_widget = None

    def _refresh_out_label(self) -> None:
        self.out_label.set(f"Output: {self.out_dir}")

    def _on_close(self) -> None:
        self.destroy()

    def choose_output(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.out_dir, title="Output folder")
        if selected:
            self.out_dir = selected
            self.cfg["output_dir"] = selected
            save_config(self.cfg)
            self._refresh_out_label()

    def set_status(self, text: str) -> None:
        self.after(0, lambda: self.status.set(text))

    def set_progress(self, value: float) -> None:
        self.after(0, lambda: self.bar.configure(value=value))

    def _finish(self, ok: bool, message: str) -> None:
        self.go_btn.configure(state="normal")
        self.status.set(message)
        if ok:
            self.bar.configure(value=100)
        else:
            self.bar.configure(value=0)
            messagebox.showerror("Error", message)

    def start(self) -> None:
        url = self.url.get().strip()
        name = self.name.get().strip()
        if not url:
            messagebox.showwarning("Missing", "Paste a YouTube link first.")
            return
        if not name:
            messagebox.showwarning("Missing", "Enter a name for the pack.")
            return

        try:
            manifest_version = int(self.manifest.get())
        except ValueError:
            manifest_version = 2

        pack_json = {
            "name": name,
            "description": self.desc.get("1.0", "end").strip(),
            "author": self.author.get().strip(),
            "version": self.version.get().strip(),
            "manifest_version": manifest_version,
            "music": bool(self.music.get()),
            "ignore": [],
            "mappings": {},
        }
        folder = slugify(self.folder.get().strip() or name)

        self.go_btn.configure(state="disabled")
        self.bar.configure(value=0)
        self.status.set("Downloading...")
        threading.Thread(
            target=self.worker,
            args=(url, pack_json, folder, self.out_dir),
            daemon=True,
            name="soundpack-download",
        ).start()

    def worker(self, url: str, pack_json: dict, folder: str, out_dir: str) -> None:
        temporary_dir = tempfile.mkdtemp(prefix="soundpack_")
        try:
            audio = download_mp3(url, temporary_dir, self.set_progress)
            self.set_status("Packing ZIP...")
            zip_path = build_zip(audio, pack_json, folder, out_dir)
            self.after(0, lambda: self._finish(True, f"Done: {zip_path}"))
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            self.after(0, lambda message=message: self._finish(False, message))
        finally:
            shutil.rmtree(temporary_dir, ignore_errors=True)


if __name__ == "__main__":
    App().mainloop()
