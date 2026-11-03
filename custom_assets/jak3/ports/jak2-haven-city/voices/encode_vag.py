#!/usr/bin/env python3
"""
Encode audio files into PS2 voice lines (.vag: the "VAGp" header and PS-ADPCM data), the format
goalc's pack-vags tool packs into the mod's voice wads (VAGDIRM.AYB, VAGWADM.<language>).

    python encode_vag.py <in.mp3|wav...> --out <dir>     # writes <dir>/<NAME>.vag per input
    python encode_vag.py --check                         # encodes a test tone, decodes it back

The inputs are decoded by ffmpeg (on PATH) to mono 22050 Hz, normalized to -15 dBFS RMS (the
level of Jak 2's and Jak 3's lines), then encoded: every 28 samples, the PS-ADPCM filter and shift
with the least error, predicted from the decoded samples as the SPU decodes them. A line's name
is its file name without extension, upper case, at most 8 characters.

Used for the Torn speaker lines of Haven City: New Dawn (the user's recordings,
TORN_SPEAKER2.mp3 ... TORN_SPEAKER5.mp3 -> TORN2.vag ... TORN5.vag, committed next to this
script: the launcher's install has no ffmpeg).
"""
from __future__ import annotations

import argparse
import math
import struct
import subprocess
import sys
from pathlib import Path

RATE = 22050
TARGET_RMS_DB = -15.0
# PS-ADPCM prediction filters (coefficients / 64)
FILTERS = [(0, 0), (60, 0), (115, -52), (98, -55), (122, -60)]


def decode_with_ffmpeg(path: Path) -> list[int]:
    """The file as mono 16-bit samples at RATE, through ffmpeg."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(RATE),
                          "-f", "s16le", "-"], check=True, capture_output=True).stdout
    return list(struct.unpack(f"<{len(raw) // 2}h", raw))


def normalize(samples: list[int]) -> list[int]:
    """Scale the samples to TARGET_RMS_DB RMS, clipped to 16 bits."""
    rms = math.sqrt(sum(s * s for s in samples) / max(1, len(samples))) or 1.0
    gain = 32767.0 * 10 ** (TARGET_RMS_DB / 20) / rms
    return [max(-32768, min(32767, round(s * gain))) for s in samples]


def clamp16(v: int) -> int:
    return max(-32768, min(32767, v))


def decode_sample(nibble: int, shift: int, f: tuple[int, int], s1: int, s2: int) -> int:
    """The SPU's decoding of one nibble (signed 4 bits) with this shift and filter."""
    v = ((nibble << 12) & 0xFFFF)
    if v & 0x8000:
        v -= 0x10000
    v >>= shift
    return clamp16(v + ((s1 * f[0] + s2 * f[1] + 32) >> 6))


def encode_block(block: list[int], s1: int, s2: int):
    """The best (filter, shift, nibbles, s1, s2) for 28 samples after history s1, s2."""
    best = None
    for fi, f in enumerate(FILTERS):
        # the shift the residual needs, from the residual against the source history
        p1, p2, peak = s1, s2, 0
        for s in block:
            peak = max(peak, abs(s - ((p1 * f[0] + p2 * f[1] + 32) >> 6)))
            p1, p2 = s, p1
        bits = 0
        while (7 << bits) < peak and bits < 12:
            bits += 1
        for shift in {12 - bits, max(0, 12 - bits - 1)}:
            h1, h2, err, nibbles = s1, s2, 0, []
            for s in block:
                pred = (h1 * f[0] + h2 * f[1] + 32) >> 6
                n = max(-8, min(7, round((s - pred) * (1 << shift) / 4096)))
                d = decode_sample(n, shift, f, h1, h2)
                err += (s - d) ** 2
                nibbles.append(n & 0xF)
                h1, h2 = d, h1
            if best is None or err < best[0]:
                best = (err, fi, shift, nibbles, h1, h2)
    return best[1:]


def encode(samples: list[int]) -> bytes:
    """PS-ADPCM frames (16 bytes per 28 samples), after one silent frame."""
    out = bytearray(16)
    samples = samples + [0] * (-len(samples) % 28)
    s1 = s2 = 0
    for i in range(0, len(samples), 28):
        fi, shift, nibbles, s1, s2 = encode_block(samples[i:i + 28], s1, s2)
        out += bytes([(fi << 4) | shift, 0])
        out += bytes(nibbles[k] | (nibbles[k + 1] << 4) for k in range(0, 28, 2))
    return bytes(out)


def decode(data: bytes) -> list[int]:
    """PS-ADPCM frames back to samples (the check)."""
    s1 = s2 = 0
    out = []
    for i in range(0, len(data), 16):
        fi, shift = data[i] >> 4, data[i] & 0xF
        for b in data[i + 2:i + 16]:
            for n in (b & 0xF, b >> 4):
                n = n - 16 if n & 8 else n
                d = decode_sample(n, shift, FILTERS[fi], s1, s2)
                out.append(d)
                s1, s2 = d, s1
    return out


def vag_file(name: str, data: bytes) -> bytes:
    """A .vag: the big-endian "VAGp" header (version 0x20, data size, sample rate, name), the data."""
    header = b"VAGp" + struct.pack(">III", 0x20, 0, len(data)) + struct.pack(">I", RATE)
    header += b"\0" * 12 + name.encode("ascii")[:16].ljust(16, b"\0")
    return header + data


def check() -> None:
    """Encode a 440 Hz tone with a fade and decode it back: the error must stay small."""
    tone = [round(12000 * math.sin(2 * math.pi * 440 * t / RATE) * min(1.0, t / 2000)) for t in range(RATE)]
    back = decode(encode(tone))[28:28 + len(tone)]
    noise = sum((a - b) ** 2 for a, b in zip(tone, back))
    snr = 10 * math.log10(sum(a * a for a in tone) / max(1, noise))
    print(f"tone: {len(tone)} samples, SNR {snr:.1f} dB")
    assert snr > 20, "PS-ADPCM round trip too noisy"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="*", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        check()
        return 0
    for path in args.inputs:
        name = path.stem.upper()[:8]
        samples = normalize(decode_with_ffmpeg(path))
        data = encode(samples)
        back = decode(data)[28:28 + len(samples)]
        noise = sum((a - b) ** 2 for a, b in zip(samples, back))
        snr = 10 * math.log10(sum(a * a for a in samples) / max(1, noise))
        (args.out / f"{name}.vag").write_bytes(vag_file(name, data))
        print(f"{path.name} -> {name}.vag: {len(samples) / RATE:.2f} s, {len(data)} bytes, SNR {snr:.1f} dB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
