"""Literal per-instruction decode for the TMS1600.

Given a mnemonic + operand (as the disassembler prints them), return a short,
always-correct description of *what the instruction does* — derived purely from
the TMS1600 instruction semantics (matching Jason's emulator). This is the
mechanical "what"; the hand-written annotations in annotations.tsv are the
semantic "why" and always take precedence over these glosses.

X = file-select register, Y = word index, A = accumulator, K = inputs,
R[] = latched outputs, M(X,Y) = the addressed RAM nibble, status = the S flag
that the next BR/CALL tests.
"""

_FIXED = {
    "TMA": "A = M(X,Y)",
    "TAM": "M(X,Y) = A",
    "TMY": "Y = M(X,Y)",
    "TYA": "A = Y",
    "TAY": "Y = A",
    "XMA": "swap A and M(X,Y)",
    "TKA": "A = K inputs",
    "TDO": "drive the O outputs = OPLA(A)",
    "CLA": "A = 0",
    "COMX": "complement X (select the other RAM file)",
    "TPC": "chapter-buffer = page-buffer (arm the next branch/call's chapter)",
    "SETR": "set output line R[Y]",
    "RSTR": "clear output line R[Y]",
    "RETN": "return from CALL (pop the saved address)",
    "IYC": "Y = Y + 1 (status = carry)",
    "DYN": "Y = Y - 1 (status = no borrow)",
    "IMAC": "A = M(X,Y) + 1 (status = carry)",
    "DMAN": "A = M(X,Y) - 1 (status = no borrow)",
    "AMAAC": "A = A + M(X,Y) (status = carry)",
    "SAMAN": "A = M(X,Y) - A (status = no borrow)",
    "CPAIZ": "A = -A (two's complement; status if A was 0)",
    "TAMIYC": "M(X,Y) = A; Y = Y + 1 (status = carry)",
    "TAMDYN": "M(X,Y) = A; Y = Y - 1 (status = no borrow)",
    "TAMZA": "M(X,Y) = A; A = 0",
    "MNEA": "status = (M(X,Y) != A)",
    "MNEZ": "status = (M(X,Y) != 0)",
    "YNEA": "status = (Y != A)",
    "ALEM": "status = (A <= M(X,Y))",
    "KNEZ": "status = (K inputs != 0)",
}


def gloss(mnem, operand, hexb):
    """Return a literal decode string (or '' if the mnemonic is unknown)."""
    if mnem == "MNEA" and hexb == "00":
        return "(unused — 0x00 fill)"
    if mnem in _FIXED:
        return _FIXED[mnem]
    o = operand
    if mnem == "TCY":
        return f"Y = {o}"
    if mnem == "LDX":
        return f"X = {o} (select RAM file {o})"
    if mnem == "LDP":
        return f"page-buffer = {o} (arm the next branch/call to page {o})"
    if mnem == "TCMIY":
        return f"M(X,Y) = {o}; Y = Y + 1"
    if mnem == "SBIT":
        return f"set bit {o} of M(X,Y)"
    if mnem == "RBIT":
        return f"clear bit {o} of M(X,Y)"
    if mnem in ("TBIT", "TBIT1"):
        return f"status = bit {o} of M(X,Y)"
    if mnem == "YNEC":
        return f"status = (Y != {o})"
    if mnem == "ALEC":
        return f"status = (A <= {o})"
    if mnem in ("ACxAC", "AC1AC", "AC"):
        return f"A = A + {o} + 1 (status = carry)"
    if mnem == "BR":
        return f"if status: branch to {o}"
    if mnem == "CALL":
        return f"if status: call {o}"
    return ""
