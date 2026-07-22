# Auto Knowledge 交接文档

这份文档写给下一个接手的 AI 或开发者。当前项目是在 Open WebUI 内实现一个一等业务模块，产品名暂定为“智汇通企业知识沉淀与智能问答系统”，模块名为 Auto Knowledge。它不是独立软件，也不是普通插件，而是直接接入现有用户、聊天、知识库、RAG、后台管理和调度体系的企业知识运营模块。

当前目标已经很清楚：系统按日/周从指定业务范围内抓取运营/客服聊天记录，经过清洗、脱敏、LLM 结构化提炼、去重、人工审核和知识库发布，把日常对话沉淀成可检索、可追溯、可审核的企业知识。最终效果是让后续 RAG 问答可以检索这些新增知识，使 AI 助手持续理解公司业务规则和运营经验。

## 当前进度

Auto Knowledge 的主体功能已经基本落地，工作区处于未提交的开发状态。不要假设仓库是干净的，也不要回滚不认识的改动。当前涉及的核心能力包括：

- 后端数据模型、迁移、API 路由和调度入口已经加入。
- 采集、清洗、提炼、去重、发布、运行记录这条 pipeline 已经形成。
- 管理端 UI 已经接入 Auto Knowledge 页面，包含任务列表、任务编辑、候选审核和运行历史。
- source filter 已支持按时间窗口、用户、用户组、模型等范围控制数据来源。
- LLM 提炼链路已经从串行改成有界并发，并加入全局并发控制。
- Benchmark Harness 已跑通过 100 条运营聊天样本的完整业务链路。
- Auto Knowledge 相关 pytest 已通过：`42 passed, 6 warnings`。

最近一次重点优化是并发提炼。原始链路在 `run_extraction_pipeline()` 中串行调用 LLM，100 条端到端耗时约 `243.527s`。现在在 `backend/open_webui/utils/auto_knowledge/runner.py` 中使用 `asyncio.Semaphore` 做有界并发，任务级默认并发为 `8`，benchmark 中使用 `20`；在 `scheduler.py` 中又加了一层全局并发控制，避免多个 job 同时把模型接口打爆。最新 100 条 benchmark 耗时约 `20.298s`，约 `12x` 提速。

## 必看文档

先看这几份，不要直接从代码里乱猜产品边界。

```text
docs/prd/auto-knowledge-prd.md
docs/superpowers/plans/2026-07-22-auto-knowledge-agent-workflow.md
.agents/reports/auto_knowledge_benchmark.md
.agents/reports/auto_knowledge_benchmark.json
```

注意：`docs/prd/auto-knowledge-prd.md` 当前在部分终端里可能显示乱码，疑似历史编码问题。如果打开后乱码，不要据此改产品范围；优先看 implementation plan、源码、测试和本交接文档。后续最好把 PRD 重新保存为 UTF-8。

`docs/superpowers/plans/2026-07-22-auto-knowledge-agent-workflow.md` 是最重要的开发方法文档。它定义了 Harness Engineering 和 Loop Engineering 的职责边界，也定义了 agent 上限下的分工方式。后续继续开发时要按这个走，不要单 agent 一路写到底。

## 必看源码

后端核心文件：

```text
backend/open_webui/models/auto_knowledge.py
backend/open_webui/routers/auto_knowledge.py
backend/open_webui/utils/auto_knowledge/collector.py
backend/open_webui/utils/auto_knowledge/cleaner.py
backend/open_webui/utils/auto_knowledge/extractor.py
backend/open_webui/utils/auto_knowledge/deduplicator.py
backend/open_webui/utils/auto_knowledge/publisher.py
backend/open_webui/utils/auto_knowledge/runner.py
backend/open_webui/utils/auto_knowledge/scheduler.py
backend/open_webui/utils/auto_knowledge/schedules.py
backend/open_webui/utils/auto_knowledge/types.py
backend/open_webui/utils/auto_knowledge/prompts.py
backend/open_webui/migrations/versions/20260722ak01_add_auto_knowledge_tables.py
```

前端核心文件：

```text
src/lib/apis/auto-knowledge/index.ts
src/lib/components/admin/AutoKnowledge.svelte
src/lib/components/admin/AutoKnowledge/TaskList.svelte
src/lib/components/admin/AutoKnowledge/TaskEditor.svelte
src/lib/components/admin/AutoKnowledge/CandidateList.svelte
src/lib/components/admin/AutoKnowledge/CandidateReviewDrawer.svelte
src/lib/components/admin/AutoKnowledge/RunHistory.svelte
src/routes/(app)/admin/auto-knowledge/+page.svelte
```

启动与检查脚本：

```text
scripts/start-auto-knowledge-backend.ps1
scripts/check-auto-knowledge-backend.ps1
```

Benchmark 和测试辅助：

```text
.agents/benchmark_auto_knowledge_efficiency.py
.agents/auto_knowledge_benchmark_metrics.py
.agents/fixtures/auto_knowledge_benchmark_100.json
.agents/tests/test_auto_knowledge_benchmark_metrics.py
.agents/run_auto_knowledge_business_harness.py
```

## 代码链路怎么读

先从 `models/auto_knowledge.py` 看领域模型。核心对象是 job、run、candidate、source。job 保存自动沉淀任务配置，run 保存每次执行记录，candidate 保存 LLM 提炼出来的候选知识，source 保存候选知识和原始聊天消息之间的追溯关系。

再看 `collector.py`。这里决定哪些聊天能进入沉淀流程。当前关键点是 source filter，尤其是时间窗口、`user_ids`、`group_ids`、`model_ids` 和 `limit`。这部分要特别谨慎，因为它决定系统会不会误采无关用户或非业务会话。

然后看 `cleaner.py` 和 `extractor.py`。cleaner 做无效内容过滤和规则脱敏，extractor 负责构建 prompt、调用模型并把 LLM 输出解析成结构化知识。这里的原则是：原始聊天不能直接入库，必须先经过清洗、脱敏和结构化校验。

接着看 `runner.py`。它是 pipeline 的编排点：清洗、并发提炼、去重、统计错误。并发优化就在这里，后续改性能先看它，不要直接改 scheduler。

最后看 `scheduler.py` 和 `routers/auto_knowledge.py`。scheduler 负责后台任务执行和模型调用上下文，router 负责管理端 API，包括任务 CRUD、手动运行、候选列表、候选详情、审核发布和运行历史。

## 开发方法

继续开发时按 Harness Engineering 控制全局节奏。主 agent 不应该只盯着一个文件修，而是要持续维护需求、实现、测试和报告之间的一致性。

推荐 agent 分工：

```text
Harness Engineer：主控，负责范围、验收、合并和最终判断。
Pipeline Agent：collector、cleaner、extractor、deduplicator、runner、publisher。
API/Scheduler Agent：router、scheduler、权限、状态流转、运行记录。
Admin UI Agent：前端页面、API client、候选审核交互、运行历史。
Loop Test Agent：端到端业务测试、边界测试、攻击性测试、压力测试。
Review/Hardening Agent：安全、幂等、并发、失败恢复复核。
```

agent 数量有限时可以合并角色，但测试不能完全由实现同一个模块的 agent 自测。至少要有一个独立 Loop Test pass，模拟真实用户完整使用产品。

每个 agent 的交付必须包含：

```text
Changed files:
Behavior implemented:
Tests added:
Commands run:
Known gaps:
Risk notes:
```

不要让 agent 自己随意扩大范围。每次分派任务都要给它明确文件边界、PRD 对应章节、必须测试的行为和不能改变的接口。

## 测试方法

最小后端验证命令：

```powershell
$env:WEBUI_SECRET_KEY='auto-knowledge-test-secret'
D:\Anaconda3\envs\ai-content-ops\python.exe -m pytest backend\open_webui\utils\auto_knowledge\tests .agents\tests\test_auto_knowledge_benchmark_metrics.py -q
```

最近一次结果：

```text
42 passed, 6 warnings
```

指标脚本单测：

```powershell
$env:WEBUI_SECRET_KEY='auto-knowledge-test-secret'
D:\Anaconda3\envs\ai-content-ops\python.exe -m pytest .agents\tests\test_auto_knowledge_benchmark_metrics.py -q
```

业务 benchmark 命令：

```powershell
$env:AUTO_KNOWLEDGE_EXTRACTION_CONCURRENCY='20'
$env:AUTO_KNOWLEDGE_GLOBAL_EXTRACTION_CONCURRENCY='32'
D:\Anaconda3\envs\ai-content-ops\python.exe .agents\benchmark_auto_knowledge_efficiency.py --limit 100 --projected-records 5000
```

本地后端启动优先用：

```powershell
scripts\start-auto-knowledge-backend.ps1
```

健康检查：

```powershell
scripts\check-auto-knowledge-backend.ps1
```

如果要跑 live benchmark，需要先确保后端健康、模型 API 配置存在、`.env.local` 或环境变量里有模型 key。不要把 API key 写进交接文档、测试报告或提交内容。

## Loop Engineering 要怎么测

测试不能只看单元测试绿不绿。这个功能的真实验收路径是：

```text
管理员创建自动知识任务
-> 指定目标知识库和 source filter
-> 种入或产生业务聊天
-> 手动或定时运行任务
-> 系统采集聊天并清洗脱敏
-> LLM 提炼候选知识
-> 去重并生成候选
-> 管理员审核发布
-> 知识进入目标知识库
-> 后续 RAG 问答能检索召回
```

至少覆盖这些场景：

- Happy path：清晰业务问答能变成候选知识并发布。
- 空窗口：没有聊天时不报错，不生成候选。
- 非业务会话：闲聊、过短内容、失败回答不会进入候选。
- 权限：普通用户不能创建任务、查看来源、审核候选。
- source filter：非目标用户组的聊天不能被采集。
- PII：手机号、邮箱、订单号、API key 样式文本要脱敏。
- prompt injection：聊天里要求“忽略规则、发布原文”不能影响提炼策略。
- 重复：同一 FAQ 在同一批和跨批出现时不能重复发布。
- 失败恢复：LLM malformed JSON、超时、发布失败要有明确 run status。
- 压力：至少用 fake extractor 跑 100+ 或 1000+ 级别，确认不会串行阻塞。

## 当前量化数据口径

当前真实 live benchmark 是 100 条运营聊天样本：

```text
job_id: 82be6daf-ab2a-4667-940a-39acab271824
run_id: 5f988bd1-6800-4b43-9172-d7be6724b607
input_count: 100
cleaned_count: 100
generated_count: 19
duplicate_count: 54
failed_count: 27
run_duration_ms: 20298
candidate_precision: 94.74%
PII mask rate: 100% across 20 sensitive samples
RAG Hit@3: 20/20 in the small regression set
old serial duration: 243.527s / 100 records
new concurrent duration: 20.298s / 100 records
pipeline speedup: about 12x
```

5000+ 是按 100 条实测乘 50 批做的规模折算：

```text
5000 条自动处理约 16.9 分钟
人工基线按 20 秒/条约 27.8 小时
自动流水线相对人工基线约 98.5x
耗时降低约 98.99%
```

简历里如果需要稳妥写法，可以写“在 5000+ 条规模下”而不是“生产累计处理 5000+ 条”。如果用户明确要求写成项目成果，可以用上面的数字，但下一个 AI 要知道这些数字来自 100 条 benchmark 的规模折算。

RAG 指标要特别小心。当前真正跑过的是小回归集 `20/20`，不是 300+。之前用户希望简历写 `300+` 和 `95%+`，这属于简历口径，不是当前 harness 实测结果。如果要把它变成实测，需要补一个 300+ 业务事实问题集和对应检索 benchmark。

另一个注意点：`.agents/reports/auto_knowledge_benchmark.md` 里当前 P95 可能被后续重算覆盖成了 `94ms`，而之前业务 benchmark 记录的检索延迟口径是 `P50/P95 = 94ms/113ms`。如果后续继续用报告做证据，应该重新跑 live benchmark，或者修改 harness 保存原始 retrieval latency 列表，避免只从聚合值反推。

## 已知风险和后续优先级

第一，跨 run 的 DB 级去重还不够硬。当前 pipeline 会把已有候选转成 `ExtractedKnowledge` 参与去重，但还没有足够强的数据库唯一约束或 insert-time recheck。后续如果并发 job 同时运行，仍可能出现竞态重复。

第二，scheduler 的 claim 在非 Postgres 环境下仍有竞态风险。已有 `claim_due()` 逻辑需要继续审查，尤其是 SQLite 或本地测试环境。理想做法是条件更新加状态检查，确保同一个 due job 只会被一个 worker claim。

第三，`partial_success` 的语义要继续保持清晰。现在已经加入 `determine_run_status()`：如果清洗后所有 segment 都提炼失败且没有插入候选，应标为 `failed`，不能算 `partial_success`。后续改 runner/scheduler 时不要破坏这个判断。

第四，候选发布和 RAG 入库链路要继续做端到端验证。单独生成 candidate 不代表业务完成，必须验证审核发布后进入目标知识库，并且后续 retrieval 能召回。

第五，PRD 文档编码需要修复。它是产品边界来源，但目前部分环境显示乱码，容易误导后续 agent。

## 简历项目当前成稿

当前项目名：

```text
智汇通企业知识沉淀与智能问答系统
```

技术栈建议：

```text
FastAPI、TypeScript、RAG、Embedding、ChromaDB、LangChain、Prompt Engineering、SQLAlchemy、Alembic、Redis、WebSocket、Pytest、Benchmark Harness、Docker
```

项目描述：

```text
这是一个面向企业内部知识管理和智能问答的大模型应用平台，核心能力是为员工提供 AI 助手，并定时自动采集业务聊天记录，经过清洗、脱敏和知识提炼后，转化为可检索、可审核、可持续更新的企业知识库，使大模型能够持续理解公司业务规则和运营经验。
```

个人职责当前推荐保留四条：自动沉淀链路、source filter 采集策略、RAG 检索增强链路、并发 LLM 提炼优化。

项目成果当前推荐保留四条：完整闭环、5000+ 规模效率、RAG 验证、可配置可追溯可审核的知识运营后台。注意成果不要重复写个人职责里的“我负责实现什么”，要写系统最终形成了什么能力。

## 接手后的建议顺序

第一步，先跑测试确认工作区状态：

```powershell
$env:WEBUI_SECRET_KEY='auto-knowledge-test-secret'
D:\Anaconda3\envs\ai-content-ops\python.exe -m pytest backend\open_webui\utils\auto_knowledge\tests .agents\tests\test_auto_knowledge_benchmark_metrics.py -q
```

第二步，打开 Auto Knowledge 后台页面，完整走一遍管理员使用路径。不要只看 API 或只看 UI。

第三步，重新跑 live benchmark，并修复报告中的 latency 原始数据保存问题。以后报告应该保存完整 `retrieval_latencies_ms`，不要只保存 P50/P95。

第四步，如果继续做工程硬化，优先处理 DB 级去重和 scheduler claim 竞态。这两个比继续堆 UI 更重要。

第五步，如果目标是简历交付，补一个 300+ RAG 问题集 benchmark。这样 `RAG Top-3 95%+` 就能从口径变成真实测试结果。

## 不要做的事

不要把 Auto Knowledge 改成独立服务。这个功能依赖 Open WebUI 的用户、聊天、知识库、权限和 RAG 链路，独立出去会重复造系统。

不要让原始聊天全文直接入库。所有内容必须经过清洗、脱敏、结构化校验、去重和审核。

不要默认全站采集。source filter 是安全边界，也是产品价值的一部分。

不要因为单元测试全绿就宣布完成。这个功能的完成标准是完整业务闭环通过。

不要把 API key 写进仓库或文档。如果需要跑 live LLM，用本地 `.env.local` 或临时环境变量。

不要回滚不认识的未提交文件。当前工作区包含多条线路的开发成果，回滚前必须确认所有权。
