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

**File 7 — the user's 16 registers.** `M(7,0)`…`M(7,15)` *are* the Microtronic
registers `R0`…`R15`. An opcode that names a register indexes file 7 by the
operand nibble. (Confirmed: `MOV`/`MOVI` read and write exactly these cells.)

**File 1 — the interpreter's control block:**

| Cell | Role |
| --- | --- |
| `M(1,0)` | current instruction — **last** digit (destination‑register operand) |
| `M(1,1)` | current instruction — **middle** digit (source‑register / immediate operand) |
| `M(1,2)` | current instruction — **command** (opcode digit) |
| `M(1,4)` | external SRAM address pointer — low nibble |
| `M(1,5)` | external SRAM address pointer — high nibble |
| `M(1,13)` / `M(1,14)` | saved return address (low/high) for `CALL`, restored by `RET` |
| `M(1,15)` | temporary / working cell |

A Microtronic instruction is three hex digits (`c s d`, e.g. `0` `A` `5`); the
firmware holds it decomposed across `M(1,2)`=`c`, `M(1,1)`=`s`, `M(1,0)`=`d`.

**File 2 — the program counter.** `M(2,5):M(2,4)` is the 2‑nibble user program
counter (0–255). It is incremented each executed instruction and copied into the
SRAM address pointer `M(1,5):M(1,4)` (see §3.2). `M(2,2)` holds interpreter
state/mode bits.

**File 4 — the ALU scratch and the flags.** `M(4,15)` and `M(4,14)` hold the two
*resolved* operand values for the current instruction — typically `M(4,15)` the
destination register's value and `M(4,14)` the source's. **`M(4,13)` is the flags
cell: bit 0 = CARRY, bit 1 = ZERO** — the user‑visible flags that `BRC`/`BRZ`
test and the arithmetic opcodes set (§4).

**File 3 — backups.** Receives copies of the program counter (§3.2) and, via the
page‑`0f` block‑copy helpers, of operand/register fields, so the interpreter can
save and restore working state around subroutine calls.

**File 0 — flags & decode scratch.** `M(0,8)` holds mode/status bits — bit 3 is
the "execute an instruction this pass" flag the main loop tests. `M(0,14)`/
`M(0,15)` are used to decode the operation class. The user‑visible **carry** and
**zero** flags live here too *(exact cells: pending the arithmetic pass)*.

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

## 3. The main interpreter loop

The interpreter proper lives in chapter 1 (pages `1c`, `16`, `15`, `17`, `1b`,
`1e`) with the fetch/execute machinery down in chapter 0 (pages `08`, `09`). The
pieces below are traced and annotated; the full opcode‑dispatch table is the next
step.

### 3.1 Run check (page 1c)

Each pass through the loop reaches `1c:21`:

```
1c:21  LDX 0 / TCY 8 / TBIT 3   ; test M(0,8) bit 3 — "execute an instruction this pass?"
1c:24  BR 27                    ;   set  -> execute one instruction
1c:25  LDP e / BR 1a            ;   clear-> idle: keypad / command entry at 1e:1a
1c:27  RBIT 3                   ; clear the flag for this pass
1c:28  LDP 0 / TPC / LDP 8 / BR 02   ; drop to chapter 0, execute at 08:02
```

So the machine advances **one Microtronic instruction per loop pass** when the
"run" bit is set; otherwise it services the keypad. Between passes the loop
refreshes the display, which sets the Microtronic's real‑world instruction rate.

### 3.2 Fetch and program‑counter advance (page 08)

`08:02` is the execute‑one‑instruction entry. It first **advances the program
counter** — the two‑nibble value in `M(2,5):M(2,4)`:

```
08:04  IMAC ; A = M(2,4)+1, carry if it was 15   (increment PC low)
08:06  TAM  ; store PC low
08:08  ...  ; on carry, increment PC high M(2,5)
```

then **copies the new PC into the SRAM address pointer** `M(1,5):M(1,4)` (and a
backup in file 3):

```
08:0c..18  M(3,5)=M(1,5)=PChi ,  M(3,4)=M(1,4)=PClo
```

and finally **fetches the instruction from external SRAM** at that address:

```
08:1a  LDP 9 / CALL 02   ; -> SRAM read routine at 9:02
```

which loads the three nibbles into `M(1,2)` (command), `M(1,1)`, `M(1,0)`. The
2114 SRAM read itself (bit‑banged over the `R` address/control lines and the `L`
data lines through the `KL` multiplexer) is documented in its own pass.

### 3.3 Operand resolution and write‑back (page 17)

Once the instruction is in `M(1,*)`, page `17` provides the primitives every
opcode is built from. File 7 is the register file:

- **Resolve a register operand** (`17:00`): `Y ← M(1,1)`; `A ← M(7,Y)`; stash in
  scratch `M(4,15)`. A shared entry at `17:02` lets the caller pick which operand
  nibble to use (with `Y=0` it resolves `M(1,0)`, the destination register).
- **Take an immediate** (`17:1d`): `A ← M(1,1)` (the literal middle digit).
- **Write back** (`17:10`): `R[M(1,0)] ← A` — store the result into the
  destination register named by the last digit.

### 3.4 Worked example: `MOV` and `MOVI`

With those primitives, the two simplest opcodes are two instructions each
(`17:24`–`28`):

| Microtronic op | Encoding | Implementation | Effect |
| --- | --- | --- | --- |
| `MOV s,d` | `0 s d` | `CALL 17:00` (A ← R[s]) then `BR 17:10` (R[d] ← A) | `Rd ← Rs` |
| `MOVI n,d` | `1 n d` | `CALL 17:1d` (A ← n) then `BR 17:10` (R[d] ← A) | `Rd ← n` |

This is the template for the whole instruction set: **resolve operand(s) →
compute → write back to `R[M(1,0)]`.** The arithmetic and logic opcodes add a
compute step in the middle (using the two scratch operands `M(4,14)`/`M(4,15)`)
and set the carry/zero flags — see §4.

### 3.5 The opcode dispatch (page 10 → page 11)

After the fetch, the command digit is decoded by a two‑level jump table. The
decode trick is worth seeing: instead of a `TBIT` tree, it reloads the opcode and
runs it through `ACxAC n` — "A ← A + n + 1, set carry if > 15" — so that a chosen
constant makes exactly one opcode value carry:

```
10:04  TMA         ; A = M(1,2)  (command digit)
10:05  ACxAC 0     ; A+1 > 15  <=> A == 15   -> take the F branch
10:07  TMA         ; reload
10:08  ACxAC 1     ; A+2 > 15  <=> A == 14   -> take the E branch
...                ; ... catching 13,12,…,5 ...
10:25  (fallthru)  ; A <= 4    -> second-level table at 11:00
```

Each matched arm is an `LDP p / BR off` to that opcode's handler. Opcodes 0–4
drop to a second identical ladder on page `11`. The result is the **complete
Microtronic instruction → firmware handler map**:

| Op | Mnemonic | Form | Handler | Op | Mnemonic | Form | Handler |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `0` | `MOV s,d` | reg | `17:25` | `8` | `CMP s,d` | reg | `16:03` |
| `1` | `MOVI n,d` | imm | `17:27` | `9` | `CMPI n,d` | imm | `16:00` |
| `2` | `AND s,d` | reg | `15:14` | `A` | `OR s,d` | reg | `1c:00` |
| `3` | `ANDI n,d` | imm | `15:0d` | `B` | `CALL a` | ctl | `14:2c` |
| `4` | `ADD s,d` | reg | `17:00` | `C` | `GOTO a` | ctl | `14:00` |
| `5` | `ADDI n,d` | imm | `17:1d` | `D` | `BRC a` | ctl | `14:1f` |
| `6` | `SUB s,d` | reg | `16:1b` | `E` | `BRZ a` | ctl | `14:27` |
| `7` | `SUBI n,d` | imm | `16:16` | `F` | *F‑group* | — | `11:17` |

Two structural facts fall out of the handler column and confirm the decode:

- **Register/immediate pairs share a page.** AND/ANDI both land on page `15`,
  ADD/ADDI on `17`, SUB/SUBI and CMP/CMPI on `16`, MOV/MOVI on `17`. The even
  opcode is the register form, the odd one the immediate form, and they merge
  into a common tail after the operand is resolved (§3.3).
- **`MOV`→`17:25` and `MOVI`→`17:27`** are exactly the two‑instruction handlers
  decoded in §3.4 — the dispatch and the handler agree.

### 3.6 The F‑group (third dispatch level)

Opcode `F` is itself a family. `11:17` decodes the **second** digit `M(1,1)` with
the same `ACxAC` ladder:

| 2nd digit | Op | Handler | | 2nd digit | Op | Handler |
| --- | --- | --- | --- | --- | --- | --- |
| `9` | `SHR` | `1a:00` | | `D` | `DIN` | `18:20` |
| `A` | `SHL` | `1a:29` | | `E` | `DOT` | `18:10` |
| `B` | `ADC` | `19:0d` | | `F` | `KIN` | `18:00` |
| `C` | `SUBC` | `19:00` | | `0`–`8` | `F0x` ext ops, `DISP`, `MAS`, `INV` | `12:00` |

So `FEd`/`FDd`/`FFd` (`DOT`/`DIN`/`KIN` — the I/O opcodes) live on page `18`, the
shift/carry ops on `19`/`1a`, and the `F0x` extended operations (`HALT`, `NOP`,
`HXDZ`, `RND`, `TIME`, `CLEAR`, `MULT`, `DIV`, …) plus `DISP` and `MAS`/`INV` are
reached through `12:00`.

### 3.7 The opcode handlers themselves *(next)*

The dispatch skeleton is complete. §4 covers the arithmetic/logic handlers and
the flags; the display, keypad, SRAM, and remaining F‑op passes are on the
[roadmap](../README.md#roadmap-and-status).

## 4. Arithmetic, logic, flags, and control flow

Every arithmetic/logic opcode follows the template from §3.4 — **resolve
operand → compute → write back to `Rd`** — with the compute step working on the
two scratch cells `M(4,15)` (the destination value `Rd`) and `M(4,14)`/`A` (the
source value or immediate). The results feed two flags.

### 4.1 The flags: `M(4,13)`

The Microtronic's user‑visible flags are two bits of one RAM cell:

| | Cell/bit | Set by | Read by |
| --- | --- | --- | --- |
| **CARRY** | `M(4,13)` bit 0 | ADD (overflow), SUB/CMP (no‑borrow), … | `BRC` |
| **ZERO** | `M(4,13)` bit 1 | SUB/CMP (result == 0), … | `BRZ` |

This is confirmed from both directions: the setters (`16:07`/`16:0a` for carry,
`16:0e`/`16:12` for zero — all `X=4, Y=13`) and the readers (`14:1f`/`14:27`).

### 4.2 Add and subtract

**`ADD`/`ADDI`** (page 17) resolve the operand into `M(4,15)`, then:

```
17:0a  A = Rd                 ; load-Rd helper 1a:00
17:0b  AMAAC ; A = Rd + M(4,15)   ; add operand; S = carry (sum > 15)
17:0c..1c  set/clear CARRY, then write the sum back to Rd
```

**`SUB`/`SUBI`/`CMP`/`CMPI`** (page 16) use `SAMAN`:

```
16:05  SAMAN ; A = M(4,15) - A = Rd - operand ; S = (Rd >= operand) = "no borrow"
16:06..0b    set CARRY = no-borrow
16:0c  CPAIZ ; S = (difference == 0)
16:0d..12    set ZERO accordingly
```

Note the Microtronic convention that **carry means "no borrow"** on a subtract —
it is set when `Rd >= operand`. `CMP`/`CMPI` set the flags and discard the
difference; `SUB`/`SUBI` store it back into `Rd`.

### 4.3 Logic

**`AND`/`ANDI`** (page 15) and **`OR`** (`1c:00`) combine `M(4,15)` and `M(4,14)`
bit by bit — `AND` clears each result bit where the other operand is 0, `OR` sets
each bit where the other operand is 1 — then write the result back to `Rd` via
the shared register write‑back tail at `15:2f`.

### 4.4 Control flow (page 14)

- **`GOTO a`** — copy the two‑digit target `M(1,1):M(1,0)` into the SRAM address
  pointer, then **decrement by one** and store it as the program counter. The
  decrement is deliberate: the fetch step (§3.2) pre‑increments the PC, so
  setting it to *target − 1* makes the next fetch read the target.
- **`CALL a`** — the same, but first exchange (`XMA`) the current PC out and save
  it as the return address in `M(1,13):M(1,14)`. The Microtronic's single‑level
  `RET` (`F07`) restores it. (There is no stack — a second `CALL` overwrites the
  saved return address, which is why Microtronic subroutines cannot nest.)
- **`BRC a` / `BRZ a`** — test `M(4,13)` bit 0 / bit 1. If set, **take the branch
  by falling into the `GOTO` handler** (`14:00`) with the same target; if clear,
  skip to the next instruction. Reusing `GOTO` for the taken‑branch case is a
  neat bit of ROM economy.

## 5. External memory: the 2114 SRAM

The user's program (and its data area) does not live in the TMS1600's tiny
internal RAM — it lives in an **external 2114 static RAM**, 1024 × 4 bits, wired
to the TMS1600's I/O lines. Everything the interpreter does begins by reading an
instruction out of it.

### 5.1 Addressing: 256 instruction slots

The 2114's 1024 nibbles are organised as **256 slots of 4 nibbles each**. A slot
holds one Microtronic instruction: nibble 0 = command, nibble 1 = middle digit,
nibble 2 = last digit (nibble 3 unused). The address has two parts:

- the **8‑bit instruction number** `M(1,5):M(1,4)` — i.e. the program counter
  (§3.2) — presented on the address lines by the setup routine `0b:20`;
- a **2‑bit nibble select** toggled directly on outputs `R4`/`R5`, which the read
  routine steps to walk the three nibbles of the instruction.

Together they span all 1024 nibbles as 256 four‑nibble slots. (The exact wiring
of each address bit to a physical `R`/`O` pin is in the
[PicoRAM 2090](https://github.com/lambdamikel/picoram2090) firmware; here we take
the addressing at the logical level the firmware works in.)

### 5.2 Reading a nibble

The data bus is the TMS1600's `L` inputs, reached through the `KL` multiplexer.
The read routine (`09:02`) is a clean four‑step handshake per nibble:

```
09:03  SETR (Y=11)     ; R11 = KL selector = 1  -> route the L data lines onto the K bus
09:04  CALL 0b:20      ; drive the address (M(1,5):M(1,4)) onto the output lines
09:06  CALL 0e:36      ; settle delay — wait for the 2114's data to be valid
09:08  TKA             ; A = K = the L data nibble
09:09  CALL 09:23      ; one's-complement it (SRAM data is stored inverted)
       ... store to M(1,2), bump R5/R4, repeat for M(1,1) and M(1,0) ...
09:20  RSTR (Y=11)     ; R11 = 0  -> KL back to keyboard-scan mode
```

Two hardware details worth flagging, both cross‑checked:

- **`R11` is the `KL` selector.** Setting it makes `TKA`/`KNEZ` read the SRAM `L`
  lines instead of the keypad; the firmware sets it around every SRAM access and
  clears it afterwards. (Jason's emulator defines `get_kl()` as exactly bit 11 of
  the `R` register.)
- **SRAM data is complemented.** Every nibble read is passed through the
  one's‑complement helper `09:23`, so the bits on the `L` lines are the inverse of
  the stored value. (The write path inverts correspondingly.)

### 5.3 Where reads and writes happen

Instruction *reads* are driven by the fetch (§3.2 → `09:02`) on every executed
instruction. *Writes* use the mirror‑image routine on page **`0c`**: it sets up
the same address (`0b:20`), drives each data nibble onto outputs **`R7`–`R10`**
(via the nibble‑unpack helper `0e:02`), and latches it with a pulse on the
**`R13`** write‑enable strobe. Writes happen when a program is entered from the
keypad or loaded by a `PGM` program (those higher‑level paths are on the
roadmap). Read data arrives on the `L` lines through the `KL` mux; write data
leaves on `R7`–`R10`.

## 6. The display: multiplexed 7‑segment output

The Microtronic's six‑digit LED display is not memory‑mapped and has no frame
buffer of segments — it is **multiplexed in software**. The refresh routine on
page **`0d`** lights one digit at a time, fast enough that all six look steady,
and this refresh doubles as the interpreter's main timing loop (it runs between
executed instructions, which is part of what sets the machine's speed).

### 6.1 The refresh loop

The six digit values live in RAM (one nibble each). For each digit, from 5 down
to 0:

```
0d:11  TMY           ; Y = M(x,14) = the current digit index
0d:12  TMA           ; A = M(x,Y)  = that digit's value (0..F)
0d:13  TDO           ; O bus = OPLA(SL:A)  -> the 7-segment pattern
0d:14  SETR          ; R[index] = 1  -> strobe this digit's common line (R0..R5)
       ... short delay (A counts 0->15) ...
0d:1d  RSTR          ; R[index] = 0  -> turn the digit off
0d:28  DMAN          ; index = index - 1, next digit
```

`R0`–`R5` are the six digit‑common strobes; only one is high at a time. Because
the display, the keypad columns, and the SRAM address all borrow the same handful
of `R` lines, these roles are **time‑multiplexed** — the firmware is careful to
drive each subsystem only during its own phase.

### 6.2 Segments come from the OPLA, not a font table

There is no 7‑segment font in the ROM. `TDO` drives the eight `O` outputs through
the **Output PLA** — a mask‑programmed lookup that converts the 5‑bit value
`SL:A` into an arbitrary 8‑bit pattern. So loading a hex digit `0`–`F` into `A`
and executing `TDO` emits that digit's segment pattern directly. The OPLA is why
a 4‑bit machine can show hex glyphs "for free": the decode is baked into the
silicon.

The extra `SL` (status‑latch) bit into `TDO` selects the **decimal point**. The
firmware sets it per digit to drive the status dots — the `CARRY`, `ZERO`, and
`1 Hz` indicators that appear on individual digits' decimal points (`0d:06`
derives them from mode bits before the loop).

## 7. The keypad and digital I/O

The keypad, the digital inputs, and the digital outputs all hang off the same
handful of I/O lines as the display and the SRAM. The organising idea is that the
**`K` input bus is shared**, and which device drives it is chosen by whichever
`R` output is currently strobed.

### 7.1 The keypad matrix scan (page 01)

The keys form a matrix: **columns** are driven by the strobe lines `R1`–`R5`
(the same lines that strobe display digits, used in a different phase), and
**rows** are read on the four `K` inputs. The scan (`01:0e`):

```
01:0e  TCY 5                 ; start at column R5
01:0f  SETR                  ; drive this column
01:10  KNEZ                  ; any key in this column down?  (K != 0)
01:11  BR 1a                 ;   yes -> handle it
01:12  RSTR / DYN / BR 0f    ;   no  -> next column (R4, R3, R2, R1)
```

On a hit it **saves the column** in `M(0,14)`, waits out a **debounce** delay and
re‑tests, then **reads the row bits** with `TKA` into `M(0,15)`, and finally
**waits for release**. The pressed key is identified by the (column, row) pair.
When the machine is halted, the decoded key is dispatched as a command/function
key by the ladder on page `1e` (`NEXT`, `RUN`, `PGM`, `CCE`, …).

### 7.2 The I/O opcodes (page 18)

| Op | Mnemonic | Handler | Behaviour |
| --- | --- | --- | --- |
| `FFd` | `KIN` | `18:00` | Wait for a keypress; return its code in `Rd` (from `M(0,15)`). |
| `FEd` | `DOT` | `18:10` | Drive `Rd` onto the four output lines `R7`–`R10`. |
| `FDd` | `DIN` | `18:20` | Read the four input lines into `Rd` (`SETR R6` / `TKA` / `RSTR R6`). |

`DIN` sets `R6` to route the external inputs onto `K`; the keypad scan uses a
column strobe instead; and the SRAM read (§5) uses `R11` (`KL`). Same `K` bus,
three sources, selected by which `R` line is high.

### 7.3 The I/O line map

Putting the display, SRAM, and keypad passes together, the TMS1600's outputs
carry these roles (time‑multiplexed where they overlap):

| Line(s) | Role |
| --- | --- |
| `R0`–`R5` | the six display digit strobes; `R1`–`R5` double as keypad column strobes |
| `R6` | gate that routes the external **DIN** inputs onto the `K` bus |
| `R7`–`R10` | the four **DOT** output lines (also carry SRAM write data) |
| `R11` | `KL` selector — routes the SRAM `L` data lines onto `K` (read) |
| `R12` | asserted during display refresh (display enable) |
| `R13` | SRAM **write‑enable** strobe |
| `K1`–`K4` | shared input bus: keypad rows, or DIN inputs, or SRAM read data |
| `O0`–`O7` | 7‑segment pattern (via the OPLA); also the SRAM address nibble (via `TDO`) |

## 8. The F‑operations

Opcode `F` is a whole family of operations, decoded in up to **three levels**:

1. **2nd digit** (`11:17`): routes to the shift/carry/I/O ops (`9`–`F`) or, for
   `0`–`8`, to page `12`.
2. **On page `12`**: 2nd digit `1`–`6` → `DISP`; `7` → `MAS`; `8` → `INV`;
   `0` → the `F0x` extended group on page `29`.
3. **On page `29`** (and, for `F00`–`F05`, `1e:00`): the **3rd digit** selects
   the specific extended operation.

Putting all three levels together gives the complete `F`‑op → handler map:

| Encoding | Mnemonic | Meaning | Handler |
| --- | --- | --- | --- |
| `F00` | `HALT` | stop the program | `1c:21` (the run‑check) |
| `F01` | `NOP` | do nothing | `1e:32` |
| `F02` | `DISOUT` | blank the display | `1e:34` |
| `F03` | `HXDZ` | hex → decimal | `1d:00` |
| `F04` | `DZHX` | decimal → hex | `1f:00` |
| `F05` | `RND` | random → `Rd` | `1e:12` |
| `F06` | `TIME` | read the clock | `12:18` |
| `F07` | `RET` | return from `CALL` | ch1 pg5 |
| `F08` | `CLEAR` | zero the registers | `2a:00` |
| `F09` | `STC` | set carry | `2a:0a` |
| `F0A` | `RSC` | reset carry | `2a:0e` |
| `F0B` | `MULT` | multiply | `2b:00` |
| `F0C` | `DIV` | divide | `2b:2b` |
| `F1d`–`F6d` | `DISP` | show digits on the display | `13:00` |
| `F7d` | `MAS` | display‑address set | `12:0a` |
| `F8d` | `INV` | invert `Rd` | `1b:1f` |
| `F9d` | `SHR` | shift `Rd` right | `1a:00` |
| `FAd` | `SHL` | shift `Rd` left | `1a:29` |
| `FBd` | `ADC` | `Rd += carry` | `19:0d` |
| `FCd` | `SUBC` | `Rd -= carry` | `19:00` |
| `FDd` | `DIN` | read inputs → `Rd` | `18:20` |
| `FEd` | `DOT` | `Rd` → outputs | `18:10` |
| `FFd` | `KIN` | read a key → `Rd` | `18:00` |

A few of these are worth a note:

- **`HALT` is not special.** It simply branches to the run‑check `1c:21`. Because
  the run flag is not set on that path, the interpreter drops into keypad/idle
  mode — the program stops "for free," with no dedicated stop machinery.
- **`STC`/`RSC`** just set/clear bit 0 of the flags cell `M(4,13)`; `ADC`/`SUBC`
  add/subtract that same carry bit through the ordinary ADD/SUB tails — this is
  how multi‑digit arithmetic is built up from the 4‑bit ALU.
- **`DISP`** copies the requested register digits into the six display cells that
  the refresh loop (§6) scans; the OPLA then turns each into segments.
- **`HXDZ`/`DZHX`** are the hex↔decimal converters. `HXDZ`'s overflow handling
  was a genuine Microtronic quirk (later emulators, e.g. the Busch‑2090 Neo, ship
  an explicit `HXDZ` overflow fix) — the ROM behaviour here is the authentic one.

### 8.1 What remains *(pending)*

The internal algorithms of the heavier `F0x` ops (`HXDZ`/`DZHX`, `MULT`, `DIV`,
`RND`, `TIME`) and the built‑in `PGM` programs (self‑test, cassette `PGM 1`/`2`,
clock, Nim) — up in chapters 2–3 — are the last items on the
[roadmap](../README.md#roadmap-and-status).

## 4. Display, keypad, SRAM, and the F‑operations *(pending)*

*Also on the roadmap:* the 7‑segment multiplexing and flag LEDs; the hex keypad
matrix scan and `KIN`; external 2114 SRAM read/write (the `L`/`O` data path via
the `KL` multiplexer); the arithmetic/logic opcodes and their carry‑is‑no‑borrow
semantics; and the built‑in `F` operations and `PGM` programs.
