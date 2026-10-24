# Cotton 2 English (Sega ST-V) — work in progress

An English translation of the ST-V arcade game *Cotton 2* (Success, 1997,
set `cotton2`), planned as a bootleg/homebrew clone set for
[mame2003-plus](https://github.com/zanac/mame2003-plus-libretro)
(branch `stv-cotton2-english`).

The arcade ROM has no English text: the story dialogue, the stage titles
and the title screen are all Japanese graphics. The Saturn port of the
game has an English fan translation. This project takes the translated
graphics from the Saturn files and moves them into the arcade cartridge.



## Status

| Step | State |
|---|---|
| Rebuild the English Saturn files from the disc and the patch | done, verified by MD5 |
| Decode the Saturn `LZ00` sprite compression | done |
| Convert Saturn MF graphics containers to the arcade layout | done, byte-identical on `CHR_VS0/2/3/4.MF` |
| Port the `VS*.BIN` code and table changes to the arcade overlays | **to do** |
| Transplant the changed sprites of `CHR_VS1/5/6/7.MF` (arcade content differs) | **to do** |
| Stage titles (`CHR_ST*.MF`, 4 sprites each) and title screen (`CHR_TTL.MF`) | **to do** |
| Write the new ROM set, patch file, emulator test | **to do** |

`build.py` runs the steps marked done. It does not write a ROM set yet.

## Requirements

- Python 3, standard library only
- `cotton2.zip` (arcade, MAME set)
- the Japanese Saturn disc of *Magical Night Dreams: Cotton 2* (cue/bin or
  an .iso of the data track)
- `ss_cotton_2_eng_v0.9.zip`, the Saturn English patch (not included here)

## Usage

```
python3 build.py ROMDIR DISC PATCH [OUTDIR]
```

Example:

```
python3 build.py roms "Magical Night Dreams Cotton 2 (Japan).cue" ss_cotton_2_eng_v0.9.zip out
```

Output:

- `out/saturn/orig/`, `out/saturn/eng/`: the 26 Saturn files touched by the
  patch, original and English
- `out/arcade/CHR_VS*.MF`: the English dialogue graphics in the arcade layout

The single steps are in `tools/`:

| Script | Purpose |
|---|---|
| `make_saturn_english.py DISC PATCH OUTDIR` | extract the disc, check MD5, apply the bsdiff patches |
| `check_converter.py ROMDIR SATDIR` | convert the original Saturn `CHR_VS*.MF` and compare with the cartridge |
| `analyze.py SATDIR` | list what the English patch changes in each file |
| `c2lib.py` | shared code (cartridge, ISO 9660, MF, LZ00) |
| `bsdiff.py` | BSDIFF40 patch applier |

## Technical notes

### Cartridge

`mpr20122.7` is loaded at 0x200000 (2 MB); `mpr20117.2` … `mpr20123.8`
follow at 4 MB steps (`ROM_LOAD16_WORD_SWAP`). Files are chained
entries: size (4), name (16), size2 at +0x14, an 8-byte stamp, data
from +0x20. The game DMAs them from 0x22xxxxxx.

Some names occur more than once (`VS1.BIN` is also a sound file inside
the `BGM_*.MF` containers). The game overlays used here:

| File | Region offset | Size | Saturn size |
|---|---|---|---|
| VS0.BIN | 0x454bb0 | 0x20164 | 0x197c0 |
| VS1.BIN | 0xababa0 | 0x1b1fc | 0x18a30 |
| VS2.BIN | 0xe11ab0 | 0x1a1cc | 0x17960 |
| VS3.BIN | 0x1085520 | 0x1b8ac | 0x193d0 |
| VS4.BIN | 0x14500c0 | 0x19d10 | 0x17560 |
| VS5.BIN | 0x1794c00 | 0x1acd0 | 0x186b0 |
| VS6.BIN | 0x1b18710 | 0x1c7a8 | 0x19d00 |
| VS7.BIN | 0x1ccb750 | 0x255c8 | 0x1e4e0 |

### Saturn patch

The `.SSP` file is a zip of `BSDIFF40` patches (`NAME._DFR`, bzip2
streams). `CHANGES._MD5` holds the MD5 of the original files (not of the
patched ones). 18 MF containers and the 8 `VS*.BIN` overlays are changed.

### MF containers

An MF file is a chain of subfiles with the same header as the cartridge
file system (size, 16-byte name, size2, stamp), ended by a 4-byte word
(0 on Saturn, 0xffffffff on the cartridge):

- `SCH`: pointer table, then 20-byte sprite records in the `VS` files
  (word 0 = offset into `SPT`); command lists in the `ST` files
- `SPT`: sprite patterns, entries of a 0x20-byte header (width at +4,
  height at +6, data size at +8) followed by the data
- `SPL`: palettes, `SAN`: animations, `SIF`: info, `SCP`: cell patterns

### LZ00 compression

The Saturn stores most sprites compressed; the arcade stores them raw
(4bpp). A compressed sprite starts with `LZ00` and the 32-bit unpacked
size. Then:

- byte `b < 0x10`: copy the next `b + 1` bytes
- byte `b >= 0x10`: copy `next + 3` bytes from `b - 0x0f` bytes back
  (positions before the start read as 0)

Converting a Saturn MF to the arcade layout means unpacking every
`LZ00` sprite, fixing its size field and moving the `SCH` offsets.
On the original data this gives exactly the arcade `CHR_VS0/2/3/4.MF`.

### What the English patch changes

- `CHR_VS*.MF`: the dialogue graphics. Many sprites are redrawn and the
  sprite count changes (e.g. `CHR_VS0` 265 → 191 sprites, the `SCH`
  records 718 → 1096).
- `VS*.BIN`: SH-2 overlays loaded at 0x0606e000. Changes:
  - a new routine at 0xe8d8 that calls the routine at 0xfdc only every
    other frame, hooked through the pointer at 0x11084
  - two constants: 0x1091b (5 → 3) and 0x11035 (13 → 9 or 8, a
    multiplier for the text position)
  - data tables at the end of each overlay (sprite numbers and positions)

  The arcade overlays are a different build of the same code, so the
  code changes have to be found and rewritten by hand. The data tables
  are found in the arcade overlays at a fixed shift (e.g. +0x7c1c in
  `VS0.BIN`).
- `CHR_ST*.MF`: 4 sprites per stage (stage title). The arcade stage files
  have different content, so these sprites go in one by one.
- `CHR_TTL.MF`: 5 sprites. The arcade title file has a different structure.
- `CHR_INF.MF` and `CHR_VS70.MF` have no arcade counterpart.

## Credits

Translation hack by Vanni Brutto. The game is © Success 1997. This
repository holds no game data and no translation data, only the tools;
you need your own copies of the game and of the patch.
