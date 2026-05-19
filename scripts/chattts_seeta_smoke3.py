#!/usr/bin/env python3
"""
SeetaCloud ChatTTS Smoke v3 — minimal path, separate steps.
"""

import paramiko
import time
import os

HOST = "connect.westd.seetacloud.com"
PORT = 18786
USER = "root"
PASSWORD = "fn38jSChAGFt"
CONDA_ENV = "/root/autodl-tmp/conda-envs/voice311"
PYTHON_BIN = f"{CONDA_ENV}/bin/python"
PIP_BIN = f"{CONDA_ENV}/bin/pip"
WORK_DIR = "/root/autodl-tmp/voice-lab"

def run(ssh, cmd, timeout=120, get_pty=True):
    short = cmd[:150].replace("\n", "\\n")
    print(f"  \u25b6 {short}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=get_pty)
    ec = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if ec == 0:
        print(f"    OK. out={out.strip()[:500]}")
        if err.strip():
            print(f"    stderr={err.strip()[:200]}")
    else:
        print(f"    FAIL Exit={ec}. err={err.strip()[:500]}")
        if out.strip():
            print(f"    stdout={out.strip()[:200]}")
    return ec, out, err

def main():
    print("="*60)
    print("SeetaCloud ChatTTS Smoke v3")
    print("="*60)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    print("SSH connected")

    print("\n1) Environment sanity")
    run(ssh, f"{PYTHON_BIN} -c \"import torch; print('OK', torch.__version__, torch.cuda.is_available())\"", timeout=15)
    run(ssh, f"{PYTHON_BIN} -c \"import ChatTTS; print('ChatTTS OK')\"", timeout=15)

    print("\n2) Check disk space")
    run(ssh, "df -h /root/autodl-tmp/", timeout=10)

    print("\n3) Check if model already cached anywhere")
    run(ssh, "find /root -name '*.safetensors' -o -name '*.bin' 2>/dev/null | head -20", timeout=15)
    run(ssh, "ls -la /root/.cache/huggingface/hub/ 2>/dev/null || echo 'no hub dir'", timeout=10)

    print("\n4) Write remote inference script (with live logging)")
    script = """#!/usr/bin/env python3
import os, sys, time, torch, torchaudio, ChatTTS

log_path = "/root/autodl-tmp/voice-lab/output/smoke_log.txt"
os.makedirs("/root/autodl-tmp/voice-lab/output", exist_ok=True)

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(log_path, "a") as f:
        f.write(line + "\\n")

log(f"PyTorch {torch.__version__}, CUDA {torch.cuda.is_available()}")
if torch.cuda.is_available():
    log(f"GPU: {torch.cuda.get_device_name(0)}")
    log(f"Mem total: {torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB")

log("Loading ChatTTS...")
chat = ChatTTS.Chat()
chat.load(compile=False, source="huggingface")
log("Model loaded OK")

log("Inferring...")
texts = ["你好，我在。这是一个最小可验证测试。"]
wavs = chat.infer(texts, use_decoder=True)
log(f"Inference OK, type={type(wavs).__name__}")

saved = False
if isinstance(wavs, list):
    log(f"Got list of {len(wavs)}")
    for i, w in enumerate(wavs):
        if hasattr(w, 'cpu'): w = w.cpu()
        if hasattr(w, 'detach'): w = w.detach()
        w = w.squeeze()
        if w.ndim == 1: w = w.unsqueeze(0)
        p = f"/root/autodl-tmp/voice-lab/output/smoke_{i}.wav"
        torchaudio.save(p, w, 24000)
        sz = os.path.getsize(p)
        dur = w.shape[-1]/24000.0
        log(f"SAVED {p}: {sz}B {dur:.2f}s")
        saved = True
elif hasattr(wavs, 'shape'):
    w = wavs
    if hasattr(w, 'cpu'): w = w.cpu()
    if hasattr(w, 'detach'): w = w.detach()
    w = w.squeeze()
    if w.ndim == 1: w = w.unsqueeze(0)
    p = "/root/autodl-tmp/voice-lab/output/smoke_0.wav"
    torchaudio.save(p, w, 24000)
    sz = os.path.getsize(p)
    dur = w.shape[-1]/24000.0
    log(f"SAVED {p}: {sz}B {dur:.2f}s")
    saved = True

if saved:
    log("=== SMOKE SUCCESS ===")
else:
    log("=== SMOKE FAIL (no output) ===")
    sys.exit(1)
"""
    sftp = ssh.open_sftp()
    with sftp.open(f"{WORK_DIR}/smoke_v3.py", "w") as f:
        f.write(script)
    sftp.close()
    print("  Remote script written OK")

    print("\n5) Run inference (will stream when polled)...")
    # Use a simpler command with shell redirect to capture output
    run_cmd = f"cd {WORK_DIR} && {PYTHON_BIN} smoke_v3.py 2>&1 | tee output/smoke_stdout.txt"
    ec, out, err = run(ssh, run_cmd, timeout=600, get_pty=True)
    print(f"\n6) Exit code: {ec}")

    print("\n7) Check output dir")
    run(ssh, f"ls -la {WORK_DIR}/output/", timeout=10)
    run(ssh, f"cat {WORK_DIR}/output/smoke_log.txt 2>/dev/null || echo 'no log'", timeout=10)

    ssh.close()
    print("\n=== Done ===")

if __name__ == "__main__":
    main()
