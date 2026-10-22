"""Find a song's top melody notes and the key that puts them at your ceiling.

Usage: python top_note.py song.mp3 G [F4]
  G   = original key of the song
  F4  = your ceiling in standard numbering (C4 = middle C); F4 here = F3 on a C0 keyboard
"""

import sys
from collections import Counter

import librosa
import numpy as np
from scipy.signal import medfilt

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
BPO, HOP = 36, 512  # CQT bins per octave (3 per semitone), hop length


def melody_midi(path: str) -> tuple[np.ndarray, np.ndarray]:
    y, sr = librosa.load(path, sr=22050, mono=True)
    y_h, _ = librosa.effects.hpss(y, margin=3.0)  # keep harmonic content, drop drums
    fmin = librosa.note_to_hz("C2")
    cqt = np.abs(
        librosa.cqt(y_h, sr=sr, hop_length=HOP, fmin=fmin, n_bins=BPO * 6, bins_per_octave=BPO)
    )
    cqt = librosa.util.normalize(cqt, axis=0, norm=np.inf)

    lo = round(BPO * np.log2(librosa.note_to_hz("E3") / fmin))
    hi = round(BPO * np.log2(librosa.note_to_hz("G5") / fmin))
    salience = np.zeros((hi - lo + 1, cqt.shape[1]))
    for k, b in enumerate(range(lo, hi + 1)):  # harmonic summation: f0 + its overtones
        for h, w in zip(range(1, 6), (1.0, 0.8, 0.6, 0.45, 0.3)):
            bb = b + round(BPO * np.log2(h))
            if bb < cqt.shape[0]:
                salience[k] += w * cqt[bb]

    midi = librosa.hz_to_midi(fmin * 2 ** ((salience.argmax(axis=0) + lo) / BPO))
    return medfilt(midi, 9), salience.max(axis=0)


def main(path: str, original_key: str, ceiling: str = "F4") -> None:
    midi, conf = melody_midi(path)
    strong = midi[conf > np.percentile(conf, 60)]
    counts = Counter(librosa.midi_to_note(round(m)) for m in strong)

    print("High notes by frames detected (standard numbering):")
    ranked = sorted(counts, key=librosa.note_to_midi, reverse=True)[:8]
    for n in ranked:
        print(f"  {n:<4} {counts[n]}")

    # Top note = highest one detected in at least 100 frames (~2.3 s in total)
    top = next(n for n in ranked if counts[n] >= 100)
    shift = (librosa.note_to_midi(ceiling) - librosa.note_to_midi(top)) % 12
    shift = shift - 12 if shift >= 6 else shift
    new_key = NOTES[(NOTES.index(original_key) + shift) % 12]
    print(f"\nTop note: {top} | shift: {shift:+d} semitones | new key: {new_key}")


if __name__ == "__main__":
    main(*sys.argv[1:])
