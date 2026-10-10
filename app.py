"""Run with: python app.py"""
import os
import queue
import shutil
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime
from mimo_api import VOICES, make_payload, complete


class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('MiMo Voice Studio')
        self.geometry('1000x820')
        self.minsize(780, 700)
        self.events = queue.Queue()
        self.busy = False
        self.last_audio = None
        self.configure(background='#f5f6fa')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TFrame', background='#f5f6fa')
        style.configure('TLabel', background='#f5f6fa', font=('Microsoft YaHei UI', 10))
        style.configure('TButton', font=('Microsoft YaHei UI', 10), padding=8)
        style.configure('TNotebook.Tab', padding=(18, 10))
        root = ttk.Frame(self, padding=24)
        root.pack(fill='both', expand=True)
        ttk.Label(root, text='MiMo Voice Studio', font=('Segoe UI', 24, 'bold')).pack(anchor='w')
        ttk.Label(root, text='声音创作工作台 · 合成 / 设计 / 克隆 / 转写').pack(anchor='w', pady=(3, 16))
        settings = ttk.Frame(root)
        settings.pack(fill='x')
        ttk.Label(settings, text='API Key').grid(row=0, column=0, sticky='w', padx=(0, 12))
        self.key = tk.StringVar(value=os.getenv('MIMO_API_KEY', ''))
        ttk.Entry(settings, textvariable=self.key, show='•').grid(row=0, column=1, sticky='ew')
        ttk.Label(settings, text='API 地址').grid(row=1, column=0, sticky='w', pady=10)
        self.url = tk.StringVar(value='https://api.xiaomimimo.com/v1')
        ttk.Entry(settings, textvariable=self.url).grid(row=1, column=1, sticky='ew')
        settings.columnconfigure(1, weight=1)
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill='both', expand=True, pady=12)
        self.pages = []
        for mode, title in enumerate(['语音合成', '音色设计', '音色克隆', '语音识别']):
            page = ttk.Frame(self.tabs, padding=16)
            self.tabs.add(page, text=title)
            fields = {}
            if mode == 0:
                ttk.Label(page, text='预置音色').pack(anchor='w')
                fields['voice'] = tk.StringVar(value='冰糖')
                ttk.Combobox(page, textvariable=fields['voice'], values=VOICES, state='readonly').pack(anchor='w', pady=6)
            if mode in (2, 3):
                ttk.Label(page, text='参考音频（WAV / MP3）' if mode == 2 else '待识别音频（WAV / MP3）').pack(anchor='w')
                row = ttk.Frame(page)
                row.pack(fill='x', pady=6)
                fields['source'] = tk.StringVar()
                ttk.Entry(row, textvariable=fields['source']).pack(side='left', fill='x', expand=True)
                ttk.Button(row, text='选择文件', command=lambda f=fields: self.pick(f)).pack(side='left', padx=(8, 0))
            if mode == 3:
                ttk.Label(page, text='识别语言代码').pack(anchor='w', pady=(10, 0))
                fields['language'] = tk.StringVar(value='zh')
                ttk.Combobox(page, textvariable=fields['language'], values=['zh', 'en']).pack(anchor='w', pady=6)
                ttk.Label(page, text='上传音频后开始识别，结果可复制或导出为文本。').pack(anchor='w', pady=20)
            else:
                ttk.Label(page, text='音色描述（必填）' if mode == 1 else '演绎指导（可选）').pack(anchor='w', pady=(8, 4))
                fields['prompt'] = tk.Text(page, height=3, wrap='word', font=('Microsoft YaHei UI', 10), relief='solid', borderwidth=1)
                fields['prompt'].pack(fill='x')
                ttk.Label(page, text='待合成文本 · 可插入情绪、停顿等标签').pack(anchor='w', pady=(12, 4))
                fields['text'] = tk.Text(page, height=6, wrap='word', font=('Microsoft YaHei UI', 11), relief='solid', borderwidth=1)
                fields['text'].pack(fill='both', expand=True)
                fields['text'].insert('1.0', '你好，欢迎来到 MiMo 语音工作台。让每一句话，都有自己的声音。')
                fields['stream'] = tk.BooleanVar(value=mode == 0)
                ttk.Checkbutton(page, text='流式接收（PCM16 → WAV，24 kHz）', variable=fields['stream']).pack(anchor='w', pady=(10, 0))
                if mode in (1, 2):
                    ttk.Label(page, text='按提供的文档：设计与克隆的流式接口可能在推理结束后一次返回。').pack(anchor='w', pady=4)
                if mode == 1:
                    fields['optimize'] = tk.BooleanVar()
                    ttk.Checkbutton(page, text='智能润色 / 自动生成播报文本', variable=fields['optimize']).pack(anchor='w')
            self.pages.append(fields)
        row = ttk.Frame(root)
        row.pack(fill='x')
        self.run_button = ttk.Button(row, text='开始生成 / 识别', command=self.run)
        self.run_button.pack(side='left')
        ttk.Button(row, text='播放音频', command=self.play).pack(side='left', padx=8)
        ttk.Button(row, text='停止播放', command=self.stop).pack(side='left')
        ttk.Button(row, text='另存结果', command=self.save).pack(side='right')
        self.status = tk.StringVar(value='就绪 · API Key 仅保留在当前进程内存中')
        ttk.Label(root, textvariable=self.status, wraplength=900).pack(anchor='w', pady=10)
        self.result = tk.Text(root, height=5, wrap='word', font=('Microsoft YaHei UI', 10))
        self.result.pack(fill='x')
        self.after(100, self.poll)

    def pick(self, fields):
        path = filedialog.askopenfilename(filetypes=[('Audio', '*.wav *.mp3')])
        if path:
            fields['source'].set(path)

    def run(self):
        if self.busy:
            return
        mode = self.tabs.index(self.tabs.select())
        fields = self.pages[mode]
        values = {k: v.get('1.0', 'end-1c') if isinstance(v, tk.Text) else v.get() for k, v in fields.items()}
        try:
            payload = make_payload(mode, **values)
            key, url = self.key.get(), self.url.get()
            if not key.strip():
                raise ValueError('请先填写 API Key。')
        except Exception as exc:
            messagebox.showerror('检查输入', str(exc))
            return
        self.busy = True
        self.run_button.state(['disabled'])
        self.status.set('正在请求 MiMo API…')
        self.last_audio = None
        self.result.delete('1.0', 'end')
        def worker():
            try:
                output_dir = Path(__file__).resolve().parent / 'outputs'
                output_dir.mkdir(exist_ok=True)
                output = output_dir / (datetime.now().strftime('%Y%m%d_%H%M%S_%f') + ('.txt' if mode == 3 else '.wav'))
                text = complete(key, url, payload, output, lambda msg: self.events.put(('status', msg)))
                if mode == 3:
                    output.write_text(text, encoding='utf-8')
                self.events.put(('done', (mode, output, text)))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'status':
                    self.status.set(value)
                else:
                    self.busy = False
                    self.run_button.state(['!disabled'])
                    if kind == 'error':
                        self.status.set('请求失败，请检查输入或网络后重试。')
                        self.result.insert('end', value)
                    else:
                        mode, output, text = value
                        self.last_audio = output if mode != 3 else None
                        self.status.set(f'完成 · 已保存到 {output}')
                        self.result.insert('end', text or '音频已生成，可播放或另存。')
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def play(self):
        if not self.last_audio:
            messagebox.showinfo('播放', '请先生成音频。')
            return
        try:
            import winsound
            winsound.PlaySound(str(self.last_audio), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as exc:
            messagebox.showerror('播放失败', str(exc))

    def stop(self):
        try:
            import winsound
            winsound.PlaySound(None, 0)
        except ImportError:
            pass

    def save(self):
        audio = self.last_audio
        text = self.result.get('1.0', 'end-1c')
        if not audio and not text:
            return
        path = filedialog.asksaveasfilename(defaultextension='.wav' if audio else '.txt', filetypes=[('WAV audio', '*.wav')] if audio else [('Text', '*.txt')])
        if path:
            try:
                if audio:
                    shutil.copyfile(audio, path)
                else:
                    Path(path).write_text(text, encoding='utf-8')
            except Exception as exc:
                messagebox.showerror('保存失败', str(exc))


if __name__ == '__main__':
    Studio().mainloop()
