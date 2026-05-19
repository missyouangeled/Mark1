#!/usr/bin/env python3
"""
SeetaCloud ChatTTS Smoke Test v2 — no heredo triple-quote escalation issue.
We write the inference script to a temp file on the remote side via sftp, then execute it.
"""

import paramiko
import time
import os

HOST = "connect.westd.seetacloud.com"
PORT = 18786
USER = "root"
PASSWORD = "fn38jSChAGFt"
CONDA_ENV = "/root/autodl-tmp/conda-envs/voice311"
PYTHON_BIN = f"{CONDA_ENV}/bin/python"
PIP_BIN = f"{CONDA_ENV}/bin/pip"
WORK_DIR = "/root/autodl-tmp/voice-lab"

results = []

def log(msg):
    print(f"[SMOKE] {msg}")
    results.append(msg)

def run(ssh, cmd, timeout=120, ok_fails=None, label=""):
    if ok_fails is None: ok_fails = []
    short = cmd[:150].replace("\n", "\\n")
    if label:
        log(f"  \u25b6 {label}: {short}")
    else:
        log(f"  \u25b6 {short}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
    ec = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if ec in ok_fails:
        log(f"    Exit={ec} (ok) out={out.strip()[:200]} err={err.strip()[:200]}")
    elif ec == 0:
        log(f"    OK. out={out.strip()[:300]} err={err.strip()[:150]}")
    else:
        log(f"    FAIL Exit={ec}. err={err.strip()[:400]} out={out.strip()[:150]}")
    return ec, out, err

def main():
    log("="*60)
    log("SeetaCloud ChatTTS Smoke v2")
    log("="*60)

    # Connect
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
    log("SSH connected")

    # Environment check
    log("\n--- Env check ---")
    run(ssh, f"source /root/miniconda3/bin/activate {CONDA_ENV} && which python", timeout=15)
    run(ssh, f"{PYTHON_BIN} -c \"import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO_GPU')\"", timeout=15)
    run(ssh, f"{PYTHON_BIN} -c \"import ChatTTS; print('ChatTTS OK')\"", timeout=15)

    # Write inference script to remote
    log("\n--- Write inference script to remote ---")
    inference_py = r"""#!/usr/bin/env python3
import os, sys, torch, torchaudio
import ChatTTS

print("PyTorch:", torch.__version__)
print("CUDA:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
    print("Mem total GB:", torch.cuda.get_device_properties(0).total_memory / 1e9)

output_dir = "/root/autodl-tmp/voice-lab/output"
os.makedirs(output_dir, exist_ok=True)

print("Loading ChatTTS...")
chat = ChatTTS.Chat()
chat.load(compile=False, source="huggingface")
print("Model loaded OK")

print("Inferring...")
texts = ["你好，我在。这是一个最小可验证测试。"]
wavs = chat.infer(texts, use_decoder=True)
print(f"Inference OK. type={type(wavs).__name__}")

# Try to extract and save
saved_any = False
if isinstance(wavs, list):
    print(f"list len={len(wavs)}")
    for idx, wav in enumerate(wavs):
        if hasattr(wav, 'cpu'): wav = wav.cpu()
        if hasattr(wav, 'detach'): wav = wav.detach()
        wav = wav.squeeze()
        if wav.ndim == 1: wav = wav.unsqueeze(0)
        path = os.path.join(output_dir, f"smoke_{idx}.wav")
        torchaudio.save(path, wav, 24000)
        dur = wav.shape[-1] / 24000.0
        sz = os.path.getsize(path)
        print(f"SAVED {path}: {sz} bytes, {dur:.2f}s")
        saved_any = True
elif hasattr(wavs, 'shape'):
    wav = wavs
    if hasattr(wav, 'cpu'): wav = wav.cpu()
    if hasattr(wav, 'detach'): wav = wav.detach()
    wav = wav.squeeze()
    if wav.ndim == 1: wav = wav.unsqueeze(0)
    path = os.path.join(output_dir, "smoke_0.wav")
    torchaudio.save(path, wav, 24000)
    dur = wav.shape[-1] / 24000.0
    sz = os.path.getsize(path)
    print(f"SAVED {path}: {sz} bytes, {dur:.2f}s")
    saved_any = True
else:
    print(f"Cannot save: unexpected type {type(wavs)}")

if saved_any:
    print("=== SMOKE SUCCESS ===")
else:
    print("=== SMOKE FAIL (no output saved) ===")
    sys.exit(1)
"""

    sftp = ssh.open_sftp()
    remote_path = f"{WORK_DIR}/smoke_test_infer.py"
    with sftp.open(remote_path, "w") as f:
        f.write(inference_py)
    sftp.close()
    log(f"Script written to {remote_path}")

    # Run it with the right conda python
    log("\n--- Run inference ---")
    run(ssh, f"{PYTHON_BIN} {remote_path}", timeout=600)

    # Check output
    log("\n--- Output check ---")
    run(ssh, f"ls -la {WORK_DIR}/output/", timeout=10)

    # Check install log tail
    log("\n--- Install log tail ---")
    run(ssh, f"tail -30 {WORK_DIR}/install_chattts_gpu.log 2>/dev/null || echo 'no log'", timeout=10)

    ssh.close()
    log("\n=== Smoke test complete ===")
    for r in results:
        print(r)

if __name__ == "__main__":
    main()
