from __future__ import annotations

import faulthandler
import os
import sys
import threading


def dump_stacks() -> None:
    faulthandler.dump_traceback(file=sys.stderr, all_threads=True)


threading.Timer(30, dump_stacks).start()

os.environ["PYTHONPATH"] = r"D:\Projects\Open-WebUI\open-webui\backend"
os.environ["WEBUI_SECRET_KEY"] = "dev-auto-knowledge-local-secret"
os.environ["OPENAI_API_BASE_URL"] = "https://openrouter.ai/api/v1"
os.environ["RAG_EMBEDDING_ENGINE"] = ""
os.environ["RAG_EMBEDDING_MODEL"] = r"D:\Projects\llm_customer_service_ops\models\bge-base-zh-v1.5"
os.environ["BYPASS_EMBEDDING_AND_RETRIEVAL"] = "false"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import uvicorn

uvicorn.run("open_webui.main:app", host="127.0.0.1", port=8081)
