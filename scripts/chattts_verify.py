"""Final verification of the generated WAV file."""
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

# Full verification of the new file
print("=== smoke_gpu_0.wav ===", flush=True)
run(f"file {WORK_DIR}/output/smoke_gpu_0.wav", 10)
run(f"wc -c {WORK_DIR}/output/smoke_gpu_0.wav", 10)
run(f"{PY} -c 'import soundfile as sf; d,sr=sf.read(\"{WORK_DIR}/output/smoke_gpu_0.wav\"); print(f\"sr={sr} shape={d.shape} dtype={d.dtype} min={d.min():.4f} max={d.max():.4f} dur={len(d)/sr:.2f}s\")'", 10)

# Verify other wavs too
print("\n=== smoke-default.wav ===", flush=True)
run(f"{PY} -c 'import soundfile as sf; d,sr=sf.read(\"{WORK_DIR}/output/smoke-default.wav\"); print(f\"sr={sr} shape={d.shape} dur={len(d)/sr:.2f}s min={d.min():.4f} max={d.max():.4f}\")'", 10)
print("\n=== smoke-oral1-break3.wav ===", flush=True)
run(f"{PY} -c 'import soundfile as sf; d,sr=sf.read(\"{WORK_DIR}/output/smoke-oral1-break3.wav\"); print(f\"sr={sr} shape={d.shape} dur={len(d)/sr:.2f}s min={d.min():.4f} max={d.max():.4f}\")'", 10)

# Check disk space
print("\n=== Remaining disk ===", flush=True)
run("df -h /root/autodl-tmp/", 10)

ssh.close()
print("\n=== VERIFICATION DONE ===", flush=True)
