# 面向长期记忆 Agent 的 Memory Watermark 系统

## 1. 背景与 Motivation —— State-Evolution Provenance

长期记忆 agent 会把用户对话、偏好、项目状态、规则、决策过程持续写入 memory。问题在于：

- 这些 memory 是 agent 核心能力的一部分，但目前很难证明"某段长期记忆轨迹是某个特定 agent 系统生成的"。
- 普通日志只能证明"发生过一次写入"，不能证明"这次写入来自带私钥控制的特定系统"。
- 在 memory 被导出、迁移、蒸馏、复用甚至被第三方挪用后，缺少 provenance 机制。

本项目的 **核心 claim 是:

> **State-Evolution Provenance** —— 在 agent 的 *latent long-term state* 演化过程中嵌入可验证水印,
> 让我们能回答 "*who changed the long-term state*",
> 即便这次改动 **没有产生任何可见的 action 或 tool call**。

与已有的 agent watermark 工作的本质区别:

| 工作 | watermark 层 | 验证需要的证据 | 能否归因到"无可见行为的 state 改动" |
|------|-------------|---------------|---------------------------------|
| AgentMark / Agent Guide | planning / tool / subgoal 决策 | action trajectory | 否 |
| ActHook | trajectory 中的 hook action | trajectory dataset | 否 | 
| AGENTWM | tool 执行路径等价类 | tool call sequence | 否 |
| **本项目 (State-Evolution Provenance)** | **memory evolve 决策 (update / link / semantic / merge)** | **memory snapshot + 部分 reveal log** | **是** |

因此这里要做的是：

- 对 `memory evolution` 这条 latent state 演化路径做 behavioral watermark
- 让 watermark 嵌入 *state-transition* 决策中（而非可见行为决策）
- 后续可仅从 *memory snapshot* + *cryptographic audit trace* 验证其来源,**不需要完整 action trajectory**

## 2. 为什么要做这个 Watermark

核心价值有四类，每一类都和 state-evolution provenance 这条主线对齐：

- `Ownership / Provenance (state-level)`
  证明某套长期 memory state 由某个 agent runtime 演化得到，而不只是某段 action 被某个 agent 跑过。
  ↳ 机制见 §4.2 carrier taxonomy + §7 sampling 算法;验证见 §10.5 RQ3 (R1/R2/R3 三档,尤其 R3 snapshot-only,论文 headline);量化指标见 §10.2 (bit recovery / decode success / wrong-key acceptance)。
- `Forensics (persistence-layer attribution)`
  在 memory 被复制、二次封装、跨系统迁移后，即便 action trajectory 已不可得，仍能做归因分析。
  ↳ 关键实验见 §10.5 RQ3 R3 (snapshot-only verification,headline);威胁面见 §10.6 RQ4 攻击模型中的 `poisoning / pruning / manual edits` 行。
- `Tamper Detection (commitment-bound)`
  当 memory history 被压缩、篡改、重排时，commitment + Merkle log 可独立检测，不依赖 memory system 数据库自身的诚实性。
  ↳ 机制见 §9 (per-decision commitment + per-session Merkle log + signed root);量化指标见 §10.6 RQ4 表格中的 `tamper detection rate` 列 (commitment 校验失败率)。


## 3. 目标场景

适用的真实场景：

- 长期陪伴型 agent
- 个人助理 / 工作流 agent
- 多 session coding agent
- 企业知识助手
- 多 agent 系统中的 per-agent memory namespace


## 4. 任务定义

我们要 watermark 的对象不是最终回答文本，而是 `memory operation selection`，即 `memory evolve` 决策。

在本项目里，先聚焦三个 memory system：

- `Cognee`
- `A-MEM`
- `Graphiti`

并且只研究以下四类最有代表性的细粒度 watermark 载体：

- 哪条 memory 被更新
- 哪个 existing memory 被链接
- 同一事实写成哪个语义等价版本
- 哪个 merge strategy 被采用

选择这四类的原因是：

- 它们都发生在 `memory evolve` 过程内部，而不是最终回答表面
- 它们都可以通过“等价候选选择”来嵌水印，较不容易直接伤害 utility
- 它们在 `Cognee / A-MEM / Graphiti` 这三类结构化 memory system 里都能找到自然对应物
不用粗粒度 watermark 容量太低。
  如果只在 ADD / UPDATE / DELETE / NONE 这种层面嵌，单次决策能承载的信息非常有限，而且很多真实 turn 根本不会同时存在这四种都合理的候选。长期记忆写入本来就比
  普通 agent step 稀疏，粗粒度操作再压一层，最终 bit rate 会很低。
  
### 4.1 三个 Memory System 中的具体定义

#### Cognee

在 Cognee 里，memory 更接近持续演化的 knowledge graph / triplet store，因此这四类 watermark 可以定义为：

- `哪条 memory 被更新`
  - 多个已有 node / triplet / fact snippet 都可能与新信息相关，系统需要决定更新哪一个已有表示。
- `哪个 existing memory 被链接`
  - 新信息写入时，可以挂接到不同已有 entity、triplet cluster 或 node set。
- `同一事实写成哪个语义等价版本`
  - 同一关系或事实可以用不同但语义等价的 canonical description / relation formulation 表达。
- `哪个 merge strategy 被采用`
  - 对相似 entity / relation，是保留分离、做 canonical merge，还是在图中保留弱连接。

#### A-MEM

在 A-MEM 里，memory 更接近 agentic notes 与动态组织网络，因此这四类 watermark 可以定义为：

- `哪条 memory 被更新`
  - 多条历史 note 都可能和当前经验相关，系统需要决定更新哪条已有 note。
- `哪个 existing memory 被链接`
  - 新 note 可以链接到不同已有 notes、tags、keywords cluster 或 memory box。
- `同一事实写成哪个语义等价版本`
  - 同一经验可以用不同的 contextual description、keywords、tags 组合来表述。
- `哪个 merge strategy 被采用`
  - 对高相似 note，是直接合并、保留并双向链接，还是只做弱关联与共现组织。

#### Graphiti

在 Graphiti 里，memory 更接近 temporal context graph，因此这四类 watermark 可以定义为：

- `哪条 memory 被更新`
  - 多个已有 fact edge、entity summary 或 episodic trace 都可能是更新对象，系统需要决定更新哪一个。
- `哪个 existing memory 被链接`
  - 新 episodic / factual information 可以连接到不同已有 entity、edge 或 episode chain。
- `同一事实写成哪个语义等价版本`
  - 同一 temporal fact 可以采用不同但语义等价的 edge label、fact phrasing 或 summary phrasing。
- `哪个 merge strategy 被采用`
  - 对冲突或相似事实，是 supersede 旧事实、invalidate 旧边、并存两个时间窗口，还是归并 entity summary。

### 4.2 Backend-Invariant Carrier Taxonomy

虽然三种 system 的内部结构不同，但这四类 evolve 决策可以统一抽象成同一个数学对象。我们把每一次 memory 写入决策形式化为一个可被 watermark sampler 接管的 `state-transition decision point`。

#### 4.2.1 形式化定义

设 memory state 在 turn `t` 为 `M_t`，新到达信息为 `e_t`，则 evolve 决策被定义为一个四元组：

```text
D_t = ⟨τ, C_t, p_t, ctx_t⟩
```

- `τ ∈ {update, link, semantic, merge}` —— carrier 类型 (load 哪一种 state-transition 自由度)
- `C_t = {c_t^1, …, c_t^k}` —— 候选集合 (k ≥ 2 才能嵌入信息)
- `p_t : C_t → [0,1]` —— LLM 给出的可接受度分布 (∑ = 1)
- `ctx_t` —— 与该决策绑定的上下文 (见 §8)

watermark sampler 仅作用在 `(C_t, p_t, ctx_t)` 上，不读不写 backend 的内部结构。这就是 `backend-invariant` 的含义：sampler 与 Cognee / A-MEM / Graphiti 完全解耦。

#### 4.2.2 四类 Carrier 的统一签名

| Carrier `τ` | 候选 `c` 的语义 | state-transition 性质 | 三个 backend 的具体实例 |
|-------------|----------------|----------------------|------------------------|
| `update_target` | 旧 memory 的 id | 改变 *哪一条* 已有 state | Cognee node id / A-MEM note id / Graphiti edge id |
| `link_target` | 已有 memory 的 id 或集合 | 改变 *拓扑连接* | KG entity / note keyword cluster / entity-edge attach point |
| `semantic_realization` | 同义改写候选文本 | 改变 *表述形式*,不改变事实 | triplet phrasing / note description+tags / edge label phrasing |
| `merge_policy` | `{keep_separate, canonical_merge, weak_link, supersede, coexist_temporal}` 子集 | 改变 *truth-maintenance 行为* | KG canonicalization / note evolve strategy / fact invalidation |

#### 4.2.3 Backend Adapter 的最小接口

要把任意 memory backend 接入 watermark 层，只需要实现:

```text
enumerate_candidates(M_t, e_t, τ) -> C_t
score_candidates(C_t, ctx_t) -> p_t
apply_selected(M_t, c*) -> M_{t+1}
```

- `enumerate_candidates` 决定该 backend 在该 carrier 上有多少 evolve 自由度
- `score_candidates` 复用 LLM-as-judge 或 backend 自带的 ranker
- `apply_selected` 是唯一一个 backend-specific 的写入路径

watermark sampler 只看 `(C_t, p_t)`,因此论文里可以独立报告每类 carrier 在每个 backend 上的:

- average candidate-set size `|C_t|` (容量上界)
- entropy `H(p_t)` (实际可嵌入 bit 上界)
- per-carrier acceptance rate (有多少 turn 满足 `|C_t| ≥ 2`)



## 5. 系统形态

真实 watermark 需要在线 agent runtime，而不是纯离线脚本。

建议结构：

- `LLM`
  生成 memory 候选及其概率。本项目固定使用两个 LLM:
  - **DeepSeek v4 Pro** —— headline + cost 主线,与 `agentmark/proxy/server.py` 现有 DeepSeek 路径无缝衔接
  - **Qwen3.5-397B-A17B** —— reproducibility + open-weights 主线,确保 audit trace 可被独立重放
  调用形态均为 OpenAI-compatible API。候选枚举阶段 `T=0.7`,scoring 阶段 `T=0.0`,统一开 JSON 模式以对齐 `agentmark/sdk/prompt_adapter.py` 的 `action_weights` 协议。
- `Agent harness`
  管理 turn、session、agent identity、hooks。
- `Memory system`
  负责实际写入与检索，如 `Cognee`、`A-MEM`、`Graphiti`。
- `Watermark selector`
  用私钥控制的采样器，在候选中做可验证选择，`AgentMark`。
- `Audit store`
  记录可验证 trace。

### 5.1 Memory System 适配

本项目把 `memory system` 视为可替换后端，而不是绑定单一实现。不同系统的内部记忆结构不同，但都可以接到同一个 watermark 抽象层上。

- `Cognee`
  把 watermark 放在：
  - node attachment selection
  - triplet / relation formulation
  - canonicalization / merge choice
  - temporal graph update choice
- `A-MEM`
  把 watermark 放在：
  - note linking
  - keyword / tag / context description selection
  - note evolve / merge / organization strategy
- `Graphiti`
  把 watermark 放在：
  - entity / edge linking
  - fact invalidation vs new fact creation
  - temporal fact rewrite choice
  - merge / supersede policy

因此，系统形态上不要求所有 memory backend 暴露完全相同的内部操作，而是要求它们都能提供：

- 一个可观测的 `memory evolve` 生命周期
- 一个可枚举的候选选择空间
- 一个可记录的 audit trace

本项目**不引入额外的 agent harness**。`Cognee` / `A-MEM` / `Graphiti` 各自的官方仓库都已经文档化了"如何接入 LLM、跑 LoCoMo / LongMemEval / MemoryAgentBench 的 evaluation"这条端到端路径,我们直接复用各自原生的 LLM 接入与 benchmark 评测脚本,不需要再写一层协调层。watermark 仅在 backend 已经暴露的 evolve 入口挂上 §4.2.3 的 adapter 与 §9 的 audit trace,改动量限制在 backend 自身的 native API wrapper 上。

## 6. Benchmark 设计

不建议只用单一 benchmark。一个可信的长期记忆 watermark 评测，应该覆盖：

- 长对话 QA 与事件总结
- 多 session 推理
- 知识更新与时间变化
- memory 的结构化组织能力
- 在线 / streaming memory 演化场景


### 6.2 Benchmark 分工

#### LoCoMo

适合测：

- 长时间跨度多 session 对话记忆
- conversation-level QA
- event summarization
- retrieval-augmented memory utility

LoCoMo 官方仓库说明当前公开版本是 `10` 个长对话样本；每个样本包含：

- `conversation` 及各 session 时间戳
- `observation`
- `session_summary`
- `event_summary`
- 带 `evidence` 的 `qa`

这使它非常适合：

- session replay
- memory write / recall 评测
- watermark 在长对话轨迹上的恢复测试

LoCoMo 官方信息：

- 仓库说明：当前 benchmark 由十个长对话组成，并带 QA 与 event summarization 标注  
  https://github.com/snap-research/locomo
- 论文：`Evaluating Very Long-Term Conversational Memory of LLM Agents`  
  https://arxiv.org/abs/2402.17753

#### LongMemEval

适合测：

- knowledge updates
- temporal reasoning
- multi-session reasoning
- information extraction
- abstention

LongMemEval 官方仓库说明它包含 `500` 个高质量问题，并专门测试五类长期记忆能力：

- Information Extraction
- Multi-Session Reasoning
- Knowledge Updates
- Temporal Reasoning
- Abstention

这对 memory watermark 很关键，因为 watermark 不能显著破坏：

- 用户事实抽取
- 事实随时间更新
- 会话间信息链接
- 在无法回答时正确 abstain

LongMemEval 官方信息：

- 仓库：`Benchmarking Chat Assistants on Long-Term Interactive Memory`  
  https://github.com/xiaowu0162/LongMemEval
- 论文：  
  https://arxiv.org/abs/2410.10813

#### MemoryAgentBench

适合测：

- 在 *incremental multi-turn interactions* 下的 memory 行为
- 四类 core competencies: `accurate retrieval` / `test-time learning` / `long-range understanding` / `selective forgetting`
- agent 端从 context-based / RAG 到 external memory module 的全谱系评测
- 包括 EventQA 与 FactConsolidation 两个新数据集,直接覆盖 *准确检索* 与 *选择性遗忘*

这对 memory watermark 重要的原因是:

- `accurate retrieval` 直接对应 `update_target / link_target` 这两类 carrier 的 utility 底线
- `selective forgetting` 是触发 §10.6 中 `pruning` 攻击的天然评测面
- `incremental multi-turn` 形式覆盖了 streaming 演化场景,用一个 benchmark 同时压住"结构化组织 + 持续演化"两条路径,不用再单列其它

MemoryAgentBench 官方信息：

- 仓库: https://github.com/HUST-AI-HYZ/MemoryAgentBench
- 论文 (ICLR 2026)：`Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions`  
  https://arxiv.org/abs/2507.05257
- 数据集: https://huggingface.co/datasets/ai-hyz/MemoryAgentBench

### 6.3 推荐 Benchmark 组合

固定三组(LoCoMo + LongMemEval + MemoryAgentBench):

- `LoCoMo`
  负责长对话、多 session、QA、event summary。
- `LongMemEval`
  负责 knowledge update、temporal reasoning、abstention。
- `MemoryAgentBench`
  负责 incremental multi-turn 下的 retrieval / test-time learning / long-range understanding / selective forgetting,同时覆盖结构化组织与持续演化。

一个更完整的说法是：

- `LoCoMo` 测 conversation memory
- `LongMemEval` 测 long-term interactive memory mechanics
- `MemoryAgentBench` 测 incremental memory agent 的四类 core competencies

## 7. 核心算法

**watermark 嵌入机制直接复用 AgentMark**,不引入新的 sampling 算法。

具体地,每次 §4.2.3 adapter 在一个 evolve 决策点产出三元组 `(C_t, p_t, ctx_t)` 后,直接调用 AgentMark 的 sampler:

- [agentmark/sdk/watermarker.py](/Users/henry_mao/AgentMark/agentmark/sdk/watermarker.py:48) —— `AgentWatermarker.sample(probabilities, context, ...)`
- [agentmark/core/watermark_sampler.py](/Users/henry_mao/AgentMark/agentmark/core/watermark_sampler.py:16) —— distribution-preserving binning + DRBG-driven keyed selection
- [README_en.md](/Users/henry_mao/AgentMark/README_en.md:38) —— 算法细节与 capacity / utility 分析

- **输入端**(§4.2 / §4.2.3) —— 把 memory evolve 决策抽象成 sampler 能消费的 `(C_t, p_t, ctx_t)`
- **输出端**(§9) —— 把 sampler 的 keyed selection 锁进 commitment + Merkle log,使 watermark 从 runtime-only 的归因机制升级为 lifecycle-survivable 的 provenance 证据(详见 §9.5)


## 8. Memory Watermark 的输入与上下文

建议 context key 绑定以下信息：

- `agent_id`
- `user_id`
- `session_id`
- `turn_id`
- `timestamp`
- `retrieved_memory_ids`
- `recent_dialog_ids`

示例：

```text
agent_id || user_id || session_id || turn_id || recent_dialog_ids || retrieved_memory_ids
```

这样能避免 watermark 脱离真实运行上下文。

## 9. Cryptographic Audit Trace

普通 JSON log 不够。一个可在 forensics 场景成立的 audit trace 必须满足：

- **append-only** —— 不可被回溯改写
- **commit-then-reveal** —— 决策时刻先承诺,事后才暴露候选/概率
- **partial-verifiable** —— 任何子集都可以被独立验证而不需要完整日志

因此本项目把 audit trace 设计成 commitment + Merkle log 的两层结构,而不是平面 JSON。

### 9.1 Per-decision Commitment

在每次 evolve 决策 `D_t` 发生时，watermark sampler 立即产出一个 commitment:

```text
commit_t = H(
    ctx_t           ||
    H(C_t)          ||   # 候选集合的有序 hash
    H(p_t)          ||   # 概率向量的有序 hash (定长量化)
    selected_idx    ||
    bits_embedded   ||
    nonce_t
)
```

其中:

- `H = SHA-256` (或 BLAKE3)
- `C_t / p_t` 在 hash 前要做 canonical serialization (排序 + 定点量化),否则验证端重建时哈希不可复现
- `nonce_t` 由 `PRF(K, ctx_t)` 派生,而不是 system random

`commit_t` 立刻写入下文的 Merkle log,只有它在写入时是 binding 的。原始的 `(C_t, p_t, selected_idx)` 之后存为 `reveal record`,验证时才比对。

↳ **支撑 RQ4 (§10.6)** —— commitment 校验失败率即 §10.6 表格中的 `tamper detection rate` 列,直接对应 `manual edits` 与 `poisoning` 两类攻击的 detection 信号。

### 9.2 Per-session Merkle Log

每个 session 维护一棵 Merkle tree:

```text
leaf_t   = commit_t
root_T   = MerkleRoot(leaf_1, …, leaf_T)
header_T = (agent_id, user_id, session_id, T, root_T, sig_K(root_T))
```

`session_header` 是公开锚点,可以:

- 周期性写入 memory system 自身的 history / changelog 末端,作为 in-storage anchor
- 周期性外发到独立 audit store (S3 + object lock / transparency log)

这样即便 memory system 内部的 history / changelog 被篡改,只要外部 anchor 还在,任何子集 commitments 都可以通过 Merkle proof 被验证属于原始 session。

↳ **支撑 RQ3 R2 (§10.5) 与 RQ4 (§10.6)** —— Merkle proof 是 R2 (Snapshot + Partial Reveal) 在保留比例 `∈ {90%, 70%, …, 10%}` 下能平滑下降而非直接归零的物理基础,同时也是 `compaction / dedup / pruning` 攻击下"任意子集仍可验证"的密码学机制。

### 9.3 Reveal Record

`reveal_t` 是相对独立的存储对象,可以与 commitment 解耦:

```text
reveal_t = {
    trace_id, agent_id, user_id, session_id, turn_id, round_num,
    carrier_type τ,
    candidate_set C_t (canonical order),
    probabilities p_t (quantized),
    selected_candidate c*,
    bits_embedded, watermark_version,
    nonce_t
}
```

`watermark_version` 必须把 LLM 身份完整记录,否则换模型重放就过不了 verification。本项目的两个固定取值:

```text
agentmark-mem-v1::deepseek-v4-pro@<api-version>::T_score=0.0::T_enum=0.7::json_mode=true
agentmark-mem-v1::qwen3.5-397b-a17b@<weights-hash>::T_score=0.0::T_enum=0.7::json_mode=true
```

`<api-version>` 用 vendor 返回的 `model` 字段,`<weights-hash>` 用 open-weights 模型的权重 SHA。这两个字符串都参与 §9.1 中 `commit_t` 的哈希,任一项变化都会让 commitment 失配。

验证时:

- 用 `reveal_t` 重新计算 `commit_t'`
- 检查 `commit_t' == leaf` 且 `MerkleProof(leaf, root_T)` 通过
- 用相同 `K` 重放采样器,核对 `selected_candidate` 是否落在 keyed 的中标区间

只有以上三步全部通过,该决策才被认为 *"带水印地、可验证地、未被篡改地"* 产生过。

↳ **支撑 RQ1 / RQ2 跨 LLM 实验 (§10.3 / §10.4)** —— `watermark_version` 把 DeepSeek v4 Pro 与 Qwen3.5-397B-A17B 的身份(model id + api-version / weights-hash + 温度 + JSON 模式)一起 hash 进 `commit_t`,任一项变化即 commitment 失配,从而保证 §10.3 utility 对比与 §10.4 capacity 报告在跨 LLM 复现时不会被误读为同一 audit trace。

### 9.4 与 Memory System 自身 history 的关系

三种 memory system 都有不同形式的内置 changelog:

- `Cognee` —— graph/triplet 的 update history 与 dataset 版本
- `A-MEM` —— note 的 evolve / link 修改历史
- `Graphiti` —— temporal graph 的 fact invalidation / supersession 链

它们各自的 history 都只能记录 `ADD / UPDATE / DELETE` 这一类业务事件,**没有密码学性质**。任何有 DB 写权限的人都能静默改history,改完看不出来。本项目的做法:

- 把 `header_T` 写进各 backend 自身 history 的末端 (in-storage anchor)
- 把 `reveal_t` 与 memory record 同表/同对象存储 (snapshot-only verification 的关键,见 §10.5)
- 验证端不再依赖任何 memory system 数据库的诚实性,只依赖外部 anchor 与 PRF key

↳ **支撑 RQ3 R3 / Headline (§10.5)** —— `reveal_t` 与 `memory record` 同表存储 + `header_T` anchor 写入 snapshot 内,是 "仅凭 memory snapshot 完成 provenance 归因" 在物理层的成立条件。

§7 的 watermark只能保证 *"这次 keyed selection 来自 key K"*,不能保证 *"这条 reveal record 是当时写下的"*。本节描述的 audit trace 把 watermark 的 keyed selection 与 keyed nonce 哈希锁进 commitment,使 watermark 从 runtime-only 的归因机制升级为 lifecycle-survivable 的 provenance 证据。

## 10. Experiments

本章按论文 Results section 的结构组织。每个研究问题(RQ)对应一个独立的实验 block,统一遵循 §10.1 的 setup 与 §10.2 的指标定义。

### 10.1 Experimental Setup

- **Memory backends**: `Cognee` (KG / triplet store) / `A-MEM` (agentic notes) / `Graphiti` (temporal graph)。每个 backend 通过 §4.2.3 的最小 adapter + §5 中描述的 ~50–100 行 native-API wrapper 接入,backend 源码不修改;不引入外部 agent harness。
- **Benchmark drivers**: 每个 benchmark 自带的 evaluation harness 直接驱动被 wrap 过的 backend native API —— LoCoMo session replay / LongMemEval `_S` 评测脚本 / MemoryAgentBench incremental multi-turn driver。
- **LLMs**: 固定两个,见 §5。
  - `DeepSeek v4 Pro` —— headline + cost 主线
  - `Qwen3.5-397B-A17B` —— reproducibility + open-weights 主线
  调用形态 OpenAI-compatible,候选枚举 `T_enum = 0.7`,scoring `T_score = 0.0`,JSON 模式开启。
- **Benchmarks**: `LoCoMo` / `LongMemEval` / `MemoryAgentBench` (见 §6.2)。
- **Baselines**:
  - `no-watermark` —— 不嵌水印,只跑 backend + harness,用于上界 utility
  - `random-replace` —— 同样在 evolve 决策点随机替换候选,无密钥,用于测 FPR / wrong-key 下界
- **Protocol**: 每个 (backend × LLM × benchmark) 组合跑 ≥ 3 个 seed;evolve 决策与 audit trace 同时落盘 (§9);所有指标在 episode 级别计算,均值 + 标准差。

### 10.2 Evaluation Metrics

| 类别 | 指标 |
|------|------|
| **Utility** (per-benchmark) | `LoCoMo`: QA accuracy / F1, event summary coverage, evidence-grounded answer quality;`LongMemEval`: question-type accuracy, knowledge-update correctness, temporal reasoning correctness, abstention quality;`MemoryAgentBench`: accurate retrieval (EventQA), test-time learning, long-range understanding, selective forgetting (FactConsolidation), ingest / retrieval / generation latency, token cost |
| **Watermark** | bit recovery rate, decode success rate, false-positive rate (FPR), wrong-key acceptance rate, per-turn / per-session capacity |
| **Capacity (memory-aware)** | bits per memory decision, bits per session, bits per benchmark episode, 每百轮对话可嵌入 bit 数, 每次 memory write 平均容量 |
| **Carrier-level breakdown** | 上述所有指标在四类 carrier `update_target / link_target / semantic_realization / merge_policy` 上分别报告 |
| **Tamper detection** | commitment / Merkle proof 校验失败率 (per-attack,见 §10.5) |
| **Memory integrity** | update target accuracy, link target accuracy, merge correctness, delete correctness, duplication rate, contradiction rate, stale-memory retention, temporal consistency |

### 10.3 RQ1 — Utility Preservation

**Question**: watermark 是否破坏 memory system 自身的 utility?这是后续所有 RQ 的成立前提:provenance 不能以 broken memory 为代价。

**Setup**: 三个 benchmark × 两个 LLM × 三个 backend,各跑 `no-watermark` 与 `+ memory-watermark`,比较 §10.2 中 Utility 列的全部指标。

**Expected outcome**: 在所有 (LLM, backend, benchmark) 组合上,watermark 引入的 utility 下降在统计噪声范围内;retain / recall latency 与 token cost 的相对增幅 ≤ 一个预先声明的阈值(如 5%);memory write 路径无额外失败。

### 10.4 RQ2 — Capacity

**Question**: memory evolve 决策能承载多少 bit?

**Setup**: 在每个 turn 上记录 candidate-set size `|C_t|` 与分布 entropy `H(p_t)`(见 §4.2.3),以及 sampler 实际嵌入的 `bits_embedded`。按 carrier 分别汇总。

**Expected outcome**: 报告 (i) 每类 carrier 的平均 `|C_t|` 与 `H(p_t)`(理论上界),(ii) 实际 bits per decision / per session / per episode(实际容量),(iii) 每百轮对话平均嵌入 bit 数。同时回应 reviewer attack *"prompted enumeration ≠ intrinsic decision freedom"*:per-carrier per-backend `H(p_t)` 分布必须显著高于零。

### 10.5 RQ3 — Snapshot-Only / Partial-Log Verification (Headline)

**Question**: 在 RQ1 / RQ2 已证 watermark 既不破坏 utility 也有非平凡容量后,**这一节是论文的 headline**:没有完整 action trajectory 时,仅凭 memory snapshot 能否完成可验证归因?这是 *state-evolution provenance* 与 AgentMark / ActHook 的核心差异点。

**动机**: 在最有取证价值的情形里 —— memory database 被外泄 / 二次封装 / 蒸馏 / 跨系统迁移 —— action trace 通常不可得。这正是 §1 motivation 表格里 *"能否归因到无可见行为的 state 改动"* 一列的承诺。RQ1 / RQ2 给的是 *watermark 本身能不能用* 的回答;RQ3 给的是 *watermark 能不能在 trajectory 缺失下仍然完成归因* 的回答。

**Verification regime**: 三档逐步降级的证据可得性。

| Regime | 给定的证据 | 适用威胁模型 | 期望性能 |
|--------|-----------|-------------|---------|
| `R1: Full` | 完整 reveal log + Merkle tree + memory snapshot | 内部审计 | bit recovery ≈ 1.0,FPR ≈ 0 |
| `R2: Snapshot + Partial Reveal` | memory snapshot + 部分 reveal record (随机 / 时间窗 / per-carrier 子集) | 部分日志被截断 / 丢失 | bit recovery 随保留比例平滑下降 |
| `R3: Snapshot Only` | 仅 memory snapshot (无外部 reveal log) | 数据被外泄 / 蒸馏后无 audit | 利用 §9.4 中存于 memory record 旁的 `reveal_t` 残留 + Merkle anchor 反推 |

**R3 可行性依据**: §9.4 已把 `reveal_t` 与 `memory record` 同表 / 同对象存储,且 `header_T` (Merkle root + signature) 写入 snapshot 内的 anchor table。验证流程:

1. 从 snapshot 抽取 `(reveal_t, anchor)` 对
2. 对每条 reveal,用 PRF key 重放采样器,核对 keyed 中标
3. 用 anchor 中的 Merkle root 校验 reveal 子集属于原始 session
4. 聚合所有命中的 keyed 决策,decode bit stream

**Setup**: R1 上跑全量 episode,R2 在 `保留比例 ∈ {90%, 70%, 50%, 30%, 10%}` 下扫,R3 完全去除外部 reveal log,仅依赖 snapshot 内残留。Baseline 包含 `AgentMark @ action layer`,在 R3 下其 bit recovery ≡ 0(by construction),作为 headline 的 *qualitative gap*。

**Expected outcome**: 通用指标 (bit recovery / decode success / FPR / wrong-key acceptance) 套用 §10.2 定义,**不重复列出**。本节只追加一条 R3-specific 指标:

- **carrier-level R3 成功率** —— 四类 carrier 在 snapshot-only 下的 decode 成功率分别报告,用于识别哪些 carrier 在仅有 snapshot 时信号最稳

只要 R3 的 decode 成功率显著高于 wrong-key baseline 且 FPR 可控,即完成 AgentMark / ActHook 在原理上做不到的事情 —— **仅凭 latent state 完成 provenance 归因**。

### 10.6 RQ4 — Robustness against Memory-Specific Attacks

**Question**: watermark 在长期记忆系统天然会经历的 lifecycle 操作与定向攻击下是否仍可恢复 / 可检测?(RQ3 在真实威胁模型下的延伸)

**Threat model**(对应 §9 cryptographic audit trace):

| 攻击 | 含义 | 对 watermark 的威胁 | 评测信号 |
|------|------|---------------------|---------|
| `compaction` | 多条旧 memory 被合并压缩成 summary | reveal record 与原始 commit 的对应关系断裂 | 压缩前后 bit recovery rate |
| `dedup` | 系统检测到重复 fact 自动去重 | 部分 leaf 被消除,Merkle proof 仍需可走通 | 去重比例 vs decode 成功率 |
| `supersession` | 旧 fact 被新 fact 取代 (Graphiti 原生行为) | 被取代的 leaf 是否还可解码 | supersession 链上 watermark 持续性 |
| `paraphrase rewrite` | summary / note 被等价改写 | 验证上下文 `ctx_t` 重建失败 | 改写比例 vs decode 成功率 |
| `pruning` | 低重要性 memory 被删除 / 归档 | 删除随机子集后剩余 trace 的可解码性 | 不同 prune 比例下的 bit recovery |
| `poisoning` | 攻击者向 memory 注入伪造条目 | FPR / wrong-key acceptance 上升 | 注入比例 vs FPR、wrong-key acceptance |
| `manual edits` | 用户手动改动 memory record | 单个 leaf 被改写后是否能被检测 | edit detection rate (commitment 校验失败率) |

**Setup**: 每类攻击在三档强度(轻 / 中 / 重)下作用于已嵌水印的 memory snapshot + audit trace,然后跑解码与验证。

**Expected outcome**: 每类攻击单独报告 (i) 攻击前 / 后 bit recovery rate,(ii) per-session decode success rate,(iii) tamper detection rate (commitment / Merkle proof 校验失败率),(iv) 攻击对 utility 自身的影响(防止 watermark "看起来稳"但 memory 已经坏)。任何无法被 audit trace 检测的攻击 = watermark 漏洞,需在 limitations 中明确。

### 10.7 RQ5 — Memory Integrity

**Question**: watermark 是否引入"写错对象 / 错误合并 / 保留过期事实 / 引入脏 memory"?

**Setup**: 在每个 benchmark 上,对 `no-watermark` 与 `+ memory-watermark` 比较以下 ground-truth-driven 指标:update target accuracy / link target accuracy / merge correctness / delete correctness / duplication rate / contradiction rate / stale-memory retention / temporal consistency。

**Expected outcome**: 所有指标在 watermark 开启后无显著退化。这里的关键是 watermark 不能 "可验证但 memory 写坏"。

### 10.8 RQ6 — Composability with Content Watermark — appendix

**Question**: memory watermark 与已有 content watermark (LLM 文本水印 / AgentMark action-layer) 同时开启时是否兼容?

**Setup**: 三档配置 —— `memory-only` / `content-only` / `both`,在 §10.5 的 R1 协议下分别跑 utility 与 decode 指标。

**Expected outcome**: (i) memory decode 不受明显影响,(ii) content watermark 检测能力仍保留,(iii) utility 没有叠加性崩坏。如果两者出现冲突,应在 carrier-level 指出哪种 carrier 与 content watermark 不正交,作为后续工作。


## 11. 一句话结论

这个系统本质上是在做 **state-evolution provenance**：

- 在 `Cognee / A-MEM / Graphiti` 三种结构不同的 memory system 上，统一抽象出 backend-invariant 的 evolve carrier taxonomy (update / link / semantic / merge),仅靠 ~200–300 行的 backend native API wrapper 接入,不引入外部 harness
- 用 `AgentMark` 风格的 distribution-preserving sampling 把 watermark 嵌入 *latent state-transition* 决策
- 用 commitment + Merkle log 的 cryptographic audit trace 替代普通 JSON log,实现 tamper-evident、partial-verifiable 的归因
- 用 `LoCoMo + LongMemEval + MemoryAgentBench` 
- 用 memory-specific 攻击模型 (compaction / dedup / supersession / paraphrase rewrite / pruning / poisoning / manual edits) 取代 LLM 文本水印的通用扰动测试
- 用 **snapshot-only / partial-log verification** 完成一个 AgentMark / ActHook 在原理上做不到的实验:仅凭 memory snapshot 也能完成可验证归因

## 12. 参考资料

- AgentMark 论文 PDF： [2601.03294v2.pdf]
- AgentMark 代码说明： [README_en.md]
- AgentMark 采样器： [agentmark/core/watermark_sampler.py]
- Cognee： https://github.com/topoteretes/cognee
- A-MEM： https://arxiv.org/abs/2502.12110
- Graphiti： https://github.com/getzep/graphiti
- LoCoMo： https://github.com/snap-research/locomo
- LoCoMo 论文： https://arxiv.org/abs/2402.17753
- LongMemEval： https://github.com/xiaowu0162/LongMemEval
- LongMemEval 论文： https://arxiv.org/abs/2410.10813
- MemoryAgentBench 仓库： https://github.com/HUST-AI-HYZ/MemoryAgentBench
- MemoryAgentBench 论文 (ICLR 2026)： https://arxiv.org/abs/2507.05257
- MemoryAgentBench 数据集： https://huggingface.co/datasets/ai-hyz/MemoryAgentBench
- ActHook (Watermarking LLM Agent Trajectories)： https://arxiv.org/abs/2602.18700
- AGENTWM (Protecting Agentic Systems' IP via Watermarking)： https://arxiv.org/abs/2602.08401
- Agent Guide： https://arxiv.org/abs/2504.05871
