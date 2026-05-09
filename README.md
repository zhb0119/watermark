# MemMark: State-Evolution Attribution Watermarking for Long-Term Agent Memory Systems


## 1. Introduction

### 1.1 Provenance-Aware Memory Is Already a Hot Topic — and Bound to Honest Writers

为长期记忆加 provenance 已经是一条活跃的研究线。**TierMem** 显式给 memory 加 provenance 链 + immutable source anchoring,**MemOS** 的 ``MemCube`` 抽象自带 versioning / origin / lifecycle 字段,**多数企业部署**都会在 memory record 上 stamp tenant ID / write timestamp / source agent identifier。在受监管 / 多租户场景下,这条线的实现细节差异不小,但在结构上它们共享同一个**前提**:

> 写入方诚实,metadata 字段等于事实。

换句话说,provenance 是 "我说我是谁"。在 in-system 部署、可信运维下这个前提合理 —— DB 写权限有限,审计运营层兜底。问题是,memory 在 agent 价值堆栈里**既是最贵的一层、又是最容易脱离原系统的一层**(导出一份 A-MEM note 库或 Graphiti graph dump 在工程上几乎没有摩擦),一旦它走出原系统,这个前提立刻塌掉。

### 1.2 But the Attacker Is the Writer

memory 离开原系统、出现在攻击者手里的瞬间,**所有 metadata 字段对持有 snapshot 的人来说都是可写的**。攻击者可以:

- 把自己的 memory stamp 上 ``"by Acme Agent v3"`` 主张所有权
- 把我们的 memory 上 ``source_agent`` / ``tenant_id`` 等字段抹掉、改写,声称是他自己演化出来的
- 给伪造的、注入有毒数据的 memory 同样填上看似合规的 provenance 链
- 把 memory system 自身的 changelog (A-MEM evolve 历史、Graphiti fact invalidation 链) 整段重写 —— 它们与 memory 数据本身存于同一个图 / 向量库,无 cryptographic integrity

也就是说,**任何"靠填字段"的 provenance,在 adversarial-storage 场景下原理上不成立**。要让 provenance 在敌手控制 memory store 的场景下保住,需要一种**无法仅通过填字段伪造**的 attribution。

token-level LLM 文本水印与 agent 可见行为水印 (在 tool call / planning 决策上嵌 watermark) 都不解决这个问题:它们假设验证时拿得到原始的可见输出或 action trajectory,而 memory 大多数演化根本不发生在可见输出上 —— 哪条 note 被更新、新事实链接到哪个已有 entity、同一事件被写成哪个等价表述,这些决策完全发生在 agent 的内部状态里;而当 memory 被外泄或迁移之后,可见 trajectory 一定先于 memory 被丢弃。

换句话说:最有取证价值的场景里,可见行为已经没了,**只剩下 memory 本身,而 memory 上的 metadata 又被攻击者控制**。这是现有 watermark / provenance 工作都没有覆盖的位置。

### 1.3 把 Attribution 嵌进 Memory 演化本身的 Keyed 决策

我们的回答是把 attribution 嵌到 memory 演化本身的 keyed 决策里 —— 让 attribution **不再是字段,而是行为痕迹**。

每一次 memory 写入,实际上是 agent 在以下三个维度上做选择:

- **更新哪一条已有记忆** —— 多条历史 note / fact edge 都可能与新信息相关
- **链接到哪一个已有对象** —— 新内容可以挂到不同的 entity / cluster / episode
- **以哪一个等价版本写下** —— 同一事实可以用不同但语义等价的措辞、tag、edge label 表达

这三类决策有几个共同性质:**它们各自都有非平凡的候选空间**(真实 memory system 里多数 turn 都同时存在多个合理选项);**在等价候选之间做不同的选择不破坏 memory 的 utility**(无论挂到哪个等价的 entity,无论用哪个等价的 phrasing,下游 retrieval 与 QA 都是接受的);**这些决策完整保留在 memory 自身的状态里**(被更新的是哪条、链接到了哪个、写成了哪个版本,都是 memory snapshot 直接可读的事实)。

我们把 PRF key 嵌进这条 latent state-evolution 决策序列:每个决策点的 keyed pick 都由 ``HMAC(K, ctx_t)`` 决定。**metadata 的可信度不再来自 "我们说它是真的",而来自 "用 PRF key 重放采样器能复现这条选择序列"**。这意味着:

- 攻击者就算把所有 metadata 字段重写,只要 memory 内容没改干净,选择序列仍能被 PRF key 重放出来 → 我们仍能归因
- 反过来,他要伪造一份 memory 声称是我们的,必须不仅写对内容、还要让选择序列在我们 key 下重放成功 —— 这在不知道 key 的前提下计算上不可行

我们称之为 **state-evolution attribution**:**谁演化出了这份长期记忆**。

### 1.4 Headline: In-Record Attribution Verification (R3)

State-evolution attribution 要在最坏情况下兑现:**memory 已经离开原系统、原系统的 audit log 已不可得、metadata 字段已被攻击者改写或抹除**。我们称这一档为 **R3**,本文的 headline result。

具体地,我们把 watermark 的 keyed selection 与一个 commit-then-reveal 的密码学结构绑定:每次决策的 commitment 与对应的 reveal record 直接随 memory record 同表落地,session 级 Merkle root 的签名 anchor 也写在 snapshot 内部 (§8)。R3 验证流程对持有 PRF key 的验证方:

1. 从 snapshot 抽取 ``(record, reveal)`` 对
2. 用 PRF key 重放 keyed 采样器,核对每个 reveal 是否落在 keyed 区间
3. 用 anchor 校验 reveal 集属于原始 session 的 Merkle tree
4. 聚合命中的 keyed 决策,decode bit stream

**全程不依赖 memory system 数据库的诚实性,也不依赖任何外部 audit store 的可得性**。即使攻击者能写所有 memory record 的 metadata 字段、抹掉原 changelog,只要他不知道 key,他就(a)无法把伪造 memory 的选择序列匹配到我们的 key,(b)无法在重写 memory 内容后让原 reveal 仍然 keyed-valid。R3 在 §9.5 作为论文核心实验给出,与 ``signed-metadata-only`` baseline 直接对照 —— 后者就是当前 provenance-aware memory 范式 (TierMem / MemOS) 在 R3 下的退化。

### 1.5 Contributions

(i) **Backend-invariant evolve carrier taxonomy.** 我们把两类结构差别很大的 memory system —— A-MEM 的 agentic notes 网络与 Graphiti 的 temporal graph —— 在 evolve 决策层抽象成同一个三元 carrier taxonomy (update / link / semantic, §3.2),并给出 ~50–100 行 native API wrapper 即可接入的最小 adapter 接口 (§3.2.3),不引入外部 agent harness。

(ii) **LLM-call-boundary interception with self-reported candidate weights.** memory SDK 内部的 LLM call 输出是开词表结构化 JSON,没有显式离散候选集。我们在 SDK 内部 LLM client 边界做拦截,把 SDK 原 prompt 后接一段 AgentMark 风格的 instruction,让 LLM 在**单次调用**里枚举 K 个等价候选并自报权重 ``{candidates: [{decision, weight}, ...]}``;wrapper parse 出 (C_t, p_t) 喂给 distribution-preserving binning sampler,按 key 挑一个 ``decision`` 还原成 SDK 原 schema 返回 (§6)。

(iii) **Cryptographic audit trace for memory evolution.** 我们用 commitment + per-session Merkle log + signed root anchor 替代普通 JSON log,使每次 evolve 决策的归因证据 tamper-evident、partial-verifiable,并将 reveal record 与 memory record 同表落地,以支撑 in-record 验证 (§8)。

(iv) **In-Record Attribution Verification.** 我们形式化三档 verification regime (R1 完整外部日志 / R2 部分外部日志 / R3 仅 snapshot),并通过 signed-metadata-only baseline 量化 watermark 相对纯 metadata 在 R3 下提供的边际归因价值 (§9.5)。

(v) **Memory-specific evaluation.** 我们在 LoCoMo / LongMemEval / MemoryAgentBench 三个 benchmark 上,用一套针对 memory lifecycle 的攻击模型 (compaction, dedup, supersession, paraphrase rewrite, pruning, poisoning, manual edits, KG-specific edge relabel / subgraph reanchor) 报告 utility / capacity / robustness / integrity 全套指标 (§9),并在 KG backend 上以 KGMark 为直接 baseline。


## 2. 目标场景

适用的真实场景：

- 长期陪伴型 agent
- 个人助理 / 工作流 agent
- 多 session coding agent
- 企业知识助手
- 多 agent 系统中的 per-agent memory namespace


## 3. 任务定义

我们要 watermark 的对象不是最终回答文本，而是 `memory operation selection`，即 `memory evolve` 决策。

在本项目里，先聚焦两个 memory system：

- `A-MEM`
- `Graphiti`

并且只研究以下三类最有代表性的细粒度 watermark 载体:

- 哪条 memory 被更新
- 哪个 existing memory 被链接
- 同一事实写成哪个语义等价版本

选择这三类的原因是:

- 它们都发生在 `memory evolve` 过程内部,而不是最终回答表面
- 它们都可以通过"等价候选选择"来嵌水印,较不容易直接伤害 utility
- 它们在 `A-MEM / Graphiti` 这两类结构化 memory system 里都能找到自然对应物
- 不用粗粒度 watermark 容量太低 —— 如果只在 ADD / UPDATE / DELETE / NONE 这种层面嵌,单次决策能承载的信息非常有限,而且很多真实 turn 根本不会同时存在这三种都合理的候选。长期记忆写入本来就比普通 agent step 稀疏,粗粒度操作再压一层,最终 bit rate 会很低。
  
### 3.1 两个 Memory System 中的具体定义

#### A-MEM

在 A-MEM 里,memory 更接近 agentic notes 与动态组织网络,因此这三类 watermark 可以定义为:

- `哪条 memory 被更新`
  - 多条历史 note 都可能和当前经验相关,系统需要决定更新哪条已有 note。
- `哪个 existing memory 被链接`
  - 新 note 可以链接到不同已有 notes、tags、keywords cluster 或 memory box。
- `同一事实写成哪个语义等价版本`
  - 同一经验可以用不同的 contextual description、keywords、tags 组合来表述。

#### Graphiti

在 Graphiti 里,memory 更接近 temporal context graph,因此这三类 watermark 可以定义为:

- `哪条 memory 被更新`
  - 多个已有 fact edge、entity summary 或 episodic trace 都可能是更新对象,系统需要决定更新哪一个。
- `哪个 existing memory 被链接`
  - 新 episodic / factual information 可以连接到不同已有 entity、edge 或 episode chain。
- `同一事实写成哪个语义等价版本`
  - 同一 temporal fact 可以采用不同但语义等价的 edge label、fact phrasing 或 summary phrasing。

### 3.2 Backend-Invariant Carrier Taxonomy

虽然三种 system 的内部结构不同,但这三类 evolve 决策可以统一抽象成同一个数学对象。我们把每一次 memory 写入决策形式化为一个可被 watermark sampler 接管的 `state-transition decision point`。

#### 3.2.1 形式化定义

设 memory state 在 turn `t` 为 `M_t`，新到达信息为 `e_t`，则 evolve 决策被定义为一个四元组：

```text
D_t = ⟨τ, C_t, p_t, ctx_t⟩
```

- `τ ∈ {update, link, semantic}` —— carrier 类型 (load 哪一种 state-transition 自由度)
- `C_t = {c_t^1, …, c_t^k}` —— 候选集合 (k ≥ 2 才能嵌入信息)
- `p_t : C_t → [0,1]` —— LLM 给出的可接受度分布 (∑ = 1)
- `ctx_t` —— 与该决策绑定的上下文 (见 §7)

watermark sampler 仅作用在 `(C_t, p_t, ctx_t)` 上，不读不写 backend 的内部结构。这就是 `backend-invariant` 的含义：sampler 与 A-MEM / Graphiti 完全解耦。

#### 3.2.2 三类 Carrier 的统一签名

| Carrier `τ` | 候选 `c` 的语义 | state-transition 性质 | 三个 backend 的具体实例 |
|-------------|----------------|----------------------|------------------------|
| `update_target` | 旧 memory 的 id | 改变 *哪一条* 已有 state | A-MEM note id / Graphiti edge id |
| `link_target` | 已有 memory 的 id 或集合 | 改变 *拓扑连接* | KG entity / note keyword cluster / entity-edge attach point |
| `semantic_realization` | 同义改写候选文本 | 改变 *表述形式*,不改变事实 | triplet phrasing / note description+tags / edge label phrasing |

#### 3.2.3 Backend Adapter 的最小接口

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



## 4. 系统形态

真实 watermark 需要在线 agent runtime，而不是纯离线脚本。

建议结构：

- `LLM`
  驱动 memory system 内部的 evolution 决策(由各 backend 的 SDK 自行调用)。本项目固定使用两个 LLM:
  - **DeepSeek v4 Pro** —— headline + cost 主线
  - **Qwen3.5-397B-A17B** —— reproducibility + open-weights 主线,确保 audit trace 可被独立重放
  调用形态均为 OpenAI-compatible API。我们在每个 SDK 内部 LLM call 边界上拦截,做 n 次采样后 keyed pick(详见 §6)。
- `Memory system`
  负责实际写入与检索,如 `A-MEM` / `Graphiti`。turn / session / agent identity / hooks 全由 backend 自身的 SDK 与 benchmark evaluation harness 协同提供,本项目不再额外引入 agent harness。
- `Watermark selector`
  在每个被拦截的 LLM call 上,用私钥控制的 distribution-preserving binning sampler 在 n 个经验样本中做可验证选择(§6.2 给出 (C_t, p_t) 的构造,§6.3 陈述性质)。
- `Audit store`
  记录可验证 trace。

### 4.1 Memory System 适配

本项目把 `memory system` 视为可替换后端，而不是绑定单一实现。不同系统的内部记忆结构不同，但都可以接到同一个 watermark 抽象层上。

- `A-MEM`
  把 watermark 放在:
  - note linking
  - keyword / tag / context description selection
  - 同一经验的等价表述
- `Graphiti`
  把 watermark 放在:
  - entity / edge linking
  - 已有 fact edge 与 episode 的更新目标选择
  - temporal fact 的等价改写

因此，系统形态上不要求所有 memory backend 暴露完全相同的内部操作，而是要求它们都能提供：

- 一个可观测的 `memory evolve` 生命周期
- 一个可枚举的候选选择空间
- 一个可记录的 audit trace

`A-MEM` / `Graphiti` 各自的官方仓库都已经文档化了"如何接入 LLM、跑 LoCoMo / LongMemEval / MemoryAgentBench 的 evaluation"这条端到端路径,我们直接复用各自原生的 LLM 接入与 benchmark 评测脚本,不需要再写一层协调层。watermark 仅在 backend 已经暴露的 evolve 入口挂上 §3.2.3 的 adapter 与 §8 的 audit trace,改动量限制在 backend 自身的 native API wrapper 上。

## 5. Benchmark 设计

不建议只用单一 benchmark。一个可信的长期记忆 watermark 评测，应该覆盖：

- 长对话 QA 与事件总结
- 多 session 推理
- 知识更新与时间变化
- memory 的结构化组织能力
- 在线 / streaming memory 演化场景


### 5.2 Benchmark 分工

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
- `selective forgetting` 是触发 §9.6 中 `pruning` 攻击的天然评测面
- `incremental multi-turn` 形式覆盖了 streaming 演化场景,用一个 benchmark 同时压住"结构化组织 + 持续演化"两条路径,不用再单列其它

MemoryAgentBench 官方信息：

- 仓库: https://github.com/HUST-AI-HYZ/MemoryAgentBench
- 论文 (ICLR 2026)：`Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions`  
  https://arxiv.org/abs/2507.05257
- 数据集: https://huggingface.co/datasets/ai-hyz/MemoryAgentBench

### 5.3 推荐 Benchmark 组合

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

## 6. 核心算法

MemMark 在 memory carrier 上嵌入 watermark,需要解决三个问题:

1. **Where to intercept** —— 第三方 memory SDK 是黑盒,watermark 应该挂在 SDK
   流程的哪一层
2. **How to construct (C_t, p_t)** —— SDK 内部 LLM call 输出的是开词表结构化
   JSON,候选空间无界,没有显式离散候选集供 sampler 消费
3. **How to compose audits** —— 一条 memory event 触发 SDK 内部多次 LLM call,
   多条 audit 如何组装成 lifecycle-survivable 的 attribution trace

第 (3) 问题由 §8 解决。本节集中说 (1) 和 (2),分别对应**架构层贡献**与
**数学层贡献**。

### 6.1 LLM-Call 边界拦截 — 架构层贡献

关键观察:

> 每一次 SDK 内部 LLM call **本身就是一个 ε-equivalent 决策点**。

LLM 在 `T = 0.7` 下对同一 prompt 重复采样会产出多个语义等价但表述不同的合法
JSON(不同 keyword 选词、不同 edge label、不同 contradiction target),都是
backend 在不带 watermark 时本就会接受的输出。

我们在 `attach_sampler` 时把一个 wrapper 装到每个 SDK 的 LLM client 上:

- A-MEM:替换 `AgenticMemorySystem.llm_controller`
- Graphiti:替换 `Graphiti.llm_client`(继承 `LLMClient` ABC)

→ 水印嵌进 backend 自己的 evolution 决策里,而不是叠在它旁边的外部 overlay。
SDK 拿到的字符串是我们 keyed pick 的某一个 cluster 代表,但 SDK 不知情
地按它继续运行 `add_note` / `add_episode` / contradiction detection 等下游。
这是 backend-invariance 的物理基础。具体实现见
[memmark/llm/watermarked.py](memmark/llm/watermarked.py:1)。

### 6.2 开词表 → LLM 自报候选与权重 — 数学层贡献

memory SDK 内部 LLM call 输出是 unbounded 结构化 JSON,没有显式离散候选集供
binning sampler 消费。MemMark 复用 AgentMark 的
``action_weights`` pattern:**让 LLM 自己在单次调用里枚举候选集并自报权重**。
我们在 SDK 原 prompt 末尾追加一段 instruction:

```
CRITICAL OVERRIDE: instead of returning a single answer, return JSON
in EXACTLY this multi-candidate form:
{
  "candidates": [
    {"decision": <answer matching the original schema>, "weight": <float>},
    {"decision": <plausible alternative>, "weight": <float>},
    ...
  ],
  "thought": "..."
}
- Provide K candidate alternatives;
- Each "decision" must independently match the original schema;
- Weights > 0, rank by your real preference; sum normalized.
```

LLM 单次返回后,wrapper parse 出:

```
decisions = [c["decision"] for c in resp["candidates"]]   # K 个原 schema 合法输出
weights   = [c["weight"]   for c in resp["candidates"]]   # 自报权重,归一化后即 p_t
keyed pick: c* = sampler(decisions, p_t, ctx_t, K)        # binning sampler
```

K=4 默认,1 次 underlying API call 完成候选集 + 概率 + 选取。binning sampler 调用
[agentmark/core/watermark_sampler.py](/Users/henry_mao/AgentMark/agentmark/core/watermark_sampler.py)
的 `sample_behavior_differential`。**贡献不在 sampler 本身,而在把第三方 SDK
内部 LLM call 改造成同时输出候选 + 权重的 1-call 形态**(§6.2),以及紧接
§6.3 的性质陈述。

LLM 不合规返回(weights 缺失 / candidates 不到 2 个)时,wrapper 重发原 prompt
拿单一返回直接交给 SDK,**该次 LLM call 不写 audit / 不嵌 bit**。

### 6.3 性质陈述

设 `p_t` 为 LLM 在 §6.2 的多候选 prompt 下自报的归一化权重分布(LLM 把它当成
"我对每个候选的偏好",作为 sampler 的输入分布)。

- **Lemma 1 (Strict distribution preservation)**: 给定 `p_t`,binning sampler 在
  PRF key `K` 下的 keyed pick `c^*` 边缘分布严格等于 `p_t`;即
  `Pr[c^* = c_i | K, ctx_t]_marg = p_t(c_i)`。证明直接复用 AgentMark 的 binning
  argument(整数化分桶 + cyclic shift)。这意味着 SDK 拿到的输出在分布上与
  LLM 在多候选 prompt 下自然采样得到的输出**不可区分**。
- **Lemma 2 (Composition across LLM cascade)**: backend 处理一条 memory event
  触发 K 次内部 LLM call,每次的 `ctx_t` 由
  `{round, dia_ids, prompt_hash, previous_commitment}` 决定;HMAC nonce 在
  各次决策上独立 → keyed pick 独立。capacity 在 K 上加性,marginal bias
  不累积。
- **Lemma 3 (Backend-invariant marginal)**: Lemma 1 的 strict preservation 不
  依赖 backend(只依赖 LLM 自报的 `p_t` 与 PRF key),与 SDK 之间换 (A-mem ↔
  Graphiti) 无关。这给 §9.1 的 cross-backend 对照提供同一个 marginal 不变性
  保证。

完整证明留 appendix。Lemma 1 用 binning 的标准论证;Lemma 2 用 PRF
independence;Lemma 3 是 Lemma 1 的 corollary。


## 7. Memory Watermark 的输入与上下文

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

## 8. Cryptographic Audit Trace

普通 JSON log 不够。一个可在 forensics 场景成立的 audit trace 必须满足：

- **append-only** —— 不可被回溯改写
- **commit-then-reveal** —— 决策时刻先承诺,事后才暴露候选/概率
- **partial-verifiable** —— 任何子集都可以被独立验证而不需要完整日志

因此本项目把 audit trace 设计成 commitment + Merkle log 的两层结构,而不是平面 JSON。

### 8.1 Per-decision Commitment

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

↳ **支撑 RQ4 (§9.6)** —— commitment 校验失败率即 §9.6 表格中的 `tamper detection rate` 列,直接对应 `manual edits` 与 `poisoning` 两类攻击的 detection 信号。

### 8.2 Per-session Merkle Log

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

↳ **支撑 RQ3 R2 (§9.5) 与 RQ4 (§9.6)** —— Merkle proof 是 R2 (Snapshot + Partial Reveal) 在保留比例 `∈ {90%, 70%, …, 10%}` 下能平滑下降而非直接归零的物理基础,同时也是 `compaction / dedup / pruning` 攻击下"任意子集仍可验证"的密码学机制。

### 8.3 Reveal Record

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
memmark-v1::deepseek-v4-pro@<api-version>::T_score=0.0::T_enum=0.7::json_mode=true
memmark-v1::qwen3.5-397b-a17b@<weights-hash>::T_score=0.0::T_enum=0.7::json_mode=true
```

`<api-version>` 用 vendor 返回的 `model` 字段,`<weights-hash>` 用 open-weights 模型的权重 SHA。这两个字符串都参与 §8.1 中 `commit_t` 的哈希,任一项变化都会让 commitment 失配。

验证时:

- 用 `reveal_t` 重新计算 `commit_t'`
- 检查 `commit_t' == leaf` 且 `MerkleProof(leaf, root_T)` 通过
- 用相同 `K` 重放采样器,核对 `selected_candidate` 是否落在 keyed 的中标区间

只有以上三步全部通过,该决策才被认为 *"带水印地、可验证地、未被篡改地"* 产生过。

↳ **支撑 RQ1 / RQ2 跨 LLM 实验 (§9.3 / §9.4)** —— `watermark_version` 把 DeepSeek v4 Pro 与 Qwen3.5-397B-A17B 的身份(model id + api-version / weights-hash + 温度 + JSON 模式)一起 hash 进 `commit_t`,任一项变化即 commitment 失配,从而保证 §9.3 utility 对比与 §9.4 capacity 报告在跨 LLM 复现时不会被误读为同一 audit trace。

### 8.4 与 Memory System 自身 history 的关系

两种 memory system 都有不同形式的内置 changelog:

- `A-MEM` —— note 的 evolve / link 修改历史
- `Graphiti` —— temporal graph 的 fact invalidation / supersession 链

它们各自的 history 都只能记录 `ADD / UPDATE / DELETE` 这一类业务事件,**没有密码学性质**。任何有 DB 写权限的人都能静默改history,改完看不出来。本项目的做法:

- 把 `header_T` 写进各 backend 自身 history 的末端 (in-storage anchor)
- 把 `reveal_t` 与 memory record 同表/同对象存储 (snapshot-only verification 的关键,见 §9.5)
- 验证端不再依赖任何 memory system 数据库的诚实性,只依赖外部 anchor 与 PRF key

↳ **支撑 RQ3 R3 / Headline (§9.5)** —— `reveal_t` 与 `memory record` 同表存储 + `header_T` anchor 写入 snapshot 内,是 "仅凭 memory snapshot 完成 attribution 归因" 在物理层的成立条件。

§6 的 watermark只能保证 *"这次 keyed selection 来自 key K"*,不能保证 *"这条 reveal record 是当时写下的"*。本节描述的 audit trace 把 watermark 的 keyed selection 与 keyed nonce 哈希锁进 commitment,使 watermark 从 runtime-only 的归因机制升级为 lifecycle-survivable 的 attribution 证据。

## 9. Experiments

本章按论文 Results section 的结构组织。每个研究问题(RQ)对应一个独立的实验 block,统一遵循 §9.1 的 setup 与 §9.2 的指标定义。

### 9.1 Experimental Setup

- **Memory backends**: `A-MEM` (agentic notes) / `Graphiti` (temporal graph)。每个 backend 通过 §3.2.3 的最小 adapter + §4 中描述的 ~50–100 行 native-API wrapper 接入,backend 源码不修改;不引入外部 agent harness。
- **Benchmark drivers**: 每个 benchmark 自带的 evaluation harness 直接驱动被 wrap 过的 backend native API —— LoCoMo session replay / LongMemEval `_S` 评测脚本 / MemoryAgentBench incremental multi-turn driver。
- **LLMs**: 固定两个,见 §4。
  - `DeepSeek v4 Pro` —— headline + cost 主线
  - `Qwen3.5-397B-A17B` —— reproducibility + open-weights 主线
  调用形态 OpenAI-compatible,候选枚举 `T_enum = 0.7`,scoring `T_score = 0.0`,JSON 模式开启。
- **Benchmarks**: `LoCoMo` / `LongMemEval` / `MemoryAgentBench` (见 §5.2)。
- **Baselines**:
  - `no-watermark` —— 不嵌水印,只跑 backend + harness,用于上界 utility
  - `random-replace` —— 同样在 evolve 决策点随机替换候选,无密钥,用于测 FPR / wrong-key 下界
  - `signed-metadata-only` —— 在 evolve 入口存 `reveal_t` 与 Merkle anchor,但 sampler 不嵌 watermark bit;直接对照 watermark 是否在 R3 下提供 *边际归因价值*(见 §9.5 RQ3)
  - `KGMark @ Graphiti` —— ICLR 2025 的动态 KG watermarking 方法,作为 KG-backend 直接 baseline;不适用于 A-MEM(非 KG 结构)
  - `Action-layer watermark @ ToolBench` —— 在 ToolBench tool-use trajectory 上做 action-layer watermark,用于 R1/R2/R3 跨层对比(see §9.5)
- **Memory integrity audit**: §9.7 RQ5 报告 update / link target accuracy、duplication rate、contradiction rate 等 ground-truth-driven 指标,确保 watermark 不引入脏 memory
- **Protocol**: 每个 (backend × LLM × benchmark) 组合跑 ≥ 3 个 seed;evolve 决策与 audit trace 同时落盘 (§8);所有指标在 episode 级别计算,均值 + 标准差。

### 9.2 Evaluation Metrics

| 类别 | 指标 |
|------|------|
| **Utility** (per-benchmark) | `LoCoMo`: **F1 / BLEU-1 / ROUGE-L**(LoCoMo paper Table 4 + A-mem `utils.py:calculate_metrics` 主三列;Porter-stemmed token F1 用 `score_one()`,BLEU-1 用 nltk `sentence_bleu(weights=(1,0,0,0))`,ROUGE-L 用 `rouge_score.RougeScorer`);`LongMemEval`: question-type accuracy, knowledge-update correctness, temporal reasoning correctness, abstention quality;`MemoryAgentBench`: accurate retrieval (EventQA), test-time learning, long-range understanding, selective forgetting (FactConsolidation), ingest / retrieval / generation latency, token cost |
| **Watermark** | bit recovery rate, decode success rate, false-positive rate (FPR), wrong-key acceptance rate, per-turn / per-session capacity |
| **Capacity (memory-aware)** | bits per memory decision, bits per session, bits per benchmark episode, 每百轮对话可嵌入 bit 数, 每次 memory write 平均容量 |
| **Carrier-level breakdown** | 上述所有指标在三类 carrier `update_target / link_target / semantic_realization` 上分别报告 |
| **Tamper detection** | commitment / Merkle proof 校验失败率 (per-attack,见 §9.5) |
| **Memory integrity** | update target accuracy, link target accuracy, merge correctness, delete correctness, duplication rate, contradiction rate, stale-memory retention, temporal consistency |

### 9.3 RQ1 — Utility Preservation

**Question**: watermark 是否破坏 memory system 自身的 utility?这是后续所有 RQ 的成立前提:attribution 不能以 broken memory 为代价。

**Setup**: 三个 benchmark × 两个 LLM × 三个 backend,各跑 `no-watermark` 与 `+ memory-watermark`。LoCoMo 主指标固定为 **F1 / BLEU-1 / ROUGE-L** 三列(LoCoMo paper Table 4 + A-mem `utils.py:calculate_metrics` 对齐);其它 benchmark 的指标见 §9.2。我们刻意不引入 LLM-as-judge:LoCoMo / A-mem 官方均无 LLM judge,deterministic F1 + BLEU + ROUGE 已是上游主表口径。

**Expected outcome**: 在所有 (LLM, backend, benchmark) 组合上,watermark 引入的 F1 / BLEU-1 / ROUGE-L 下降均在统计噪声范围内(per-seed 标准差内);retain / recall latency 与 token cost 的相对增幅 ≤ 一个预先声明的阈值(如 5%);memory write 路径无额外失败。

### 9.4 RQ2 — Capacity

**Question**: memory evolve 决策能承载多少 bit?

**Setup**: 在每个 turn 上记录 candidate-set size `|C_t|` 与分布 entropy `H(p_t)`(见 §3.2.3),以及 sampler 实际嵌入的 `bits_embedded`。按 carrier 分别汇总。

**Expected outcome**: 报告 (i) 每类 carrier 的平均 `|C_t|` 与 `H(p_t)`(理论上界),(ii) 实际 bits per decision / per session / per episode(实际容量),(iii) 每百轮对话平均嵌入 bit 数。同时回应 reviewer attack *"prompted enumeration ≠ intrinsic decision freedom"*:per-carrier per-backend `H(p_t)` 分布必须显著高于零。

### 9.5 RQ3 — Snapshot-Only / Partial-Log Verification (Headline)

**Question**: 在 RQ1 / RQ2 已证 watermark 既不破坏 utility 也有非平凡容量后,**这一节是论文的 headline**:没有完整 action trajectory 时,仅凭 memory snapshot 能否完成可验证归因?这是 *state-evolution attribution* 区别于 action-layer behavioral watermark 的核心差异点。

**动机**: 在最有取证价值的情形里 —— memory database 被外泄 / 二次封装 / 蒸馏 / 跨系统迁移 —— action trace 通常不可得。这正是 §1 motivation 表格里 *"能否归因到无可见行为的 state 改动"* 一列的承诺。RQ1 / RQ2 给的是 *watermark 本身能不能用* 的回答;RQ3 给的是 *watermark 能不能在 trajectory 缺失下仍然完成归因* 的回答。

**Verification regime**: 三档逐步降级的证据可得性。

| Regime | 给定的证据 | 适用威胁模型 | 期望性能 |
|--------|-----------|-------------|---------|
| `R1: Full External Log` | 完整外部 reveal log + Merkle tree + memory snapshot | 内部审计,审计员有外部 audit store | bit recovery ≈ 1.0,FPR ≈ 0 |
| `R2: Partial External Log` | memory snapshot + 部分外部 reveal record(随机 / 时间窗 / per-carrier 子集) | 外部日志被截断 / 丢失 | bit recovery 随外部保留比例平滑下降 |
| **`R3: In-Record Attribution Verification (Headline)`** | 仅 memory snapshot,无任何外部 reveal log;依赖 §8.4 中**存于 memory record 内 sidecar 的 `reveal_t` 残留** + snapshot 内 anchor table 的 `header_T` | 数据被外泄 / 蒸馏 / 跨系统迁移后,外部 audit store 不可得 | bit recovery 显著高于 wrong-key baseline,FPR ≤ 0.01 |

**R3 可行性依据**: §8.4 已把 `reveal_t` 与 `memory record` 同表 / 同对象存储,且 `header_T` (Merkle root + signature) 写入 snapshot 内的 anchor table。验证流程:

1. 从 snapshot 抽取 `(reveal_t, anchor)` 对
2. 对每条 reveal,用 PRF key 重放采样器,核对 keyed 中标
3. 用 anchor 中的 Merkle root 校验 reveal 子集属于原始 session
4. 聚合所有命中的 keyed 决策,decode bit stream

**Setup**: R1 上跑全量 episode,R2 在 `外部保留比例 ∈ {90%, 70%, 50%, 30%, 10%}` 下扫,R3 完全去除外部 reveal log,仅依赖 snapshot 内 sidecar。Baselines:

- `Action-layer watermark baseline` —— R1/R2/R3 协议套用在 ToolBench tool-use trajectory 上;在 trajectory 缺失时 bit recovery 趋零,从而量化 *trajectory-bound* 与 *snapshot-bound* attribution 在 forensic 设定下的差距。
- **`signed-metadata-only` (no watermark)** —— 同样在 evolve 入口存 `reveal_t` 与 Merkle anchor,但 sampler **不嵌任何 watermark bit**,选择仍按 `p_t` 自然采样。这条 baseline 直接回答 reviewer 必问的问题:*"R3 的归因到底是 watermark 在工作还是 sidecar metadata 在工作?"* 如果 metadata-only 已经能识别 writer,论文 contribution 退化;如果 metadata-only 在 wrong-key 场景下区分不开 writer 而 watermark 能,则证明 watermark 提供边际价值

**Expected outcome**: 通用指标 (bit recovery / decode success / FPR / wrong-key acceptance) 套用 §9.2 定义,**不重复列出**。本节追加两条 R3-specific 指标:

- **carrier-level R3 成功率** —— 三类 carrier 在 in-record 下的 decode 成功率分别报告
- **watermark vs metadata-only marginal gain** —— `+memory-watermark` 相对 `signed-metadata-only` 在 R3 下的 attribution 信号差距(关键 ablation,直接刻画 watermark 是否真的提供归因价值)

只要 (i) R3 的 decode 成功率显著高于 wrong-key baseline 且 FPR 可控,(ii) `+memory-watermark` 在 R3 下显著优于 `signed-metadata-only`,即认为 in-record attribution verification 与 watermark 边际价值同时成立。

### 9.6 RQ4 — Robustness against Memory-Specific Attacks

**Question**: watermark 在长期记忆系统天然会经历的 lifecycle 操作与定向攻击下是否仍可恢复 / 可检测?(RQ3 在真实威胁模型下的延伸)

**Threat model**(对应 §8 cryptographic audit trace):

| 攻击 | 含义 | 对 watermark 的威胁 | 评测信号 | 攻击源参考 |
|------|------|---------------------|---------|----------|
| `compaction` | 多条旧 memory 被合并压缩成 summary | reveal record 与原始 commit 的对应关系断裂 | 压缩前后 bit recovery rate | memory lifecycle |
| `dedup` | 系统检测到重复 fact 自动去重 | 部分 leaf 被消除,Merkle proof 仍需可走通 | 去重比例 vs decode 成功率 | memory lifecycle |
| `supersession` | 旧 fact 被新 fact 取代 (Graphiti 原生行为) | 被取代的 leaf 是否还可解码 | supersession 链上 watermark 持续性 | Graphiti native |
| `paraphrase rewrite` | summary / note 被等价改写 | 验证上下文 `ctx_t` 重建失败 | 改写比例 vs decode 成功率 | RAG-WM `paraphrase attack` |
| `pruning` | 低重要性 memory 被删除 / 归档 | 删除随机子集后剩余 trace 的可解码性 | 不同 prune 比例下的 bit recovery | memory lifecycle / KGMark `subgraph removal` |
| `poisoning` | 攻击者向 memory 注入伪造条目 | FPR / wrong-key acceptance 上升 | 注入比例 vs FPR、wrong-key acceptance | A-MemGuard / KGMark `node insertion` |
| `manual edits` | 用户手动改动 memory record | 单个 leaf 被改写后是否能被检测 | edit detection rate (commitment 校验失败率) | MemoryGraft / 一般 tampering |
| `edge relabel` (KG) | KG backend 上对 entity-relation 边重新打标 / 重写 | `semantic_realization` 候选被改 | 重打标比例 vs decode 成功率 | KGMark `edge perturbation` |
| `subgraph reanchor` (KG) | KG 上把子图挂到不同的根 entity | `link_target` 候选语义被改 | 重新挂接率 vs decode 成功率 | KGMark `anchor swap` |

**Setup**: 每类攻击在三档强度(轻 / 中 / 重)下作用于已嵌水印的 memory snapshot + audit trace,然后跑解码与验证。

**Expected outcome**: 每类攻击单独报告 (i) 攻击前 / 后 bit recovery rate,(ii) per-session decode success rate,(iii) tamper detection rate (commitment / Merkle proof 校验失败率),(iv) 攻击对 utility 自身的影响(防止 watermark "看起来稳"但 memory 已经坏)。任何无法被 audit trace 检测的攻击 = watermark 漏洞,需在 limitations 中明确。

### 9.7 RQ5 — Memory Integrity

**Question**: watermark 是否引入"写错对象 / 错误合并 / 保留过期事实 / 引入脏 memory"?

**Setup**: 在每个 benchmark 上,对 `no-watermark` 与 `+ memory-watermark` 比较以下 ground-truth-driven 指标:update target accuracy / link target accuracy / merge correctness / delete correctness / duplication rate / contradiction rate / stale-memory retention / temporal consistency。

**Expected outcome**: 所有指标在 watermark 开启后无显著退化。这里的关键是 watermark 不能 "可验证但 memory 写坏"。

### 9.8 RQ6 — Composability with Content Watermark — appendix

**Question**: memory watermark 与已有 content watermark (LLM 文本水印 / agent action-layer watermark) 同时开启时是否兼容?

**Setup**: 三档配置 —— `memory-only` / `content-only` / `both`,在 §9.5 的 R1 协议下分别跑 utility 与 decode 指标。

**Expected outcome**: (i) memory decode 不受明显影响,(ii) content watermark 检测能力仍保留,(iii) utility 没有叠加性崩坏。如果两者出现冲突,应在 carrier-level 指出哪种 carrier 与 content watermark 不正交,作为后续工作。


## 10. Related Work

MemMark 与五条研究线相关。**没有任何已有工作同时覆盖** *behavioral watermark* + *memory-evolve 决策层* + *cryptographic / snapshot-only verification* 这三件事;每条 prior line 都只覆盖其中一个或两个维度。

### 10.1 Agent Behavioral Watermarking

最相邻的工作。所有这些方法都在 *visible action* 层嵌水印,验证必须有 action trajectory:

- **AgentMark** [`2601.03294`] —— planning / tool / subgoal 决策的 distribution-preserving keyed sampling。MemMark 与之**层级不同**:AgentMark 解决 "已知 (C_t, p_t) 时如何按 key 挑",MemMark 解决 "在第三方 memory SDK 的开词表 LLM call 上 (C_t, p_t) 根本不存在,如何构造,挂在哪,多次 cascade 如何 compose"(§6.1 / §6.2)。两者关系是**MemMark 在 §6.2 内部把 AgentMark sampler 当一个离散 binning 组件调用**,不是 MemMark 是 AgentMark 的 carrier 扩展。
- **Agent Guide** [`2504.05871`] —— 同框架,通过概率偏置引导高层行为决策。
- **ActHook** (Watermarking LLM Agent Trajectories) [`2602.18700`] —— 在 trajectory dataset 中插入 hook actions,运行时由 secret key 触发。
- **AGENTWM** (On Protecting Agentic Systems' IP via Watermarking) [`2602.08401`] —— 偏置语义等价 tool 执行路径的分布。

**Memory ops as actions** —— 另有一条研究线把 memory 写入本身视为 RL agent 的可学习 action:

- **Memory as Action** [`2510.12635`] —— 显式把 memory store / retrieve / update 当作 RL agent 的可学习动作。
- **A-MAC: Adaptive Memory Admission Control** [`2603.04549`] —— memory write / admission 当作显式决策问题。

这条线与 MemMark 解决的是不同问题:它优化 memory 写入策略,MemMark 把 keyed-attestation 嵌入这些写入决策。具体地,MemMark 做三件这两条线都不覆盖的事:(a) 在第三方 SDK 的内部 LLM call 边界上做拦截(§6.1);(b) 把开词表 LLM 输出归约为 binning sampler 可消费的离散输入(§6.2);(c) 把验证证据从外部 trajectory 转移到 memory record 自身的 in-record sidecar(§9.5 R3),让归因在 forensic 场景里独立于 trajectory 完成。

### 10.2 RAG / Corpus-Level Watermarking

最容易与 MemMark 混淆的一条线。**全部都在静态 corpus 内容上做 watermark**,检测必须 black-box 查询 LLM:

- **RAG-WM** [`2501.05249`, 2025] —— 把 entity-relation tuple 注入 RAG 知识库文档,通过响应文本中的 watermark artifact 检测 RAG 是否被偷。
- **Ward / RAG-DI** [`2410.03537`, ICLR 2025] —— 用 LLM text watermark 给 corpus 文档加签,通过 dataset inference 验证。
- **Watermarked Canaries** [`2502.10673`, 2025] —— 在 IP dataset 中注入合成 canary 文档,黑盒查询 canary 检测 watermark。
- **AQUA** [`2506.10030`, 2025] —— multimodal RAG 的图像内容 watermark,signal 通过 image retriever → text generator 间接传播。
- **KGMark** [ICLR 2025, OpenReview `GKZySvM2t9`] —— **动态 knowledge-graph watermarking**;直接对应 Graphiti backend 的 KG 结构,在 KG 节点 / 边上嵌入水印。这是 **MemMark 在 KG-backend 上的直接 baseline**(见 §9.3 baseline 列表);A-MEM 因为是 notes 网络非严格 KG,KGMark 不适用。
- **Graph Database Watermarking via Pseudo-Nodes** [ACM 2023] —— 通过插入 pseudo-node 给图数据库加水印;静态 graph DB watermark,与 MemMark 的 behavioral evolve watermark 正交。

→ **MemMark 差异**: 这些方法保护 *数据 IP*("谁偷了我的文档"),MemMark 做的是 *writer attribution*("这套 memory state 是谁演化出来的")。机制上,前者是静态内容注入,MemMark 是 behavioral 在 evolve 决策上做 keyed selection;验证上,前者必须 LLM 查询,MemMark 可仅凭 in-record sidecar(R3)。**KGMark 是这条线里离 MemMark 最近的,也是 §9.3 的直接 baseline**。

### 10.3 LLM Text Watermarking

更底层的一条线,只与 MemMark 在 §9.8 RQ6 (Composability) 的 appendix 里有交集:

- **KGW** [`2301.10226`] —— green/red token list 的 logits-level watermark。
- **SynthID-Text** (Nature 2024) [`s41586-024-08025-4`] —— Tournament sampling,distribution-preserving。
- **MarkLLM** (EMNLP 2024 Demo) —— 整合多种 token-level 水印的开源工具包。

→ **MemMark 差异**: 这些是 token-level 水印,作用在 LLM 最终输出文本上;MemMark 不动输出文本,只动 memory backend 的 evolve 决策。两者正交,§9.8 验证在同时开启时彼此不打架。

### 10.4 Long-Term Memory Systems for Agents

MemMark 的 *运行环境* 而非竞争方法。这些系统都没有内建的 cryptographic provenance,本项目把它们当 backend 接入:

- **A-MEM** [`2502.12110`] —— agentic notes + 动态组织网络。
- **Graphiti** —— temporal context graph,带 fact invalidation / supersession。
- **MemOS** [`2505.22101` / `2507.03724`] —— `MemCube` 抽象,包含 provenance / versioning metadata,但**只是字段而非密码学证据**。
- **MemMachine** [`2604.04853`] —— ground-truth-preserving memory system,无 watermark。
- **TierMem: Provenance-Aware Tiered Memory** [`2602.17913`, 2026] —— 显式给 memory 加 provenance 链 + 不可变源 anchoring。**这是 MemMark 在 "memory provenance" 概念上最近的工作**,直接削弱 "为 memory 引入 provenance 是新事物" 的论点;MemMark 的差异不在 provenance 的存在,而在把 *behavioral keyed sampling* 与 provenance 结合,让验证可以与攻击者持有的 corpus 截然区分。
- **A-MemGuard** [`2510.02373`] / **MemoryGraft** [`2512.16962`] —— memory 安全攻防,对 RQ4 攻击模型(§9.6)的 motivation 提供支持;不是 baseline,但威胁面证据的来源。
- **Preference-Aware Memory Update** [`2510.09720`] —— 长期 LLM agent 的 memory update policy;与 MemMark 在 evolve 决策点正交,但同处 "memory update 是显式决策" 的研究脉络。
- *Memory in the Age of AI Agents: A Survey* [`2603.07670` / `2603.11768` SSGM] —— 长期记忆 agent 的 mechanisms / evaluation 综述。
- *A Survey on Long-Term Memory Security / Mnemonic Sovereignty* [`2604.16548`, 2026] —— 显式覆盖 governance / access control / 投毒防御,**不覆盖 behavioral watermark on memory-evolve decisions** —— 反而支持 MemMark 的空白点定位。

→ **MemMark 关系**: 这些是 *backend* 与 *motivation source*,不是 *competing watermark*。MemMark 在 §3.2.3 的最小 adapter 接口下兼容它们。**TierMem 与 MemOS 的 metadata-style / provenance-aware 设计与 MemMark 的密码学-加-watermark 设计形成最近的对照**(§8.4 解释了 metadata 不够,§9.5 `signed-metadata-only` baseline 给出量化证明)。

### 10.5 Cryptographic Provenance Primitives

MemMark §8 的 audit trace 是把成熟密码学原语**移植到 memory-evolve 场景**:

- **Commitment schemes** —— 标准的 commit-then-reveal 协议,MemMark §8.1 用于 per-decision commitment。
- **Merkle trees / transparency logs** —— Certificate Transparency 等公开 anchor 实践,MemMark §8.2 用于 per-session log + signed root。
- **PRF-keyed nonce** —— 防 replay,§8.1 的 `nonce_t = PRF(K, ctx_t)`。

→ **MemMark 关系**: MemMark 把这些成熟原语在 memory evolve 决策点上系统化组合(§8 audit trace 三层结构 + §9.5 R3 in-record verification),贡献在 systems 层。

### 10.6 总结定位

| 维度 | §10.1 Agent Behavioral | §10.2 RAG/Corpus | §10.2 KGMark (单点) | §10.3 LLM Text | §10.4 Memory Systems / TierMem | §10.5 Crypto Primitives | **MemMark** |
|------|----|------|------|------|------|------|------|
| 是否 behavioral | ✅ | ❌(static) | ✅ (KG only) | ❌(token) | N/A | N/A | ✅ |
| 嵌在 memory layer | ❌(action) | ❌(corpus) | ✅ (KG only) | ❌(output) | N/A | N/A | ✅ (3 类 backend) |
| In-record verifiable(无外部 log) | ❌ | ❌ | ❌(需 KG dump 比对) | ❌ | partial(TierMem 有 anchoring) | N/A | ✅ (R3) |
| 抗 memory lifecycle 攻击 | ❌ | partial | partial(KG-only) | ❌ | N/A | N/A | ✅ (§9.6) |
| Cryptographic audit | ❌ | ❌ | ❌ | ❌ | metadata only | ✅ | ✅ |
| Backend-invariant | N/A | partial | ❌(只 KG) | N/A | N/A | N/A | ✅ (3 类 backend) |

MemMark 的独特点是同时勾上 **behavioral × memory layer × in-record verifiable × lifecycle-attack robust × cryptographic audit × backend-invariant** 这六个维度。**KGMark 与 TierMem 是离 MemMark 最近的两个工作**:KGMark 在 KG-only 范围内做了 behavioral memory watermarking,TierMem 做了 provenance-aware 但无 watermark。MemMark 的差异是 *把这两条线合到一起,且跨 KG / notes / temporal-graph 三种结构*。

## 11. 一句话结论

**MemMark** 本质上是在做 **state-evolution attribution**：

- 在 `A-MEM / Graphiti` 两种结构不同的 memory system 上,统一抽象出 backend-invariant 的 evolve carrier taxonomy (update / link / semantic),仅靠 ~200–300 行的 backend native API wrapper 接入,不引入外部 harness
- 在每个 SDK 内部 LLM call 边界上拦截,复用 AgentMark 的 self-reported weight pattern,让 LLM 在单次调用里枚举候选 + 自报权重 (§6.2),再用 distribution-preserving binning sampler 做 keyed pick,把 watermark 嵌入 *latent state-transition* 决策(三类 carrier:update / link / semantic)
- 用 commitment + Merkle log 的 cryptographic audit trace 替代普通 JSON log,实现 tamper-evident、partial-verifiable 的归因
- 用 `LoCoMo + LongMemEval + MemoryAgentBench` 三个 benchmark 跨 conversation / knowledge-update / incremental multi-turn 三类 regime 评估
- 用 memory-specific 攻击模型 (compaction / dedup / supersession / paraphrase rewrite / pruning / poisoning / manual edits + KGMark-style edge relabel / subgraph reanchor) 取代 LLM 文本水印的通用扰动测试
- 用 **In-Record Attribution Verification (R3)** 把归因从 trajectory-bound 解放到 snapshot-only:仅凭 memory snapshot 内的 in-record sidecar 完成 writer attribution,**且通过 `signed-metadata-only` baseline 量化 watermark 相对纯 metadata 的边际归因价值**

## 12. 参考资料

- AgentMark (binning sampler used in §6.2)： [`2601.03294`]
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
- KGMark (Dynamic KG Watermarking, ICLR 2025)： https://openreview.net/forum?id=GKZySvM2t9
- TierMem (Provenance-Aware Tiered Memory, 2026)： https://arxiv.org/abs/2602.17913
- Memory as Action： https://arxiv.org/abs/2510.12635
- A-MAC (Adaptive Memory Admission Control)： https://arxiv.org/abs/2603.04549
- A-MemGuard： https://arxiv.org/abs/2510.02373
- MemoryGraft： https://arxiv.org/abs/2512.16962
- Preference-Aware Memory Update： https://arxiv.org/abs/2510.09720
- Mnemonic Sovereignty Survey： https://arxiv.org/abs/2604.16548
- MemOS preprint： https://arxiv.org/abs/2505.22101
