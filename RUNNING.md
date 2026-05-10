# MemMark — 完整运行指令

从零到真实 backend 的全部命令。每个步骤独立可复现,**不依赖前一步在另一个 shell 跑过**。

---

## 0. 一次性前置(所有 backend 共用)

```bash
# 0.1 仓库
git clone https://github.com/zhb0119/watermark.git memmark
cd memmark
git checkout henry/full-pipeline

# 0.2 Python 环境(>= 3.10)
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install --upgrade pip

# 0.3 MemMark + AgentMark 共同依赖
pip install -r requirements.txt

# 0.4 AgentMark sampler(已经在仓库里,但需要 torch 才能跑真实采样器)
pip install torch numpy

# 0.5 LoCoMo 数据(只要 locomo10.json 这一份)
git clone https://github.com/snap-research/locomo.git ../locomo
export MEMMARK_LOCOMO_PATH=$(realpath ../locomo/data/locomo10.json)

# 0.6 必须的 secret(签 Merkle root 用)
export MEMMARK_KEY="memmark-research-key-please-rotate"

# 0.7 LLM 凭据 —— 都走 OpenAI-compatible API,任意 provider 三选一

# 选项 A:DeepSeek(直连官方,headline + cost 主线)
export MEMMARK_BASE_URL="https://api.deepseek.com"
export MEMMARK_API_KEY="<DeepSeek key>"
export MEMMARK_MODEL="deepseek-chat"                    # 或 deepseek-reasoner

# 选项 B:Qwen3.5(走 DashScope OpenAI-compatible endpoint,reproducibility 主线)
export MEMMARK_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export MEMMARK_API_KEY="<DashScope key>"
export MEMMARK_MODEL="qwen3.5-coder-a3b-instruct"        # 或 qwen3-235b-a22b-instruct
# 自部署 Qwen vLLM 也行:
# export MEMMARK_BASE_URL="http://your-vllm-host:8000/v1"
# export MEMMARK_API_KEY="EMPTY"
# export MEMMARK_MODEL="Qwen/Qwen3.5-397B-A17B"

# 选项 C:OpenRouter(同时拿 DeepSeek + Qwen + GPT-4o 一份 key)
export MEMMARK_BASE_URL="https://openrouter.ai/api/v1"
export MEMMARK_API_KEY="<OpenRouter key>"
export MEMMARK_MODEL="deepseek/deepseek-chat"            # 或 qwen/qwen3.5-...

# 跨 LLM ablation(§10.5 RQ3 marginal-gain 实验)只需重跑同一 conv,
# 改 MEMMARK_MODEL,watermark_version 字段会自动区分两次 trace。
```

### 0.8 LLM mode —— stub vs real(决定能不能拿 paper 数)

`run_locomo_full.py` 有 `--llm-mode {stub,real}` 决定 9 步 pipeline 里 3 个关键步骤走 LLM 还是 stub:

| 步骤 | `--llm-mode stub`(默认,smoke) | `--llm-mode real`(paper) |
|------|-----------------------------|--------------------------|
| 1. LoCoMo 加载 | 真实数据 | 真实数据 |
| 2. 回放 turn | 真 turn | 真 turn |
| **3. turn → memory record** | 简单过滤(去问候语)直接喂 backend | 简单过滤(去问候语)直接喂 backend(P0 #1 后,**不再外部 LLM 抽**;backend SDK 自己抽 keywords/tags/context/entity) |
| **4. carrier 候选生成** | 写死 3 个 paraphrase 模板 | LLM 生成 paraphrase **+ backend 真实 retrieval**(A-MEM ChromaDB / Graphiti graph)给 update/link 候选 |
| 5. AgentMark sampler 选 1 个 | ✅ | ✅ |
| 6. backend.apply 写入 | ✅ | ✅ |
| 7. commitment + Merkle log | ✅ | ✅ |
| **8. memory 答 QA** | substring lookup | LoCoMo **官方 QA prompt**(`QA_PROMPT` / `QA_PROMPT_CAT_5` 按 5 类 category 分)+ Porter-stem F1 评分 |
| 9. R1/R2/R3 验证 | ✅ | ✅ |
| RQ5 evidence-grounded check | dia_id 已存 record,但 default judge 不查 | 每条 QA 报 `evidence_recall = 命中 dia_id / 总 evidence dia_id` |

**论文 main table 必须 `--llm-mode real`**,因为:
1. stub 的 paraphrase 模板候选集 = 3 个固定串,**不是 backend 真实自由度**,RQ2 capacity 数失真
2. stub 的 QA 是 substring,**不可与 LoCoMo 论文 Table 4 / 后续 replication 对位**
3. stub 的 RQ5 evidence_recall 没意义,无法验 update_target accuracy

> **注:** 仓库根目录里 `agentmark/` 是 AgentMark 的源码副本,不需要单独 pip install。`memmark/core/sampler.py` 直接 `from agentmark.core.watermark_sampler import sample_behavior_differential`。

---

## 1. Smoke:JsonMemoryStore + stub mode(无外部依赖,< 1 分钟,zero API cost)

跑这一步**先确认管线本身没坏**,再去搞真实 backend / real mode。

```bash
python -m memmark.examples.run_locomo_full \
    --locomo "$MEMMARK_LOCOMO_PATH" \
    --conversation 0 \
    --max-sessions 2 \
    --max-qa 10 \
    --backend json \
    --llm-mode stub \
    --baselines watermark no_watermark signed_metadata_only random_replace \
    --output ./results/smoke_json.json
```

期望输出末尾(headline R3):

```json
"r3": {
  "anchor_signature_valid": 1.0,
  "root_matches": 1.0,
  "bit_recovery_rate": 1.0
},
"r3_wrong_key": {
  "anchor_signature_valid": 0.0,
  "bit_recovery_rate": 0.55
}
```

R3 = 1.0、wrong-key < 0.7 ⇒ 管线 OK。**这是 stub 数,不是 paper 数;qa_accuracy 在 stub 下接近 0 是正常的(default substring judge 太弱)。**

---

## 2. Backend A:A-MEM(本地 ChromaDB,最容易跑)

A-MEM 把 memory 当 agentic notes,用 ChromaDB 做检索。本地纯 Python,**无需任何外部服务**。

### 2.1 安装

```bash
git clone https://github.com/agiresearch/A-mem.git ../A-mem
cd ../A-mem
pip install -e .
pip install rank_bm25 sentence-transformers chromadb litellm nltk

# A-MEM 内部用 nltk 做 tokenize,首次需要拉资源
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"

cd -   # 回到 memmark 根
```

### 2.2 跑 smoke + 全部 5 个 RQ(stub 验通)

```bash
python -m memmark.examples.run_locomo_full \
    --locomo "$MEMMARK_LOCOMO_PATH" \
    --conversation 0 \
    --max-sessions 2 \
    --max-qa 20 \
    --backend amem \
    --llm-mode stub \
    --baselines watermark signed_metadata_only \
    --output ./results/amem_conv0_smoke.json
```

### 2.2.1 真实 LLM run(paper 数据)

```bash
python -m memmark.examples.run_locomo_full \
    --locomo "$MEMMARK_LOCOMO_PATH" \
    --conversation 0 \
    --backend amem \
    --llm-mode real \
    --async-assess --async-max-concurrency 4 \
    --baselines watermark no_watermark signed_metadata_only \
    --output ./results/amem_conv0_real.json
```

`--llm-mode real` 自动:
- 把 LoCoMo turn(`Speaker (D1:3): text`)直接喂 `AgenticMemorySystem.add_note()`,A-MEM 自己抽 keywords/tags/links
- carrier 候选的 update/link 目标来自 **A-MEM 真实 ChromaDB top-k**,不是 LLM 编造的 memory_id
- QA 用 LoCoMo 官方 prompt(category-aware)+ Porter-stem F1 评分
- RQ5 报 `evidence_recall_mean`,看 QA 用到的 memory 是不是真有对应的 dia_id

### 2.3 跑全 10 段对话(主网格的 1/3)

```bash
mkdir -p ./results/amem
for i in $(seq 0 9); do
    python -m memmark.examples.run_locomo_full \
        --locomo "$MEMMARK_LOCOMO_PATH" \
        --conversation $i \
        --backend amem \
        --llm-mode real \
        --async-assess --async-max-concurrency 4 \
        --baselines watermark no_watermark signed_metadata_only random_replace \
        --output ./results/amem/conv${i}.json
done
```

(去掉 `--max-sessions / --max-qa` 即跑全量;若先要快版本,加 `--max-sessions 5 --max-qa 50`。)

### 2.4 常见报错

| 报错 | 处理 |
|------|------|
| `ModuleNotFoundError: agentic_memory` | `pip install -e ../A-mem` 后再确认 `python -c "import agentic_memory"` 不报错 |
| `chromadb.errors.NoCollectionExists` | 删 `~/.chroma` 重跑 |
| `litellm.BadRequestError` | 检查 `MEMMARK_API_KEY` 与 `MEMMARK_MODEL`,A-MEM 内部用 litellm 调 LLM |

---

## 3. Backend B:Graphiti(temporal graph,需要 Neo4j)

Graphiti 必须有 Neo4j 5.x。本机起一个 docker 即可。

### 3.1 起 Neo4j

```bash
docker run -d --name memmark-neo4j \
    -p 7474:7474 -p 7687:7687 \
    -e NEO4J_AUTH=neo4j/memmark-neo4j-pass \
    -e NEO4J_PLUGINS='["apoc"]' \
    -v $HOME/.memmark-neo4j-data:/data \
    neo4j:5.20

# 验证起来了
docker logs memmark-neo4j --tail 30 | grep -i 'started\|bolt'
```

### 3.2 安装 Graphiti

```bash
git clone https://github.com/getzep/graphiti.git ../graphiti
cd ../graphiti
pip install -e .

cd -
```

### 3.3 设环境变量

```bash
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="memmark-neo4j-pass"
export MEMMARK_GRAPHITI_GROUP="memmark_$(date +%s)"

# Graphiti 用 OpenAI key 抽取 entity / edge
export OPENAI_API_KEY="<你的 OpenAI key>"
export OPENAI_MODEL="gpt-4o-mini"   # 默认就够用
```

### 3.4 跑 smoke

```bash
python -m memmark.examples.run_locomo_full \
    --locomo "$MEMMARK_LOCOMO_PATH" \
    --conversation 0 \
    --max-sessions 1 \
    --max-qa 5 \
    --backend graphiti \
    --llm-mode real \
    --async-assess --async-max-concurrency 4 \
    --baselines watermark \
    --output ./results/graphiti_smoke.json
```

### 3.5 跑全 10 段对话

```bash
mkdir -p ./results/graphiti
for i in $(seq 0 9); do
    export MEMMARK_GRAPHITI_GROUP="memmark_conv${i}"
    python -m memmark.examples.run_locomo_full \
        --locomo "$MEMMARK_LOCOMO_PATH" \
        --conversation $i \
        --backend graphiti \
        --llm-mode real \
        --async-assess --async-max-concurrency 4 \
        --baselines watermark no_watermark signed_metadata_only \
        --output ./results/graphiti/conv${i}.json
done
```

### 3.6 清空 Neo4j(每次实验前)

```bash
docker exec memmark-neo4j cypher-shell -u neo4j -p memmark-neo4j-pass \
    "MATCH (n) DETACH DELETE n"
```

### 3.7 常见报错

| 报错 | 处理 |
|------|------|
| `ServiceUnavailable: Failed to establish connection to bolt://...` | `docker ps \| grep neo4j` 确认起来了 + 端口 7687 没被占 |
| `AuthError: invalid credentials` | 重设 `NEO4J_PASSWORD` 与 `docker run` 时的 `NEO4J_AUTH` 一致 |
| Graphiti 抽取很慢 | OpenAI gpt-4o-mini 是默认; `gpt-4o` 更准但更贵 |
| `RuntimeError: graphiti_core not installed` | `cd ../graphiti && pip install -e .` |

---

## 5. Grid 主网格(两档:fast / full)

> **LoCoMo 实际数据量:10 段对话 / 272 sessions / 5,882 turns / 1,986 QA / 134k 词。**
> 下面两档分别截不同比例,看你想要的是 *一晚验通* 还是 *paper 用 final number*。

### 5.1 Fast grid(stub mode,一晚跑完;前 5 conv × `3 session / 30 QA`)

适用:第一次跑通整个 backend 网格、找 acceptance bug、验工程链路。**不能上 paper main table**(stub mode + 只覆盖 ~7% 的 LoCoMo)。

```bash
mkdir -p ./results/grid_fast

for backend in json amem graphiti; do
    for i in $(seq 0 4); do                # 前 5 段
        out=./results/grid_fast/${backend}_conv${i}.json
        [ -f $out ] && { echo "skip $out"; continue; }
        python -m memmark.examples.run_locomo_full \
            --locomo "$MEMMARK_LOCOMO_PATH" \
            --conversation $i \
            --max-sessions 3 \
            --max-qa 30 \
            --backend $backend \
            --llm-mode stub \
            --baselines watermark no_watermark signed_metadata_only random_replace \
            --output $out 2>&1 | tee ./results/grid_fast/${backend}_conv${i}.log
    done
done
```

Fast 预算(单 cell ~ 30 QA × 3 sessions ≈ ~110 LLM 调用):
- json:< 5 min(无内部 LLM,水印结构上无 bits 嵌入,纯管线 baseline)
- A-MEM:~10 min(本地 embedding + LLM 评估)
- Graphiti:~20–40 min(LLM 抽 entity / edge)

5 conv × 3 backend = 15 cell;一晚跑完,**API 成本 ≈ $4–6**(DeepSeek)。

### 5.2 Full LoCoMo grid(paper main table;10 conv × 全 sessions × 全 QA + real mode)

适用:跑出能放进论文 §10 主表的数字。**关键:`--llm-mode real --async-assess`** 与 **不传 `--max-sessions` / `--max-qa`**(driver 默认走全 LoCoMo)。

```bash
mkdir -p ./results/grid_full

for backend in json amem graphiti; do
    for i in $(seq 0 9); do                # 全 10 段
        out=./results/grid_full/${backend}_conv${i}.json
        [ -f $out ] && { echo "skip $out"; continue; }
        python -m memmark.examples.run_locomo_full \
            --locomo "$MEMMARK_LOCOMO_PATH" \
            --conversation $i \
            --backend $backend \
            --llm-mode real \
            --async-assess --async-max-concurrency 4 \
            --baselines watermark no_watermark signed_metadata_only random_replace \
            --output $out 2>&1 | tee ./results/grid_full/${backend}_conv${i}.log
    done
done
```

Full 预算(单 cell 全量 ≈ 199 QA × ~27 sessions ≈ ~680 LLM 调用):

| Backend | 单 cell wall time | 10 cell × 4 baseline 总时长 |
|---------|------------------|-------------------------|
| json | ~10 min | ~7 hr 串行 / ~1–2 hr 并发 |
| A-MEM | ~30 min | ~20 hr 串行 / ~4 hr 并发 |
| Graphiti | ~1–3 hr | ~40–120 hr 串行 / **多日** |

总成本(30 cell × ~680 LLM 调用 ≈ 20k 调用 × DeepSeek $0.0002/call):

| LLM | 全 grid API 成本 |
|-----|---------------|
| DeepSeek-Chat | ~$18 |
| GPT-4o-mini | ~$12 |
| GPT-4o | ~$200 |
| 自部署 Qwen3.5-397B | GPU-hr 替代 API,~2200 GPU-hr |

并发跑法(每段 conv 一进程):

```bash
# GNU parallel,每个 backend 4 路并发(适合 json + amem)
mkdir -p ./results/grid_full
parallel -j 4 \
    "python -m memmark.examples.run_locomo_full \
        --locomo $MEMMARK_LOCOMO_PATH \
        --conversation {1} --backend {2} \
        --llm-mode real \
        --async-assess --async-max-concurrency 4 \
        --baselines watermark no_watermark signed_metadata_only random_replace \
        --output ./results/grid_full/{2}_conv{1}.json \
        > ./results/grid_full/{2}_conv{1}.log 2>&1" \
    ::: $(seq 0 9) ::: json amem
```

> Graphiti **不要并发**(共享 Neo4j 实例会锁死),按 backend 串行跑。

### 5.3 子集策略(中间档)

如果 full grid 太重,fast grid 又太薄,可以折中跑 5 conv × full sessions,只保 watermark + signed_metadata_only 两个 baseline:

```bash
for i in $(seq 0 4); do
    python -m memmark.examples.run_locomo_full \
        --locomo "$MEMMARK_LOCOMO_PATH" \
        --conversation $i \
        --backend amem \
        --llm-mode real \
        --async-assess --async-max-concurrency 4 \
        --baselines watermark signed_metadata_only \
        --output ./results/mid_amem_conv${i}.json
done
```

5 cell × 2 baseline ≈ 1.5 hr,API ~$2,够拿 §10.5 RQ3 R3 + signed-metadata-only 边际收益的 headline 数字。

---

## 6. 读取结果

每个 `*.json` 文件包含 5 个 RQ 的全量指标。**real mode 才有 paper 可用的 F1 / evidence_recall**;stub mode 只能看 R1/R2/R3 通不通。

```bash
# headline:R3 in-record bit recovery + wrong-key gap
python -c "
import json, glob
for f in sorted(glob.glob('./results/grid_full/*.json')):
    r = json.load(open(f))
    wm = r['rq3_in_record'].get('watermark', {})
    print(f.split('/')[-1],
          'R3=', round(wm.get('r3', {}).get('bit_recovery_rate', 0), 3),
          'wrong-key=', round(wm.get('r3_wrong_key', {}).get('bit_recovery_rate', 0), 3))
"

# RQ1 + RQ2 汇总:LoCoMo F1 / capacity per baseline
python -c "
import json
r = json.load(open('./results/grid_full/amem_conv0.json'))
print('=== RQ1 utility (rows) ===')
for row in r['rq1_utility']['rows']:
    print(f\"  {row['label']:24s} qa_f1={row.get('qa_accuracy', 0):.3f} \"
          f\"bits/dec={row['capacity_bits_per_decision']:.2f} \"
          f\"mem_count={row['memory_count']}\")

print('=== RQ2 per-carrier capacity (watermark only) ===')
for tau, info in r['rq2_capacity']['watermark']['by_carrier'].items():
    print(f\"  {tau:24s} bits/dec={info['bits_per_decision']:.2f} \"
          f\"H(p_t)={info['avg_entropy']:.2f} \"
          f\"acceptance={info['acceptance_rate']:.2f}\")
"

# RQ5 evidence-grounded integrity(只在 real mode 有用)
python -c "
import json
r = json.load(open('./results/grid_full/amem_conv0.json'))
for label, rep in r['rq5_integrity'].items():
    print(f\"{label:24s} evidence_recall={rep.get('evidence_recall_mean', 0):.3f} \"
          f\"({rep.get('qa_with_full_evidence', 0)}/{rep.get('evidence_required_qas', 0)} full)\")
"

# QA 分类后的 F1(category-aware,论文 Table 4 同口径)
python -c "
import json, collections
r = json.load(open('./results/grid_full/amem_conv0.json'))
# qa_predictions 在 driver_result 里;需要用单 RQ runner 才能拿到
# 这里只展示 rq1_utility 的合计
print('Per-baseline qa F1 mean:')
for row in r['rq1_utility']['rows']:
    print(f\"  {row['label']:24s} f1≈{row.get('qa_accuracy', 0):.3f}\")
"
```

---

## 7. 跑单个 RQ(开发时)

不想每次跑全套,可以单独 import RQ runner:

```python
from memmark.backends import JsonMemoryStore
from memmark.baselines import build_baseline
from memmark.benchmarks.locomo import LoCoMoDriver, load_locomo
from memmark.benchmarks.locomo.driver import keyword_memory_extractor
from memmark.experiments import run_rq3_in_record

conv = load_locomo("locomo/data/locomo10.json")[0]
wm = build_baseline("watermark", backend=JsonMemoryStore(),
                    payload_bits="10110100"*8,
                    secret_key="my-key",
                    agent_id="dev", session_id="dev")
result = LoCoMoDriver(watermarker=wm,
                     memory_extractor=keyword_memory_extractor,
                     max_sessions=2, max_qa=10).run(conv)
print(run_rq3_in_record(driver_result=result, secret_key="my-key"))
```

---

## 8. 关键命令对照表

| 你想做的事 | 命令 |
|----------|------|
| 跑 stub smoke,只看 R3 通不通 | `--backend json --llm-mode stub --max-sessions 1 --max-qa 0` |
| 跑 paper-quality real smoke | `--backend amem --llm-mode real --async-assess --max-sessions 2 --max-qa 20` |
| 跑 R1/R2/R3 完整对比 | `--backend json --baselines watermark` |
| 跑 watermark vs metadata-only(headline ablation) | `--baselines watermark signed_metadata_only` |
| 跑攻击鲁棒性 | 默认就跑了 RQ4(9 attack × 3 strength),看 `rq4_robustness` |
| 跑 utility delta + LoCoMo F1(Table 1) | `--llm-mode real --baselines watermark no_watermark` |
| 用真实 backend 替代 json | `--backend amem` / `--backend graphiti` |
| 跨 LLM ablation | 改 `MEMMARK_MODEL`,重跑同一段 conv;`watermark_version` 字段会自动区分 |
| 换 secret key 测 wrong-key 攻击 | 在 `experiments/rq3_in_record.py` 里改 `wrong_key=` |
| 看 Merkle anchor 是否签得对 | 结果里 `r3.anchor_signature_valid == 1.0` |
| 看 evidence-grounded RQ5 | real mode + 看结果里 `rq5_integrity[label].evidence_recall_mean` |
| 调候选枚举温度 | 用 Python 入口,改 `LLMCarrierPlanner` 内部 prompt 的 temperature(默认 0.7 enum / 0.0 score) |

---

## 9. 一行命令验所有 backend

```bash
# 仅作 sanity:每个 backend 跑 1 conv × 1 session × 5 QA × watermark only(stub)
for b in json amem graphiti; do
    echo "=== $b ==="
    python -m memmark.examples.run_locomo_full \
        --locomo "$MEMMARK_LOCOMO_PATH" \
        --conversation 0 --max-sessions 1 --max-qa 5 \
        --backend $b --llm-mode stub --baselines watermark \
        --output ./results/sanity_${b}.json 2>&1 | tail -10
done
```

如果 4 行都 print 出 `r3 bit_recovery_rate=1.0`,**说明 4 个 backend 都连通了**,可以开始正式跑主网格(§5)。

---

## 10. 故障排查总览

| 现象 | 最可能原因 | 处理 |
|------|---------|------|
| `KeyError: 'memmark-default-dev-key'` | 没设 `MEMMARK_KEY` | `export MEMMARK_KEY=...` |
| `ModuleNotFoundError: torch` | AgentMark sampler 走真实路径需要 torch | `pip install torch` |
| `r3.bit_recovery_rate < 1.0` 在 json backend | 不可能;先看 `r1.commitment_pass_rate`,如果 < 1.0 说明 audit 落盘有 bug | 看 `r3.leaf_results` 里哪条失败 |
| `acceptance_rate < 0.5`(real mode) | 候选枚举太窄;调高 `T_enum` 或换更强 LLM | 改 `planner.py` 的 generate_candidates 温度,或 `MEMMARK_MODEL` 换成 deepseek-chat |
| RQ4 全部 attack 都 0% recovery | 攻击实现可能改动太狠;先单独跑 `_attack_compaction(strength=0.1)` debug | 看 `rq4_robustness.py` 的 `_attack_*` 函数 |
| `qa_accuracy = 0` 一直 | stub mode default substring judge 太弱;真测时改 `--llm-mode real` 用 LoCoMo 官方 F1 | 切 real mode 才有意义 |
| `evidence_recall_mean = 0` | dia_id 没串到 record。检查 backend.apply 的 record 里有没有 `dia_ids` 字段 | 4 个 backend 在 P2 #4 后都已支持;若仍为 0,看是不是用了旧版本 |
| real mode `RuntimeError: Set MEMMARK_API_KEY...` | 没设 LLM 凭据 | 见 §0.7,设 3 个 env(`MEMMARK_API_KEY` / `MEMMARK_BASE_URL` / `MEMMARK_MODEL`) |
| real mode 跑得很慢 | ingest/evolve 必须串行;最终 QA assessment 可并发 | 开 `--async-assess --async-max-concurrency 4`,再用 §11.4 多 conv 进程并行 |

---

## 11. 加速 —— 安全并发边界

`memmark.examples.run_locomo_full` 支持 `--async-assess`。它只并发最终 QA assessment,不并发 ingestion/evolve。

瓶颈不是 batch_size(我们没在 train),而是 LLM 调用等待。安全边界:
- ingestion/evolve 必须串行: memory state、watermark bit index、Merkle audit 都有顺序依赖。
- final QA assessment 可并发: memory snapshot 已固定,每个问题只读检索 + 回答 + 打分。

### 11.1 合并 generate + score(默认已开,~30% 加速)

`LLMCarrierPlanner` 的 `merge_gen_and_score=True` 让候选枚举与打分在**一次 LLM 调用**里完成 —— 让 LLM 直接吐 `[{text/memory_id, weight}]`,Python 端做 normalize → 概率分布。

无需任何改动,新代码默认 ON。手动关掉(回到旧两步):

```python
from memmark.carriers.planner import LLMCarrierPlanner
planner = LLMCarrierPlanner(client, fallback_carrier=..., merge_gen_and_score=False)
```

### 11.2 Async QA assessment fan-out(当前 CLI 已支持)

把最终 QA 问题并发评估。A-MEM robust QA 每题仍保持 `keyword → raw retrieval → cat-aware answer` 协议;只是多题并发。

```bash
python -m memmark.examples.run_locomo_full \
    --locomo "$MEMMARK_LOCOMO_PATH" \
    --conversation 0 \
    --backend amem \
    --llm-mode real \
    --async-assess --async-max-concurrency 4 \
    --baselines watermark no_watermark signed_metadata_only \
    --output ./results/amem_conv0_real.json
```

`--async-max-concurrency` 建议 2–8;遇到 rate limit 就降到 2。

### 11.3 多 provider 并发(历史设计;当前 CLI 未暴露)

旧版设计可把请求 round-robin 派给多个 OpenAI-compatible endpoint。**注意:论文实验的单条 trace 必须钉死一个 LLM**(否则 `watermark_version` mismatch),所以多 provider 只用于 *无 paper claim* 的开发 / debug / 加速 baseline 跑批。

```python
from memmark.llm import MultiProviderClient

mp = MultiProviderClient(
    [
        {
            "name": "deepseek",
            "base_url": "https://api.deepseek.com",
            "api_key": "<DeepSeek key>",
            "model": "deepseek-chat",
        },
        {
            "name": "qwen-dashscope",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "<DashScope key>",
            "model": "qwen3.5-coder-a3b-instruct",
        },
        {
            "name": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "<OpenRouter key>",
            "model": "deepseek/deepseek-chat",
        },
    ],
    mode="weighted_random",      # 或 "round_robin"
    async_mode=True,             # 配合 §11.2 用,效果最佳
)
planner = LLMCarrierPlanner(mp, fallback_carrier=..., async_assess=True)
```

### 11.4 多 conv 并行进程(N× 加速,N = 进程数)

backend 进程之间相互独立(json / amem 各持一个 ChromaDB / SQLite 文件),开 GNU parallel:

```bash
parallel -j 4 \
    "python -m memmark.examples.run_locomo_full \
        --locomo $MEMMARK_LOCOMO_PATH \
        --conversation {1} --backend {2} \
        --baselines watermark no_watermark signed_metadata_only random_replace \
        --output ./results/grid_full/{2}_conv{1}.json \
        > ./results/grid_full/{2}_conv{1}.log 2>&1" \
    ::: $(seq 0 9) ::: json amem
```

> Graphiti **不要** parallel —— Neo4j session 不耐多进程并发,单进程串行跑。

### 11.5 缓存 prompt → response(~2× 加速重跑)

实验同一段 conv 多次(seed 改变 / baseline 切换)时,extract / assess / score 的 prompt 都是确定性的,可以缓存:

```python
import hashlib, json, os
class CachedClient:
    def __init__(self, inner, cache_dir=".llm_cache"):
        self.inner = inner; os.makedirs(cache_dir, exist_ok=True); self.cache_dir = cache_dir
    def complete(self, messages, **kw):
        key = hashlib.sha256(json.dumps([messages, kw], sort_keys=True, default=str).encode()).hexdigest()
        path = f"{self.cache_dir}/{key}.txt"
        if os.path.exists(path): return open(path).read()
        out = self.inner.complete(messages, **kw)
        open(path, "w").write(out)
        return out
```

把它包到 `OpenAIChatClient` 外面即可。

### 11.6 加速效果总览

按 `1 cell = LoCoMo 1 conv (199 QA × 27 sessions) ≈ 680 串行 LLM call ≈ 30 min wall (DeepSeek 1.3 s/call)` 算:

| 优化 | 单 cell 时长 | 全网格(40 cell) wall time |
|------|------------|------------------------|
| 默认(ingest/evolve 串行 + QA 串行) | ~30 min | ~20 hr |
| §11.2 async QA assessment | 取决于 QA 占比 | 取决于 QA 占比 |
| §11.4 4-way 进程并行 | ~30 min × 1/4 | ~5 hr |
| §11.5 缓存(同一 conv 重跑) | 取决于缓存命中率 | 取决于缓存命中率 |

---

跑通 §1 + §2 之后(JsonMemoryStore + A-MEM),你已经有头条 RQ3 的真实数字。Graphiti 是验证 backend 不变性(B4 simplicity check)和 KG 攻击(KGMark baseline)用的,可以晚一点接。
