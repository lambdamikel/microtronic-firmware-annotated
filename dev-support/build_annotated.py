#!/usr/bin/env python3
"""Build the annotated Microtronic firmware listing.

Merges human-written annotations into the canonical (unmodified) Decle/Jason
disassembly, producing annotated/microtronic-annotated.txt. Every instruction
that has no hand-written annotation gets a literal decode from dev-support/gloss.py
(the mechanical "what it does"), so the listing is fully commented.

Inputs
------
  rom/microtronic-firmware-disassembled.txt   canonical disassembly (never edited)
  annotated/annotations.tsv                    <addr> \t <comment>   per-line "why" comments
  annotated/banners.tsv                        <addr> \t <text>      section banner before a line

`addr` is the LOGICAL address as printed after the '#', e.g. "0f:00".
Run from the repo root:  python3 dev-support/build_annotated.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gloss import gloss  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "rom", "microtronic-firmware-disassembled.txt")
ANN = os.path.join(ROOT, "annotated", "annotations.tsv")
BAN = os.path.join(ROOT, "annotated", "banners.tsv")
OUT = os.path.join(ROOT, "annotated", "microtronic-annotated.txt")

# Captures the whole line-head (up to the trailing '-') plus mnemonic/operand/hex.
LINE_RE = re.compile(
    r"^(?P<head>\s+(?P<mnem>[A-Za-z][A-Za-z0-9]*)(?:\s+(?P<op>[0-9a-fx]+))?\s+#\s+"
    r"(?P<addr>[0-9a-f]{2}:[0-9a-f]{2})\s+\([0-9a-f]{2}:[0-9a-f]{2}\)\s+"
    r"(?P<hex>[0-9a-f]{2})\s+-)(?P<rest>.*)$"
)


def load_tsv(path):
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if "\t" not in line:
                sys.exit(f"{path}: no TAB in line: {line!r}")
            addr, val = line.split("\t", 1)
            out[addr.strip()] = val.strip()
    return out


def main():
    comments = load_tsv(ANN)
    banners = load_tsv(BAN)

    n_body = n_hand = n_gloss = 0
    out_lines = []
    with open(SRC, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            m = LINE_RE.match(line)
            if not m:
                out_lines.append(line)
                continue
            n_body += 1
            addr = m.group("addr")
            if addr in banners:
                for seg in banners[addr].split("\\n"):
                    out_lines.append(f"    # === {seg} ===")
            if addr in comments:
                n_hand += 1
                comment = comments[addr]
            else:
                comment = gloss(m.group("mnem"), m.group("op") or "", m.group("hex"))
                if comment:
                    n_gloss += 1
            if comment:
                out_lines.append(f"{m.group('head')}  {comment}")
            else:
                out_lines.append(line)

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out_lines) + "\n")

    total = n_hand + n_gloss
    print(f"wrote {OUT}")
    print(f"  hand-written annotations : {n_hand}/{n_body} ({100.0*n_hand/n_body:.1f}%)")
    print(f"  + literal gloss fallback : {n_gloss}")
    print(f"  = commented lines        : {total}/{n_body} ({100.0*total/n_body:.1f}%)")


if __name__ == "__main__":
    main()
