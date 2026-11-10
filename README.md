# Sound Pack Maker

A small desktop utility that downloads the audio from one YouTube video, converts it to MP3, and creates a ZIP sound pack containing:

```text
<packname>.zip
└── <packname>/
    ├── menu_music.mp3
    └── pack.json
```

## Interface style packs

Use the **Style Pack** dropdown in the top-right corner to switch between three complete themes. The selected theme is remembered between launches.

- **Basic** — the clean, light default interface, updated with the refined layout and new controls.
- **Signal** — a darker graphite interface with warm amber accents and restrained contrast.
- **Half-Life 1 Console** — a GoldSrc-inspired green phosphor console treatment with monospaced typography, dark green surfaces, thin terminal-style borders, uppercase labels, and a console-like status prompt.

Changing themes only changes the interface. It does not change the downloader, audio conversion, manifest fields, or ZIP contents, and it does not clear anything already entered in the form.

## Interface improvements

- More consistent spacing, field sizing, typography, section hierarchy, and progress presentation.
- Compact style-pack selector with a short description of the active theme.
- **Choose output folder** and **Open** actions in the footer.
- Clearer source, manifest, and build sections.
- Right-click **Cut**, **Copy**, **Paste**, and **Select All** menu on every editable text field; `Shift+F10` also opens it.
- Output folder and selected style pack are saved in `~/.soundpack_maker.json` (Windows: the user's home directory).

## Build Windows and Linux executables with GitHub Actions

The included workflow builds native x86-64 executables on their target operating systems:

- Windows: `SoundPackMaker.exe`
- Linux: `SoundPackMaker`

### Uploading this project to GitHub

Extract this ZIP and upload the **contents** of the `SoundPackMaker-UI-Refined` folder to the root of your GitHub repository. The repository root should contain `build.py`, `requirements-build.txt`, `src/`, and `.github/workflows/build.yml`.

When updating an existing repository, replace the entire `.github/workflows/build.yml` file. Do not paste individual steps into an older workflow: duplicate `uses`, `with`, or `files` keys inside one step cause GitHub to reject the YAML.

Then open **Actions → Build executables → Run workflow**. When the run finishes, download both platform artifacts from the workflow summary.

Pushing a version tag such as `v1.1.0` also builds both executables and attaches them to a GitHub release.

## Build locally

Requirements: Python 3.11+, Tk development libraries, and Deno 2.x on `PATH`.

```bash
python -m pip install -r requirements-build.txt
python build.py
```

The executable is written to `dist/`.

On Debian/Ubuntu, install Tk build dependencies with:

```bash
sudo apt install python3-tk tk-dev tcl-dev
```

## Bundled runtime components

The executable packages Python, Tkinter, `yt-dlp`, the YouTube EJS challenge scripts, `imageio-ffmpeg` (including FFmpeg), and Deno. End users do not need to install these separately. An internet connection is still required to download media.

YouTube may change its delivery mechanisms. When downloads stop working, update `yt-dlp[default]` and rebuild.

## Usage note

Only download and use media you have the right to use, and comply with the source site's terms.
