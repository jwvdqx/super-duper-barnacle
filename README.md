# Sound Pack Maker

A desktop application that downloads the audio from one YouTube video, converts it to MP3, and creates a ZIP sound pack containing:

```text
<packname>.zip
└── <packname>/
    ├── menu_music.mp3
    └── pack.json
```

## Build Windows and Linux executables with GitHub Actions

The workflow builds native x86-64 executables on their target operating systems:

- Windows: `SoundPackMaker.exe`
- Linux: `SoundPackMaker`

### Uploading this project to GitHub

**Recommended:** Extract this ZIP and upload the *contents* of the `SoundPackMaker-Fixed-Build-Project` folder to the root of your GitHub repository. The repository root must contain `build.py`, `requirements-build.txt`, `src/`, and `.github/workflows/build.yml`.

The workflow also detects the project inside a `soundpack-maker/` subfolder, provided the workflow file itself is in the repository root at `.github/workflows/build.yml`.

Then open **Actions → Build executables → Run workflow**. When the run finishes, download both platform artifacts from its summary page.

Pushing a version tag such as `v1.0.0` also builds both executables and attaches them to a GitHub release.

## Build locally

Requirements: Python 3.11+, Tk development libraries, and Deno 2.x on `PATH`.

```bash
python -m pip install -r requirements-build.txt
python build.py
```

The executable is written to `dist/`.

On Debian/Ubuntu, install Tk build dependencies with:

```bash
sudo apt install python3-tk tk-dev
```

## Bundled runtime components

The executable packages Python, Tkinter, `yt-dlp`, the YouTube EJS challenge scripts, `imageio-ffmpeg` (including FFmpeg), and Deno. End users do not need to install these separately. An internet connection is still required to download media.

YouTube may change its delivery mechanisms. When downloads stop working, update `yt-dlp[default]` and rebuild.

## Editable fields

All editable fields provide a right-click menu with **Cut**, **Copy**, **Paste**, and **Select All**. `Shift+F10` opens the menu from the keyboard. The menu is available for the YouTube URL, pack name, description, author, version, folder/ZIP name, and manifest version.

## Output and settings

- Output directory defaults to the user's home directory.
- The gear button changes the output directory.
- The selected directory is saved in `~/.soundpack_maker.json`.

## Usage note

Only download and use media you have the right to use, and comply with the source site's terms.
