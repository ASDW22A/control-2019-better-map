# Control Better Map

A mod for **Control (2019)** that replaces the in-game map textures with
clearer, more readable versions.

## Why

The in-game map of the Oldest House is notoriously hard to read: extremely
dark, low contrast, and cluttered with baked-in text that covers exits and
corridors. This mod fixes readability while keeping the exact original
texture dimensions (2048x1152 RGBA), so the game renders the improved maps
in place of the originals.

## What you get

| Variant | Description |
|---|---|
| `better` | Contrast-boosted, sharpened, saturation-enhanced map. Same layout, much clearer. |
| `labeled` | The `better` map + clean room-name labels with leader lines (from the Control wiki's location data). |

Sectors covered: Executive, Research, Maintenance, Containment, Foundation,
Investigations, Quarry Site Beta, Unmapped Area.

## Requirements

- Control (Steam / Epic / GOG, base game or Ultimate Edition)
- [Loose Files Loader](https://www.nexusmods.com/control/mods/11) (framework mod by registrator2000)
- Python 3.9+ with `pip install -r requirements.txt` (only needed for conversion)

## Install

### 1. Install Loose Files Loader

Download it from Nexus Mods (Control > Loose Files Loader) and install per
its instructions. It is a single DLL that hooks the game's file loader so
loose files override the packed archives.

### 2. Run the installer

```powershell
.\install.ps1                    # auto-detect game, DXT5, 'better' variant
.\install.ps1 -Variant labeled   # labeled maps
.\install.ps1 -Format bgra8      # lossless quality (larger files)
.\install.ps1 -GameDir "D:\Games\Control"
```

The installer converts the textures to DDS and places them under
`<game>\data\`.

### 3. Match the archive paths (one-time)

Loose files must mirror the exact paths inside the game's package archives.
Find the original map textures and copy the improved ones over them:

```powershell
python tools\extract_map_textures.py --game-dir "<game dir>"
```

This scans all `.bin/.rmdp` packages, finds the map texture files, extracts
them, and prints their internal paths. Move the matching improved `.tex`
files into the same relative paths under `<game>\data\`.

### 4. Convert to .tex

The game loads Northlight `.tex` textures, not raw DDS. Convert the improved
DDS back to `.tex` with [neat](https://github.com/TomEvin/neat) (TomEvin's
Northlight Engine Archive Tool):

1. Open neat, load a `.tex` file extracted in step 3 to see its format
2. Convert your improved `.dds` to `.tex` (same format as the original)
3. Place the `.tex` files at the mirrored paths under `<game>\data\`

## Manual install (no Python)

The installer converts the improved PNGs to DDS for you. If you want to convert
by hand, run `tools\make_dds.py` on any PNG in `maps\improved\`:

```powershell
python tools\make_dds.py maps\improved\research_better.png out\research_better.dds --format dxt5
```

- `dxt5` (BC3) — ~2.4 MB per file, matches the original texture format
- `bgra8` — lossless, much larger

Then convert to `.tex` with neat and place at mirrored archive paths under
`<game>\data\`.

> `maps\mod\ready\` is **generated output** and is not committed. The installer
> recreates it on first run.

## Files

```
control-better-map/
├── install.ps1                  # installer
├── requirements.txt
├── maps/
│   ├── improved/                # processed PNGs (better + labeled)
│   ├── source/                  # NOT committed — see "Building from source"
│   └── mod/ready/               # generated DDS output (not committed)
├── data/                        # wiki location data (for labels)
└── tools/
    ├── process_maps.py          # texture enhancement pipeline
    ├── make_dds.py              # PNG -> DDS converter (DXT5/DXT1/BGRA8)
    ├── rmdp_extract.py          # Northlight package extractor
    ├── extract_map_textures.py  # find map textures in game archives
    ├── verify_dds.py            # DDS round-trip checker
    ├── verify.py                # before/after quality metrics
    └── inspect_data.py          # wiki data sanity check
```

## Building from source

`maps\improved\` ships with the repo, so the installer works immediately. To
regenerate the improved textures yourself you need the original map textures in
`maps\source\`, which are **not** committed because they are extracted from the
game. Pull them from your own install:

```powershell
python tools\extract_map_textures.py --game-dir "<game dir>"
# then place the extracted overlay textures into maps\source\ as
#   <sector>_blueprint.png
```

## Rebuilding the textures

```powershell
python tools\process_maps.py              # regenerate all variants
python tools\process_maps.py --sector research
python tools\process_maps.py --skip-labels

python tools\verify.py                    # before/after contrast metrics
python tools\verify_dds.py <file.dds>     # DDS round-trip check
```

## Credits

- Map textures derived from *Control* (2019), original blueprints referenced via the Control Wiki (Fandom)
- Location data from the Control Wiki interactive maps
- Loose Files Loader by registrator2000
- neat by TomEvin

## License

Code and tooling (`tools/`, `install.ps1`, `data/`) are MIT — see [LICENSE](LICENSE).

The textures under `maps/` are derived from Remedy Entertainment's *Control* and
are **not** covered by the MIT license. They remain the property of their
respective owners and are provided as loose-file mod content for personal use.

## Disclaimer

Unofficial fan mod. Not affiliated with or endorsed by Remedy Entertainment or
505 Games. Control is a trademark of its respective owners. Use at your own risk.
