# The host CPU: Texas Instruments TMS1600

The Busch Microtronic is a single‑chip design. Everything the user thinks of as
"the computer" — the 16‑instruction machine language, the 6‑digit display, the
keypad, the flags, the clock, the cassette interface — is a program running on
one **Texas Instruments TMS1600** 4‑bit microcontroller. To read the firmware you
first have to understand the machine it runs *on*. That is this document. The
next one, [`02-how-the-microtronic-works.md`](02-how-the-microtronic-works.md),
covers the machine the firmware *builds*.

Everything below is stated to match the behaviour of **Jason T. Jacques'
TMS1000‑family emulator** (`references/jason-tms1000-emulator.ino`), which is the
executable reference we annotate against. Where the emulator and a datasheet
disagree about a corner, the emulator wins, because the emulator is what actually
runs the ROM correctly.

---

## 1. The TMS1000 family in one paragraph

The TMS1000 series (1974 onward) were among the first single‑chip
microcontrollers: CPU, mask ROM, RAM, and I/O on one die, sold by the million in
calculators, toys (Simon), and appliances. They are **Harvard, 4‑bit** machines.
Program and data live in separate memories; the ALU, accumulator, and all data
paths are 4 bits wide; instructions are 8 bits wide. The **TMS1600** is a
top‑of‑range family member: same core as the TMS1100/1400 but with the most
ROM (4 KB), the most I/O, and a **three‑level** subroutine stack.

| Resource | TMS1600 |
| --- | --- |
| Program ROM | 4,096 × 8‑bit = 4 KB, organised as **4 chapters × 16 pages × 64 words** |
| Data RAM | 128 × 4‑bit (= 64 bytes), organised as **8 files × 16 words** |
| ALU / registers | 4‑bit |
| Instruction word | 8‑bit |
| Subroutine stack | 3 levels deep (hardware) |
| Inputs | `K` bus: 4 lines (K1, K2, K4, K8) |
| Outputs | `R`: 11 latched lines (R0–R10); `O`: 8 lines via an output PLA |

## 2. Programmer's model (registers)

All registers are 4 bits unless noted.

| Reg | Width | Role |
| --- | --- | --- |
| **A** | 4 | Accumulator. The one general‑purpose working register; source/target of the ALU. |
| **Y** | 4 | Index register. Selects the **word** (0–15) within the current RAM file, *and* names which `R` output line `SETR`/`RSTR` act on, *and* is a second ALU operand. |
| **X** | 3 | File select. Chooses which of the 8 RAM files (0–7) `A`/`Y` addressing uses. |
| **S** | 1 | **Status.** Set (or cleared) as a side effect of almost every instruction (a compare result, a carry, an "always 1"). `BR` and `CALL` are *conditional on S*. |
| **SL** | 1 | Status latch. A one‑bit holdover of `S` used by `TDO` (it becomes the 5th output bit) and by `YNEA`. |
| **PA** | 4 | Page address — the page currently executing. |
| **PB** | 4 | Page buffer — the page a following branch/call will jump *into* (see §4). |
| **CA** | 2 | Chapter address — the chapter currently executing. |
| **CB** | 2 | Chapter buffer — the chapter a following branch/call will jump into. |
| **PC** | 6 | Program counter — but not a counter; a shift register (see §3). |
| **SR / PSR / CSR** ×3 | — | The three‑level return stack: saved PC, page, and chapter for `CALL`/`RETN`. |

There is **no flags word, no stack pointer, no memory‑mapped anything.** The
entire programmer's model is the table above. Everything the Microtronic offers
its user — 16 registers, a carry flag, a zero flag — is *synthesised in RAM* by
the firmware out of these parts.

### Power‑on state

`reg_init()` sets `PC = 0`, `PA = PB = 0xF`, `CA = CB = 0`, and everything else
to 0. So execution begins at **chapter 0, page 15 (0xF), offset 0** — which is
logical page `0f`, offset `00`, in the disassembly. That is the firmware's reset
entry point.

## 3. The program counter is a shift register (this is the big one)

The single most confusing thing about reading a TMS1000‑family disassembly is
that **the program counter does not count.** It is a 6‑bit **linear‑feedback
shift register (LFSR)**. Each "increment" shifts left one bit and feeds back a
computed bit; the sequence it walks through all 64 states is pseudo‑random, not
0,1,2,3,….

The exact recurrence (from the emulator) is:

```
next(pc) = ((pc << 1) | feedback) & 0x3f
  where feedback = 1  if pc == 0x1f   (0b011111)   // "msb 0, rest 1"
                 = 0  if pc == 0x3f   (0b111111)   // "all ones"
                 = (bit5(pc) == bit4(pc)) ? 1 : 0  // else XNOR of the top two bits
```

Starting from 0 it produces:

```
00 → 01 → 03 → 07 → 0f → 1f → 3f → 3e → 3d → 3b → 37 → 2f → 1e → 3c → 39 → 33 → …
```

Now look at the very top of the disassembly:

```
TCY f   # 00:00 (00:00) 4f
RSTR    # 00:01 (00:01) 0c
DYN     # 00:02 (00:03) 04
BR 01   # 00:03 (00:07) 81
RETN    # 00:04 (00:0f) 0f
LDX 0   # 00:05 (00:1f) 28
```

The number **after** the `#`, e.g. `00:05`, is the **logical** address — the
disassembler numbering instructions in *execution order* (0,1,2,3,…). The number
**in parentheses**, e.g. `(00:1f)`, is the **physical** address — the actual LFSR
state, i.e. the real byte offset in `microtronic.bin`. Read down the parenthesised
column and you are reading the LFSR sequence: `00, 01, 03, 07, 0f, 1f, …`.

**Consequences for reading the ROM:**

- Consecutive instructions are physically scattered across the 64‑word page. The
  disassembler undoes this for you: read it top‑to‑bottom by the *logical* number
  and it flows like normal code.
- A page is exactly **64 words**; the LFSR cycles through all 64 states and wraps.
  Code cannot silently "fall off the end" of a page into the next — it wraps
  within the page. Crossing a page boundary is always deliberate, via a
  page/chapter‑buffer load followed by a branch (§4).
- Because the design pre‑computes an LFSR value for the *last* word of a page as a
  known constant, `RETN`/`BR` targets and the reset entry are chosen with the
  scrambling in mind. You do not have to: the disassembler already resolved every
  `BR`/`CALL` operand to a **logical** offset.

That last point matters for the annotations: when a line says `CALL 06` or
`BR 08`, the `06`/`08` are **logical offsets** you can find directly as the
`page:06` / `page:08` line. The raw instruction byte encodes the *physical* LFSR
target; the disassembler inverted the LFSR to show you the friendly number.

## 4. ROM layout: chapters, pages, and deferred branching

The 4 KB ROM is addressed as:

```
physical byte address = (CA << 10) | (PA << 6) | PC
                          2 bits      4 bits     6 bits
                         chapter      page      LFSR offset
```

In the disassembly the two are merged into a single **logical page number
`00`–`3f`**, where `page = CA·16 + PA`. So disassembly "Page 0f" is chapter 0 /
page 15; "Page 3f" is chapter 3 / page 15.

Branches and calls only carry a **6‑bit offset** — they can reach anywhere *within
the current page*. To go to a different page or chapter you use the **buffer /
deferred‑load** mechanism, which is the other TMS quirk to internalise:

- **`LDP p`** loads the 4‑bit page buffer `PB`. It does **not** jump. It arms the
  *next* branch/call to land in page `p`.
- **`TPC`** (called `COMC` on the TMS1100) copies `PB`'s low 2 bits into the
  chapter buffer `CB`. Again deferred — arms the chapter of the next branch/call.
- **`BR off`** — if `S==1`: set `PA←PB`, `CA←CB`, `PC←off`. If `S==0`: do nothing
  but restore `S←1` and fall through. So a branch is *taken only when status is
  set*, and it commits the armed page/chapter.
- **`CALL off`** — like `BR`, but also pushes the return address (PC, page,
  chapter) onto the 3‑level stack and sets the call latch. `RETN` pops it.

This is why the ROM is full of idioms like:

```
LDP 9       # arm page 9
CALL 23     # ... now call into page 9, offset 23
```

The `LDP`/`TPC` and the branch/call are **read as a unit**: the load names the
destination page/chapter, the branch/call is the actual transfer. A `BR`/`CALL`
with no preceding `LDP` stays in the current page.

### Status‑driven control flow

There are no explicit "compare then jump‑if‑equal" instructions. Instead:

1. An instruction sets `S` as a side effect (e.g. `YNEC 5` sets `S = (Y != 5)`;
   `TBIT 3` sets `S` to bit 3 of the addressed RAM word; `TCY 4` sets `S = 1`).
2. The **very next** `BR`/`CALL` consumes `S`: it is taken iff `S==1`.
3. If the branch was **not** taken (`S` was 0), `S` is reset to 1 and execution
   falls through to the next instruction.

So the canonical "skip / take" pattern is *test‑instruction* immediately followed
by *branch*. Most non‑test instructions set `S=1`, which is why an unconditional
jump is just any `BR` reached with `S` already 1.

## 5. Data RAM: files and words

RAM is 128 nibbles seen as **8 files × 16 words**:

- **X** (0–7) selects the file.
- **Y** (0–15) selects the word within the file.
- `M(X,Y)` is the addressed 4‑bit cell.

Instructions move data between `A`, `Y`, and `M(X,Y)`, and can test or set/reset
**individual bits** of `M(X,Y)` (`SBIT`/`RBIT`/`TBIT`). The Microtronic firmware
lays out its entire world in this RAM — the user's 16 registers, the current
instruction being interpreted, the display digits, the SRAM address pointer, the
clock — as specific `(file, word)` cells. That map is the subject of the next
document.

## 6. I/O

- **`K` inputs (4 lines).** Read with `TKA` (`A←K`) or tested with `KNEZ`
  (`S = K != 0`). In the Microtronic these are the return lines of the keypad
  matrix, and — multiplexed via the `KL` selector (here output `R11`) — the `L`
  data lines from the external 2114 SRAM.
- **`R` outputs (11 lines, R0–R10).** Individually latched: `SETR` sets the line
  named by `Y`, `RSTR` clears it. Used as keypad column strobes, display digit
  strobes, and SRAM control/address lines.
- **`O` outputs (8 lines) via the Output PLA.** `TDO` drives the O bus from
  `SL:A` (a 5‑bit value) *through the OPLA*, a mask‑programmed lookup that turns
  the 4‑bit accumulator into an arbitrary 8‑bit pattern — this is how a nibble
  becomes a 7‑segment glyph, and how data bytes are shipped to the SRAM.

## 7. Instruction set

The mnemonics in the disassembly are the standard TMS1000‑family set (the
TMS1600 is the TMS1100 set with `COMC` reinterpreted as `TPC`). Semantics below
are exactly as the emulator implements them. `S` is the status bit set by the
instruction; "→" shows the register effect.

### Data movement

| Mnemonic | Effect | S set to |
| --- | --- | --- |
| `TAY` | Y ← A | 1 |
| `TYA` | A ← Y | 1 |
| `TMA` | A ← M(X,Y) | 1 |
| `TMY` | Y ← M(X,Y) | 1 |
| `TAM` | M(X,Y) ← A | 1 |
| `TAMZA` | M(X,Y) ← A; A ← 0 | 1 |
| `XMA` | swap A ↔ M(X,Y) | 1 |
| `TKA` | A ← K inputs | 1 |
| `CLA` | A ← 0 | 1 |
| `TCY n` | Y ← n (constant) | 1 |
| `TCMIY n` | M(X,Y) ← n; Y ← Y+1 | 1 |
| `LDX n` | X ← n | 1 |
| `COMX` | complement X (bit 2 on TMS1100/1600) | 1 |

### Arithmetic / logic (on A and M)

| Mnemonic | Effect | S set to |
| --- | --- | --- |
| `AMAAC` | A ← M+A | carry (M+A > 15) |
| `SAMAN` | A ← M−A | A ≤ M (no borrow) |
| `IMAC` | A ← M+1 | M == 15 |
| `DMAN` | A ← M−1 | M ≥ 1 |
| `IAC`‑style `AC1AC n` | A ← A+n+1 | carry (>15) |
| `IYC` | Y ← Y+1 | Y == 15 (carry) |
| `DYN` | Y ← Y−1 | Y ≥ 1 (no borrow) |
| `CPAIZ` | A ← (−A) i.e. 2's complement | A was 0 |
| `ALEM` | (compare) | A ≤ M(X,Y) |
| `ALEC n` | (compare, TMS1000) | A ≤ n |
| `MNEA` | (compare) | M(X,Y) != A |
| `MNEZ` | (compare) | M(X,Y) != 0 |
| `YNEA` | (compare) | Y != A (also sets SL) |
| `YNEC n` | (compare) | Y != n |
| `KNEZ` | (compare) | K != 0 |

### RAM bit operations

| Mnemonic | Effect | S set to |
| --- | --- | --- |
| `SBIT b` | set bit b of M(X,Y) | 1 |
| `RBIT b` | reset bit b of M(X,Y) | 1 |
| `TBIT b` | test bit b of M(X,Y) | value of that bit |

### Combined store/index (used all over the interpreter loops)

| Mnemonic | Effect | S set to |
| --- | --- | --- |
| `TAMIYC` | M(X,Y) ← A; Y ← Y+1 | Y was 15 (carry) |
| `TAMDYN` | M(X,Y) ← A; Y ← Y−1 | Y ≥ 1 (no borrow) |

### I/O

| Mnemonic | Effect | S set to |
| --- | --- | --- |
| `SETR` | R[Y] ← 1 | 1 |
| `RSTR` | R[Y] ← 0 | 1 |
| `TDO` | O bus ← OPLA(SL:A) | 1 |

### Control flow

| Mnemonic | Effect |
| --- | --- |
| `LDP p` | PB ← p (arm next branch's page) |
| `TPC` | CB ← PB[1:0] (arm next branch's chapter) |
| `BR off` | if S: PA←PB, CA←CB, PC←off; else S←1, fall through |
| `CALL off` | if S: push return (PC,PA,CA), PA←PB, CA←CB, PC←off; else S←1, fall through |
| `RETN` | pop return address from the 3‑level stack |

> **Note on constants.** The immediate fields for `TCY`, `TCMIY`, `YNEC`,
> `AC1AC`, `LDX`, `SBIT`/`RBIT`/`TBIT` are stored **bit‑reversed** in the ROM
> byte (a hardware artefact of the PLA decode). The disassembler already decodes
> them to their true value, so the operand you read in the listing is the real
> constant. You only need to know this if you ever hand‑decode a raw byte.

## 8. How this shapes the firmware

Three facts from above drive almost every idiom you'll see in the annotated ROM:

1. **4‑bit everything.** A "byte" of user data, a display digit, an SRAM nibble —
   all are single RAM cells; multi‑nibble quantities (like a 2‑nibble SRAM
   address or the packed Microtronic instruction) are spread across adjacent
   `Y` positions and walked with `IYC`/`DYN`.
2. **Test‑then‑branch.** Every decision is an instruction that sets `S` followed
   by a `BR`/`CALL`. Long `if/else` ladders (like opcode dispatch) become chains
   of `YNEC n / BR` comparisons.
3. **Deferred paging.** Any transfer out of the current 64‑word page is a
   `LDP`(/`TPC`)+branch pair. Subroutines that live on other pages are always
   reached this way, so the physical code is a patchwork of pages stitched
   together by these pairs — which is exactly why a top‑down "theory of
   operation" is needed to see the structure. That's the next document.
