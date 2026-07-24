#!/usr/bin/env python3
"""Build the annotated Microtronic firmware listing.

Merges human-written annotations into the canonical (unmodified) Decle/Jason
disassembly, producing annotated/microtronic-annotated.txt.

Inputs
------
  rom/microtronic-firmware-disassembled.txt   canonical disassembly (never edited)
  annotated/annotations.tsv                    <addr> \t <comment>   per-line comments
  annotated/banners.tsv                        <addr> \t <text>      section banner before a line

`addr` is the LOGICAL address as printed after the '#', e.g. "0f:00".
Blank lines and lines beginning with '#' in the .tsv files are ignored.
A banner line's text may contain '\\n' to force multiple banner lines.

Run from the repo root:  python3 dev-support/build_annotated.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "rom", "microtronic-firmware-disassembled.txt")
ANN = os.path.join(ROOT, "annotated", "annotations.tsv")
BAN = os.path.join(ROOT, "annotated", "banners.tsv")
OUT = os.path.join(ROOT, "annotated", "microtronic-annotated.txt")

# A disassembly body line looks like:
#     LDX    1        # 00:0c (00:1e) 2c  -  <optional existing comment>
LINE_RE = re.compile(
    r"^(?P<code>\s+\S.*?#\s+)"
    r"(?P<addr>[0-9a-f]{2}:[0-9a-f]{2})"
    r"(?P<mid>\s+\([0-9a-f]{2}:[0-9a-f]{2}\)\s+[0-9a-f]{2}\s+-)"
    r"(?P<rest>.*)$"
)


def load_tsv(path):
    """addr -> value (last one wins), ignoring blanks and #-comments."""
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

    n_body = n_annotated = 0
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
                n_annotated += 1
                out_lines.append(f"{m.group('code')}{addr}{m.group('mid')}  {comments[addr]}")
            else:
                out_lines.append(line)

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out_lines) + "\n")

    pct = (100.0 * n_annotated / n_body) if n_body else 0.0
    print(f"wrote {OUT}")
    print(f"annotated {n_annotated}/{n_body} instruction lines ({pct:.1f}%)")


if __name__ == "__main__":
    main()
