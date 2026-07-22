# Auto Knowledge

这是一个企业知识自动沉淀项目。它不是独立服务，也不是普通插件，而是直接接入现有的用户、聊天、知识库、RAG、后台管理和调度体系。

项目的核心目标是：从指定业务范围内的客服/运营聊天记录里，自动提炼可以复用的企业知识。系统会先采集聊天，再做清洗、脱敏、LLM 结构化提炼、去重、人工审核，最后把审核通过的内容发布到目标知识库，让后续 RAG 问答能够检索到这些新增知识。

## 这个项目能做什么

Auto Knowledge 的主流程是：

```text
管理员创建知识沉淀任务
-> 选择目标知识库和聊天来源范围
-> 手动或定时运行任务
-> 系统采集聊天并清洗脱敏
-> LLM 提炼候选知识
-> 系统去重并生成候选项
-> 管理员审核、编辑、通过或拒绝
-> 通过的知识发布到目标知识库
-> 后续 RAG 问答可以检索命中
```

这里最重要的边界是：原始聊天不能直接入库。所有内容都必须经过清洗、脱敏、结构化校验、去重和审核，才允许进入知识库。

## 环境要求

本地开发建议使用下面的版本：

- Node.js：`18.13` 到 `22.x`
- npm：`6.0` 或更高
- Python：`3.11` 或 `3.12`
- Git

如果你只是想用 Docker 跑完整项目，也可以直接看仓库里的 `Dockerfile` 和 `docker-compose.yaml`。如果你要开发 Auto Knowledge，建议按下面的源码方式启动。

## 第一次启动

先克隆仓库：

```bash
git clone https://github.com/FrozenfishKiel/auto-knowledge.git
cd auto-knowledge
```

Windows 用户可以直接双击根目录里的：

```text
启动项目.bat
```

这个脚本会帮你做几件事：检查 Node.js、npm 和 Python 是否存在；如果 `node_modules/` 不存在，会自动执行 `npm ci`；如果后端依赖缺失，会自动安装 `backend/requirements.txt`；然后启动后端和前端，等服务可用后自动打开浏览器。

双击启动后，窗口不要关。这个窗口负责维持本次启动的服务，按 Enter 会停止脚本启动的前后端进程。

如果你的 Python 不在系统 PATH 里，先在 PowerShell 里指定路径，再运行脚本：

```powershell
$env:PYTHON_EXE='C:\Path\To\python.exe'
.\启动项目.bat
```

第一次运行前建议复制环境变量文件：

```powershell
Copy-Item .env.example .env.local
```

然后打开 `.env.local`，按你的模型服务配置 API 地址和 key。不要把真实 key 提交到仓库里。

至少建议配置一个本地开发用密钥：

```env
WEBUI_SECRET_KEY=dev-local-secret
```

如果要跑真实 LLM 提炼，还需要配置类似下面的变量：

```env
OPENAI_API_KEY=你的模型服务密钥
OPENAI_API_BASE_URL=你的 OpenAI-compatible API 地址
```

## 手动启动方式

如果你不想用双击脚本，也可以手动启动。先安装前端依赖：

```bash
npm ci
```

再安装后端依赖：

```bash
python -m pip install -r backend/requirements.txt
```

复制环境变量文件：

```bash
cp .env.example .env.local
```

Windows PowerShell 可以用：

```powershell
Copy-Item .env.example .env.local
```

后端默认跑在 `http://localhost:8080`。

macOS / Linux：

```bash
bash backend/dev.sh
```

Windows：

```powershell
backend\start_windows.bat
```

然后另开一个终端启动前端：

```bash
npm run dev
```

前端默认地址是 `http://localhost:5173`。浏览器打开这个地址后，前端会请求本地 `8080` 端口的后端。

## Auto Knowledge 本地调试

仓库里额外放了两个 Auto Knowledge 辅助脚本，主要用于单独调试这个模块。

启动 Auto Knowledge 调试后端：

```powershell
scripts\start-auto-knowledge-backend.ps1
```

这个脚本会把后端启动在：

```text
http://127.0.0.1:8081
```

检查后端是否还活着：

```powershell
scripts\check-auto-knowledge-backend.ps1
```

脚本会读取 `.env.local`，并把运行日志写到 `.agents/logs/`。这个目录是本地运行产物，不会提交到仓库。

如果你的 Python 不在系统 PATH 里，可以在运行脚本前指定：

```powershell
$env:PYTHON_EXE='C:\Path\To\python.exe'
scripts\start-auto-knowledge-backend.ps1
```

## 后台怎么使用

启动前后端后，登录管理后台，进入 Auto Knowledge 页面。管理员可以在这里做三件事：

1. 创建自动沉淀任务，配置任务名称、目标知识库、执行周期、来源用户/用户组/模型和时间窗口。
2. 手动运行任务，等待系统从符合条件的聊天中生成候选知识。
3. 审核候选知识，查看脱敏后的来源，必要时编辑答案，然后通过、拒绝或重新发布。

普通用户不应该看到 Auto Knowledge 管理入口，也不能调用任务创建、运行、审核、来源查看等管理 API。

后端 API 挂载在：

```text
/api/v1/auto-knowledge
```

## 测试命令

Auto Knowledge 的最小后端验证命令：

```powershell
$env:WEBUI_SECRET_KEY='auto-knowledge-test-secret'
python -m pytest backend\open_webui\utils\auto_knowledge\tests .agents\tests\test_auto_knowledge_benchmark_metrics.py -q
```

API 测试：

```powershell
$env:WEBUI_SECRET_KEY='auto-knowledge-test-secret'
python -m pytest backend\open_webui\routers\tests\test_auto_knowledge_api.py -q
```

前端类型和 Svelte 检查：

```bash
npm run check
```

前端测试：

```bash
npm run test:frontend
```

## Benchmark 和业务链路验证

项目里有一组 Auto Knowledge benchmark 和业务链路脚本，放在 `.agents/` 目录下。

跑 100 条样本 benchmark：

```powershell
$env:AUTO_KNOWLEDGE_EXTRACTION_CONCURRENCY='20'
$env:AUTO_KNOWLEDGE_GLOBAL_EXTRACTION_CONCURRENCY='32'
python .agents\benchmark_auto_knowledge_efficiency.py --limit 100 --projected-records 5000
```

跑业务 harness 前，需要先启动后端，并且配置模型 API：

```powershell
$env:OPEN_WEBUI_BASE_URL='http://127.0.0.1:8081'
$env:AUTO_KNOWLEDGE_MODEL_ID='gpt-4o-mini'
python .agents\run_auto_knowledge_business_harness.py
```

注意：`5000+` 规模数据是基于 100 条真实样本 benchmark 的折算结果，不是生产累计真实处理量。如果要对外引用指标，建议重新跑一次 benchmark 并保存原始报告。

## 哪些文件不会提交

仓库已经把本地运行和缓存文件加入 ignore。常见不会提交的内容包括：

- `.env.local`：本地密钥和模型配置
- `node_modules/`：前端依赖
- `.svelte-kit/`、`build/`：前端构建产物
- `.agents/cache/`：模型和 HuggingFace 缓存
- `.agents/logs/`：本地调试日志
- `tmp/`：临时文件
- Python `__pycache__/` 和 pytest 缓存

这些文件不提交不会影响别人 clone 后启动项目。依赖可以通过 `npm ci` 和 `python -m pip install -r backend/requirements.txt` 重新安装；缓存和日志本来就应该在本地生成。

## 重要文档

接手 Auto Knowledge 时，建议先看这几份文档：

```text
docs/auto-knowledge-handoff.md
docs/prd/auto-knowledge-prd.md
docs/superpowers/plans/2026-07-22-auto-knowledge-agent-workflow.md
```

其中 PRD 和交接文档在部分终端里可能出现中文编码显示问题。如果看到乱码，不要直接按乱码内容改产品范围，优先参考代码、测试和 implementation plan。

## 当前已知风险

这个项目已经有完整的 Auto Knowledge 主链路，但后续继续开发时要优先关注几个风险点：

- 跨 run 的数据库级去重还需要继续加强，多个 job 并发时仍可能出现竞态重复。
- scheduler claim 在非 Postgres 环境下还需要继续审查，尤其是 SQLite 本地测试场景。
- `partial_success` 的语义要保持清楚：如果清洗后所有 segment 都提炼失败，而且没有插入候选，应该算 `failed`。
- 候选发布后必须继续验证是否真的进入目标知识库，并能被后续 RAG 检索命中。

## License

本项目基于现有代码改造，许可证信息请查看 `LICENSE`、`LICENSE_HISTORY` 和 `LICENSE_NOTICE`。
