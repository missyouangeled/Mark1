#!/usr/bin/env python3
"""ChatTTS minimal GPU inference using local assets."""
import os, sys, time, logging
import warnings
warnings.filterwarnings("ignore")

os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import torch
print("torch:", torch.__version__, file=sys.stderr, flush=True)
print("cuda:", torch.cuda.is_available(), file=sys.stderr, flush=True)
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0), file=sys.stderr, flush=True)

import ChatTTS
print("ChatTTS imported", file=sys.stderr, flush=True)

ASSET_DIR = "/root/autodl-tmp/voice-lab/workspace/tmp/voice-replies/chattts-hybrid/asset"
output_dir = "/root/autodl-tmp/voice-lab/output"
os.makedirs(output_dir, exist_ok=True)

device = torch.device("cuda")
chat = ChatTTS.Chat()
chat.logger.setLevel(logging.WARNING)

print("Loading from local:", ASSET_DIR, file=sys.stderr, flush=True)

try:
    result = chat.load(
        source="custom",
        custom_path=ASSET_DIR,
        device=device,
        compile=False,
    )
except Exception as e:
    print("Load FAILED:", e, file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

print("Load result:", result, file=sys.stderr, flush=True)

texts = ["你好，我在。"]
print("Inferring:", texts, file=sys.stderr, flush=True)

try:
    wavs = chat.infer(texts, use_decoder=True)
except Exception as e:
    print("Infer FAILED:", e, file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

print("Inferred type:", type(wavs).__name__, file=sys.stderr, flush=True)

import torchaudio
saved = False
if isinstance(wavs, list):
    for idx, w in enumerate(wavs):
        if hasattr(w, "cpu"): w = w.cpu()
        if hasattr(w, "detach"): w = w.detach()
        w = w.squeeze()
        if w.ndim == 1: w = w.unsqueeze(0)
        p = os.path.join(output_dir, "smoke_local_" + str(idx) + ".wav")
        torchaudio.save(p, w, 24000)
        dur = w.shape[-1]/24000.0
        sz = os.path.getsize(p)
        print("SAVED", p, ":", sz, "B", round(dur, 2), "s", file=sys.stderr, flush=True)
        saved = True
elif hasattr(wavs, "shape"):
    w = wavs
    if hasattr(w, "cpu"): w = w.cpu()
    if hasattr(w, "detach"): w = w.detach()
    w = w.squeeze()
    if w.ndim == 1: w = w.unsqueeze(0)
    p = os.path.join(output_dir, "smoke_local_0.wav")
    torchaudio.save(p, w, 24000)
    dur = w.shape[-1]/24000.0
    sz = os.path.getsize(p)
    print("SAVED", p, ":", sz, "B", round(dur, 2), "s", file=sys.stderr, flush=True)
    saved = True

if saved:
    print("=== SMOKE SUCCESS ===", file=sys.stderr, flush=True)
else:
    print("=== SMOKE FAIL ===", file=sys.stderr, flush=True)
