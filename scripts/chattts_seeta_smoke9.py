#!/usr/bin/env python3
"""
SeetaCloud ChatTTS Smoke v9 — USE LOCAL ASSETS, no internet needed.
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
    if out.strip(): print(out.strip()[:1500], flush=True)
    if err.strip(): print(f"STDERR: {err.strip()[:300]}", flush=True)
    return ec

ASSET_DIR = "/root/autodl-tmp/voice-lab/workspace/tmp/voice-replies/chattts-hybrid/asset"

# Write the minimal GPU inference script to remote (using local assets)
infer_script = f'''#!/usr/bin/env python3
"""Minimal ChatTTS GPU inference with local assets."""
import os, sys, time, logging
warnings.filterwarnings("ignore")

os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import torch
print("torch:", torch.__version__, file=sys.stderr, flush=True)
print("cuda:", torch.cuda.is_available(), file=sys.stderr, flush=True)
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0), file=sys.stderr, flush=True)

import ChatTTS
print("ChatTTS imported", file=sys.stderr, flush=True)

output_dir = "{WORK_DIR}/output"
os.makedirs(output_dir, exist_ok=True)

device = torch.device("cuda")
chat = ChatTTS.Chat()
chat.logger.setLevel(logging.WARNING)

print(f"Loading from local: {ASSET_DIR}", file=sys.stderr, flush=True)

try:
    result = chat.load(
        source="custom",
        custom_path="{ASSET_DIR}",
        device=device,
        compile=False,
    )
except Exception as e:
    print(f"Load FAILED: {{e}}", file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

print(f"Load result: {{result}}", file=sys.stderr, flush=True)

texts = ["你好，我在。"]
print(f"Inferring: {{texts}}", file=sys.stderr, flush=True)

try:
    wavs = chat.infer(texts, use_decoder=True)
except Exception as e:
    print(f"Infer FAILED: {{e}}", file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

print(f"Inferred type={{type(wavs).__name__}}", file=sys.stderr, flush=True)

import torchaudio
saved = False
if isinstance(wavs, list):
    for i, w in enumerate(wavs):
        if hasattr(w, "cpu"): w = w.cpu()
        if hasattr(w, "detach"): w = w.detach()
        w = w.squeeze()
        if w.ndim == 1: w = w.unsqueeze(0)
        p = f"{{output_dir}}/smoke_local_{i}.wav"
        torchaudio.save(p, w, 24000)
        dur = w.shape[-1]/24000.0
        sz = os.path.getsize(p)
        print(f"SAVED {{p}}: {{sz}}B {{dur:.2f}}s", file=sys.stderr, flush=True)
        saved = True
elif hasattr(wavs, "shape"):
    w = wavs
    if hasattr(w, "cpu"): w = w.cpu()
    if hasattr(w, "detach"): w = w.detach()
    w = w.squeeze()
    if w.ndim == 1: w = w.unsqueeze(0)
    p = f"{{output_dir}}/smoke_local_0.wav"
    torchaudio.save(p, w, 24000)
    dur = w.shape[-1]/24000.0
    sz = os.path.getsize(p)
    print(f"SAVED {{p}}: {{sz}}B {{dur:.2f}}s", file=sys.stderr, flush=True)
    saved = True

if saved:
    print("=== SMOKE SUCCESS ===", file=sys.stderr, flush=True)
else:
    print("=== SMOKE FAIL ===", file=sys.stderr, flush=True)
'''

# Write to remote
sftp = ssh.open_sftp()
with sftp.open(f"{WORK_DIR}/smoke_local_gpu.py", "w") as f:
    f.write(infer_script)
sftp.close()
print("Remote script written", flush=True)

# Run it
print("\n=== Running GPU inference with local assets ===", flush=True)
ec, out, err = run(f"{PY} -u {WORK_DIR}/smoke_local_gpu.py 2>&1", 300)
print(f"Exit={ec}", flush=True)
if out.strip(): print(out.strip()[:2000], flush=True)
if err.strip(): print(f"STDERR: {err.strip()[:300]}", flush=True)

# Check output
print("\n=== Output check ===", flush=True)
check("List output", f"ls -la {WORK_DIR}/output/", 10)

# nvidia-smi check
print("\n=== GPU status ===", flush=True)
check("nvidia-smi", "nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || echo 'nvidia-smi not available'", 10)

ssh.close()
print("\n=== DONE ===", flush=True)
