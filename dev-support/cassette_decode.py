#!/usr/bin/env python3
"""
Decode a Busch Microtronic 2095 cassette recording (WAV) back into a program.

The 2095 tape format (as implemented in Ingo D. Rullhusen's mic2wav/wav2mic,
part of his Microtronic emulator, https://freeshell.de/~d01c/) is a square-wave
FSK:

    568 Hz  = data bit 0        (FREQ_0)
    1136 Hz = data bit 1         (FREQ_1)
    2272 Hz = leader / sync / end tone (FREQ_2)

    - ~10 s leader of 2272 Hz, then 256 program lines, then ~1 s of 2272 Hz.
    - each line = 3 hex digits = 3 nibbles, each nibble = 4 bits sent LSB-first
      (0x1, 0x2, 0x4, 0x8); bit time 63 ms (~16 baud), first bit of a line 47 ms.
    - line 0 follows the leader directly; lines 1..255 are each preceded by a
      sync of 30 ms @568 Hz + 170 ms @2272 Hz.

`wav2mic` decodes clean recordings by counting pulse edges. This tool instead
uses a Goertzel (matched-filter) demodulator and re-syncs on every 2272 Hz
marker, which is far more tolerant of noisy / lossy-compressed / tape-flutter
captures (e.g. audio lifted from a video) where edge counting fails. Validated
byte-for-byte against mic2wav output; recovers real off-air recordings by
combining redundant SAVE and LOAD passes.

    python3 cassette_decode.py recording.wav        # print decoded program lines

Confirms the format that the firmware's cassette handlers use - SAVE on ROM page
38, LOAD on ROM page 23 (see the annotated listing). Pairs with microtronic_emu.py.
"""
import sys, wave
import numpy as np

FREQ = {'0': 568.0, '1': 1136.0, 'S': 2272.0}   # bit0, bit1, leader/sync
T_BIT, T_BIT_F = 0.063, 0.047                    # bit time; first bit of a line
BIT_BOUNDS = [0.0, T_BIT_F] + [T_BIT_F + T_BIT * i for i in range(1, 12)]  # 12 bit edges


def load_wav(path):
    w = wave.open(path, 'rb')
    sr, sw, n = w.getframerate(), w.getsampwidth(), w.getnframes()
    raw = w.readframes(n); w.close()
    if sw == 1:      x = np.frombuffer(raw, np.uint8).astype(float) - 128.0
    elif sw == 2:    x = np.frombuffer(raw, np.int16).astype(float)
    else:            raise ValueError("need 8- or 16-bit PCM WAV")
    if w.getnchannels() > 1:
        x = x.reshape(-1, w.getnchannels()).mean(1)
    return x, sr


def _goertzel(x, f, sr, ms):
    n = np.arange(len(x))
    d = x * np.exp(-2j * np.pi * f * n / sr)
    k = max(2, int(ms / 1000 * sr))
    return np.abs(np.convolve(d, np.ones(k) / k, 'same'))


def decode(sig, sr, max_lines=256):
    E0 = _goertzel(sig, FREQ['0'], sr, 5)
    E1 = _goertzel(sig, FREQ['1'], sr, 4)
    ES = _goertzel(sig, FREQ['S'], sr, 3)
    dur = len(sig) / sr

    # run-length map of "is this instant the 2272 Hz tone?" on a 1 ms grid
    g = np.arange(0, dur, 0.001)
    ji = (g * sr).astype(int)
    is_s = (ES[ji] > E0[ji]) & (ES[ji] > E1[ji])
    runs = []
    cur, st = is_s[0], 0
    for i in range(1, len(is_s)):
        if is_s[i] != cur:
            runs.append((cur, g[st], g[i] - g[st])); cur, st = is_s[i], i
    runs.append((cur, g[st], g[-1] - g[st]))
    tone_runs = [r for r in runs if r[0]]
    if not tone_runs:
        return []
    leader = max(tone_runs, key=lambda r: r[2])   # longest 2272 run = leader
    pos = leader[1] + leader[2]

    def bit(a, b):                                # integrate over middle 60% of a bit
        m = (b - a) * 0.2
        i0, i1 = int((a + m) * sr), int((b - m) * sr)
        return 1 if E1[i0:i1].sum() > E0[i0:i1].sum() else 0

    lines = []
    for _ in range(max_lines):
        if pos + BIT_BOUNDS[-1] > dur:
            break
        bits = [bit(pos + BIT_BOUNDS[i], pos + BIT_BOUNDS[i + 1]) for i in range(12)]
        nibs = ''.join('%X' % sum(bits[k * 4 + b] << b for b in range(4)) for k in range(3))
        lines.append(nibs)
        after = pos + BIT_BOUNDS[-1]              # advance past the 12 bits ...
        nxt = [r for r in tone_runs if r[1] > after and r[2] > 0.09]  # ... to next sync
        if not nxt:
            break
        pos = nxt[0][1] + nxt[0][2]
    return lines


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("usage: cassette_decode.py <recording.wav>"); sys.exit(1)
    sig, sr = load_wav(sys.argv[1])
    prog = decode(sig, sr)
    # trim trailing all-zero padding for display
    while prog and prog[-1] == '000':
        prog.pop()
    print("sample rate %d Hz, %.1f s, %d program line(s):" % (sr, len(sig) / sr, len(prog)))
    for i, ln in enumerate(prog):
        print("  %02X: %s" % (i, ln))
