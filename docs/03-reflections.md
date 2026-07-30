# Reflections: reverse engineering in the age of agentic AI

This repository is a small artifact with a large subtext. The technical content —
[doc 01](01-tms1600-architecture.md), [doc 02](02-how-the-microtronic-works.md),
and the [annotated listing](../annotated/) — explains a 1981 firmware ROM. This
document is about *how that explanation came to exist*, and what that says about
where reverse engineering is heading.

## What was lost

The Busch Microtronic's operating system lived in the mask ROM of a Texas
Instruments TMS1600 — 4,096 bytes fused into silicon in 1981 and never published.
For almost **45 years** it was, for all practical purposes, gone: unreadable
without physically coaxing it out of the chip, undocumented, and written for an
architecture (the TMS1000 family) that was already a museum piece. The manuals
described what the machine *did*; nothing described how it *worked*. The firmware
was a black box inside a black box.

## The human feat came first — and it is not reproducible by AI

The ROM was resurrected by **human ingenuity**. Getting the bytes out at all was
the hard, irreplaceable part: [Decle](https://forums.atariage.com/profile/46336-decle/),
[Jason T. Jacques](https://jsonj.co.uk/), and [Michael
Wessel](https://www.michael-wessel.info/) worked out how to put the TMS1600 into
an **undocumented test mode** and clock the ROM contents out over a serial line —
a hardware‑level reverse‑engineering achievement involving decapping‑adjacent
electrical trickery, trial and error, and genuine invention, with no manual to
follow. Jason then curated the raw dump, hand‑corrected the ambiguities, and
built a TMS1xxx emulator that could actually *run* the recovered ROM.

That work is **prior to, and outside of, anything an AI can do today.** A language
model cannot hold a soldering iron, cannot discover a physical test mode by
experiment, cannot build the breadboard. The dump — the act of turning fused
silicon back into bytes — remains a human, physical accomplishment. This
repository stands entirely on top of it.

## What the model did

What changed is the step *after* the dump: turning 4,096 recovered bytes into an
*understanding* that is written down in one place. Much of this ground had already
been charted — Jason T. Jacques' own long public write‑up of the ROM covers a good
deal of it — but it had never been assembled into a single, uniformly annotated map
from the reset vector to the last built‑in program. That map now exists, and it was
put together in about a day.

Given Decle's raw disassembly, the published TMS1000 manuals, Jason's TMS1600
emulator, and Jason's public description of the ROM, **Claude Opus 4.8 reconstructed
the firmware architecture in roughly half a day.** With those references in hand, it
traced — instruction by instruction:

- that the machine's whole instruction set is a **software virtual machine**
  hand‑written in TMS1600 microcode;
- the complete **RAM memory map** — which files hold the user registers, the
  program counter, the flags, the instruction buffer, a hidden extended register
  bank — none of it labelled;
- the **fetch/decode/execute cycle**, the two‑level opcode dispatch, and every
  one of the sixteen opcodes plus the entire `F`‑operation family down to their
  handler addresses;
- the **algorithms** the ROM uses to fake capabilities the 4‑bit chip lacks —
  hex/decimal conversion, multiply, divide, and a random generator, all built out
  of counting loops;
- and the fact that the built‑in demo is itself a **Microtronic program stored in
  the ROM as data** and loaded into RAM at runtime.

Along the way it settled questions that had never been written down anywhere:
where the carry and zero flags physically live, why `RND` touches three registers
instead of one, that the display carries no font table because the segment decode
is baked into the output PLA, that `HALT` is nothing more than a jump into the
run‑check. Small mysteries, decades old, resolved by reading the bytes.

Every claim was cross‑checked against Jason's emulator and the Busch‑2090 opcode
definitions, so the result is firmware‑accurate rather than plausible‑sounding.
And the sourcing should be stated plainly, without the lawyerly hedge: the model
did not work from zero. It had a raw disassembly, the TMS1000 manuals, an emulator
to validate against, and Jason's public write‑up — which it read, as it read the
manuals, and which already described much of this. What the model added was speed,
breadth, and a single consistently annotated synthesis of the whole ROM — plus a
handful of inferences Jason had not published (for instance, why `RND` touches
three registers, and the purpose of some periodic register updates). Those have since
been verified by running the ROM in the emulator: `RND` copies a free‑running counter
`M(5,d:e:f)` into `R13:R14:R15`, and that counter is the periodic update.

## Why this is not a job for Ghidra

The reflexive question is "couldn't a decompiler do this?" For this target, not
easily. [Ghidra](https://ghidra-sre.org/) and IDA are built around
register‑machine, von‑Neumann architectures. The TMS1000 family is almost
adversarial to that model:

- it is **4‑bit and Harvard** — program and data in separate spaces, no bytes,
  no stack pointer, no memory‑mapped anything;
- its **program counter is a linear‑feedback shift register**, so instructions
  execute in a pseudo‑random address order rather than sequentially;
- there is **no processor module for it** in mainstream tools — someone would
  first have to write a SLEIGH/processor spec from the datasheet before Ghidra
  could disassemble a single instruction, let alone decompile;
- and even then, the thing you would be decompiling is **microcode that
  implements an interpreter for another instruction set** — two levels of
  indirection that defeat naïve decompilation.

Doing this the traditional way — writing the processor support, then manually
walking a scrambled 4 KB ROM full of deferred page switches and shared‑tail
subroutines — would be **weeks to months** of specialist labour. The pattern
recognition that let a model see "this `ACxAC` ladder is a jump table," "these two
cells are the carry and zero flags," "this loop is a hex‑to‑decimal conversion by
counting" is exactly the kind of fuzzy, context‑dependent reasoning that frontier
models are now good at and that static tools are not.

## The implications cut both ways

The honest summary is that a capability which used to require a specialist and a
month of focused effort now takes an afternoon and a good prompt. That is a real
shift, and it points in two directions at once.

**For preservation, education, and defence, this is wonderful.** Dead
architectures can be documented before the last person who understands them is
gone. Retrocomputing, digital archaeology, and firmware curation get a force
multiplier. On the defensive side, a maintainer can now feasibly *audit* the
firmware in their own devices — understand what a black‑box blob actually does,
find the backdoor or the bug, before shipping.

**But the same lever moves the other way.** Firmware reverse engineering has long
been a bottleneck that quietly protected a lot of embedded systems: routers, cars,
medical devices, industrial controllers, IoT hardware. Much of their security was,
in practice, the security of *obscurity plus tedium* — attacking them meant
someone spending weeks understanding an undocumented binary for an odd chip. As
that tedium collapses, so does that incidental protection. The ability to map an
unfamiliar firmware image quickly and cheaply is dual‑use by nature: the same
skill that documents a 1981 educational computer can accelerate the discovery of
exploitable flaws in a 2026 embedded device, at a scale and speed that did not
exist before.

None of that is a reason not to do this work — it is a reason to do it in the
open, on things that deserve to be understood, and to be clear‑eyed that the
capability is now widely available. The Microtronic ROM is the benign, joyful end
of the spectrum: a beloved old machine, its designer's blessing to publish, and
nothing at stake but the pleasure of understanding. It is also a clean
demonstration of what the tooling can now do.

## The bottom line

A ROM was buried in silicon for four and a half decades. Human ingenuity dug it
out of the chip — and the people who did that, Jason above all, had already begun
mapping what it meant. What is new is the last step's speed: in an afternoon, a
frontier model read the recovered bytes and worked through them — instruction by
instruction, subsystem by subsystem — until the whole of the little computer's
operation was written down in one place. That last step would not have been
possible a few years ago.

Much of the Microtronic had already been charted by the people who pulled it out
of the chip. What's new is how quickly the rest fell.

---

*This repository's reverse engineering and documentation were produced by Claude
Opus 4.8 (Anthropic), working from the recovered ROM and Jason T. Jacques'
TMS1600 emulator, and directed by Michael A. Wessel. The ROM recovery itself is
the work of Decle, Jason T. Jacques, and Michael Wessel — see the
[credits](../README.md#provenance-credit-and-permissions).*
