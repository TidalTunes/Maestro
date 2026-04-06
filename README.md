# Maestro

Maestro is an open-source beta app for AI-assisted composition and live MuseScore editing. You describe a musical change, optionally hum an idea, and Maestro turns that request into score edits that can be applied inside MuseScore.

Maestro `v0.1.0` is the first public beta release.

- License: [MIT](LICENSE)
- Disclaimer: [DISCLAIMER.md](DISCLAIMER.md)
- Credits: [AUTHORS.md](AUTHORS.md)
- GitHub release: [v0.1.0](https://github.com/TidalTunes/Maestro/releases/tag/v0.1.0)

## macOS Quick Start

1. Open the [v0.1.0 release page](https://github.com/TidalTunes/Maestro/releases/tag/v0.1.0).
2. Download `Maestro-v0.1.0-macOS-unsigned.dmg`.
   Fallback: `Maestro-v0.1.0-macOS-unsigned.zip`.
3. Open the DMG and drag `Maestro.app` into `Applications`, or unzip the ZIP and move `Maestro.app` wherever you prefer.
4. Launch `Maestro.app`.
5. Use the in-app setup flow to install `Maestro Plugin`, open MuseScore, and verify the bridge connection.

### Unsigned App Warning

`v0.1.0` is not signed or notarized.

On first launch:

1. Right-click `Maestro.app`.
2. Click `Open`.
3. Confirm the warning dialog.

If macOS blocks the app again:

1. Open `System Settings`.
2. Go to `Privacy & Security`.
3. Click `Open Anyway` for Maestro.

## Manual Setup for Windows, Linux, or Source-Based macOS Use

If you do not want the packaged macOS app, use the plugin + Python combo directly from source.

### 1. Install Prerequisites

- Python 3.10 or newer
- MuseScore 4
- Git
- either an OpenAI API key or a local Ollama installation, depending on which provider you want to use

### 2. Clone the Repository

```bash
git clone https://github.com/TidalTunes/Maestro.git
cd Maestro
```

### 3. Create a Virtual Environment and Install Maestro

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-desktop.txt
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-desktop.txt
```

### 4. Install the MuseScore Plugin

From the activated environment:

```bash
maestro-install-plugin install
```

If MuseScore uses a non-default plugin folder, install to it explicitly:

```bash
maestro-install-plugin install --plugin-dir "<your MuseScore plugin folder>"
```

Default MuseScore 4 plugin folders:

| Platform | Default plugin folder |
| --- | --- |
| macOS | `~/Documents/MuseScore4/Plugins` |
| Windows | `C:\Users\<User>\Documents\MuseScore4\Plugins` |
| Linux | `~/Documents/MuseScore4/Plugins` |

You can inspect the detected location at any time with:

```bash
maestro-install-plugin status
```

### 5. Enable the Plugin in MuseScore

In MuseScore:

1. Open the plugin manager.
2. Enable `Maestro Plugin`.
3. Run `Plugins > Maestro > Maestro Plugin`.
4. Keep that plugin window open while Maestro is sending edits.

### 6. Launch the Python App

If you want to use OpenAI, set your key first:

macOS or Linux:

```bash
export OPENAI_API_KEY="your-key-here"
python maestro_gui.py
```

Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="your-key-here"
python maestro_gui.py
```

If you want to use Ollama instead, make sure Ollama is installed and running before you launch Maestro, then choose the Ollama-backed model inside the app.

## How AI-Assisted Composition Works

Maestro takes your prompt or hummed melody, sends that request through its score-generation pipeline, converts the resulting musical intent into score operations, and applies those operations to a live MuseScore session through `Maestro Plugin`. The result is not autonomous composition magic; it is a beta co-writing tool that still requires human review.

## Developers

Maestro is developed by:

- Kashi Tuteja — Lead
- Arthur Gilfanov
- Matthew Li

We are students at Yale University.

## Build and Developer Notes

For engineering docs and packaging internals:

- [Desktop app notes](apps/frontend-desktop/README.md)
- [Plugin asset notes](apps/plugin/README.md)
- [Bridge package notes](packages/maestro-musescore-bridge/README.md)
- [macOS packaging scripts](packaging/macos/README.md)
- [Repository docs](docs/README.md)
