#!/usr/bin/env python3
"""
chattts_seeta_gpu.py — Minimal GPU TTS via SeetaCloud remote.

Reads SSH credentials from credentials/ssh/seetacloud-chattts-westd.md (markdown table),
connects via paramiko (no system ssh / GUI askpass), pushes a self-contained
patched inference script, runs it on the remote GPU (voice311 conda env), and
SFTPs the output WAV back to the local workspace.

Intended as a pure remote complement to the local CPU chattts_stable.py.
Does NOT modify the local stable mainline.

Usage:
  python3 scripts/chattts_seeta_gpu.py --text "你好，我在。"
  python3 scripts/chattts_seeta_gpu.py --text "测试" --tag mytest
  python3 scripts/chattts_seeta_gpu.py --text "你好" --preset preset-1
  python3 scripts/chattts_seeta_gpu.py --list-presets

Presets loaded from: skills/chattts-stable/assets/presets.json
Exit code: 0 on success (prints local output path), 1 on failure.
"""

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw" / "workspace"
CRED_FILE = WORKSPACE / "credentials" / "ssh" / "seetacloud-chattts-westd.md"
PRESETS_FILE = WORKSPACE / "skills" / "chattts-stable" / "assets" / "presets.json"
PRESET_DIR = WORKSPACE / "skills" / "chattts-stable" / "assets" / "presets"
DEFAULT_OUT_DIR = WORKSPACE / "tmp" / "voice-replies"
REMOTE_WORK_DIR = "/root/autodl-tmp/voice-lab"
REMOTE_OUT_DIR = "/root/autodl-tmp/voice-lab/output"
REMOTE_CONDA_PY = "/root/autodl-tmp/conda-envs/voice311/bin/python"


def load_presets() -> dict:
    """Load presets.json config."""
    return json.loads(PRESETS_FILE.read_text(encoding="utf-8"))


def resolve_preset(name: str | None, config: dict) -> tuple[str, dict]:
    """Resolve preset name (or alias), return (name, preset_dict).

    Falls back to config["defaultPreset"] when name is None.
    """
    presets = config["presets"]
    wanted = (name or config.get("defaultPreset") or "default").strip()
    normalized = wanted.lower()
    if wanted in presets:
        return wanted, presets[wanted]
    alias_map = {}
    for pn, ps in presets.items():
        for a in ps.get("aliases", []):
            alias_map[a.lower()] = pn
    if normalized in alias_map:
        target = alias_map[normalized]
        return target, presets[target]
    available = ", ".join(presets.keys())
    raise SystemExit(f"Unknown preset: {wanted}. Available: {available}")


def load_spk_emb(preset: dict) -> str | None:
    """Read the spk_emb text file for a preset, or return None."""
    spk_file = preset.get("spkEmbFile")
    if not spk_file:
        return None
    # spkEmbFile paths in presets.json are relative to ASSETS_DIR
    return (WORKSPACE / "skills" / "chattts-stable" / "assets" / spk_file).read_text(encoding="utf-8").strip()


def parse_credentials(path: Path) -> dict:
    """Parse SSH host/port/user/password from the markdown credential file."""
    text = path.read_text(encoding="utf-8")
    # Format: "- Host：`value`" or "- Host: `value`" — Chinese/Japanese-style colon
    m_host = re.search(r"Host[：:]+[\s]*`([^`]+)`", text)
    m_port = re.search(r"Port[：:]+[\s]*`([^`]+)`", text)
    m_user = re.search(r"User[：:]+[\s]*`([^`]+)`", text)
    m_pwd  = re.search(r"Password[：:]+[\s]*`([^`]+)`", text)
    if not (m_host and m_port and m_user and m_pwd):
        raise ValueError(f"Cannot parse SSH credentials from {path}")
    return {
        "host": m_host.group(1).strip(),
        "port": int(m_port.group(1)),
        "user": m_user.group(1).strip(),
        "password": m_pwd.group(1).strip(),
    }


INFER_SCRIPT_TEMPLATE = r'''import os,sys,logging,warnings,json
warnings.filterwarnings("ignore")
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import numpy as np
import torch

# --- Patch asset checks ---
import ChatTTS.utils.dl as dl_mod
def always_pass(*a,**kw): return True
dl_mod.check_all_assets = always_pass
dl_mod.check_model = always_pass
dl_mod.check_folder = always_pass

# --- Patch DVAE strict loading ---
import ChatTTS.model.dvae as dvae_mod
orig_dvae = dvae_mod.DVAE.load_state_dict
def pdvae(self,sd,strict=True,assign=False): return orig_dvae(self,sd,strict=False,assign=assign)
dvae_mod.DVAE.load_state_dict = pdvae
orig_dec = dvae_mod.DVAEDecoder.load_state_dict
def pdec(self,sd,strict=True,assign=False): return orig_dec(self,sd,strict=False,assign=assign)
dvae_mod.DVAEDecoder.load_state_dict = pdec

# --- Patch tokenizer.encode ---
import ChatTTS.model.tokenizer as tokenizer_mod
def patched_encode(self,text,num_vq,prompt=None,device='cpu'):
    input_ids_lst,attention_mask_lst,max_ids,max_attn,prompt_size=[],[],-1,-1,0
    if prompt is not None:
        assert prompt.size(0)==num_vq
        prompt_size=prompt.size(1)
    for t in text:
        x=self._tokenizer(t,return_tensors='pt',add_special_tokens=False,padding=True)
        input_ids_lst.append(x['input_ids'].squeeze_(0))
        attention_mask_lst.append(x['attention_mask'].squeeze_(0))
        ids_sz=input_ids_lst[-1].size(0)
        if ids_sz>max_ids: max_ids=ids_sz
        attn_sz=attention_mask_lst[-1].size(0)
        if attn_sz>max_attn: max_attn=attn_sz
    if prompt is not None:
        max_ids+=prompt_size; max_attn+=prompt_size
    input_ids=torch.zeros(len(input_ids_lst),max_ids,device=device,dtype=input_ids_lst[0].dtype)
    for i in range(len(input_ids_lst)):
        input_ids.narrow(0,i,1).narrow(1,max_ids-prompt_size-input_ids_lst[i].size(0),input_ids_lst[i].size(0)).copy_(input_ids_lst[i])
    attention_mask=torch.zeros(len(attention_mask_lst),max_attn,device=device,dtype=attention_mask_lst[0].dtype)
    for i in range(len(attention_mask_lst)):
        attn=attention_mask.narrow(0,i,1)
        attn.narrow(1,max_attn-prompt_size-attention_mask_lst[i].size(0),attention_mask_lst[i].size(0)).copy_(attention_mask_lst[i])
        if prompt_size>0: attn.narrow(1,max_attn-prompt_size,prompt_size).fill_(1)
    text_mask=attention_mask.bool()
    new_ids=input_ids.unsqueeze_(-1).expand(-1,-1,num_vq).clone()
    del input_ids
    if prompt_size>0:
        text_mask.narrow(1,max_ids-prompt_size,prompt_size).fill_(0)
        pt=prompt.t().unsqueeze_(0).expand(new_ids.size(0),-1,-1)
        new_ids.narrow(1,max_ids-prompt_size,prompt_size).copy_(pt)
        del pt
    return new_ids,attention_mask,text_mask
tokenizer_mod.Tokenizer.encode=patched_encode

import ChatTTS

ASSET_PARENT = "/root/autodl-tmp/voice-lab/workspace/tmp/voice-replies/chattts-hybrid"
OUT = os.environ.get("CHATITTS_OUT_DIR", "/root/autodl-tmp/voice-lab/output")
os.makedirs(OUT, exist_ok=True)

device = torch.device("cuda")
chat = ChatTTS.Chat()
chat.logger.setLevel(logging.ERROR)

print("LOADING...", flush=True)
r = chat.load(source="custom", custom_path=ASSET_PARENT, device=device, compile=False)
if not r:
    print("LOAD_FAILED", flush=True)
    sys.exit(1)
print("LOAD_OK", flush=True)

import base64
spk_emb_b64 = os.environ.get("CHATITTS_SPK_EMB_B64", "")
spk_emb_str = None
if spk_emb_b64:
    try:
        spk_emb_str = base64.b64decode(spk_emb_b64).decode("utf-8")
    except Exception as e:
        print(f"WARN: spk_emb decode failed: {e}", flush=True)

# --- Read all tuning params from env (with stable-matching defaults) ---
texts_input = [os.environ.get("CHATITTS_TEXT", "你好，我在。")]
temperature = float(os.environ.get("CHATITTS_TEMPERATURE", "0.3"))
top_p = float(os.environ.get("CHATITTS_TOP_P", "0.7"))
top_k = int(os.environ.get("CHATITTS_TOP_K", "20"))
max_new_token_env = os.environ.get("CHATITTS_MAX_NEW_TOKEN", "")
max_new_token = int(max_new_token_env) if max_new_token_env else None
infer_prompt_env = os.environ.get("CHATITTS_INFER_PROMPT", "")
infer_prompt = infer_prompt_env if infer_prompt_env else None

print(f"INFER: {texts_input} spk_emb={'provided' if spk_emb_str else 'None'}", flush=True)
print(f"PARAMS: temp={temperature} top_p={top_p} top_k={top_k} max_new={max_new_token} prompt={infer_prompt}", flush=True)

infer_params = ChatTTS.Chat.InferCodeParams(
    spk_emb=spk_emb_str,
    prompt=infer_prompt,
    temperature=temperature,
    top_P=top_p,
    top_K=top_k,
    max_new_token=max_new_token,
)
wavs = chat.infer(texts_input, use_decoder=True, params_infer_code=infer_params)
print(f"DONE_INFER type={type(wavs).__name__}", flush=True)

import soundfile as sf
items = wavs if isinstance(wavs, list) else [wavs]
out_tag = os.environ.get("CHATITTS_OUT_TAG", "gpu")
for idx,w in enumerate(items):
    if isinstance(w,np.ndarray): w=w.squeeze()
    else: w=w.cpu().detach().squeeze().numpy()
    p=os.path.join(OUT,f"out_{out_tag}_{idx}.wav")
    sf.write(p,w,24000)
    print(f"SAVED {p} {os.path.getsize(p)}B {len(w)/24000:.2f}s", flush=True)
print("SUCCESS", flush=True)
'''


def synthesize_on_remote(
    text: str,
    ssh_creds: dict,
    out_tag: str = "gpu",
    spk_emb: str | None = None,
    temperature: float = 0.3,
    top_p: float = 0.7,
    top_k: int = 20,
    max_new_token: int | None = None,
    infer_prompt: str = "[speed_5]",
    tempo: float = 1.0,
) -> str | None:
    """Run one TTS inference on the remote GPU machine.

    New params (v2) mirror local stable defaults:
      temperature=0.3, top_p=0.7, top_k=20,
      max_new_token=dynamic, infer_prompt="[speed_5]",
      tempo=1.10 (applied locally via ffmpeg after download).

    Returns:
        Local path to the downloaded WAV, or None on failure.
    """
    import paramiko

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        ssh_creds["host"],
        port=ssh_creds["port"],
        username=ssh_creds["user"],
        password=ssh_creds["password"],
        timeout=30,
    )

    def run_cmd(cmd: str, timeout: int = 120) -> tuple[int, str, str]:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout, get_pty=True)
        ec = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return ec, out, err

    try:
        # 1. Write the inference script to remote
        remote_script = f"{REMOTE_WORK_DIR}/_gpu_infer_{out_tag}.py"
        sftp = ssh.open_sftp()
        with sftp.open(remote_script, "w") as f:
            f.write(INFER_SCRIPT_TEMPLATE)
        sftp.close()

        # 2. Run with environment variables for text, tag, and optional spk_emb
        # Pass text via single-quoted env var to handle spaces/unicode
        # Escape single quotes in text by closing, adding escaped quote, reopening
        safe_text = text.replace("'", "'\\''")
        env_vars = (
            f"CHATITTS_TEXT='{safe_text}' "
            f"CHATITTS_OUT_TAG={out_tag} "
            f"CHATITTS_OUT_DIR={REMOTE_OUT_DIR} "
            f"CHATITTS_TEMPERATURE={temperature} "
            f"CHATITTS_TOP_P={top_p} "
            f"CHATITTS_TOP_K={top_k} "
            f"CHATITTS_INFER_PROMPT='{infer_prompt}'"
        )
        if max_new_token is not None:
            env_vars += f" CHATITTS_MAX_NEW_TOKEN={max_new_token}"
        if spk_emb is not None:
            # Pass spk_emb via base64 to avoid shell quoting issues with the raw b14 string
            import base64
            spk_emb_b64 = base64.b64encode(spk_emb.encode("utf-8")).decode("ascii")
            # The remote script will decode it back
            env_vars += f" CHATITTS_SPK_EMB_B64='{spk_emb_b64}'"
        else:
            env_vars += " CHATITTS_SPK_EMB=\"\""
        ec, out, err = run_cmd(
            f"cd {REMOTE_WORK_DIR} && {env_vars} {REMOTE_CONDA_PY} -u {remote_script} 2>&1",
            timeout=300,
        )

        if ec != 0:
            print(f"[GPU] Inference failed (exit={ec})", flush=True)
            return None

        # 3. Find the output file on remote
        expected_name = f"out_{out_tag}_0.wav"
        remote_wav = f"{REMOTE_OUT_DIR}/{expected_name}"

        sftp2 = ssh.open_sftp()
        try:
            sftp2.stat(remote_wav)
        except FileNotFoundError:
            print(f"[GPU] Output file not found: {remote_wav}", flush=True)
            sftp2.close()
            return None

        # 4. SFTP download
        os.makedirs(DEFAULT_OUT_DIR, exist_ok=True)
        local_wav = str(DEFAULT_OUT_DIR / f"chattts-gpu-{out_tag}.wav")
        sftp2.get(remote_wav, local_wav)
        sftp2.close()

        local_size = os.path.getsize(local_wav)
        print(f"[GPU] Downloaded: {local_wav} ({local_size}B)", flush=True)

        # 5. Apply tempo via ffmpeg locally (mirrors stable's finalize_audio)
        if abs(tempo - 1.0) >= 1e-6:
            import shutil
            import subprocess
            ffmpeg_path = shutil.which("ffmpeg")
            if ffmpeg_path:
                tempo_wav = local_wav.rsplit(".", 1)[0] + "_tempo.wav"
                factors = []
                remaining = tempo
                while remaining > 2.0:
                    factors.append("atempo=2.0")
                    remaining /= 2.0
                while remaining < 0.5:
                    factors.append("atempo=0.5")
                    remaining /= 0.5
                factors.append(f"atempo={remaining:.6f}")
                filter_str = ",".join(factors)
                subprocess.run(
                    [ffmpeg_path, "-y", "-i", local_wav, "-af", filter_str, tempo_wav],
                    check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                os.replace(tempo_wav, local_wav)
                print(f"[GPU] Applied tempo={tempo}: {local_wav}", flush=True)
            else:
                print(f"[GPU] WARN: ffmpeg not found, skipping tempo={tempo}", flush=True)

        print(f"[GPU] Final: {local_wav} ({os.path.getsize(local_wav)}B)", flush=True)
        return local_wav

    finally:
        ssh.close()


def recommend_max_new_token(text: str, explicit: int | None) -> int | None:
    """Mimic stable's recommendation logic."""
    if explicit is not None:
        return explicit
    if not text:
        return 384
    normalized = "".join(text.split())
    units = max(1, len(normalized))
    estimated = max(384, units * 12)
    rounded = ((estimated + 127) // 128) * 128
    return min(1024, rounded)


def main():
    config = load_presets()

    ap = argparse.ArgumentParser(description="ChatTTS GPU inference via SeetaCloud remote (v2 - enhanced params)")
    ap.add_argument("--text", default="", help="Text to synthesize")
    ap.add_argument("--tag", default="reply", help="Output tag (default: reply)")
    ap.add_argument("--preset", default=None, help="Preset name or alias (default: use presets.json defaultPreset)")
    ap.add_argument("--list-presets", action="store_true", help="List available presets and exit")
    ap.add_argument("--temperature", type=float, default=0.3, help="Sampling temperature (default: 0.3)")
    ap.add_argument("--top-p", type=float, default=0.7, help="Top-p sampling (default: 0.7)")
    ap.add_argument("--top-k", type=int, default=20, help="Top-k sampling (default: 20)")
    ap.add_argument("--max-new-token", type=int, default=None, help="Max new tokens (default: dynamic)")
    ap.add_argument("--infer-prompt", default="[speed_5]", help="InferCodeParams prompt string (default: [speed_5])")
    ap.add_argument("--tempo", type=float, default=float(config.get("defaultTempo", 1.10)),
                    help=f"Playback speed via atempo filter (default: {config.get('defaultTempo', 1.10)})")
    ap.add_argument("--no-tempo", action="store_true", help="Skip tempo adjustment")
    args = ap.parse_args()

    if args.list_presets:
        print("ChatTTS GPU presets (from presets.json):")
        for name, preset in config["presets"].items():
            alias_text = ""
            aliases = preset.get("aliases", [])
            if aliases:
                alias_text = f" | aliases: {', '.join(aliases)}"
            label = preset.get("label", "")
            mode = preset.get("mode", "spk-emb")
            print(f"  {name}: {label} | {mode}{alias_text}")
        sys.exit(0)

    if not args.text:
        print("Error: --text is required (use --list-presets to show available presets)", file=sys.stderr, flush=True)
        sys.exit(2)

    if not CRED_FILE.exists():
        print(f"[GPU] Credential file not found: {CRED_FILE}", file=sys.stderr, flush=True)
        sys.exit(1)

    preset_name, preset = resolve_preset(args.preset, config)
    spk_emb = load_spk_emb(preset)

    # Dynamic max_new_token matching stable's logic
    resolved_max_new_token = recommend_max_new_token(args.text, args.max_new_token)

    if spk_emb:
        print(f"[GPU] Using preset '{preset_name}' with spk_emb ({len(spk_emb)} chars)", flush=True)
    else:
        print(f"[GPU] Using preset '{preset_name}' (model-default, no spk_emb)", flush=True)

    print(f"[GPU] Params: temp={args.temperature} top_p={args.top_p} top_k={args.top_k} "
          f"max_new={resolved_max_new_token} prompt='{args.infer_prompt}' tempo={'skip' if args.no_tempo else args.tempo}", flush=True)

    creds = parse_credentials(CRED_FILE)
    result = synthesize_on_remote(
        args.text,
        creds,
        out_tag=args.tag,
        spk_emb=spk_emb,
        temperature=args.temperature,
        top_p=args.top_p,
        top_k=args.top_k,
        max_new_token=resolved_max_new_token,
        infer_prompt=args.infer_prompt,
        tempo=1.0 if args.no_tempo else args.tempo,
    )

    if result:
        print(result)  # stdout = contract path
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
