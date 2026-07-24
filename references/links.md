# References

## Primary sources for this project

- **Jason T. Jacques — Microtronic reverse‑engineering writeup**
  <https://jsonj.co.uk/project/microtronic/>
  The technical walkthrough of the TMS1600, the ROM dump, the LFSR PC, and the
  Microtronic virtual machine. The single best companion to this repository.
- **Jason's TMS1000‑family emulator** — local copy at
  [`jason-tms1000-emulator.ino`](jason-tms1000-emulator.ino), full project at
  <https://github.com/lambdamikel/microtronic-phoenix>. The executable reference
  for every opcode's behaviour used in the annotations.
- **Microtronic Phoenix** — <https://github.com/lambdamikel/microtronic-phoenix>
  The emulator that runs this ROM, and the origin of the published ROM +
  disassembly (with Jörg Vallen's permission).
- **The ROM dump project logs** —
  <https://hackaday.io/project/197415-microtronic-firmware-rom-archaeology>

## TMS1000 family documentation

- **TI TMS1000 Programmer's Reference Manual** (instruction set, test mode, the
  LFSR PC sequence) — <https://archive.org/details/bitsavers_tiTMS1000T_10154027>
- **TMS1000 Family Data Book** —
  <https://archive.org/details/tms-1000-family-microcomputers-data-book_202208>
- **`tms1400info.pdf`** — local copy in this folder (TMS1400/1600 family notes).
- **naken_asm** (the disassembler/assembler used, `-tms1100` mode with TPC) —
  <https://github.com/mikeakohn/naken_asm>

## Decapping / dumping background

- **Sean Riddle — TMS1100 decap & dump** — <http://www.seanriddle.com/tms1100.html>
- **Decle** (ROM dumping technology, TMS1xxx disassembler) —
  <https://forums.atariage.com/profile/46336-decle/>
- **Radio Shack Science Fair Microcomputer Trainer** test‑mode dumping (the
  technique that inspired the TMS1600 dump) —
  <https://hackaday.io/project/194876-exploring-the-science-fair-microcomputer-trainer>

## The Microtronic itself

- **Busch‑2090** (manuals, schematics, software, the Neo emulators) —
  <https://github.com/lambdamikel/Busch-2090>
- **English manual translations** —
  <https://github.com/lambdamikel/microtronic-2090-manuals-english>
- **Busch Modellbau — Microtronic product page** —
  <https://www.busch-modell.de/information/Microtronic-Computer.aspx>
- **PicoRAM 2090** (external SRAM replacement; verifies the 2114 signal mapping) —
  <https://github.com/lambdamikel/picoram2090>
