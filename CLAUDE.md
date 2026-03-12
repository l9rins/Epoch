# EPOCH ENGINE — PROJECT BIBLE

> Claude Code reads this file automatically at the start of every session.
> This is the single source of truth for what you are building.

## What This Is

Epoch Engine is an NBA Digital Twin — a system that converts real NBA statistics
into precise byte values for the NBA 2K14 `.ROS` binary roster file, then runs
Monte Carlo simulations against those rosters, and ultimately powers a
prediction/signal product for sports analytics.

## Critical Binary Format Facts (.ROS)

| Property | Value |
|---|---|
| File size | ~2.67 MB |
| CRC | `zlib.crc32(data[4:]) & 0xFFFFFFFF`, stored Big-Endian uint32 at offset `0x0000` |
| Primary records | 832 records × 2 players each = **1,664 total players** |
| EVEN players | Standard layout |
| ODD players | **Nibble-shifted**, data starts at offset `+0x1C7` within record |
| Skill codec | `tier = floor(raw_value / 3)` → rating = `(tier × 3) + 25` |
| Skill fields | 42 total, tier 0–13 (ratings 25–64) |
| Tendency fields | 57 total, tier 0–6 (raw 0–99 stored, NOT encoded) |
| Internal tendencies | Indices 57–68 are engine-internal — **never write to these** |
| Hot zones | 14 zones, 2-bit packed (Cold=0, Neutral=1, Hot=2, Burned=3) |
| Height/Weight | Float32 Big-Endian at `+0x000` / `+0x004` |
| TeamID | Single byte at `+0x00B` |
| BirthDate | Bit-packed starting at bit 149 |
| Name String Pool | UTF-16 LE at `0x25ED40`–`0x28B7DF` |
| TOC | 40 embedded CSVs at `0x0020`–`0x01FF` |
| Boundary records | 19 records where EVEN+ODD share a single TeamID byte |
| Signature skills | 5 slots per player, 41 valid entries (2K14 RED MC Enums order) |
| Sig skill stubs 41-44 | Assist Bonus, Off Awareness Bonus, Def Awareness Bonus, Attribute Penalty |

## Architecture Decisions

- **Language**: Python 3.11
- **Dependencies**: `struct` (stdlib), `zlib` (stdlib), `bitarray`, `numpy`, `pytest`, `hypothesis`
- **No external CRC library** — pure `zlib.crc32` from stdlib
- **Pure functions over classes** — the engine is functional, not OOP
- **All field indices are constants** — no magic numbers anywhere in the codebase

## Build Order (each step proves the next)

1. `src/binary/constants.py` — field offsets, codec functions, CRC. Pure constants, nothing can break.
2. `src/binary/ros_reader.py` — read + validate + parse. Test against actual `.ROS` file.
3. `tests/test_binary.py` — CRC, codec, nibble-shift round-trip tests.
4. `src/binary/ros_writer.py` — write + recalculate CRC. Read → modify → write → read back → verify.

## File Map

```
Epoch/
├── CLAUDE.md                  ← YOU ARE HERE — project bible
├── requirements.txt           ← Python dependencies
├── docs/
│   ├── EpochEngine_MasterDocument.docx
│   ├── EpochEngine_AdvancedSystems.docx
│   └── EpochEngine_TechStack.docx
├── specs/
│   ├── NBA2K14_Master_Spec_S1-S51_COMPLETE.docx
│   └── prompts.md             ← 10 Claude Opus 4.6 prompts
├── data/
│   └── roster.ros             ← actual .ROS file for testing
├── src/
│   └── binary/
│       ├── __init__.py
│       ├── constants.py       ← offsets, codecs, CRC, labels
│       ├── ros_reader.py      ← read + validate + parse
│       └── ros_writer.py      ← write + CRC recalc + save
└── tests/
    ├── __init__.py
    └── test_binary.py         ← pytest + hypothesis
```

## Rules For Every Session

1. **Never write magic numbers** — import from `constants.py`
2. **Never skip CRC recalculation** — every write path must call `recalculate_crc()`
3. **Never write to tendency indices 57–68** — these are engine-internal
4. **Always handle boundary records** — check if EVEN+ODD share TeamID byte
5. **Always validate ranges** — skill tier 0–13, tendency 0–99, hot zone 0–3
6. **Test against the real .ROS file** when available at `data/roster.ros`
7. **Stat encoding cap is 255** (not 222) — supports modded players up to rating 110
