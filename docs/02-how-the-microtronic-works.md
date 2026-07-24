# The guest machine: how the Microtronic works

[`01-tms1600-architecture.md`](01-tms1600-architecture.md) described the **host**:
a TMS1600 with a 4‑bit accumulator, RAM addressed as 8 files × 16 words, an
LFSR program counter, and `K`/`R`/`O` I/O. This document describes the **guest**:
the Busch Microtronic that the firmware *synthesises* on top of that host — its
16‑instruction machine language, its 16 user registers, its carry/zero flags,
its 6‑digit display and hex keypad, and its 1‑KB external memory.

Almost nothing the user sees maps one‑to‑one to hardware. The user's "registers"
are RAM cells; the user's "opcodes" are decoded by a software dispatch; the
"display" is produced by the firmware strobing digits thousands of times a
second. This document builds that picture routine by routine, from power‑on
outward. It grows as the annotation progresses; sections marked *(pending)* are
next on the [roadmap](../README.md#roadmap-and-status).

> **Conventions.** `M(x,y)` is the RAM cell in file `x`, word `y` (both from the
> host's point of view). `page:offset` addresses (e.g. `00:1f`) are the *logical*
> addresses from the disassembly — read the annotated listing at that address.
> Everything is cross‑checked against Jason's emulator.

---

## 1. The RAM memory map (working map)

The firmware keeps all of its state in the TMS1600's 128 nibbles of RAM. The map
below merges what Jason documented in his
[writeup](https://jsonj.co.uk/project/microtronic/) with what the boot and
block‑copy routines reveal. Cells not yet confirmed are marked *(tbd)* and will
be pinned down as their routines are traced.

**File 1 — the interpreter's control block** (the best‑understood file):

| Cell | Role |
| --- | --- |
| `M(1,0)` | current instruction — operand **LSB** (low nibble) |
| `M(1,1)` | current instruction — operand **MSB** (middle nibble) |
| `M(1,2)` | current instruction — **command** (opcode nibble) |
| `M(1,4)` | external SRAM address pointer — low bits |
| `M(1,5)` | external SRAM address pointer — high bits |
| `M(1,15)` | temporary / working cell |

A Microtronic instruction is three hex digits (e.g. `F08`, `1A5`); the firmware
holds it decomposed across `M(1,2)` (command) and `M(1,1)`/`M(1,0)` (the two
operand nibbles), fetches it from the user's program in external SRAM, and
dispatches on the command nibble.

**Files 0, 2, 3 — operand/register scratch** *(tbd, partially traced).* The
block‑copy helpers on page `0f` shuffle 2–3 nibble blocks between files 0, 1, 2,
and 3 (words 0–5). These look like save/restore of the working operand and
register fields around subroutine calls; the exact ownership is being confirmed.

**The user's 16 registers, and the carry/zero flags** *(tbd)* live in RAM too and
are the subject of the arithmetic‑opcode pass.

## 2. Boot: from power‑on to the interpreter

This sequence is fully traced; see the annotated listing, pages `0f` and `00`.

### 2.1 The reset trampoline (page 0f)

On power‑up the TMS1600 starts at chapter 0, page `0xF`, `PC = 0` — logical
address **`0f:00`**. The firmware puts a two‑instruction trampoline there:

```
0f:00  LDP 0     ; arm page 0
0f:01  BR  00    ; jump to 00:00  (the real boot init)
```

Everything else on page `0f` is a set of **RAM block‑copy subroutines** (copy an
N‑nibble block from one file to another) that the interpreter uses later to save
and restore operand fields. They are *not* on the boot path — the boot leaves
page `0f` immediately at `0f:01`.

### 2.2 Clearing the machine (page 00)

Execution lands at **`00:00`** and does three things:

**(a) Turn off every R output.**

```
00:00  TCY f        ; Y = 15
00:01  RSTR         ; R[Y] = 0
00:02  DYN          ; Y--
00:03  BR 01        ; loop  -> clears R15..R0
00:04  RETN
```

This same block is also a callable "clear all outputs" subroutine. At boot,
though, the call stack is empty, so its `RETN` doesn't return anywhere — it
**falls through** to the next instruction. The firmware exploits this
fall‑through repeatedly to save ROM: a subroutine body and a straight‑line boot
step share the same code.

**(b) Zero all 128 nibbles of RAM.**

```
00:05  LDX 0        ; file 0 ...
00:06  TCY f        ; (callable entry: "clear file X")
00:07  CLA
00:08  TAM          ; M(X,15) = 0
00:09  DYN
00:0a  BR 08        ; loop -> zero all 16 words of file X
00:0b  RETN         ; (falls through at boot)
00:0c  LDX 1 / CALL 06   ; clear file 1
       ... LDX 2..7 / CALL 06 ...          ; clear files 2..7
```

File 0 is cleared inline (by fall‑through); files 1–7 are cleared by *calling*
the very same loop. After `00:19`, all of RAM is zero.

**(c) Initialise and enter the interpreter.**

```
00:1a  LDP 9 / CALL 23   ; init subroutine at 9:23
00:1c  LDP e / CALL 02   ; init subroutine at 0e:02  (unpacks a nibble onto R7..R10)
00:1e  LDP 7 / BR  1d    ; enter the interpreter main loop at 7:1d
```

The two init subroutines set up initial hardware/output state (the `0e:02`
routine drives output lines `R7`–`R10` from the four bits of a nibble; the
`9:23` routine is a small bit‑wise helper — both are detailed in their own
pass). The boot then branches to **`7:1d`**, the interpreter.

### 2.3 Reaching the interpreter (page 07 → chapter 1)

`7:1d` is not the loop body itself; it is a paging springboard:

```
07:1d  LDP 1        ; arm page 1 ...
07:1e  TPC          ; ... and copy its low 2 bits into the chapter buffer -> chapter 1
07:1f  LDP c        ; arm page c
07:20  BR  21       ; jump to chapter 1, page c, offset 21  (logical 1c:21)
```

So the interpreter's main loop lives up in **chapter 1** (logical page `1c`), and
page `07` is a dispatch/springboard area full of `TBIT`‑driven mode tests. This
is the first place the "deferred paging" idiom (§4 of doc 01) really bites, and
it is why the running interpreter is spread across several pages rather than
sitting in one contiguous block.

## 3. The main interpreter loop *(pending)*

*Next on the roadmap:* trace `1c:21` onward — how the firmware fetches the next
three‑nibble Microtronic instruction from external SRAM into `M(1,2)`/`M(1,1)`/
`M(1,0)`, advances the user program counter, and dispatches on the command
nibble to one of the 16 opcode handlers.

## 4. Display, keypad, SRAM, and the F‑operations *(pending)*

*Also on the roadmap:* the 7‑segment multiplexing and flag LEDs; the hex keypad
matrix scan and `KIN`; external 2114 SRAM read/write (the `L`/`O` data path via
the `KL` multiplexer); the arithmetic/logic opcodes and their carry‑is‑no‑borrow
semantics; and the built‑in `F` operations and `PGM` programs.
