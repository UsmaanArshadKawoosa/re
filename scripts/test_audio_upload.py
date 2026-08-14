from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import time
import uuid
import wave
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def make_sine_wav(path: Path, duration_s=0.5, rate=16000):
    # Create a short silent WAV file for upload
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"\x00\x00" * int(rate * duration_s)
        w.writeframes(frames)


def main():
    process = subprocess.Popen(
        [sys.executable, str(ROOT / 'app' / 'main.py')],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, 'PORT': '8020'},
    )
    try:
        time.sleep(1)
        wav_path = ROOT / 'tmp_test_audio.wav'
        make_sine_wav(wav_path)

        boundary = '----WebKitFormBoundary' + uuid.uuid4().hex
        data_parts = []
        # name
        data_parts.append(f'--{boundary}')
        data_parts.append('Content-Disposition: form-data; name="name"')
        data_parts.append('')
        data_parts.append('Test User')
        # phone
        data_parts.append(f'--{boundary}')
        data_parts.append('Content-Disposition: form-data; name="phone"')
        data_parts.append('')
        data_parts.append('+911234567890')
        # city
        data_parts.append(f'--{boundary}')
        data_parts.append('Content-Disposition: form-data; name="city"')
        data_parts.append('')
        data_parts.append('TestCity')
        # file
        data_parts.append(f'--{boundary}')
        data_parts.append('Content-Disposition: form-data; name="audio"; filename="test.wav"')
        data_parts.append('Content-Type: audio/wav')
        data_parts.append('')
        data = '\r\n'.join(data_parts).encode('utf-8') + b'\r\n' + wav_path.read_bytes() + b'\r\n' + f'--{boundary}--\r\n'.encode('utf-8')

        req = Request('http://127.0.0.1:8020/submit', data=data, method='POST')
        req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
        req.add_header('Content-Length', str(len(data)))
        with urlopen(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
        assert 'Audio submission saved successfully' in body
        print('[PASS] Upload accepted by app')

        # Check DB for a new row
        # Use sqlite DB directly
        import sqlite3
        conn = sqlite3.connect(ROOT / 'database.sqlite')
        cur = conn.execute('SELECT id, audio_path FROM audio_submissions ORDER BY id DESC LIMIT 1')
        row = cur.fetchone()
        assert row is not None
        print('[PASS] Submission row exists:', row)

        # Ensure file exists on disk
        path = ROOT / row[1].lstrip('/')
        assert path.exists()
        print('[PASS] Audio file exists on filesystem:', path)

    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        if (ROOT / 'tmp_test_audio.wav').exists():
            (ROOT / 'tmp_test_audio.wav').unlink()


if __name__ == '__main__':
    main()
