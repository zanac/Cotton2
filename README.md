# Cotton 2 English (Sega ST-V)

An English translation of the ST-V arcade game *Cotton 2* (Success, 1997,
MAME set `cotton2`), as a bootleg clone set `cotton2e` for
[mame2003-plus](https://github.com/zanac/mame2003-plus-libretro)
(branch `stv-cotton2-english`).

The arcade game has no English text in its story scenes: the dialogue,
the hints on the continue screen, the prologue and the character
profiles are Japanese graphics. The Saturn port of the game has an
English fan translation. This project takes the translated graphics from
the Saturn files and puts them into the arcade cartridge.

## Status

| Part | State |
|---|---|
| Attract mode: prologue scroll, character profiles | done, checked in the emulator |
| Continue screen hints, all 7 stages | done, checked in the emulator (stages 1–2) |
| Story dialogue VS0–VS6 | built, emulator check in progress |
| Ending VS7 | built, not checked yet |
| ROM set `cotton2e`, patch, driver entry | done |

Known differences from the Saturn translation:

- The Saturn overlays also call one routine every other frame and change a
  loop limit in the ending (75 → 80). The arcade code is a different build
  and these two changes are not ported.
- `CHR_INF.MF` and `CHR_VS70.MF` (Saturn only) have no arcade counterpart.

## Getting the ROM set

You need `cotton2.zip` (the MAME set) and `stvbios.zip`.

```
python3 patch/make_cotton2e.py ROMDIR [OUTDIR]
```

This writes `cotton2e.zip`. Python 3, standard library only.

| File | CRC32 | SHA1 |
|---|---|---|
| c2e20122.7 | 0b9d225c | 074777cf0d681e334ec7d3819a4e9cd86e258ad1 |
| c2e20117.2 | b6e0e634 | cad580d39a7bf666c55794d28788cb0f6503155d |
| c2e20118.3 | 2161fac9 | 4a5430cad481786595ffab46505b67450dbea43d |
| c2e20119.4 | 0f05df2e | 6d22a2f5d238cd551913a74e7421c3b5bbf315ac |
| c2e20120.5 | 988121dd | 176badb58896cecb5f5c9f31ed9e6fa096aef03f |
| c2e20121.6 | 2a1f48d5 | 23c5ad9cea85d2dac77d60650a3acfbd0b2aa155 |
| c2e20116.1 | 65207eb8 | e0cbde50ceaf3c8c7162d2e708b0241887166d9a |
| c2e20123.8 | 33b0e7c4 | 6d99412366ff021c3177e6087eb000a77cf94a38 |

## Rebuilding everything

`build.py` redoes the whole job from the original material and writes
both the ROM set and `patch/cotton2e.dat`:

```
python3 build.py ROMDIR DISC PATCH [OUTDIR]
```

- `ROMDIR`: folder with `cotton2.zip`
- `DISC`: the Japanese Saturn disc of *Magical Night Dreams: Cotton 2*
  (`.cue`, Track 1 `.bin` or an `.iso` of the data track)
- `PATCH`: `ss_cotton_2_eng_v0.9.zip`, the Saturn English patch, or the
  `.SSP` inside it (not included here)

Example:

```
python3 build.py roms "Magical Night Dreams Cotton 2 (Japan).cue" ss_cotton_2_eng_v0.9.zip out
```

Steps:

1. rebuild the 26 English Saturn files (`out/saturn/orig`, `out/saturn/eng`)
2. check the Saturn → arcade converter against the cartridge
3. build the English cartridge
4. write `out/cotton2e.zip` and `patch/cotton2e.dat`

The result is reproducible byte for byte.

| Script | Purpose |
|---|---|
| `build.py` | the whole build |
| `patch/make_cotton2e.py` | ROM set from `cotton2.zip` and `cotton2e.dat` |
| `tools/make_saturn_english.py` | extract the disc, check MD5, apply the bsdiff patches |
| `tools/check_converter.py` | Saturn `CHR_VS*.MF` → arcade layout, compared with the cartridge |
| `tools/analyze.py` | what the English patch changes in each Saturn file |
| `tools/translate.py` | the English cartridge: dialogue, hints, attract screens |
| `tools/vsmerge.py` | 3-way merge of the dialogue containers and overlay tables |
| `tools/vsport.py` | locate the Saturn overlay changes in the arcade overlays |
| `tools/romset.py` | ROM names and patch format |
| `tools/c2lib.py` | cartridge, ISO 9660, MF containers, LZ00 |
| `tools/bsdiff.py` | BSDIFF40 patch applier |
| `tools/spritesheet.py`, `tools/shdis.py` | debugging: sprite sheets, SH-2 disassembly |

## Technical notes

### Cartridge

`mpr20122.7` is loaded at 0x200000 (2 MB); `mpr20117.2` … `mpr20123.8`
follow at 4 MB steps (`ROM_LOAD16_WORD_SWAP`). Files are chained
entries: size (4), name (16), size2 at +0x14, an 8-byte stamp, data
from +0x20. The chain ends at 0x1eb3a20; the rest of the last chip is
empty. The game DMAs files from 0x22xxxxxx.

Some names occur more than once (`VS1.BIN` is also a sound file inside
the `BGM_*.MF` containers). The game overlays:

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

- `SCH`: frames. A pointer table, then 20-byte records in the `VS`
  files (word 0 = offset into `SPT`); command lists in the `ST` files
- `SPT`: sprite patterns, entries of a 0x20-byte header (width at +4,
  height at +6, data size at +8) followed by the data
- `SAN`: animations, a pointer table then 8-byte records (frame number,
  duration, flags)
- `SIF`: frame count (word 0) and animation count (word 2)
- `SPL`: palettes, `SCP`: cell patterns

### LZ00 compression

The Saturn stores most sprites compressed; the arcade stores them raw
(4bpp). A compressed sprite starts with `LZ00` and the 32-bit unpacked
size. Then:

- byte `b < 0x10`: copy the next `b + 1` bytes
- byte `b >= 0x10`: copy `next + 3` bytes from `b - 0x0f` bytes back
  (positions before the start read as 0)

Converting a Saturn MF to the arcade layout means unpacking every
`LZ00` sprite, fixing its size field and moving the `SCH` offsets. On
the original data this gives exactly the arcade `CHR_VS0/2/3/4.MF`.

### Dialogue (VS scenes)

Three versions of each `CHR_VS*.MF` are compared, all in the arcade
layout: Saturn original (O), Saturn English (E) and arcade (A). The
arcade overlays address frames by number, and some arcade containers
have extra frames, so:

- the new frame list is the English one, with the arcade-only frames
  appended
- the frame tables at the end of each overlay and the animations are
  renumbered; animations that the arcade has as in the Saturn original
  are taken from the English file, the arcade-only ones are renumbered
- new sprites that do not fit in the old container go to the free space
  at the end of the cartridge (frames may point past the end of `SPT`)
- the two text constants of the English overlays are set in the arcade
  ones: frames per character (5 → 3) and character advance (13 → 9 or 8)

### Continue screen and attract screens

The continue screen hints are frames of `CHR_ST*.MF`; the English
sprites go to the free space and the frames point there. The prologue
and profiles are maps of 8bpp cells in `CHR_TTL.MF`; the changed cells
go to the area of `BGM_VS0.MF`, which is moved to the end of the file
chain.

## Credits

Translation hack by Vanni Brutto. The game is © Success 1997. Building
the ROM set needs your own copy of the game.
