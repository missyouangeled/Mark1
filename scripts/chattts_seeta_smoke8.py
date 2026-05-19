#!/usr/bin/env python3
"""
SeetaCloud ChatTTS Smoke v8 — use local model assets (no internet).
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

# 1) Read the existing stable script
print("\n========= READ chattts_stable.py =========", flush=True)
ec, out, err = run("cat /root/autodl-tmp/voice-lab/workspace/skills/chattts-stable/scripts/chattts_stable.py", 30)
print(out, flush=True)
if err.strip(): print("STDERR:", err[:200], flush=True)

# 2) Check what model files exist locally
check("Find model files",
    "find /root/autodl-tmp/voice-lab -name '*.pt' -o -name '*.pth' -o -name '*.safetensors' -o -name '*.bin' -o -name '*.onnx' 2>/dev/null",
    15)

# 3) Check vendor ChatTTS structure
check("Vendor structure",
    "find /root/autodl-tmp/voice-lab/vendor -maxdepth 4 -type f 2>/dev/null | head -60",
    10)

# 4) Check the config if it has model paths
check("Config",
    "cat /root/autodl-tmp/voice-lab/vendor/ChatTTS/config/config.py 2>/dev/null",
    10)

# 5) Check what git repos exist
check("Git repos", "find /root/autodl-tmp/voice-lab -name '.git' -maxdepth 4 -type d 2>/dev/null", 10)

ssh.close()
print("\n=== Done ===", flush=True)
