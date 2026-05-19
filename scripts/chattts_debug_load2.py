#!/usr/bin/env python3
"""Debug: Check exact asset structure and custom loading."""
import paramiko

HOST = "connect.westd.seetacloud.com"
PORT = 18786
USER = "root"
PASSWORD = "fn38jSChAGFt"
CONDA_ENV = "/root/autodl-tmp/conda-envs/voice311"
PY = f"{CONDA_ENV}/bin/python"""
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

# 1) Full asset directory listing
check("Full asset tree", "find /root/autodl-tmp/voice-lab/workspace/tmp/voice-replies/chattts-hybrid/ -type f -exec ls -la {} \\;", 15)

# 2) Check full core.py custom_path logic
print("\n=== Full core.py custom loading ===", flush=True)
ec, out, err = run("cat /root/autodl-tmp/conda-envs/voice311/lib/python3.11/site-packages/ChatTTS/core.py", 30)
# Find the custom source section
lines = out.split('\n')
in_load = False
for i, line in enumerate(lines):
    if 'def download_models' in line or 'def load' in line:
        in_load = True
        print(f"=== {line.strip()} ===", flush=True)
    elif in_load and line.strip().startswith('def '):
        in_load = False
    elif in_load:
        print(line.rstrip(), flush=True)

# 3) Check if CustomChatTTS or vendor version works
check("Vendor core.py", "cat /root/autodl-tmp/voice-lab/vendor/ChatTTS/core.py", 15)

ssh.close()
print("\n=== Done ===", flush=True)
