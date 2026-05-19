"""Final verification of the generated WAV file (fixed)."""
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

# Use a script file to avoid quoting hell
verify_script = '''
import soundfile as sf
import os

for fname in ["smoke_gpu_0.wav", "smoke-default.wav", "smoke-oral1-break3.wav"]:
    path = "/root/autodl-tmp/voice-lab/output/" + fname
    if not os.path.exists(path):
        print(f"{fname}: NOT FOUND")
        continue
    data, sr = sf.read(path)
    sz = os.path.getsize(path)
    print(f"{fname}: sr={sr} shape={data.shape} dtype={data.dtype} min={data.min():.4f} max={data.max():.4f} dur={len(data)/sr:.2f}s size={sz}B")
'''

print("Uploading verify script...", flush=True)
sftp = ssh.open_sftp()
with sftp.open(f"{WORK_DIR}/verify_wavs.py", "w") as f:
    f.write(verify_script.strip())
sftp.close()

ec, out, err = run(f"{PY} -u {WORK_DIR}/verify_wavs.py", 10)
print(out.strip() if out.strip() else "(empty)", flush=True)
if err.strip(): print("STDERR:", err.strip()[:200], flush=True)

print("\n=== Disk ===", flush=True)
ec2, out2, err2 = run("df -h /root/autodl-tmp/", 10)
print(out2.strip(), flush=True)

ssh.close()
print("\n=== VERIFICATION DONE ===", flush=True)
