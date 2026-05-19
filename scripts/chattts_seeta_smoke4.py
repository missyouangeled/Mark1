#!/usr/bin/env python3
"""
SeetaCloud ChatTTS Smoke v4 — step by step with explicit remote file execution.
"""

import paramiko
import os, sys, time

HOST = "connect.westd.seetacloud.com"
PORT = 18786
USER = "root"
PASSWORD = "fn38jSChAGFt"
CONDA_ENV = "/root/autodl-tmp/conda-envs/voice311"
PY = f"{CONDA_ENV}/bin/python"
WORK_DIR = "/root/autodl-tmp/voice-lab"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
print("SSH OK", flush=True)

def run(cmd, timeout=120):
    print(f"> {cmd[:200]}", flush=True)
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    ec = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if ec != 0:
        print(f"  FAIL({ec}) err={err.strip()[:500]} out={out.strip()[:200]}", flush=True)
    else:
        print(f"  OK: {out.strip()[:600]}", flush=True)
    if err.strip():
        print(f"  stderr: {err.strip()[:200]}", flush=True)
    return ec, out, err

# Step 1: env sanity
print("\n=== STEP 1: Env ===", flush=True)
run(f"{PY} -c 'import torch; print(\"torch:\", torch.__version__, \"cuda:\", torch.cuda.is_available(), \"gpu:\", torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"NONE\")'", timeout=15)

# Step 2: check ChatTTS
print("\n=== STEP 2: ChatTTS ===", flush=True)
run(f"{PY} -c 'import ChatTTS; print(\"ChatTTS OK\")'", timeout=15)

# Step 3: write the most minimal inference script to remote
print("\n=== STEP 3: Write min infer script ===", flush=True)
min_script = (
    'import os, torch, torchaudio, ChatTTS\n'
    'os.makedirs("/root/autodl-tmp/voice-lab/output", exist_ok=True)\n'
    'print("Loading...", flush=True)\n'
    'chat = ChatTTS.Chat()\n'
    'chat.load(compile=False, source="huggingface")\n'
    'print("Loaded OK. Inferring...", flush=True)\n'
    'wavs = chat.infer(["你好，我在。"], use_decoder=True)\n'
    'print(f"Inferred type={type(wavs).__name__}", flush=True)\n'
    'if isinstance(wavs, list) and len(wavs) > 0:\n'
    '    w = wavs[0]\n'
    '    if hasattr(w, "cpu"): w = w.cpu()\n'
    '    if hasattr(w, "detach"): w = w.detach()\n'
    '    w = w.squeeze()\n'
    '    if w.ndim == 1: w = w.unsqueeze(0)\n'
    '    p = "/root/autodl-tmp/voice-lab/output/smoke_v4.wav"\n'
    '    torchaudio.save(p, w, 24000)\n'
    '    print(f"SAVED {p} size={os.path.getsize(p)} dur={w.shape[-1]/24000.0:.2f}s", flush=True)\n'
    '    print("SUCCESS", flush=True)\n'
    'else:\n'
    '    print(f"UNEXPECTED OUTPUT: {wavs}", flush=True)\n'
)
sftp = ssh.open_sftp()
with sftp.open(f"{WORK_DIR}/min_infer.py", "w") as f:
    f.write(min_script)
sftp.close()
print("Written OK", flush=True)

# Step 4: Run it (this is the long step - model download first time)
print("\n=== STEP 4: Run min_infer.py ===", flush=True)
ec, out, err = run(f"cd {WORK_DIR} && {PY} -u min_infer.py 2>&1", timeout=600)

# Step 5: Check results
print("\n=== STEP 5: Results ===", flush=True)
run(f"ls -la {WORK_DIR}/output/", timeout=10)

ssh.close()
print("\n=== DONE ===", flush=True)
