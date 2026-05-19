#!/usr/bin/env python3
"""
SeetaCloud ChatTTS Smoke Test — minimal verifiable inference via SSH+Paramiko.
Goal: get a .wav file out of ChatTTS on the remote GPU machine.
"""

import paramiko
import time
import os
import json
from pathlib import Path

# ── Credentials (read from adjacent markdown, never print) ──
HOST = "connect.westd.seetacloud.com"
PORT = 18786
USER = "root"
PASSWORD = "fn38jSChAGFt"

WORK_DIR = "/root/autodl-tmp/voice-lab"
CONDA_ENV = "/root/autodl-tmp/conda-envs/voice311"
PYTHON_BIN = f"{CONDA_ENV}/bin/python"
PIP_BIN = f"{CONDA_ENV}/bin/pip"

results = []

def log(msg: str):
    print(f"[SMOKE] {msg}")
    results.append(msg)

def ssh_exec(ssh, cmd: str, timeout: int = 120, label: str = "", ok_fails=None):
    """Run command via SSH, return exit_code, stdout, stderr."""
    if ok_fails is None:
        ok_fails = []
    if label:
        log(f"  ▶ {label}: {cmd[:120]}...")
    else:
        log(f"  ▶ {cmd[:120]}...")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if exit_code in ok_fails:
        log(f"    Exit={exit_code} (expected) STDOUT={out.strip()[:300]} STDERR={err.strip()[:300]}")
    elif exit_code == 0:
        log(f"    OK. STDOUT={out.strip()[:300]} STDERR={err.strip()[:200]}")
    else:
        log(f"    FAIL Exit={exit_code}. STDERR={err.strip()[:500]} STDOUT={out.strip()[:200]}")
    return exit_code, out, err

def main():
    log("=" * 60)
    log("SeetaCloud ChatTTS Smoke Test v1")
    log("=" * 60)

    # A) Connect
    log("\n--- A) SSH Connect ---")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    log("SSH connected OK")

    # B) Python + GPU check
    log("\n--- B) Environment check ---")
    ssh_exec(ssh, f"source /root/miniconda3/bin/activate {CONDA_ENV} && which python && python --version", timeout=15)

    ssh_exec(ssh, 
        f"{PYTHON_BIN} -c \"import torch; print('torch:', torch.__version__); print('cuda:', torch.cuda.is_available()); print('gpu:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NONE'); print('count:', torch.cuda.device_count())\"",
        timeout=15)

    # C) Check ChatTTS installed
    log("\n--- C) ChatTTS package check ---")
    exit_code, out, err = ssh_exec(ssh,
        f"{PYTHON_BIN} -c \"import ChatTTS; print('ChatTTS OK, version:', getattr(ChatTTS, '__version__', 'unknown')); print('dir:', dir(ChatTTS)[:20])\"",
        timeout=15, ok_fails=[1])

    chattts_installed = (exit_code == 0)

    # D) If not installed, try pip install
    if not chattts_installed:
        log("\n--- D) pip install ChatTTS ---")
        ssh_exec(ssh,
            f"{PIP_BIN} install ChatTTS",
            timeout=300)

        # Verify again
        exit_code2, _, _ = ssh_exec(ssh,
            f"{PYTHON_BIN} -c \"import ChatTTS; print('ChatTTS now importable')\"",
            timeout=15, ok_fails=[1])
        chattts_installed = (exit_code2 == 0)

    # E) Check if model already cached locally
    log("\n--- E) Model cache check ---")
    ssh_exec(ssh,
        f"ls -la /root/.cache/huggingface/hub/models--pzc163--chatTTS/ 2>/dev/null || ls -la {WORK_DIR}/models/ 2>/dev/null || echo 'NO_CACHED_MODEL_FOUND'",
        timeout=10)

    # F) Check available disk space
    ssh_exec(ssh, "df -h /root/autodl-tmp/", timeout=10)

    # G) Run minimal inference
    log("\n--- G) Minimal ChatTTS inference ---")
    inference_script = f"""{PYTHON_BIN} << 'PYEOF'
import os
import torch
import torchaudio

print("PyTorch version:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
    print("Memory:", torch.cuda.get_device_properties(0).total_memery / 1e9, "GB")

try:
    import ChatTTS
    print("ChatTTS imported OK")
except Exception as e:
    print(f"ChatTTS import FAILED: {{e}}")
    exit(1)

# Initialize
print("Initializing ChatTTS...")
try:
    chat = ChatTTS.Chat()
    chat.load(compile=False, source="huggingface")
    print("ChatTTS model loaded OK")
except Exception as e:
    print(f"ChatTTS model load FAILED: {{e}}")
    import traceback
    traceback.print_exc()
    exit(1)

# Generate
texts = ["你好，我在。这是一个最小可验证测试。"]
print(f"Generating for: {{texts}}")
try:
    wavs = chat.infer(texts, use_decoder=True)
    print(f"Inference OK. type={{type(wavs)}}")
    if isinstance(wavs, list):
        print(f"len={{len(wavs)}}")
        for i, w in enumerate(wavs):
            print(f"  wav[{i}]: type={{type(w)}} shape={{w.shape if hasattr(w,'shape') else '?'}}")
    elif hasattr(wavs, 'shape'):
        print(f"shape={{wavs.shape}} dtype={{wavs.dtype}}")
    elif isinstance(wavs, dict):
        for k, v in wavs.items():
            print(f"  {{k}}: type={{type(v)}} shape={{v.shape if hasattr(v,'shape') else '?'}}")
except Exception as e:
    print(f"Inference FAILED: {{e}}")
    import traceback
    traceback.print_exc()
    exit(1)

# Save
output_dir = "{WORK_DIR}/output"
os.makedirs(output_dir, exist_ok=True)
out_path = os.path.join(output_dir, "smoke_test.wav")

# Try to extract waveform and save
try:
    if isinstance(wavs, list) and len(wavs) > 0:
        wav = wavs[0]
        if hasattr(wav, 'cpu'):
            wav = wav.cpu()
        if hasattr(wav, 'detach'):
            wav = wav.detach()
        # squeeze if needed
        if hasattr(wav, 'squeeze'):
            wav = wav.squeeze()
        print(f"Pre-save: shape={{wav.shape}}, dtype={{wav.dtype}}, ndim={{wav.ndim if hasattr(wav,'ndim') else '?'}}")
        
        # If 1D, add channel dim
        if hasattr(wav, 'ndim') and wav.ndim == 1:
            wav = wav.unsqueeze(0)
        
        torchaudio.save(out_path, wav, 24000)
        file_size = os.path.getsize(out_path)
        duration = wav.shape[-1] / 24000.0
        print(f"SAVED: {{out_path}}")
        print(f"SIZE: {{file_size}} bytes")
        print(f"DURATION: {{duration:.2f}} seconds")
    elif hasattr(wavs, 'shape'):
        wav = wavs
        if hasattr(wav, 'cpu'):
            wav = wav.cpu()
        if hasattr(wav, 'detach'):
            wav = wav.detach()
        wav = wav.squeeze()
        if wav.ndim == 1:
            wav = wav.unsqueeze(0)
        torchaudio.save(out_path, wav, 24000)
        file_size = os.path.getsize(out_path)
        duration = wav.shape[-1] / 24000.0
        print(f"SAVED: {{out_path}}")
        print(f"SIZE: {{file_size}} bytes")
        print(f"DURATION: {{duration:.2f}} seconds")
    else:
        print(f"Cannot save: unexpected type {{type(wavs)}}")
except Exception as e:
    print(f"Save FAILED: {{e}}")
    import traceback
    traceback.print_exc()

print("=== SMOKE TEST COMPLETE ===")
PYEOF"""

    exit_code, out, err = ssh_exec(ssh, inference_script, timeout=600)

    # H) If failed, try simpler path — check output dir anyway
    log("\n--- H) List output directory ---")
    ssh_exec(ssh, f"ls -la {WORK_DIR}/output/ 2>/dev/null || echo 'No output dir'", timeout=10)

    # I) Try picking up any existing install script log
    log("\n--- I) Last 50 lines of install log ---")
    ssh_exec(ssh, f"tail -50 {WORK_DIR}/install_chattts_gpu.log 2>/dev/null || echo 'No install log found'", timeout=10)

    ssh.close()
    log("\n=== Smoke test complete ===")
    for r in results:
        print(r)


if __name__ == "__main__":
    main()
