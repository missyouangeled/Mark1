"""Fix save to use soundfile instead of torchaudio."""
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

min_script = r'''import os, sys, logging, warnings, numpy as np
warnings.filterwarnings("ignore")
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import torch

import ChatTTS.utils.dl as dl_mod
def always_pass(*a, **kw): return True
dl_mod.check_all_assets = always_pass
dl_mod.check_model = always_pass
dl_mod.check_folder = always_pass

import ChatTTS.model.dvae as dvae_mod
import ChatTTS.model.tokenizer as tokenizer_mod

orig_dvae = dvae_mod.DVAE.load_state_dict
def pdvae(self, sd, strict=True, assign=False):
    return orig_dvae(self, sd, strict=False, assign=assign)
dvae_mod.DVAE.load_state_dict = pdvae

orig_dec = dvae_mod.DVAEDecoder.load_state_dict
def pdec(self, sd, strict=True, assign=False):
    return orig_dec(self, sd, strict=False, assign=assign)
dvae_mod.DVAEDecoder.load_state_dict = pdec

def patched_encode(self, text, num_vq, prompt=None, device='cpu'):
    input_ids_lst, attention_mask_lst = [], []
    max_ids, max_attn, prompt_size = -1, -1, 0
    if prompt is not None:
        assert prompt.size(0) == num_vq
        prompt_size = prompt.size(1)
    for t in text:
        x = self._tokenizer(t, return_tensors='pt', add_special_tokens=False, padding=True)
        input_ids_lst.append(x['input_ids'].squeeze_(0))
        attention_mask_lst.append(x['attention_mask'].squeeze_(0))
        ids_sz = input_ids_lst[-1].size(0)
        if ids_sz > max_ids: max_ids = ids_sz
        attn_sz = attention_mask_lst[-1].size(0)
        if attn_sz > max_attn: max_attn = attn_sz
    if prompt is not None:
        max_ids += prompt_size; max_attn += prompt_size
    input_ids = torch.zeros(len(input_ids_lst), max_ids, device=device, dtype=input_ids_lst[0].dtype)
    for i in range(len(input_ids_lst)):
        input_ids.narrow(0,i,1).narrow(1,max_ids-prompt_size-input_ids_lst[i].size(0),input_ids_lst[i].size(0)).copy_(input_ids_lst[i])
    attention_mask = torch.zeros(len(attention_mask_lst), max_attn, device=device, dtype=attention_mask_lst[0].dtype)
    for i in range(len(attention_mask_lst)):
        attn = attention_mask.narrow(0,i,1)
        attn.narrow(1,max_attn-prompt_size-attention_mask_lst[i].size(0),attention_mask_lst[i].size(0)).copy_(attention_mask_lst[i])
        if prompt_size > 0:
            attn.narrow(1,max_attn-prompt_size,prompt_size).fill_(1)
    text_mask = attention_mask.bool()
    new_ids = input_ids.unsqueeze_(-1).expand(-1,-1,num_vq).clone()
    del input_ids
    if prompt_size > 0:
        text_mask.narrow(1,max_ids-prompt_size,prompt_size).fill_(0)
        pt = prompt.t().unsqueeze_(0).expand(new_ids.size(0),-1,-1)
        new_ids.narrow(1,max_ids-prompt_size,prompt_size).copy_(pt)
        del pt
    return new_ids, attention_mask, text_mask
tokenizer_mod.Tokenizer.encode = patched_encode

import ChatTTS

ASSET_PARENT = "/root/autodl-tmp/voice-lab/workspace/tmp/voice-replies/chattts-hybrid"
OUT = "/root/autodl-tmp/voice-lab/output"
os.makedirs(OUT, exist_ok=True)

device = torch.device("cuda")
chat = ChatTTS.Chat()
chat.logger.setLevel(logging.ERROR)

print("Loading...", flush=True)
r = chat.load(source="custom", custom_path=ASSET_PARENT, device=device, compile=False)
print(f"Load: {r}", flush=True)
if not r: sys.exit(1)

texts = ["你好，我在。"]
print(f"Infer: {texts}", flush=True)
wavs = chat.infer(texts, use_decoder=True)
print(f"Output type: {type(wavs).__name__}", flush=True)

import soundfile as sf

items = wavs if isinstance(wavs, list) else [wavs]
for idx, w in enumerate(items):
    if isinstance(w, np.ndarray):
        w = w.squeeze()
    elif hasattr(w, "cpu"):
        w = w.cpu().detach().squeeze().numpy()
    p = os.path.join(OUT, f"smoke_gpu_{idx}.wav")
    sf.write(p, w, 24000)
    sz = os.path.getsize(p)
    dur = len(w) / 24000.0
    print(f"SAVED {p}: {sz}B {dur:.2f}s", flush=True)

print("SUCCESS", flush=True)
'''

print("Writing script...", flush=True)
ec, out, err = run(f"cat > {WORK_DIR}/smoke_gpu.py << 'SCRIPTEOF'\n{min_script}\nSCRIPTEOF\n", 10)
print(f"Write: ec={ec}", flush=True)

print("\n=== Running ===", flush=True)
ec, out, err = run(f"cd {WORK_DIR} && {PY} -u smoke_gpu.py 2>&1", timeout=600)
print(f"Exit={ec}", flush=True)
for line in (out + err).split('\n'):
    print(f"  {line}", flush=True)

print("\n=== Output check ===", flush=True)
ec2, out2, err2 = run(f"ls -la {WORK_DIR}/output/smoke_gpu* 2>/dev/null; ls -la {WORK_DIR}/output/", 10)
print(out2.strip() if out2.strip() else "(empty)", flush=True)

# GPU memory after inference
print("\n=== GPU memory after ===", flush=True)
ec3, out3, err3 = run("nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader 2>/dev/null", 10)
print(out3.strip(), flush=True)

ssh.close()
print("\n=== DONE ===", flush=True)
