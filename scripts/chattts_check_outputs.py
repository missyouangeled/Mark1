"""Check outputs after inference run."""
import paramiko

HOST = "connect.westd.seetacloud.com"
PORT = 18786
USER = "root"
PASSWORD = "fn38jSChAGFt"
WORK_DIR = "/root/autodl-tmp/voice-lab"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    ec = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return ec, out, err

# Check if new wav files appeared
print("=== Output dir ===", flush=True)
ec, out, err = run(f"ls -la {WORK_DIR}/output/", 10)
print(out, flush=True)

# Check for recent smoke_local files specifically
print("\n=== New output files ===", flush=True)
ec, out, err = run(f"ls -la {WORK_DIR}/output/smoke_local* 2>/dev/null || echo 'NO NEW FILES'", 10)
print(out, flush=True)

# If new files exist, verify them
print("\n=== WAV verification ===", flush=True)
ec, out, err = run(f"file {WORK_DIR}/output/smoke_local* 2>/dev/null || echo 'no wav to verify'", 10)
print(out, flush=True)

# Check last run's stderr (in the inference output)
print("\n=== GPU status ===", flush=True)
ec, out, err = run("nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || echo 'nvidia-smi unavailable'", 10)
print(out, flush=True)

ssh.close()
