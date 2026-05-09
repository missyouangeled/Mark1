#!/usr/bin/env python3
# 适用机器：公司（Linux）
# 系统 / OS：Linux
# 用途：为当前机器上的 OpenClaw 提供本地 NVIDIA TTS / ASR bridge 服务。
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tempfile
import wave
from functools import lru_cache
from pathlib import Path
from typing import Optional

import riva.client
import urllib.request
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse, Response

OPENCLAW_CONFIG = Path.home() / '.openclaw' / 'openclaw.json'
DEFAULT_BIND = '127.0.0.1'
DEFAULT_PORT = 18890
DEFAULT_TTS_SAMPLE_RATE = 22050
DEFAULT_ASR_SAMPLE_RATE = 16000
DEFAULT_TTS_MODEL = 'nvidia/magpie-tts-multilingual'
DEFAULT_ASR_MODEL = 'nvidia/parakeet-1_1b-rnnt-multilingual-asr'
DEFAULT_ASR_MODEL_ZH = 'nvidia/whisper-large-v3'  # Chinese ASR: whisper-large-v3 is most accurate for short Chinese phrases
DEFAULT_VOICE = 'aria'
DEFAULT_VOICE_ZH = 'aria'  # Chinese defaults also use Aria voice
FALLBACK_FFMPEG = Path.home() / '.local/share/openclaw-audio-tools/node_modules/@ffmpeg-installer/linux-x64/ffmpeg'
NVCF_FUNCTIONS_URL = 'https://api.nvcf.nvidia.com/v2/nvcf/functions?visibility=public'

TTS_MODEL_MAP = {
    'nvidia/magpie-tts-multilingual': 'ai-magpie-tts-multilingual',
    'magpie-tts-multilingual': 'ai-magpie-tts-multilingual',
}

ASR_MODEL_MAP = {
    'nvidia/parakeet-1_1b-rnnt-multilingual-asr': 'ai-parakeet-1_1b-rnnt-multilingual-asr',
    'parakeet-1_1b-rnnt-multilingual-asr': 'ai-parakeet-1_1b-rnnt-multilingual-asr',
    'nvidia/parakeet-ctc-1_1b-asr': 'ai-parakeet-ctc-1_1b-asr',
    'parakeet-ctc-1_1b-asr': 'ai-parakeet-ctc-1_1b-asr',
    'nvidia/parakeet-ctc-0_6b-zh-cn': 'ai-parakeet-ctc-0_6b-zh-cn',
    'parakeet-ctc-0_6b-zh-cn': 'ai-parakeet-ctc-0_6b-zh-cn',
    'nvidia/parakeet-ctc-0_6b-zh-tw': 'ai-parakeet-ctc-0_6b-zh-tw',
    'parakeet-ctc-0_6b-zh-tw': 'ai-parakeet-ctc-0_6b-zh-tw',
    'nvidia/canary-1b-asr': 'ai-canary-1b-asr',
    'canary-1b-asr': 'ai-canary-1b-asr',
    'nvidia/whisper-large-v3': 'ai-whisper-large-v3',
    'whisper-large-v3': 'ai-whisper-large-v3',
}

VOICE_ALIASES = {
    'aria': 'Magpie-Multilingual.EN-US.Aria',
    'diego': 'Magpie-Multilingual.ES-US.Diego',
    'louise': 'Magpie-Multilingual.FR-FR.Louise',
    'sofia': 'Magpie-Multilingual.EN-US.Aria',
}

VOICE_LANGUAGE_MAP = {
    'Magpie-Multilingual.EN-US.Aria': 'en-US',
    'Magpie-Multilingual.ES-US.Diego': 'es-US',
    'Magpie-Multilingual.FR-FR.Louise': 'fr-FR',
}

# Chinese language tags recognized for automatic ASR model selection
ZH_LANGUAGE_TAGS = {'zh-CN', 'zh-TW', 'zh-HK', 'zh', 'cmn', 'yue'}

app = FastAPI(title='OpenClaw NVIDIA Audio Bridge', version='0.1.0')


def load_openclaw_config() -> dict:
    if not OPENCLAW_CONFIG.exists():
        raise RuntimeError(f'OpenClaw 配置不存在: {OPENCLAW_CONFIG}')
    return json.loads(OPENCLAW_CONFIG.read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def get_nvidia_api_key() -> str:
    cfg = load_openclaw_config()
    # Check models.providers.nvidia.apiKey first (where OpenClaw stores it)
    api_key = (((cfg.get('models') or {}).get('providers') or {}).get('nvidia') or {}).get('apiKey') or ''
    if not api_key:
        # Fallback to providers.nvidia.apiKey
        api_key = (((cfg.get('providers') or {}).get('nvidia') or {}).get('apiKey') or '').strip()
    if not api_key:
        raise RuntimeError('OpenClaw models.providers.nvidia.apiKey 未配置。')
    return api_key


@lru_cache(maxsize=1)
def get_ffmpeg_path() -> str:
    explicit = os.environ.get('OPENCLAW_FFMPEG', '').strip()
    if explicit and Path(explicit).exists():
        return explicit
    if FALLBACK_FFMPEG.exists():
        return str(FALLBACK_FFMPEG)
    found = shutil.which('ffmpeg')
    if found:
        return found
    raise RuntimeError('找不到 ffmpeg，无法进行音频转码。可设置 OPENCLAW_FFMPEG。')


@lru_cache(maxsize=1)
def get_public_function_ids() -> dict[str, str]:
    req = urllib.request.Request(NVCF_FUNCTIONS_URL, headers={'Authorization': f'Bearer {get_nvidia_api_key()}'})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    result: dict[str, str] = {}
    for entry in payload.get('functions', []):
        name = (entry.get('name') or '').strip()
        status = (entry.get('status') or '').strip().upper()
        fn_id = (entry.get('id') or '').strip()
        if name and fn_id and status in {'ACTIVE', 'DEGRADING'}:
            result[name] = fn_id
    return result


def resolve_function_id(model: str, kind: str) -> str:
    model = (model or '').strip()
    mapping = TTS_MODEL_MAP if kind == 'tts' else ASR_MODEL_MAP
    function_name = mapping.get(model)
    if not function_name:
        supported = ', '.join(sorted(mapping))
        raise HTTPException(status_code=400, detail=f'暂不支持的 {kind.upper()} 模型: {model or "<empty>"}。可用: {supported}')
    fn_id = get_public_function_ids().get(function_name)
    if not fn_id:
        raise HTTPException(status_code=502, detail=f'NVIDIA 公共函数当前不可用: {function_name}')
    return fn_id


def resolve_asr_model_and_function_id(model: str, language: str) -> tuple[str, str]:
    """
    Resolve ASR function ID with automatic fallback.
    
    If the requested model is unavailable for the given language (common for
    Chinese on NVCF where only canary-1b works in offline mode),
    fall back to canary-1b for Chinese languages.
    Returns (resolved_model_name, function_id).
    """
    model = (model or '').strip()
    # First try the requested model normally
    function_name = ASR_MODEL_MAP.get(model)
    if function_name:
        fn_id = get_public_function_ids().get(function_name)
        if fn_id:
            return model, fn_id
    
    # Model not found or not active: auto-fallback for Chinese
    lang = (language or '').strip().lower()
    is_chinese = any(lang.startswith(zh.lower()) for zh in ZH_LANGUAGE_TAGS) or lang in ZH_LANGUAGE_TAGS
    if is_chinese:
        fallback_model = DEFAULT_ASR_MODEL_ZH
        fallback_fn_name = ASR_MODEL_MAP.get(fallback_model)
        if fallback_fn_name:
            fn_id = get_public_function_ids().get(fallback_fn_name)
            if fn_id:
                return fallback_model, fn_id
        raise HTTPException(status_code=502, detail=f'中文ASR模型均不可用。请检查网络或NVCF服务状态。')
    
    # For non-Chinese languages, give the original error
    supported = ', '.join(sorted(ASR_MODEL_MAP))
    raise HTTPException(status_code=400, detail=f'暂不支持的 ASR 模型: {model or "<empty>"}。可用: {supported}')


def make_auth(function_id: str) -> riva.client.Auth:
    return riva.client.Auth(
        uri='grpc.nvcf.nvidia.com:443',
        use_ssl=True,
        metadata_args=[
            ['function-id', function_id],
            ['authorization', f'Bearer {get_nvidia_api_key()}'],
        ],
    )


def normalize_voice(voice: Optional[str]) -> str:
    raw = (voice or DEFAULT_VOICE).strip()
    if not raw:
        raw = DEFAULT_VOICE
    return VOICE_ALIASES.get(raw.lower(), raw)


def wrap_pcm_as_wav(raw_pcm: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw_pcm)
    return buf.getvalue()


def convert_wav_to_mp3(wav_bytes: bytes) -> bytes:
    ffmpeg = get_ffmpeg_path()
    with tempfile.TemporaryDirectory(prefix='openclaw-nvidia-tts-') as tmpdir:
        wav_path = Path(tmpdir) / 'input.wav'
        mp3_path = Path(tmpdir) / 'output.mp3'
        wav_path.write_bytes(wav_bytes)
        subprocess.run([
            ffmpeg, '-y', '-i', str(wav_path), '-vn', '-acodec', 'libmp3lame', '-b:a', '128k', str(mp3_path)
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return mp3_path.read_bytes()


def convert_any_audio_to_wav_bytes(source_bytes: bytes, suffix: str = '.bin') -> tuple[bytes, int]:
    ffmpeg = get_ffmpeg_path()
    with tempfile.TemporaryDirectory(prefix='openclaw-nvidia-asr-') as tmpdir:
        src = Path(tmpdir) / f'input{suffix or ".bin"}'
        out = Path(tmpdir) / 'normalized.wav'
        src.write_bytes(source_bytes)
        subprocess.run([
            ffmpeg, '-y', '-i', str(src),
            '-ac', '1',
            '-ar', str(DEFAULT_ASR_SAMPLE_RATE),
            '-f', 'wav', str(out),
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        wav_bytes = out.read_bytes()
        with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
            sample_rate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
        return frames, sample_rate


@app.get('/health')
def health() -> dict:
    return {
        'ok': True,
        'service': 'openclaw-nvidia-audio-bridge',
        'port': int(os.environ.get('OPENCLAW_NVIDIA_AUDIO_BRIDGE_PORT', DEFAULT_PORT)),
    }


@app.post('/v1/audio/speech')
def speech(body: dict) -> Response:
    model = (body.get('model') or DEFAULT_TTS_MODEL).strip()
    text = (body.get('input') or '').strip()
    if not text:
        raise HTTPException(status_code=400, detail='缺少 input。')
    response_format = (body.get('response_format') or 'mp3').strip().lower()
    voice_name = normalize_voice(body.get('voice'))
    language_code = (body.get('language') or VOICE_LANGUAGE_MAP.get(voice_name) or 'en-US').strip()
    sample_rate = int(body.get('sample_rate') or DEFAULT_TTS_SAMPLE_RATE)

    function_id = resolve_function_id(model, 'tts')
    service = riva.client.SpeechSynthesisService(make_auth(function_id))
    try:
        raw_pcm = service.synthesize(
            text=text,
            voice_name=voice_name,
            language_code=language_code,
            sample_rate_hz=sample_rate,
        ).audio
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f'NVIDIA TTS 调用失败: {exc}') from exc

    wav_bytes = wrap_pcm_as_wav(raw_pcm, sample_rate)
    if response_format in {'wav', 'wave'}:
        return Response(content=wav_bytes, media_type='audio/wav')
    if response_format in {'pcm', 's16le'}:
        return Response(content=raw_pcm, media_type='application/octet-stream')
    if response_format == 'mp3':
        try:
            mp3_bytes = convert_wav_to_mp3(wav_bytes)
            return Response(content=mp3_bytes, media_type='audio/mpeg')
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f'音频转 mp3 失败: {exc}') from exc
    raise HTTPException(status_code=400, detail='仅支持 response_format=mp3|wav|pcm')


@app.post('/v1/audio/transcriptions')
async def transcriptions(
    file: UploadFile = File(...),
    model: str = Form(DEFAULT_ASR_MODEL),
    language: str = Form('en-US'),
    response_format: str = Form('json'),
) -> Response:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail='上传文件为空。')
    suffix = Path(file.filename or '').suffix or '.bin'
    try:
        raw_pcm, sample_rate = convert_any_audio_to_wav_bytes(data, suffix=suffix)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f'音频解码失败: {exc}') from exc

    resolved_model, function_id = resolve_asr_model_and_function_id(model, language)
    service = riva.client.ASRService(make_auth(function_id))
    try:
        config = riva.client.RecognitionConfig(
            encoding=riva.client.AudioEncoding.LINEAR_PCM,
            sample_rate_hertz=sample_rate,
            language_code=(language or '').strip(),
            max_alternatives=1,
            audio_channel_count=1,
            enable_automatic_punctuation=True,
        )
        result = service.offline_recognize(raw_pcm, config)
    except Exception as exc:  # noqa: BLE001
        # One more fallback attempt for Chinese: if the resolved model fails at runtime
        lang = (language or '').strip().lower()
        is_chinese = any(lang.startswith(zh.lower()) for zh in ZH_LANGUAGE_TAGS) or lang in ZH_LANGUAGE_TAGS
        if is_chinese and resolved_model != DEFAULT_ASR_MODEL_ZH:
            try:
                fallback_fn_name = ASR_MODEL_MAP.get(DEFAULT_ASR_MODEL_ZH)
                if fallback_fn_name:
                    fn_id2 = get_public_function_ids().get(fallback_fn_name)
                    if fn_id2:
                        service2 = riva.client.ASRService(make_auth(fn_id2))
                        result = service2.offline_recognize(raw_pcm, config)
                        resolved_model = DEFAULT_ASR_MODEL_ZH
                    else:
                        raise
                else:
                    raise
            except Exception:
                raise HTTPException(status_code=502, detail=f'NVIDIA ASR 调用失败: {exc}') from exc
        else:
            raise HTTPException(status_code=502, detail=f'NVIDIA ASR 调用失败: {exc}') from exc

    text = ' '.join(
        alt.transcript.strip()
        for item in result.results
        for alt in item.alternatives
        if alt.transcript.strip()
    ).strip()
    fmt = (response_format or 'json').strip().lower()
    if fmt == 'text':
        return PlainTextResponse(text)
    if fmt == 'verbose_json':
        return JSONResponse({
            'text': text,
            'model': resolved_model,
            'language': language,
            'sample_rate_hz': sample_rate,
        })
    return JSONResponse({'text': text, 'model_used': resolved_model})


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        'bridge:app',
        host=os.environ.get('OPENCLAW_NVIDIA_AUDIO_BRIDGE_HOST', DEFAULT_BIND),
        port=int(os.environ.get('OPENCLAW_NVIDIA_AUDIO_BRIDGE_PORT', DEFAULT_PORT)),
        reload=False,
    )
