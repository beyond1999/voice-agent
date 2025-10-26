
# 🧠 Voice Agent

一个可以**语音控制电脑**、**执行系统命令**、**读写文件**、**调用本地/云端大模型**的智能桌面助手。
本项目以 **FastAPI + LangGraph + Qwen LLM + Whisper ASR** 为核心，支持 ReAct 思维链式推理与多步工具调用。


### 演示视频地址：
https://www.bilibili.com/video/BV1K4szzvENJ/
---
### 简单讲解：
https://space.bilibili.com/416895726?spm_id_from=333.788.upinfo.head.click
---
## 🚀 功能特性

| 模块           | 功能                                      | 技术                        |
| ------------ | --------------------------------------- | ------------------------- |
| 🗣 语音识别（ASR） | 通过 Whisper 实时录音转文字                      | `pyaudio`, `whisper`      |
| 💬 LLM 对话    | 支持本地 llama.cpp 模型或云端 DashScope Qwen API | `ChatOpenAI`, `LangChain` |
| 🧩 工具调用      | 自动调用系统命令、文件操作、音乐控制、Word 写作等             | `LangGraph`, `@tool` 装饰器  |
| 🔁 思维链推理     | 使用 LangGraph 实现 ReAct 框架（推理+行动）         | `create_react_agent`      |
| 🧠 记忆系统      | FileSaver 持久化多轮对话与执行状态                  | 自定义 checkpoint            |
| 🖥 桌面助手      | 控制本地应用（QQ音乐、Word、浏览器、日历）、执行命令行任务 | `subprocess`, `win32api`  |

---

## 🧱 架构设计

```
│
├── backend/
│   ├── llm_server.py         # FastAPI 主服务，路由 /llm
│   ├── function_call/        # 工具函数注册与封装
│   │   ├── function_call_register.py
│   │   └── word_tools.py
│   ├── agent_runner.py       # LangGraph ReAct agent 模块（复杂任务执行）
│   ├── router.py             # 智能路由：判断简单任务/复杂任务
│   ├── whisper_asr.py        # 语音识别模块
│   └── requirements.txt
│
├── .env                      # 环境变量配置（含 API key、本地/云端模式）
├── README.md
└── run.bat / run.sh          # 启动脚本
```

---

## ⚙️ 环境配置

### 1. 创建虚拟环境

```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

在项目根目录创建 `.env` 文件：

```bash
USE_LOCAL_MODEL=true               # 是否使用本地 llama.cpp 模型
LLAMA_BASE=http://127.0.0.1:8003   # llama.cpp 启动地址
LLAMA_MODEL=qwen2.5-3b-instruct    # 本地模型名

# 若走云端 DashScope
USE_LOCAL_MODEL=false
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
LLAMA_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
LLAMA_MODEL=qwen-max
```

---

## 💡 启动方式

### ▶️ 启动本地模型

```bash
./llama-server -m Qwen2.5-3B-Instruct-Q4_K_M.gguf --port 8003
```

### ▶️ 启动 FastAPI 服务

```bash
python backend/llm_server.py
```

访问健康检查：

```
GET http://127.0.0.1:8001/health
```

---

## 🧠 智能交互逻辑

### 简单任务（走 JSON Action）

LLM 输出 JSON：

```json
{
  "thought": "用户想播放音乐",
  "action": {"name": "play_music", "args": {}},
  "observation": "",
  "answer": "已切换播放状态"
}
```

→ FastAPI 解析 `action` 并调用 `function_map` 执行系统操作。

---

### 复杂任务（走 ReAct 思维链）

当检测到用户请求为复杂任务（如执行命令、多步推理、文件操作等）时，自动切换至：

```python
from agent_runner import agent_runner
result = await agent_runner.run(user_text)
```

Agent 通过 LangGraph 实现多步“思考→行动→反思”循环，并可调用工具链（文件操作、命令执行等）。

---

## 🗂️ 已实现工具列表

| 工具名称                                        | 功能                              | 示例                                |
| ------------------------------------------- | ------------------------------- | -------------------------------          |
| `open_app(keyword)`                         | 打开桌面应用（.lnk）                    | 打开QQ音乐                        |
| `play_music()`                              | 播放/暂停QQ音乐                       | 播放音乐                             |
| `media_control(op)`                         | 控制音量、下一曲、静音等                    | 调高音量                       |
| `write_article_in_word(file_name, content)` | 在Word中写入文章                      | 写一篇AI主题文章                     |
| `execute_command(command)`                  | 执行命令行操作                         | ls / dir / echo / python xxx.py    |
| 文件读写                                     | 通过 FileManagementToolkit 操作文件系统 | 创建、保存、删除文件               |
| `search_web`                                |搜索或访问特定网页                       |打开B站，用xx搜索xxx                 |
| `send_email`                                |发送邮件                                |向xxx邮箱发送主题为xxx,内容是xxx的邮件|
| `create win calendar or google calendar`    |创建本地日程或谷歌日程，并查看已有日程     |提醒我明天下午三点开会               |
---

## 🧩 模块化扩展

* ✅ 你可以新增工具：在 `function_call_register.py` 中注册新的 `@tool`
* ✅ 也可加入语音输出（Edge-TTS / pyttsx3）
* ✅ 后续支持 GUI 控制面板或浏览器前端接口（React / Vue）

---

## 🧠 技术栈概览

| 层级  | 技术                              |
| --- | ------------------------------- |
| 模型层 | Qwen2.5 (llama.cpp / DashScope) |
| 推理层 | LangGraph ReAct Agent           |
| 语音层 | Whisper ASR                     |
| 应用层 | FastAPI + JSON Action 路由        |
| 存储层 | 自定义 FileSaver Checkpoint        |

---

## 🧩 典型应用场景

* 🎧 “帮我打开QQ音乐并播放”
* ✍️ “写一篇主题为AI助理的文章并保存到桌面”
* 💻 “列出桌面所有文件并压缩”
* 🧠 “自动执行多个命令组合任务”
* 🔊 “通过语音直接操作电脑”

---



## 📜 License

MIT License © 2025

---
