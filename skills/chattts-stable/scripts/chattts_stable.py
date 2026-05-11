#!/usr/bin/env python3
"""
Formal entry for the proven ChatTTS hybrid stable path.

Features:
- fixed hybrid asset path + compatibility patches
- preset-based voice switching via ChatTTS speaker embeddings
- default tempo matching the current accepted baseline
- wav/mp3 output
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import warnings
from datetime import datetime

warnings.filterwarnings("ignore")

SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = SKILL_DIR / "assets"
CONFIG_PATH = ASSETS_DIR / "presets.json"
WORKSPACE_DIR = SKILL_DIR.parent.parent
DEFAULT_OUT_DIR = WORKSPACE_DIR / "tmp" / "voice-replies"
VENV_PYTHON = Path("~/.local/share/openclaw-voice-venv311/bin/python3").expanduser()
SITE_PACKAGES = Path("~/.local/share/openclaw-voice-venv311/lib/python3.11/site-packages").expanduser()

if os.environ.get("CHATTTS_STABLE_BOOTSTRAPPED") != "1":
    if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
        env = os.environ.copy()
        env["CHATTTS_STABLE_BOOTSTRAPPED"] = "1"
        os.execve(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]], env)

if str(SITE_PACKAGES) not in sys.path:
    sys.path.insert(0, str(SITE_PACKAGES))


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_preset(name: str | None, config: dict) -> tuple[str, dict]:
    presets = config["presets"]
    wanted = (name or config.get("defaultPreset") or "default").strip()
    normalized = wanted.lower()

    if wanted in presets:
        return wanted, presets[wanted]

    alias_map = {}
    for preset_name, preset in presets.items():
        for alias in preset.get("aliases", []):
            alias_map[alias.lower()] = preset_name

    if normalized in alias_map:
        target = alias_map[normalized]
        return target, presets[target]

    available = ", ".join(presets.keys())
    raise SystemExit(f"Unknown preset: {wanted}. Available presets: {available}")


def choose_output_path(out_arg: str | None, fmt: str, preset_name: str) -> Path:
    if out_arg:
        out_path = Path(out_arg).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        return out_path

    DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = ".mp3" if fmt == "mp3" else ".wav"
    safe_preset = preset_name.replace("/", "-")
    return DEFAULT_OUT_DIR / f"chattts-stable-{safe_preset}-{ts}{suffix}"


def format_from_args(out_arg: str | None, fmt_arg: str) -> str:
    if fmt_arg != "auto":
        return fmt_arg
    if out_arg:
        ext = Path(out_arg).suffix.lower()
        if ext == ".wav":
            return "wav"
        if ext == ".mp3":
            return "mp3"
    return "mp3"


def read_text(text: str | None, text_file: str | None) -> str:
    if text and text_file:
        raise SystemExit("Use either --text or --text-file, not both")
    if text:
        return text.strip()
    if text_file:
        return Path(text_file).expanduser().read_text(encoding="utf-8").strip()
    raise SystemExit("Text is required. Use --text or --text-file")


def recommend_max_new_token(text: str, explicit: int | None) -> int:
    if explicit is not None:
        return explicit
    normalized = "".join(text.split())
    units = max(1, len(normalized))
    estimated = max(384, units * 12)
    rounded = ((estimated + 127) // 128) * 128
    return min(1024, rounded)


def patch_chattts_runtime() -> None:
    import torch
    import ChatTTS.utils.dl as dl_mod
    import ChatTTS.model.dvae as dvae_mod
    import ChatTTS.model.tokenizer as tokenizer_mod

    def always_pass(*args, **kwargs):
        return True

    dl_mod.check_all_assets = always_pass
    dl_mod.check_model = always_pass
    dl_mod.check_folder = always_pass

    orig_dvae_load = dvae_mod.DVAE.load_state_dict
    def patched_dvae_load_state_dict(self, state_dict, strict=True, assign=False):
        return orig_dvae_load(self, state_dict, strict=False, assign=assign)
    dvae_mod.DVAE.load_state_dict = patched_dvae_load_state_dict

    orig_decoder_load = dvae_mod.DVAEDecoder.load_state_dict
    def patched_decoder_load_state_dict(self, state_dict, strict=True, assign=False):
        return orig_decoder_load(self, state_dict, strict=False, assign=assign)
    dvae_mod.DVAEDecoder.load_state_dict = patched_decoder_load_state_dict

    def patched_encode(self, text, num_vq, prompt=None, device='cpu'):
        input_ids_lst = []
        attention_mask_lst = []
        max_input_ids_len = -1
        max_attention_mask_len = -1
        prompt_size = 0

        if prompt is not None:
            assert prompt.size(0) == num_vq, 'prompt dim 0 must equal to num_vq'
            prompt_size = prompt.size(1)

        for t in text:
            x = self._tokenizer(
                t, return_tensors='pt', add_special_tokens=False, padding=True
            )
            input_ids_lst.append(x['input_ids'].squeeze_(0))
            attention_mask_lst.append(x['attention_mask'].squeeze_(0))
            ids_sz = input_ids_lst[-1].size(0)
            if ids_sz > max_input_ids_len:
                max_input_ids_len = ids_sz
            attn_sz = attention_mask_lst[-1].size(0)
            if attn_sz > max_attention_mask_len:
                max_attention_mask_len = attn_sz

        if prompt is not None:
            max_input_ids_len += prompt_size
            max_attention_mask_len += prompt_size

        input_ids = torch.zeros(
            len(input_ids_lst),
            max_input_ids_len,
            device=device,
            dtype=input_ids_lst[0].dtype,
        )
        for i in range(len(input_ids_lst)):
            input_ids.narrow(0, i, 1).narrow(
                1,
                max_input_ids_len - prompt_size - input_ids_lst[i].size(0),
                input_ids_lst[i].size(0),
            ).copy_(input_ids_lst[i])

        attention_mask = torch.zeros(
            len(attention_mask_lst),
            max_attention_mask_len,
            device=device,
            dtype=attention_mask_lst[0].dtype,
        )
        for i in range(len(attention_mask_lst)):
            attn = attention_mask.narrow(0, i, 1)
            attn.narrow(
                1,
                max_attention_mask_len - prompt_size - attention_mask_lst[i].size(0),
                attention_mask_lst[i].size(0),
            ).copy_(attention_mask_lst[i])
            if prompt_size > 0:
                attn.narrow(
                    1,
                    max_attention_mask_len - prompt_size,
                    prompt_size,
                ).fill_(1)

        text_mask = attention_mask.bool()
        new_input_ids = input_ids.unsqueeze_(-1).expand(-1, -1, num_vq).clone()
        del input_ids

        if prompt_size > 0:
            text_mask.narrow(1, max_input_ids_len - prompt_size, prompt_size).fill_(0)
            prompt_t = prompt.t().unsqueeze_(0).expand(new_input_ids.size(0), -1, -1)
            new_input_ids.narrow(
                1,
                max_input_ids_len - prompt_size,
                prompt_size,
            ).copy_(prompt_t)
            del prompt_t

        return new_input_ids, attention_mask, text_mask

    tokenizer_mod.Tokenizer.encode = patched_encode


def synthesize_wav(
    *,
    text: str,
    out_wav: Path,
    asset_dir: Path,
    spk_emb: str | None,
    temperature: float,
    top_p: float,
    top_k: int,
    max_new_token: int,
) -> None:
    patch_chattts_runtime()

    import numpy as np
    import soundfile as sf
    import torch
    import ChatTTS

    device = torch.device("cpu")
    chat = ChatTTS.Chat()
    chat.logger.setLevel(logging.INFO)

    print("=" * 60)
    print("ChatTTS stable | CPU | hybrid assets")
    print("Assets:", asset_dir)
    print("Text:", text)
    print("Speaker:", "custom-spk-emb" if spk_emb else "model-default")
    print("=" * 60)

    print("\n[1/3] Loading model...")
    result = chat.load(
        source="custom",
        custom_path=str(asset_dir),
        device=device,
        compile=False,
        use_flash_attn=False,
    )
    print("Load result:", result)
    if not result:
        raise SystemExit(1)

    print("\n[2/3] Running inference...")
    params = chat.InferCodeParams(
        temperature=temperature,
        top_P=top_p,
        top_K=top_k,
        max_new_token=max_new_token,
        spk_emb=spk_emb or None,
    )
    wavs = chat.infer(
        [text],
        skip_refine_text=True,
        use_decoder=True,
        do_text_normalization=False,
        do_homophone_replacement=False,
        params_infer_code=params,
    )

    print("\n[3/3] Saving wav...")
    wav = wavs[0] if isinstance(wavs, list) else wavs
    if isinstance(wav, np.ndarray) and wav.ndim > 1:
        wav = wav[0]
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_wav), wav, 24000)
    print("Saved wav:", out_wav)


def build_atempo_filter(tempo: float) -> str:
    if tempo <= 0:
        raise SystemExit("--tempo must be > 0")
    factors = []
    remaining = tempo
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ",".join(f"atempo={factor:.6f}" for factor in factors)


def resolve_ffmpeg() -> str | None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    candidates = [
        Path("~/.local/share/openclaw-audio-tools/node_modules/@ffmpeg-installer/linux-x64/ffmpeg").expanduser(),
        Path("/usr/bin/ffmpeg"),
        Path("/usr/local/bin/ffmpeg"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def finalize_audio(temp_wav: Path, out_path: Path, fmt: str, tempo: float, bitrate: str) -> None:
    ffmpeg = resolve_ffmpeg()
    if fmt == "wav" and abs(tempo - 1.0) < 1e-6:
        shutil.copyfile(temp_wav, out_path)
        return

    if ffmpeg is None:
        raise SystemExit("ffmpeg not found in PATH or local fallback path; cannot apply tempo or encode mp3")

    filters = []
    if abs(tempo - 1.0) >= 1e-6:
        filters.append(build_atempo_filter(tempo))
    filter_arg = ",".join(filters) if filters else None

    cmd = [ffmpeg, "-y", "-i", str(temp_wav)]
    if filter_arg:
        cmd += ["-af", filter_arg]
    if fmt == "mp3":
        cmd += ["-acodec", "libmp3lame", "-b:a", bitrate, str(out_path)]
    else:
        cmd += [str(out_path)]

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def list_presets(config: dict) -> None:
    print("ChatTTS stable presets:")
    for name, preset in config["presets"].items():
        alias_text = ""
        aliases = preset.get("aliases", [])
        if aliases:
            alias_text = f" | aliases: {', '.join(aliases)}"
        label = preset.get("label", "")
        mode = preset.get("mode", "spk-emb")
        print(f"- {name}: {label} | {mode}{alias_text}")
    print(f"default tempo: {config.get('defaultTempo', 1.0)}")


def main() -> None:
    config = load_config()

    ap = argparse.ArgumentParser(description="ChatTTS hybrid stable formal entry")
    ap.add_argument("--list-presets", action="store_true", help="show available presets and exit")
    ap.add_argument("--preset", "--voice", dest="preset", default=config.get("defaultPreset", "default"), help="preset name or alias")
    ap.add_argument("--text", default="", help="text to synthesize")
    ap.add_argument("--text-file", default="", help="read text from file")
    ap.add_argument("--out", default="", help="output path; default writes into tmp/voice-replies/")
    ap.add_argument("--format", choices=["auto", "wav", "mp3"], default="auto")
    ap.add_argument("--tempo", type=float, default=float(config.get("defaultTempo", 1.0)))
    ap.add_argument("--bitrate", default="160k")
    ap.add_argument("--asset-dir", default=config.get("assetDir", "~/.openclaw/workspace/tmp/voice-replies/chattts-hybrid"))
    ap.add_argument("--temperature", type=float, default=0.3)
    ap.add_argument("--top-p", type=float, default=0.7)
    ap.add_argument("--top-k", type=int, default=20)
    ap.add_argument("--max-new-token", type=int, default=None)
    args = ap.parse_args()

    if args.list_presets:
        list_presets(config)
        return

    text = read_text(args.text, args.text_file)
    preset_name, preset = resolve_preset(args.preset, config)
    fmt = format_from_args(args.out, args.format)
    out_path = choose_output_path(args.out or None, fmt, preset_name)
    asset_dir = Path(args.asset_dir).expanduser()

    spk_emb = None
    spk_file = preset.get("spkEmbFile")
    if spk_file:
        spk_emb = (ASSETS_DIR / spk_file).read_text(encoding="utf-8").strip()

    max_new_token = recommend_max_new_token(text, args.max_new_token)

    with tempfile.TemporaryDirectory(prefix="chattts-stable-") as tmpdir:
        temp_wav = Path(tmpdir) / f"{preset_name}.wav"
        synthesize_wav(
            text=text,
            out_wav=temp_wav,
            asset_dir=asset_dir,
            spk_emb=spk_emb,
            temperature=args.temperature,
            top_p=args.top_p,
            top_k=args.top_k,
            max_new_token=max_new_token,
        )
        finalize_audio(temp_wav, out_path, fmt, args.tempo, args.bitrate)

    print("Final output:", out_path)


if __name__ == "__main__":
    main()
