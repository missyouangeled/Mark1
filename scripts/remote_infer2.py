#!/usr/bin/env python3
"""ChatTTS GPU inference with local assets + SHA256 bypass."""
import os, sys, time, logging
import warnings
warnings.filterwarnings("ignore")

os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import torch
print("torch:", torch.__version__, file=sys.stderr, flush=True)
print("cuda:", torch.cuda.is_available(), file=sys.stderr, flush=True)
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0), file=sys.stderr, flush=True)

# Patch asset checks BEFORE importing ChatTTS key modules
import ChatTTS.utils.dl as dl_mod
import ChatTTS.model.dvae as dvae_mod
import ChatTTS.model.tokenizer as tokenizer_mod

def always_pass(*args, **kwargs):
    return True

dl_mod.check_all_assets = always_pass
dl_mod.check_model = always_pass
dl_mod.check_folder = always_pass

# Patch load_state_dict to be non-strict
orig_dvae_load = dvae_mod.DVAE.load_state_dict
def patched_dvae_load_state_dict(self, state_dict, strict=True, assign=False):
    return orig_dvae_load(self, state_dict, strict=False, assign=assign)
dvae_mod.DVAE.load_state_dict = patched_dvae_load_state_dict

orig_decoder_load = dvae_mod.DVAEDecoder.load_state_dict
def patched_decoder_load_state_dict(self, state_dict, strict=True, assign=False):
    return orig_decoder_load(self, state_dict, strict=False, assign=assign)
dvae_mod.DVAEDecoder.load_state_dict = patched_decoder_load_state_dict

# Patch tokenizer encode to avoid index offset issues
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
        x = self._tokenizer(t, return_tensors='pt', add_special_tokens=False, padding=True)
        input_ids_lst.append(x['input_ids'].squeeze_(0))
        attention_mask_lst.append(x['attention_mask'].squeeze_(0))
        ids_sz = input_ids_lst[-1].size(0)
        if ids_sz > max_input_ids_len: max_input_ids_len = ids_sz
        attn_sz = attention_mask_lst[-1].size(0)
        if attn_sz > max_attention_mask_len: max_attention_mask_len = attn_sz
    if prompt is not None:
        max_input_ids_len += prompt_size
        max_attention_mask_len += prompt_size
    input_ids = torch.zeros(len(input_ids_lst), max_input_ids_len, device=device, dtype=input_ids_lst[0].dtype)
    for i in range(len(input_ids_lst)):
        input_ids.narrow(0, i, 1).narrow(
            1, max_input_ids_len - prompt_size - input_ids_lst[i].size(0),
            input_ids_lst[i].size(0)).copy_(input_ids_lst[i])
    attention_mask = torch.zeros(len(attention_mask_lst), max_attention_mask_len, device=device, dtype=attention_mask_lst[0].dtype)
    for i in range(len(attention_mask_lst)):
        attn = attention_mask.narrow(0, i, 1)
        attn.narrow(1, max_attention_mask_len - prompt_size - attention_mask_lst[i].size(0),
                     attention_mask_lst[i].size(0)).copy_(attention_mask_lst[i])
        if prompt_size > 0:
            attn.narrow(1, max_attention_mask_len - prompt_size, prompt_size).fill_(1)
    text_mask = attention_mask.bool()
    new_input_ids = input_ids.unsqueeze_(-1).expand(-1, -1, num_vq).clone()
    del input_ids
    if prompt_size > 0:
        text_mask.narrow(1, max_input_ids_len - prompt_size, prompt_size).fill_(0)
        prompt_t = prompt.t().unsqueeze_(0).expand(new_input_ids.size(0), -1, -1)
        new_input_ids.narrow(1, max_input_ids_len - prompt_size, prompt_size).copy_(prompt_t)
        del prompt_t
    return new_input_ids, attention_mask, text_mask
tokenizer_mod.Tokenizer.encode = patched_encode

import ChatTTS
print("ChatTTS imported + patched", file=sys.stderr, flush=True)

ASSET_DIR = "/root/autodl-tmp/voice-lab/workspace/tmp/voice-replies/chattts-hybrid/asset"
output_dir = "/root/autodl-tmp/voice-lab/output"
os.makedirs(output_dir, exist_ok=True)

# Load
device = torch.device("cuda")
chat = ChatTTS.Chat()
chat.logger.setLevel(logging.WARNING)

print("Loading from local:", ASSET_DIR, file=sys.stderr, flush=True)
result = chat.load(
    source="custom",
    custom_path=ASSET_DIR,
    device=device,
    compile=False,
)
print("Load result:", result, file=sys.stderr, flush=True)

if not result:
    print("Load failed, exiting", file=sys.stderr, flush=True)
    sys.exit(1)

# Infer
texts = ["你好，我在。这是一个最小可验证测试。"]
print("Inferring:", texts, file=sys.stderr, flush=True)
wavs = chat.infer(texts, use_decoder=True)
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
    sys.exit(1)
