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

# 0.7 LLM 凭据(选一)
export MEMMARK_BASE_URL="https://openrouter.ai/api/v1"   # 或 deepseek 直连等
export MEMMARK_API_KEY="<你的 OpenRouter / DeepSeek / OpenAI key>"
export MEMMARK_MODEL="deepseek/deepseek-chat"            # 或 qwen3.5 等
```

> **注:** 仓库根目录里 `agentmark/` 是 AgentMark 的源码副本,不需要单独 pip install。`memmark/core/sampler.py` 直接 `from agentmark.core.watermark_sampler import sample_behavior_differential`。

---

## 1. Smoke:JsonMemoryStore(无外部依赖,2 分钟跑通)

跑这一步**先确认管线本身没坏**,再去搞真实 backend。

```bash
python -m memmark.examples.run_locomo_full \
    --locomo "$MEMMARK_LOCOMO_PATH" \
    --conversation 0 \
    --max-sessions 2 \
    --max-qa 10 \
    --backend json \
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
  "bit_recovery_rate": 0.61
}
```

R3 = 1.0、wrong-key < 0.7 ⇒ 管线 OK。

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

### 2.2 跑 smoke + 全部 5 个 RQ

```bash
python -m memmark.examples.run_locomo_full \
    --locomo "$MEMMARK_LOCOMO_PATH" \
    --conversation 0 \
    --max-sessions 2 \
    --max-qa 20 \
    --backend amem \
    --baselines watermark signed_metadata_only \
    --output ./results/amem_conv0.json
```

### 2.3 跑全 10 段对话(主网格的 1/3)

```bash
mkdir -p ./results/amem
for i in $(seq 0 9); do
    python -m memmark.examples.run_locomo_full \
        --locomo "$MEMMARK_LOCOMO_PATH" \
        --conversation $i \
        --max-sessions 5 \
        --max-qa 50 \
        --backend amem \
        --baselines watermark no_watermark signed_metadata_only random_replace \
        --output ./results/amem/conv${i}.json
done
```

### 2.4 常见报错

| 报错 | 处理 |
|------|------|
| `ModuleNotFoundError: agentic_memory` | `pip install -e ../A-mem` 后再确认 `python -c "import agentic_memory"` 不报错 |
| `chromadb.errors.NoCollectionExists` | 删 `~/.chroma` 重跑 |
| `litellm.BadRequestError` | 检查 `MEMMARK_API_KEY` 与 `MEMMARK_MODEL`,A-MEM 内部用 litellm 调 LLM |

---

## 3. Backend B:Cognee(异步 KG,用 SQLite + 本地 vec)

Cognee 默认用 SQLite (relational) + LanceDB (vector) + NetworkX (graph),**不需要 Neo4j**。

### 3.1 安装

```bash
git clone https://github.com/topoteretes/cognee.git ../cognee
cd ../cognee
pip install -e .

# Cognee 自己的 LLM key(可与 MemMark 共用)
cp .env.example .env
# 编辑 .env,把 LLM_API_KEY=<你的 key> 填进去
# 同时记得设 LLM_PROVIDER (openai / openrouter / etc)

cd -
```

### 3.2 跑 smoke

```bash
# Cognee 把每条 memory 当一个 dataset 条目;给个隔离的 dataset 名
export MEMMARK_COGNEE_DATASET="memmark_smoke_$(date +%s)"

python -m memmark.examples.run_locomo_full \
    --locomo "$MEMMARK_LOCOMO_PATH" \
    --conversation 0 \
    --max-sessions 1 \
    --max-qa 5 \
    --backend cognee \
    --baselines watermark \
    --output ./results/cognee_smoke.json
```

> **慢:** Cognee 的 `cognify()` 会跑 KG 抽取(LLM call × 多个 task),smoke 也得 5–15 分钟。先跑 1 session 验通,再扩大。

### 3.3 把 cognify 关掉省时间(只测 add → search 路径)

如果只是想跑通 watermark + audit,不需要让 KG 真的构建:

```python
# 在 examples/run_locomo_full.py 里把
load_cognee()
# 改成
load_cognee(run_cognify=False)
```

或直接用环境变量:

```bash
export MEMMARK_COGNEE_RUN_COGNIFY=false   # (需要在 cognee_store.py 里读这个 env;暂不支持,见下)
```

(目前 `run_cognify` 是构造参数,不读 env;改 `examples/run_locomo_full.py` 里的 `_build_backend("cognee")` 把 `run_cognify=False` 传进去即可。)

### 3.4 跑全 10 段对话

```bash
mkdir -p ./results/cognee
for i in $(seq 0 9); do
    export MEMMARK_COGNEE_DATASET="memmark_conv${i}_$(date +%s)"
    python -m memmark.examples.run_locomo_full \
        --locomo "$MEMMARK_LOCOMO_PATH" \
        --conversation $i \
        --max-sessions 3 \
        --max-qa 30 \
        --backend cognee \
        --baselines watermark no_watermark signed_metadata_only \
        --output ./results/cognee/conv${i}.json
done
```

### 3.5 常见报错

| 报错 | 处理 |
|------|------|
| `RuntimeError: cognee not installed` | `cd ../cognee && pip install -e .` |
| `DatabaseNotCreatedError` | 第一次 add 之前,Cognee 会自动建库;若被中断,删 `~/.cognee` 重跑 |
| `LLM_API_KEY not set` | Cognee 自己的 env,**和 `MEMMARK_API_KEY` 不互通**,要在 `cognee/.env` 里单独填 |
| 跑很慢 | 把 `--max-sessions` 调小,或在 Cognee `.env` 里把 `EMBEDDING_PROVIDER` 改成本地模型 |

---

## 4. Backend C:Graphiti(temporal graph,需要 Neo4j)

Graphiti 必须有 Neo4j 5.x。本机起一个 docker 即可。

### 4.1 起 Neo4j

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

### 4.2 安装 Graphiti

```bash
git clone https://github.com/getzep/graphiti.git ../graphiti
cd ../graphiti
pip install -e .

cd -
```

### 4.3 设环境变量

```bash
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="memmark-neo4j-pass"
export MEMMARK_GRAPHITI_GROUP="memmark_$(date +%s)"

# Graphiti 用 OpenAI key 抽取 entity / edge
export OPENAI_API_KEY="<你的 OpenAI key>"
export OPENAI_MODEL="gpt-4o-mini"   # 默认就够用
```

### 4.4 跑 smoke

```bash
python -m memmark.examples.run_locomo_full \
    --locomo "$MEMMARK_LOCOMO_PATH" \
    --conversation 0 \
    --max-sessions 1 \
    --max-qa 5 \
    --backend graphiti \
    --baselines watermark \
    --output ./results/graphiti_smoke.json
```

### 4.5 跑全 10 段对话

```bash
mkdir -p ./results/graphiti
for i in $(seq 0 9); do
    export MEMMARK_GRAPHITI_GROUP="memmark_conv${i}"
    python -m memmark.examples.run_locomo_full \
        --locomo "$MEMMARK_LOCOMO_PATH" \
        --conversation $i \
        --max-sessions 3 \
        --max-qa 30 \
        --backend graphiti \
        --baselines watermark no_watermark signed_metadata_only \
        --output ./results/graphiti/conv${i}.json
done
```

### 4.6 清空 Neo4j(每次实验前)

```bash
docker exec memmark-neo4j cypher-shell -u neo4j -p memmark-neo4j-pass \
    "MATCH (n) DETACH DELETE n"
```

### 4.7 常见报错

| 报错 | 处理 |
|------|------|
| `ServiceUnavailable: Failed to establish connection to bolt://...` | `docker ps \| grep neo4j` 确认起来了 + 端口 7687 没被占 |
| `AuthError: invalid credentials` | 重设 `NEO4J_PASSWORD` 与 `docker run` 时的 `NEO4J_AUTH` 一致 |
| Graphiti 抽取很慢 | OpenAI gpt-4o-mini 是默认; `gpt-4o` 更准但更贵 |
| `RuntimeError: graphiti_core not installed` | `cd ../graphiti && pip install -e .` |

---

## 5. 4 个 backend 同时跑(完整 backend × benchmark 主网格)

```bash
mkdir -p ./results/grid

for backend in json amem cognee graphiti; do
    for i in $(seq 0 4); do                # 先跑前 5 段对话(seed=1)
        out=./results/grid/${backend}_conv${i}.json
        [ -f $out ] && { echo "skip $out"; continue; }
        python -m memmark.examples.run_locomo_full \
            --locomo "$MEMMARK_LOCOMO_PATH" \
            --conversation $i \
            --max-sessions 3 \
            --max-qa 30 \
            --backend $backend \
            --baselines watermark no_watermark signed_metadata_only random_replace \
            --output $out 2>&1 | tee ./results/grid/${backend}_conv${i}.log
    done
done
```

预算估计(LoCoMo 5 段 × 4 backend × 4 baseline,每段 30 QA,3 sessions):
- json:< 5 min
- A-MEM:~10 min(本地 embedding)
- Cognee:~30–60 min(LLM 抽 KG)
- Graphiti:~20–40 min(LLM 抽 entity)

---

## 6. 读取结果

每个 `*.json` 都是单一文件,用任意工具读:

```bash
# headline:R3 in-record bit recovery
python -c "
import json, glob
for f in sorted(glob.glob('./results/grid/*.json')):
    r = json.load(open(f))
    wm = r['rq3_in_record'].get('watermark', {})
    print(f, 'R3=', wm.get('r3', {}).get('bit_recovery_rate'),
              'wrong-key=', wm.get('r3_wrong_key', {}).get('bit_recovery_rate'))
"

# 全 RQ 汇总(per-baseline)
python -c "
import json
r = json.load(open('./results/grid/amem_conv0.json'))
for k in ('rq1_utility','rq2_capacity','rq3_in_record','rq4_robustness','rq5_integrity'):
    print('===', k); print(json.dumps(r[k], indent=2)[:800])
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
| 跑 smoke,只看 R3 通不通 | `--backend json --max-sessions 1 --max-qa 0` |
| 跑 R1/R2/R3 完整对比 | `--backend json --baselines watermark` |
| 跑 watermark vs metadata-only(headline ablation) | `--baselines watermark signed_metadata_only` |
| 跑攻击鲁棒性 | 默认就跑了 RQ4(9 attack × 3 strength),看 `rq4_robustness` |
| 跑 utility delta(论文 Table 1) | `--baselines watermark no_watermark` |
| 用真实 backend 替代 json | `--backend amem` / `--backend cognee` / `--backend graphiti` |
| 跨 LLM ablation | 改 `MEMMARK_MODEL`,重跑同一段 conv;`watermark_version` 字段会自动区分 |
| 换 secret key 测 wrong-key 攻击 | 在 `experiments/rq3_in_record.py` 里改 `wrong_key=` |
| 看 Merkle anchor 是否签得对 | 结果里 `r3.anchor_signature_valid == 1.0` |

---

## 9. 一行命令验所有 backend

```bash
# 仅作 sanity:每个 backend 跑 1 conv × 1 session × 5 QA × watermark only
for b in json amem cognee graphiti; do
    echo "=== $b ==="
    python -m memmark.examples.run_locomo_full \
        --locomo "$MEMMARK_LOCOMO_PATH" \
        --conversation 0 --max-sessions 1 --max-qa 5 \
        --backend $b --baselines watermark \
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
| `acceptance_rate < 0.5` | 候选枚举太窄;调高 `T_enum` 或换更强 LLM | 改 `planner.py` 的 generate_candidates 温度,或 `MEMMARK_MODEL` 换成 deepseek-chat |
| RQ4 全部 attack 都 0% recovery | 攻击实现可能改动太狠;先单独跑 `_attack_compaction(strength=0.1)` debug | 看 `rq4_robustness.py` 的 `_attack_*` 函数 |

---

跑通 §1 + §2 之后(JsonMemoryStore + A-MEM),你已经有头条 RQ3 的真实数字。Cognee + Graphiti 是验证 backend 不变性(B4 simplicity check)和 KG 攻击(KGMark baseline)用的,可以晚一点接。
