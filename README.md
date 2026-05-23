# Microsoft TTS – Multi-Voice Fix for Home Assistant

Home Assistant's built-in Microsoft TTS integration has a bug: when you configure
multiple voices (multiple `platform: microsoft` entries), **all of them route to the
same provider**. No matter which service you call, you always hear the same voice.

This project fixes that with a custom component and provides a helper script to
generate the YAML configuration from Microsoft's live voice list.

---

## Root Cause

The bug is in HA core's `homeassistant/components/tts/legacy.py`. The `_say` service
handler closes over `p_type` (always `"microsoft"`) instead of the `service_name`,
so every `tts.*_say` service ends up looking up the same provider in the registry.
The proper fix is a one-liner PR to HA core; this custom component is the workaround
until that lands.

---

## Project Structure

```
custom_components/
└── microsoft/
    ├── manifest.json
    ├── __init__.py          # replaces the built-in component
    └── tts.py               # not needed, can be omitted

get_microsoft_tts_voices.py  # helper script to generate voice config
microsoft-tts-voices.yaml    # generated voice list (included by configuration.yaml)
```

---

## Installation

1. Copy `custom_components/microsoft/` into your HA config directory.
2. Generate your voice list (see below).
3. Add the following to `configuration.yaml`:

```yaml
microsoft: !include microsoft-tts-voices.yaml
```

4. Restart Home Assistant.

---

## Generating the Voice List

The helper script fetches all available voices directly from Microsoft's REST API
and writes a ready-to-use YAML file. It supports **one or more languages** in a
single run and automatically skips unsupported voice types (HD voices and
colon-scheme voices such as `Ethan:MAI-Voice-2`).

**Requirements:** Python 3.9+, no additional packages needed.

### Usage

```bash
# Single language
python get_microsoft_tts_voices.py \
    --key YOUR_AZURE_API_KEY \
    --language de-DE \
    --region westeurope \
    > microsoft-tts-voices.yaml

# Multiple languages
python get_microsoft_tts_voices.py \
    --key YOUR_AZURE_API_KEY \
    --language de en-US fr \
    --region westeurope \
    > microsoft-tts-voices.yaml

# Neural voices only
python get_microsoft_tts_voices.py \
    --key YOUR_AZURE_API_KEY \
    --language de en \
    --region westeurope \
    --neural-only \
    > microsoft-tts-voices.yaml

# Just list available voices without generating YAML
python get_microsoft_tts_voices.py \
    --key YOUR_AZURE_API_KEY \
    --language de \
    --list
```

### All Options

| Option | Default | Description |
|---|---|---|
| `--key` | *(required)* | Azure Speech API key |
| `--language` | *(required)* | One or more language codes, e.g. `de` `de-DE` `en-US` |
| `--region` | `westeurope` | Azure region of your Speech resource |
| `--neural-only` | off | Only include Neural voices |
| `--secret` | `azure_api_key` | Name of the HA secret holding the API key |
| `--volume` | `50` | Volume offset applied to all voices (-100 to 100) |
| `--list` | off | Print available voices to stderr, no YAML output |

### Language Filtering

Language codes are matched as **prefixes**, so `de` matches `de-DE`, `de-AT`, and
`de-CH`, while `de-DE` limits the output to Germany German only.

### Output Format

The generated file contains one entry per voice and is designed for direct inclusion:

```yaml
- api_key: !secret azure_api_key
  service_name: microsoft_de_de_katja
  language: de-de
  type: KatjaNeural
  gender: Female
  region: westeurope
  volume: 50

- api_key: !secret azure_api_key
  service_name: microsoft_de_de_conrad
  ...

# Skipped unsupported voices (HD or colon-scheme, not supported by pycsspeechtts):
#   de-DE-SeraphinaMultilingual:DragonHDLatestNeural
```

---

## Calling a Voice

After restarting HA, each voice registers as `tts.{service_name}_say`:

```yaml
service: tts.microsoft_de_de_katja_say
data:
  entity_id: media_player.living_room
  message: "Hallo, das ist ein Test."
```

---

## Secrets

Add your Azure API key to `secrets.yaml`:

```yaml
azure_api_key: YOUR_AZURE_SPEECH_API_KEY
```

---

## Requirements

- Home Assistant 2023.x or later
- [`pycsspeechtts`](https://pypi.org/project/pycsspeechtts/) 1.0.8 (installed automatically by HA)
- An [Azure Speech resource](https://portal.azure.com) with a valid API key
