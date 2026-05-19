#!/usr/bin/env python3
"""
SeetaCloud ChatTTS Smoke v5 — investigate the existing outputs and fix model download.
"""

import paramiko
import os

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
    print(f"  Exit={ec} out={out.strip()[:1200]}", flush=True)
    if err.strip():
        print(f"  err={err.strip()[:400]}", flush=True)
    return ec, out, err

# 1) Check existing output files
print("=== Existing outputs ===", flush=True)
run(f"ls -la {WORK_DIR}/output/", timeout=10)
run(f"file {WORK_DIR}/output/*.wav", timeout=10)
run(f"python3 -c \"import wave; w=wave.open('{WORK_DIR}/output/smoke-default.wav'); print('default.wav:', w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()); w.close()\"", timeout=10)
run(f"python3 -c \"import wave; w=wave.open('{WORK_DIR}/output/smoke-oral1-break3.wav'); print('oral1.wav:', w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()); w.close()\"", timeout=10)

# 2) Check what model files are cached
print("\n=== Model cache ===", flush=True)
run("find /root/.cache/huggingface -name '*.safetensors' -o -name '*.bin' -o -name '*.pt' -o -name '*.pth' 2>/dev/null | head -40", timeout=15)
run("ls -la /root/.cache/huggingface/hub/ 2>/dev/null", timeout=10)
run("ls -la /root/.cache/huggingface/hub/models--pzc163--chatTTS/ 2>/dev/null; ls -la /root/.cache/huggingface/hub/models--pzc163--chatTTS/snapshots/ 2>/dev/null; ls -la /root/.cache/huggingface/hub/models--pzc163--chatTTS/snapshots/*/ 2>/dev/null", timeout=10)

# 3) Check what the install log says about any model download
print("\n=== Install log ===", flush=True)
run(f"grep -i 'download\\|model\\|hugging\\|cache\\|error' {WORK_DIR}/install_chattts_gpu.log 2>/dev/null | tail -20", timeout=10)

# 4) Try hugingface_hub API to see if we can list model files
print("\n=== HuggingFace model info ===", flush=True)
run(f"""{PY} -c "
from huggingface_hub import HfApi
api = HfApi()
files = api.list_repo_files('pzc163/chatTTS')
print('Files:', files)
" """, timeout=30)

# 5) Check if there's a local model or checkpoint elsewhere
print("\n=== Any other model dirs ===", flush=True)
run("find /root -maxdepth 4 -name '*.safetensors' 2>/dev/null | head -20", timeout=15)
run("find /root/autodl-tmp -maxdepth 3 -type d 2>/dev/null | head -30", timeout=10)

# 6) Try downloading model explicitly via huggingface_hub
print("\n=== Download model explicitly ===", flush=True)
run(f"""{PY} -c "
from huggingface_hub import snapshot_download
import os
dest = '/root/autodl-tmp/voice-lab/models/chattts'
os.makedirs(dest, exist_ok=True)
print('Downloading pzc163/chatTTS to', dest)
path = snapshot_download(repo_id='pzc163/chatTTS', local_dir=dest, local_dir_use_symlinks=False)
print('Downloaded to:', path)
for f in os.listdir(path):
    print(' ', f, os.path.getsize(os.path.join(path, f)))
" """, timeout=300)

ssh.close()
print("\n=== Done ===", flush=True)
