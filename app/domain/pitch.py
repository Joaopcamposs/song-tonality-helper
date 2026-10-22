"""Extração da melodia e do chroma de um áudio: nota mais aguda e onde ela toca."""

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
from scipy.signal import medfilt

from app.domain.errors import NoMelodyError

BINS_PER_OCTAVE = 36  # 3 divisões por semitom na CQT
HOP = 512
SAMPLE_RATE = 22050
MIN_FRAMES = 100  # a nota mais aguda precisa aparecer em pelo menos ~2,3 s no total
RANKING_SIZE = 8
MAX_TIMES = 5
MIN_RUN_FRAMES = 10  # trechos menores que isso (~0,23 s) não contam como ocorrência
RUN_GAP_SECONDS = 1.0  # quadros separados por menos que isso formam o mesmo trecho


@dataclass(frozen=True)
class AudioFeatures:
    """Resultado da análise: topo da melodia, ranking de notas, tempos e chroma."""

    top_midi: int
    ranking: list[tuple[int, int]]
    top_times: list[float]
    chroma: np.ndarray


def _melody(y_harmonic: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Nota MIDI por quadro e a confiança dela, por soma harmônica sobre a CQT."""
    fmin = librosa.note_to_hz("C2")
    cqt = np.abs(
        librosa.cqt(
            y_harmonic,
            sr=SAMPLE_RATE,
            hop_length=HOP,
            fmin=fmin,
            n_bins=BINS_PER_OCTAVE * 6,
            bins_per_octave=BINS_PER_OCTAVE,
        )
    )
    cqt = librosa.util.normalize(cqt, axis=0, norm=np.inf)

    low = round(BINS_PER_OCTAVE * np.log2(librosa.note_to_hz("E3") / fmin))
    high = round(BINS_PER_OCTAVE * np.log2(librosa.note_to_hz("G5") / fmin))
    salience = np.zeros((high - low + 1, cqt.shape[1]))
    for k, b in enumerate(range(low, high + 1)):  # f0 mais os harmônicos 2 a 5
        for h, w in zip(range(1, 6), (1.0, 0.8, 0.6, 0.45, 0.3), strict=True):
            bb = b + round(BINS_PER_OCTAVE * np.log2(h))
            if bb < cqt.shape[0]:
                salience[k] += w * cqt[bb]

    midi = librosa.hz_to_midi(fmin * 2 ** ((salience.argmax(axis=0) + low) / BINS_PER_OCTAVE))
    return medfilt(midi, 9), salience.max(axis=0)


def _runs(frames: np.ndarray) -> list[float]:
    """Início (em segundos) de cada trecho contínuo de quadros, ignorando blips."""
    if frames.size == 0:
        return []
    gap = RUN_GAP_SECONDS * SAMPLE_RATE / HOP
    starts: list[float] = []
    begin = previous = int(frames[0])
    count = 1
    for frame in (int(f) for f in frames[1:]):
        if frame - previous > gap:
            if count >= MIN_RUN_FRAMES:
                starts.append(begin * HOP / SAMPLE_RATE)
            begin, count = frame, 0
        previous = frame
        count += 1
    if count >= MIN_RUN_FRAMES:
        starts.append(begin * HOP / SAMPLE_RATE)
    return starts


def analyze_audio(path: Path) -> AudioFeatures:
    """Analisa o arquivo e devolve a nota mais aguda sustentada, o ranking e o chroma."""
    y, _ = librosa.load(path, sr=SAMPLE_RATE, mono=True)
    y_harmonic, _ = librosa.effects.hpss(y, margin=3.0)  # mantém o harmônico, tira a percussão
    midi, confidence = _melody(y_harmonic)
    chroma = librosa.feature.chroma_cqt(y=y_harmonic, sr=SAMPLE_RATE, hop_length=HOP)

    strong = confidence > np.percentile(confidence, 60)
    rounded = np.round(midi).astype(int)
    notes, counts = np.unique(rounded[strong], return_counts=True)
    ranking = sorted(zip(notes.tolist(), counts.tolist(), strict=True), reverse=True)
    ranking = ranking[:RANKING_SIZE]

    top_midi = next((note for note, frames in ranking if frames >= MIN_FRAMES), None)
    if top_midi is None:
        raise NoMelodyError("Não encontrei uma melodia detectável neste áudio.")

    top_frames = np.flatnonzero(strong & (rounded == top_midi))
    times = [round(t, 1) for t in _runs(top_frames)[:MAX_TIMES]]
    return AudioFeatures(top_midi, ranking, times, chroma)
