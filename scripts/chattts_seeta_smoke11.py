#!/usr/bin/env python3
"""Upload and run remote_infer2.py on SeetaCloud."""
import paramiko

HOST = "connect.westd.seetacloud.com"
PORT = 18786
USER = "root"
PASSWORD = "fn38jSChAGFt"
CONDA_ENV = "/root/autodl-tmp/conda-envs/voice311"
PY = f"{CONDA_ENV}/bin/python"
WORK_DIR = "/root/autodl-tmp/voice-lab"
LOCAL_SCRIPT = "/home/missyouangeled/.openclaw/workspace/scripts/remote_infer2.py"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
print("SSH OK", flush=True)

sftp = ssh.open_sftp()
sftp.put(LOCAL_SCRIPT, f"{WORK_DIR}/remote_infer2.py")
sftp.close()
print("Uploaded", flush=True)

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    ec = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return ec, out, err

print("\n=== Running inference (patched) ===", flush=True)
ec, out, err = run(f"{PY} -u {WORK_DIR}/remote_infer2.py 2>&1", 600)
print(f"Exit={ec}", flush=True)
if out.strip(): print("STDOUT:", out.strip()[:2000], flush=True)
if err.strip(): print("STDERR:", err.strip()[:300], flush=True)

print("\n=== Output check ===", flush=True)
ec2, out2, err2 = run(f"ls -la {WORK_DIR}/output/", 10)
print(out2.strip() if out2.strip() else "(empty)", flush=True)

ssh.close()
print("\n=== DONE ===", flush=True)
