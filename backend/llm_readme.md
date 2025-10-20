**1) 启动 llama.cpp 的服务器（Qwen 模型在 8080）**

```bash
MODEL=~/models/qwen2.5/3b-instruct/Qwen2.5-3B-Instruct-Q4_K_M.gguf
cd ~/work/llama.cpp/build/bin
./llama-server -m "$MODEL" --host 0.0.0.0 --port 8080 \
  -c 4096 --temp 0.7 --repeat-penalty 1.1 --n-gpu-layers 35
```

**2) 启动 LLM 代理（FastAPI 在 8001，转发到 8080）**

```bash
export LLAMA_BASE=http://127.0.0.1:8080
python -m uvicorn backend.llm.llm_app:app --host 127.0.0.1 --port 8001 --workers 1 --reload false
```

前端（或你的调试脚本）一般是打：

- `POST http://127.0.0.1:8001/llm`
  健康检查常用：
- `curl http://127.0.0.1:8001/health`（你写过这个端点）
- `curl http://127.0.0.1:8080/v1/models`（llama.cpp 的 OpenAI 兼容接口）