#!/usr/bin/env python3
"""Debug: Check what assets ChatTTS pip version expects."""
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
    if out.strip(): print(out.strip()[:2000], flush=True)
    if err.strip(): print(f"STDERR: {err.strip()[:300]}", flush=True)
    return ec, out

# 1) Check the pip-installed ChatTTS core.py to see how it validates assets
print("=== Reading pip ChatTTS core.py ===", flush=True)
ec, out, err = run("cat /root/autodl-tmp/conda-envs/voice311/lib/python3.11/site-packages/ChatTTS/core.py", 30)
print(out[:3000], flush=True)

# 2) Check pip ChatTTS __init__.py
print("\n=== pip ChatTTS __init__.py ===", flush=True)
ec, out, err = run("cat /root/autodl-tmp/conda-envs/voice311/lib/python3.11/site-packages/ChatTTS/__init__.py", 10)
print(out.strip()[:500], flush=True)

# 3) Check pip ChatTTS utils/dl.py for asset validation logic
print("\n=== pip ChatTTS utils/dl.py ===", flush=True)
ec, out, err = run("cat /root/autodl-tmp/conda-envs/voice311/lib/python3.11/site-packages/ChatTTS/utils/dl.py", 10)
print(out.strip()[:2000], flush=True)

ssh.close()
print("\n=== Done ===", flush=True)
