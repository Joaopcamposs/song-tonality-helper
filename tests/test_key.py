from app.domain.key import detect_key


def _chroma_for(weights: dict[int, float]) -> list[float]:
    profile = [0.05] * 12
    for pc, weight in weights.items():
        profile[pc] = weight
    return profile


def test_detects_g_major():
    # Escala de G maior com ênfase em G, B e D (tônica, terça e quinta).
    chroma = _chroma_for({7: 1.0, 11: 0.8, 2: 0.9, 9: 0.4, 0: 0.5, 4: 0.5, 6: 0.3})
    best = detect_key(chroma)[0]
    assert (best.tonic_pc, best.mode) == (7, "maior")


def test_returns_three_candidates():
    chroma = _chroma_for({0: 1.0, 4: 0.8, 7: 0.9})
    assert len(detect_key(chroma)) == 3
