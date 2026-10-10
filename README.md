# MiMo Voice Studio

Windows Python 桌面客户端，使用标准库，无需安装第三方依赖。

## 启动

安装带 Tkinter 的 Python 3.10 或更新版本，在本目录运行：

```powershell
python app.py
```

填写 MiMo API Key，或在启动前设置环境变量：

```powershell
$env:MIMO_API_KEY = '你的 API Key'
python app.py
```

支持预置音色 TTS、文本设计音色、参考 WAV/MP3 克隆音色，以及 MiMo ASR。文本合成放在 assistant 消息，演绎指导放在 user 消息。音色设计支持智能润色，开启时允许合成文本留空。ASR 默认语言 zh，也可填写其他接口支持的语言代码。

非流式保存 WAV；流式按文档将 PCM16LE 单声道 24 kHz 数据合并为 WAV，界面显示接收进度，完成后播放。设计与克隆的流式能力以服务端实际支持为准。唱歌仅适用于预置音色模型，在合成文本开头填写 `(唱歌)`。

生成结果自动保存在项目下 outputs 文件夹，也可另存。API Key 不写入磁盘；音频和文本会发送到配置的 API 服务，调用产生的费用按服务商计费。网络调用在后台线程执行，超时为 300 秒。播放使用 Windows winsound。
