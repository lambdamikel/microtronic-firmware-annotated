# microtronic-firmware-annotated

## An annotated, explained disassembly of the original 1981 Busch Microtronic 2090 firmware ROM

The [Busch Microtronic 2090](https://www.busch-modell.de/information/Microtronic-Computer.aspx)
was a 4‑bit educational single‑board computer released in West Germany in 1981
by [Busch Modellbau](https://www.busch-modell.de). To the user it looks like a
tiny machine with its own 16‑instruction machine language, a 6‑digit LED
display, and a hex keypad. Under the hood, none of that hardware exists as the
manual describes it: the whole machine — its instruction set, its display, its
keyboard, its 1‑Hz clock, its cassette interface — is *software*, a compact
**virtual machine** hand‑written in the mask ROM of a single **Texas Instruments
TMS1600** 4‑bit microcontroller.

This repository takes the firmware ROM that was recovered from that chip in 2024
and turns it into something a human can read: a fully **annotated disassembly**
plus a set of documents that explain, from the silicon up, **how the Microtronic
actually works**.

> **Status:** work in progress. The raw materials (ROM image + disassembly) are
> complete and authoritative; the annotations and the "theory of operation"
> documents are being written routine by routine. See
> [Roadmap](#roadmap-and-status) below.

---

## Why this exists

The Microtronic's firmware was considered lost for decades, and no procedure for
dumping a `TMS1600` mask ROM was documented anywhere. In April 2024, after a lot
of trial and error, **the team** — [Decle](https://forums.atariage.com/profile/46336-decle/),
[Jason T. Jacques](https://jsonj.co.uk/), and
[Michael A. Wessel](https://www.michael-wessel.info/) — succeeded in reading the
ROM out through the TMS test mode, and Jason built the first emulator to run the
original firmware (the ["Microtronic Phoenix"](https://github.com/lambdamikel/microtronic-phoenix)).

The ROM and its disassembly have been public since then, but as a 4,096‑byte
binary and a 4,416‑line disassembly with an empty comment column. They tell you
*what* every instruction is, but not *what it is for*. This project fills in that
comment column and writes the surrounding explanation, so that the Microtronic's
firmware becomes a readable, teachable artifact — a worked example of how you fit
a friendly 4‑bit computer into 4 KB of TMS1000‑family microcode.

## What's in here

| Path | Contents |
| --- | --- |
| [`rom/microtronic.bin`](rom/microtronic.bin) | The recovered 4,096‑byte firmware ROM image (canonical, unmodified). |
| [`rom/microtronic-firmware-disassembled.txt`](rom/microtronic-firmware-disassembled.txt) | Decle's TMS1xxx disassembly, hand‑corrected by Jason (canonical, unmodified). |
| [`docs/`](docs/) | The "theory of operation": the TMS1600 chip, and how the Microtronic VM is built on top of it. |
| [`annotated/`](annotated/) | The generated annotated listing, plus the annotation source (`annotations.tsv`, `banners.tsv`) it is built from. |
| [`dev-support/`](dev-support/) | `build_annotated.py` — merges the annotation source into the canonical disassembly to produce `annotated/microtronic-annotated.txt`. |
| [`references/`](references/) | Curated links and local copies of the primary sources (Jason's emulator, TI docs). |

The canonical disassembly in `rom/` is **never edited**. Annotations live as data
in `annotated/annotations.tsv` (per‑line comments) and `annotated/banners.tsv`
(section headers), keyed by logical address; running
`python3 dev-support/build_annotated.py` regenerates the annotated listing and
reports coverage. This keeps the annotation reviewable as a diff and always
re‑derivable from the untouched source.

### Documents

- [`docs/01-tms1600-architecture.md`](docs/01-tms1600-architecture.md) — the
  host CPU: the TMS1600's registers, its 4,096‑byte ROM organised as chapters
  and pages, the **LFSR program counter**, the RAM file, the K/R/O I/O lines,
  and the full instruction set (with exact semantics taken from Jason's
  emulator).
- `docs/02-how-the-microtronic-works.md` *(in progress)* — the guest machine:
  the RAM memory map, the fetch/decode/dispatch of the 16 Microtronic opcodes,
  display multiplexing, keyboard scanning, external 2114 SRAM access, and how
  each built‑in `F` operation and `PGM` program is implemented.

## How to read the annotated disassembly

Each line of the disassembly looks like this:

```
    LDX    1        # 00:0c (00:1e) 2c  -  <annotation goes here>
```

- `LDX 1` — the TMS1600 instruction and its operand.
- `00:0c` — the **logical** address as `page:offset` (page `00`–`3f`, offset
  `00`–`3f`). The page number packs the chapter and page: `page = chapter·16 + PB`.
- `(00:1e)` — the **physical** ROM address the instruction actually lives at.
  Because the program counter is a linear‑feedback shift register, consecutive
  logical instructions are scattered across the page in LFSR order; this is the
  real offset in `microtronic.bin`.
- `2c` — the raw instruction byte.
- everything after the `-` — our annotation.

See [`docs/01-tms1600-architecture.md`](docs/01-tms1600-architecture.md) for what
the LFSR ordering means and why the two addresses differ.

## Roadmap and status

- [x] Gather and verify the primary sources (ROM, disassembly, Jason's emulator, TI docs)
- [x] `docs/01` — TMS1600 host architecture reference
- [x] Annotation pipeline (`dev-support/build_annotated.py` + `annotated/*.tsv`)
- [~] `docs/02` — the Microtronic virtual machine (boot done; main loop → decode/dispatch next)
- [x] Annotate: reset & self‑initialisation (pages `0f`, `00`)
- [x] Annotate: the main interpreter loop and opcode dispatch (run check, fetch, PC advance, operand data path, and the full two‑level opcode→handler map incl. the F‑group)
- [x] Annotate: 7‑segment display multiplexing (`0d`) and the OPLA segment decode; SRAM write (`0c`)
- [ ] Annotate: the hex keypad scan and `KIN`
- [x] Annotate: external 2114 SRAM read — the instruction fetch (`09:02`), addressing, and the `KL`/`L` data path (writes share the same machinery; covered with keypad/`PGM` entry)
- [x] Annotate: arithmetic/logic opcodes, the flags (`M(4,13)`), and control flow (`GOTO`/`CALL`/`BRC`/`BRZ`)
- [ ] Annotate: the `F` operations (HALT, display, RND, HXDZ, …)
- [ ] Annotate: the built‑in `PGM` firmware programs (self‑test, cassette, clock, demos)

## Provenance, credit, and permissions

The firmware ROM is **© Busch GmbH**. It is reproduced here **only by the kind and
explicit permission of Mr. Jörg Vallen**, co‑designer of the Microtronic and CEO
of Busch Modellbau, who authorised publication of the operating system ROM (see
the acknowledgements in the [Microtronic Phoenix
repository](https://github.com/lambdamikel/microtronic-phoenix#acknowledgements)).
It is provided here **for reference, study, and historical interest only.**

- The **ROM dump** was produced by **Decle** and **Michael A. Wessel**, refined by **Jason T. Jacques**.
- The **disassembly** was produced by **Decle's** TMS1xxx disassembler and hand‑corrected by **Jason T. Jacques**.
- **Jason's** [TMS1000‑family emulator](https://github.com/lambdamikel/microtronic-phoenix) is the executable reference for every opcode's behaviour used throughout the annotations.
- The **annotations and `docs/` in this repository** are new work built on top of the above.

If you build on this, please credit the team and honour Mr. Vallen's generosity
in making the ROM public.

### License

- The **added annotations and documentation** (everything under `docs/` and
  `annotated/`, this README, and any tooling) are licensed **[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)** — reuse freely with attribution.
- The **firmware ROM and its disassembly** (`rom/`) are **not** under that
  license; they remain © Busch GmbH, published by permission for reference only.

See [`LICENSE`](LICENSE) for the exact scope of each.

## Further reading

See [`references/links.md`](references/links.md) for Jason's technical writeup,
Decle's AtariAge threads, the TI TMS1000‑family manuals, `naken_asm`, and Sean
Riddle's decap work.
