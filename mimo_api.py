"""MiMo API transport; uses only the Python standard library."""
import base64
import json
import mimetypes
import urllib.error
import urllib.request
import wave
from pathlib import Path

MODELS = ['mimo-v2.5-tts', 'mimo-v2.5-tts-voicedesign', 'mimo-v2.5-tts-voiceclone', 'mimo-v2.5-asr']
VOICES = ['mimo_default', '冰糖', '茉莉', '苏打', '白桦', 'Mia', 'Chloe', 'Milo', 'Dean']


def audio_uri(path, clone=False):
    path = Path(path)
    if path.suffix.lower() not in ('.wav', '.mp3'):
        raise ValueError('请选择 WAV 或 MP3 音频文件。')
    # Avoid loading an oversized clone sample into memory.
    if clone and path.stat().st_size > 7_864_320:
        raise ValueError('克隆样本 Base64 编码后不能超过 10 MB，请缩短音频。')
    data = base64.b64encode(path.read_bytes()).decode('ascii')
    mime = 'audio/wav' if path.suffix.lower() == '.wav' else 'audio/mpeg'
    return f'data:{mime};base64,{data}'


def make_payload(mode, text='', prompt='', voice='mimo_default', source='', language='zh', stream=False, optimize=False):
    if mode == 3:
        if not source:
            raise ValueError('请选择需要识别的音频。')
        return {'model': MODELS[mode], 'messages': [{'role': 'user', 'content': [{'type': 'input_audio', 'input_audio': {'data': audio_uri(source)}}]}], 'asr_options': {'language': language}}
    if mode == 1 and not prompt.strip():
        raise ValueError('请输入音色设计描述。')
    if not text.strip() and not (mode == 1 and optimize):
        raise ValueError('请输入待合成文本。')
    if mode in (1, 2) and text.lstrip().lower().startswith(('(唱歌)', '（唱歌）', '[唱歌]', '(sing)', '(singing)')):
        raise ValueError('音色设计和克隆模型不支持唱歌模式。')
    messages = [{'role': 'user', 'content': prompt}]
    if text.strip():
        messages.append({'role': 'assistant', 'content': text})
    audio = {'format': 'pcm16' if stream else 'wav'}
    if mode == 0:
        audio['voice'] = voice
    elif mode == 1:
        audio['optimize_text_preview'] = optimize
    else:
        if not source:
            raise ValueError('请选择用于克隆的音频样本。')
        audio['voice'] = audio_uri(source, clone=True)
    return {'model': MODELS[mode], 'messages': messages, 'audio': audio, 'stream': stream}


def complete(key, base_url, payload, output, progress=lambda message: None):
    if not key.strip():
        raise ValueError('请填写 API Key，或设置 MIMO_API_KEY 环境变量。')
    if not base_url.startswith(('https://', 'http://localhost', 'http://127.0.0.1')):
        raise ValueError('API 地址需要使用 HTTPS。')
    request = urllib.request.Request(base_url.rstrip('/') + '/chat/completions', data=json.dumps(payload).encode(), headers={'Authorization': f'Bearer {key.strip()}', 'Content-Type': 'application/json'})
    try:
        response = urllib.request.urlopen(request, timeout=300)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'API 请求失败（HTTP {exc.code}）：{detail[:2000]}') from None
    with response:
        if payload.get('stream'):
            pcm = bytearray()
            transcript = []
            for raw in response:
                line = raw.decode('utf-8').strip()
                if not line.startswith('data:'):
                    continue
                data = line[5:].strip()
                if data == '[DONE]':
                    break
                chunk = json.loads(data)
                if 'error' in chunk:
                    raise RuntimeError(str(chunk['error']))
                for choice in chunk.get('choices', []):
                    delta = choice.get('delta', {})
                    audio = delta.get('audio') or {}
                    if audio.get('data'):
                        pcm.extend(base64.b64decode(audio['data']))
                        progress(f'已接收 {len(pcm) / 48000:.1f} 秒音频')
                    if delta.get('content'):
                        transcript.append(delta['content'])
            if not pcm:
                raise RuntimeError('接口未返回音频数据。')
            if len(pcm) % 2:
                raise RuntimeError('接口返回的 PCM16 音频长度不完整。')
            with wave.open(str(output), 'wb') as wav:
                wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                wav.writeframes(pcm)
            return ''.join(transcript)
        result = json.load(response)
    if 'error' in result:
        raise RuntimeError(str(result['error']))
    message = result['choices'][0]['message']
    content = message.get('content') or ''
    if payload['model'] != MODELS[3]:
        audio = message.get('audio') or {}
        if not audio.get('data'):
            raise RuntimeError('接口未返回音频数据。')
        Path(output).write_bytes(base64.b64decode(audio['data']))
    return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, indent=2)
