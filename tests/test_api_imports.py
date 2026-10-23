import subprocess
import sys

HEAVY = ["librosa", "yt_dlp", "scipy", "soundfile"]


def test_api_does_not_import_audio_libs():
    # Interpretador limpo: a API sobe na nuvem sem o extra `worker` instalado.
    code = f"import sys, app.main; print([m for m in {HEAVY} if m in sys.modules])"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"
