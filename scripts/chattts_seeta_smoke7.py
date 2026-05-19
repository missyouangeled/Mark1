#!/usr/bin/env python3
"""
SeetaCloud ChatTTS Smoke v7 — no f-string nesting issues.
"""

import paramiko

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
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    ec = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return ec, out, err

def check(label, cmd, timeout=120):
    print(f"\n=== {label} ===", flush=True)
    ec, out, err = run(cmd, timeout)
    print(f"Exit={ec}", flush=True)
    s = out.strip()
    if s: print(s[:2000], flush=True)
    e = err.strip()
    if e: print(f"STDERR: {e[:300]}", flush=True)
    return ec

# Find scripts
check("Find python scripts", f"find {WORK_DIR} -name '*.py' 2>/dev/null", 10)

# WAV details
check("WAV details", PY + " -c 'import wave; "
    "w=wave.open(\"" + WORK_DIR + "/output/smoke-default.wav\"); "
    "print(\"default:\", w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), \"samples\"); "
    "w=wave.open(\"" + WORK_DIR + "/output/smoke-oral1-break3.wav\"); "
    "print(\"oral1:\", w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), \"samples\")'", 10)

# HF env
check("HF env", "echo HF_TOKEN_LEN=${#HF_TOKEN}; env | grep -i hugging 2>/dev/null || echo 'no HF env'", 10)

# Check HF API for model files via requests
check("HF model files",
    PY + " -c 'import requests; r=requests.get(\"https://huggingface.co/api/models/pzc163/chatTTS\", timeout=30); "
    "print(r.status_code); data=r.json(); "
    "print([s[\"rfilename\"] for s in data[\"siblings\"]])'",
    60)

# Try downloading model files directly with wget
check("Try listing HF repo",
    PY + " -c 'from huggingface_hub import list_repo_files; "
    "files=list_repo_files(\"pzc163/chatTTS\"); print(files)'",
    60)

ssh.close()
print("\n=== Done ===", flush=True)
