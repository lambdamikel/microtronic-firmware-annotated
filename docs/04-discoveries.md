# Discoveries: the cleverest, strangest, and most tedious things in the ROM

Mapping a firmware end to end leaves you with favourites — the tricks that made
you grin, the things that defied expectation, and the parts that were just a
slog. Here are the ones that stuck, from four decades of a designer's cleverness
packed into 4 KB.

## Credit and provenance

Several of these were mapped first by Jason T. Jacques in his own
[disassembly write-up](https://jsonj.co.uk/project/microtronic/), and this list
stands on that work. To keep the record honest:

- **Documented by Jason (and in several cases identified by him first):** the
  bit‑inverted SRAM storage; the excessively long RAM read delay *and* its fixes
  (a two‑instruction `CPAIZ`+`DAN`, or a non‑inverting buffer); the LFSR program
  counter; the shared K/L input bus; the OPLA hex→segment decode; the empty‑stack
  `RETN` being a no‑op; and the embedded **Nim** program, which he disassembled in
  full ("69 12‑bit words").
- **New in this pass:** `HALT` as a bare branch into the run‑check; `BRC`/`BRZ`
  falling through into `GOTO`; the boot sequence chaining subroutines via
  fall‑through (built on Jason's empty‑stack rule); the `ACxAC`
  add‑constant/test‑carry dispatch ladder; register/immediate opcodes sharing a
  handler; the "all the hard maths is counting" structure; `RND`'s entropy from the
  free‑running idle counter; `RND` writing three registers; and the hidden extended
  register bank (RAM file 6).
- **Candidates still to verify:** exactly why `RND` fills three registers, and the
  purpose of the periodic register updates — the latter most likely tied to the
  software timekeeping behind the Show/Set‑Time built‑ins (see the roadmap at the
  end).

## The genuinely clever

**The display has no font.** A hex digit `0`–`F` is turned into a seven‑segment
pattern by a single instruction, `TDO`, which pushes the accumulator through the
chip's **Output PLA** — a mask‑programmed lookup wired into the silicon. There is
no segment table anywhere in the ROM, because the "table" *is* the chip. A 4‑bit
machine displays hex glyphs for free. When I went looking for the font and found
that it simply doesn't exist, that was the first real "oh, that's lovely" moment.

**`HALT` is not a feature.** You would expect a "stop the program" opcode to have
some machinery behind it. It has none. `F00` (`HALT`) just branches to the same
run‑check the interpreter reaches every cycle (`1c:21`) — and because the
"execute this instruction" flag isn't set on that path, the machine quietly drops
into idle. Stopping is the *absence* of running. It costs zero extra code.

**`BRC`/`BRZ` borrow the `GOTO` handler.** A conditional branch, when taken, is
identical to an unconditional jump to the same address — so the firmware doesn't
duplicate the logic. `BRC`/`BRZ` test their flag and, if it's set, simply **fall
straight into the body of `GOTO`** (`14:00`). Two opcodes for the price of one and
a little.

**Subroutines that fall through their own `RETN`.** At boot, the very first thing
that runs is the "clear all outputs" subroutine — but it's reached by falling into
it, not calling it. Its terminating `RETN`, hit with an empty call stack, does
nothing — a behaviour Jason documents ("if our call stack is empty then this
instruction is a no-op") — and lets execution continue into the *next* subroutine.
So one block of code serves as both a callable routine and an inline boot step, and
the boot sequence is a chain of these fall‑throughs. (The empty‑stack rule is
Jason's; what's noted here is the boot path *using* it to sequence the init steps.)
Ruthlessly economical.

**Dispatch by "add a constant and check for carry."** Every jump table in the ROM
— the 16‑way opcode decode, the F‑group, the F0x group — avoids a tree of bit
tests. Instead it reloads the value and runs it through `ACxAC n` ("A = A + n +
1"), choosing `n` so that *exactly one* input value overflows and sets carry. A
ladder of these peels off `F`, then `E`, then `D`… one comparison each. It's a
genuinely elegant use of the ALU's carry flag as a decoder, and once you see it in
one place you see it everywhere.

**Register and immediate opcodes are the same opcode with a different front
door.** `ADD`/`ADDI`, `SUB`/`SUBI`, `AND`/`ANDI`, `CMP`/`CMPI` each **share a
handler page**, and the reg/immediate versions differ only in how they *fetch* the
operand — after that they merge into one common compute‑and‑write‑back tail. Even
numbers are register forms, odd numbers immediate. The whole arithmetic unit is
built around not writing anything twice.

**All the "hard" maths is just counting.** The TMS1600 has no multiplier and no
divider, so the ROM fakes them. `HXDZ` converts hex to decimal by counting the hex
value *down* to zero while counting a BCD result *up*. `MULT` multiplies by
repeated decimal addition; `DIV` divides by repeated subtraction. It is slow —
`HXDZ` of a big value is hundreds of iterations — but a 4‑bit chip with counting
loops can, given enough patience, do arithmetic it has no hardware for. There's
something wonderfully honest about it.

**Randomness out of thin air.** `RND` has no RNG hardware to call on, so it reads a
counter that free‑runs continuously through the display/keypad idle loop. By the
time your program executes `RND`, that counter's value depends on exactly *when*
you pressed the key — human reaction time as an entropy source. Cheap, and good
enough to make a dice game feel fair.

**The built‑in demo is a Microtronic program hiding in the ROM.** The single most
satisfying discovery. `PGM 7` — the Nim game — isn't native code at all; it's a
*Microtronic* program, stored in the firmware ROM as data (three constants per
instruction, pages `3a`–`3f`), loaded into RAM when you select it and then run by
the very interpreter the rest of the firmware implements. The machine ships an
application written in its own invented language. (Its source is printed in the
Busch manual and disassembled in Jason's write‑up; an independent decode of the
ROM bytes here matches.) The abstraction eats its own tail, on purpose.

**Squeezing three jobs out of one bus.** The chip has four input lines. They serve
as keypad rows, *and* the external digital inputs, *and* the SRAM data bus —
chosen by which output strobe happens to be high at that instant. The six display
digit‑strobes double as the five keypad column‑strobes. Nothing in this design has
exactly one job; the whole thing is a careful time‑sharing dance across a handful
of pins.

## The surprises

**The program counter doesn't count.** It's a linear‑feedback shift register, so
instructions are physically scattered across each 64‑word page in pseudo‑random
order. This is a real hardware economy (an LFSR is cheaper than a binary counter),
but it means the ROM you read is nothing like the ROM as stored — consecutive
logical instructions live at wildly non‑consecutive addresses. Every branch target
had to be run back through the LFSR to be understood.

**`RND` writes *three* registers, not one.** I expected `RND` to drop a random
nibble into one register. Instead it fills `R13`, `R14`, `R15` — three of them.
That surprised me in the disassembly (why copy three values?) until the emulator's
documented behaviour confirmed it. The converters `HXDZ`/`DZHX` use the same three
registers as their working number.

**There's a second, hidden register bank.** `MULT` and `DIV` need two operands, but
there are only sixteen visible registers. The second operand lives in an
*extended* register file — a whole separate bank of sixteen shadow registers
(RAM file 6) that no ordinary opcode touches. It doesn't appear in the manual's
register model at all; you only find it by watching `MULT` reach for it.

**The user's memory fits the chip exactly.** External program RAM is a 2114:
1024 nibbles. The interpreter stores each instruction in a four‑nibble slot
(three used, one wasted). 256 slots × 4 nibbles = 1024 — precisely the whole chip.
The "wasted" fourth nibble is what makes the addressing arithmetic trivial. The
fit is too clean to be an accident.

**Stored data is inverted.** Every nibble read from the SRAM is bit‑complemented on
the way in (and correspondingly on the way out). A tiny hardware‑level detail that
would silently corrupt everything if you missed it — an easy trap, quietly handled
by one shared helper routine.

**The interpreter isn't in one place.** I initially labelled one routine as "the
main loop." It turned out to be the `OR` opcode handler. The actual interpreter is
smeared across half a dozen pages in two different ROM chapters, stitched together
by deferred page switches. There is no tidy `while(true)` to point at — a good
reminder that these machines were laid out for the silicon's convenience, not the
reader's. (That mislabel is fixed in the annotations; I left this note as an honest
account of the trace.)

## The tedious — for them, and for me

**Deferred paging, everywhere.** A branch can only reach within its own 64‑word
page. To go anywhere else you load a page buffer (`LDP`), maybe a chapter buffer
(`TPC`), *then* branch — and the load takes effect one instruction later than you'd
think. The whole ROM is a patchwork of pages sewn together by these
load‑then‑jump pairs. For the 1981 authors this must have been relentless
bookkeeping; for a 2026 reverse‑engineer, the single most error‑prone part of the
trace was keeping track of which chapter and page a given `CALL` would actually
land in.

**Shared tails and bare `RETN`s.** Many opcode handlers don't end by returning to
an obvious caller — they `RETN` into a common post‑execute continuation several
pages away. Following the control flow means holding the whole call graph in your
head at once, because the "return" often isn't a return to anywhere nearby.

**Three levels of dispatch to reach one F‑op.** Getting from "opcode `F`" to, say,
`HXDZ` means: decode the command digit (level 1), discover it's an `F0x` extended
op (level 2), then decode the third digit across *two* more pages (level 3). Each
level is the same `ACxAC` ladder. Elegant in isolation, a maze in aggregate.

## The overall impression

What comes through, after all of it, is **craftsmanship under constraint — with
rough edges.** Four kilobytes, a 4‑bit ALU, a handful of I/O pins, no multiplier,
no stack to speak of, a program counter that scrambles its own addresses — and out
of that, a friendly little computer with sixteen registers, a hex keypad, a
six‑digit display, arithmetic, subroutines, a cassette interface, and a built‑in
game. The instruction‑set design — a whole virtual machine in that space — is the
genuinely clever part.

The plumbing beneath it is rougher, and it is worth being honest about. As Jason
T. Jacques' timing analysis shows, the SRAM read delay is orders of magnitude
longer than the 2114 chips need — nearly half the machine's running time is spent
waiting on memory that could answer far sooner. And the data inversion on every
read is done bit‑by‑bit, where the TMS's complement instruction (two's‑complement,
then subtract one — two instructions) would have done it, or a non‑inverting buffer
would have removed the need entirely. Elegant design, over‑built access path: the
hardware and firmware engineers were clearly still learning as they went. It was a
privilege to take apart either way.

## Known gaps and roadmap

This pass mapped the interpreter and the major subsystems, but the annotation is
uneven — more than half the ROM's pages currently carry only a mechanical,
per‑instruction decode. Some of that is genuine `0x00` padding that needs nothing;
some is real substance still to be traced. The main pieces of unfinished work:

- **The seven native `PGM` functions.** The `PGM` key invokes native TMS1600
  routines. Per the Busch manual: **0** Self‑Test, **1** Load (cassette→RAM),
  **2** Save (RAM→cassette), **3** Set time of day, **4** Show time of day,
  **5** Clear RAM (delete programs), **6** Load‑NOP (write `NOP` to every program
  address). Confirmed anchors so far: the software **clock** that Set/Show‑Time
  (3/4) read sits behind the `TIME` handler at `12:18` (Jason's "adjacent
  timekeeping"); Clear‑RAM (5) reuses the `clear RAM file X` subroutine at `00:05`;
  Load and Load‑NOP (1/6) drive the SRAM writer at `0c:02`; Load/Save (1/2) add the
  cassette FSK timing. Documenting each as its own section is the next focused
  effort. (PicoRAM re‑implements Load/Save as SD‑card operations, in its own
  firmware — not the mask ROM.)
- **PGM 7 — the Nim game.** The eighth `PGM`, and the *only* built‑in stored as
  **Microtronic** code rather than native TMS: its bytecode lives in `3a–3f` (three
  `TCMIY` constants per instruction — stored low‑nibble‑first — `CALL`'d into SRAM
  by the loader at `3a:00`, then run by the interpreter). Identified by Decle/Jason,
  who published a full disassembly; an independent decode here confirms the
  structure (~66–69 instructions, every branch target in range). A clean in‑repo
  listing, reconciled against Jason's, is the small remaining task.
- **~25 pages of native routines** — cassette FSK timing, operand data paths,
  display and arithmetic helpers — that have a per‑instruction gloss but no
  high‑level note. Several bear more than mechanical decode.

None of this is hidden; it is simply the part of a 4 KB ROM that a first end‑to‑end
pass reaches last. It is flagged here so the map's edges are honest.
