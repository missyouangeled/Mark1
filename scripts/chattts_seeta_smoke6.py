#!/usr/bin/env python3
"""
SeetaCloud ChatTTS Smoke v6 — find the working script & fix model download.
"""

import paramiko
import time

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
    print(f"=== {label} ===", flush=True)
    ec, out, err = run(cmd, timeout)
    print(f"Exit={ec}", flush=True)
    if out.strip(): print(out.strip()[:1500], flush=True)
    if err.strip(): print(f"STDERR: {err.strip()[:300]}", flush=True)
    return ec

# 1) Find all Python scripts in voice-lab
check("Find all python scripts", f"find {WORK_DIR} -name '*.py' 2>/dev/null", timeout=10)

# 2) Check the existing wav files details with the conda python
check("WAV details", f"{PY} -c \"import wave; w=wave.open('{WORK_DIR}/output/smoke-default.wav'); print('default:', w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), 'samples'); w=wave.open('{WORK_DIR}/output/smoke-oral1-break3.wav'); print('oral1:', w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), 'samples')\"", timeout=10)

# 3) Check if HF needs a token or env var
check("HF env", "echo $HF_TOKEN; env | grep -i hugging 2>/dev/null || echo 'no HF env'", timeout=10)

# 4) Try explicit wget approach for the model files
# First check what the actual pzc163/chatTTS repo has
check("Try direct HF download via requests",
    f"{PY} -c \"
import requests, json
r = requests.get('https://huggingface.co/api/models/pzc163/chatTTS', timeout=30)
if r.ok:
    data = r.json()
    siblings = data.get('siblings', [])
    for s in siblings:
        print(s['rfilename'])
else:
    print('API returned', r.status_code)
\"", timeout=60)

ssh.close()
print("\n=== Done ===", flush=True)
