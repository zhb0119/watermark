---
title: "MemMark Real LLM Agent Pipeline"
version: "v0.1"
implementation: "MemMark MVP + LLMMemoryAgent + LLMCarrierPlanner + JsonMemoryStore"
description: "真实 OpenRouter LLM Agent 从用户输入到 memory watermark 嵌入与解码的完整流程示意。"
created_at: "2026-05-07"
status: "implemented-and-verified"
entrypoint: "memmark.examples.run_real_llm_agent"
model_provider: "OpenRouter OpenAI-compatible API"
verified_model: "deepseek/deepseek-chat"
payload_bits: "101101"
bit_recovery_rate: 1.0
---

# MemMark 真实 Agent 完整流程示意

**本次真实链路已经跑通：用户输入经 OpenRouter LLM 生成回复，再经 LLM 抽取 memory，LLM 评估四类 carrier，脚本选择固定 carrier，LLM 生成候选集合，本地 memory 写入，AgentMark sampler 嵌水印，最后 full-log 解码恢复 payload。**

## 0. 输入配置

你实际使用：

```powershell
$env:MEMMARK_BASE_URL="https://openrouter.ai/api/v1"
$env:MEMMARK_MODEL="deepseek/deepseek-chat"

conda run -n torch_env python -m memmark.examples.run_real_llm_agent
```

真实模型：

```text
deepseek/deepseek-chat
```

代码入口：

```text
memmark/examples/run_real_llm_agent.py
```

核心 agent：

```text
LLMMemoryAgent
```

## 1. 用户输入

示例：

```text
I prefer concise technical answers.
```

进入：

```python
turn = agent.handle_turn(user_input)
```

对应代码：

```text
memmark/agents/memory_agent.py
LLMMemoryAgent.handle_turn()
```

## 2. 第一次 LLM 调用：生成 agent response

### 输入给 LLM

系统 prompt：

```text
You are a helpful agent. Use long-term memory only when it is relevant.
```

用户 prompt：

```text
Long-term memory snapshot:
[]

User input:
I prefer concise technical answers.
```

### LLM 输出

真实运行中得到：

```text
Understood. I’ll provide concise, technical responses.

Example:
Q: "Explain TCP/IP."
A: "Protocol suite for communication. TCP ensures reliable, ordered delivery; IP handles addressing/routing."

Proceed with your query.
```

此时只是普通 agent 回复，**还没有写 memory，也还没有水印**。

## 3. 第二次 LLM 调用：memory extraction

### 输入

代码位置：

```text
LLMMemoryAgent._extract_memory_events()
```

prompt 目标：

```text
从 user message + assistant response 中抽取 durable long-term memory facts
```

输入内容：

```text
User message:
I prefer concise technical answers.

Assistant response:
Understood. I’ll provide concise, technical responses...
```

### LLM 输出

真实运行中得到：

```json
[
  "The user prefers concise technical answers."
]
```

得到 memory event：

```text
e_t = "The user prefers concise technical answers."
```

此时仍未写入 memory。

## 4. 第三次 LLM 调用：四类 carrier feasibility/score 评估

### 固定 carrier 集合

```text
τ ∈ {
  semantic_variant,
  update_target,
  link_target,
  merge_strategy
}
```

代码位置：

```text
memmark/carriers/planner.py
LLMCarrierPlanner.assess_carriers()
```

### 输入给 LLM

包含：

```json
{
  "task": "Assess feasibility of fixed memory watermark carriers.",
  "allowed_carriers": [
    "semantic_variant",
    "update_target",
    "link_target",
    "merge_strategy"
  ],
  "event": "The user prefers concise technical answers.",
  "memory_snapshot": []
}
```

### LLM 应输出

形式：

```json
[
  {
    "carrier_type": "semantic_variant",
    "feasible": true,
    "score": 0.95,
    "reason": "The fact can be safely paraphrased."
  },
  {
    "carrier_type": "update_target",
    "feasible": false,
    "score": 0.1,
    "reason": "No existing memory to update."
  },
  {
    "carrier_type": "link_target",
    "feasible": false,
    "score": 0.1,
    "reason": "No existing target to link."
  },
  {
    "carrier_type": "merge_strategy",
    "feasible": false,
    "score": 0.1,
    "reason": "No duplicate memory to merge."
  }
]
```

## 5. 脚本选择具体 carrier

代码位置：

```text
LLMCarrierPlanner.select_carrier()
```

选择逻辑：

```text
只允许固定 carrier 类型
过滤 feasible=false
选择 score 最高者
```

本轮选择：

```text
τ* = semantic_variant
```

关键点：

```text
LLM 不直接决定协议结构
LLM 只给 feasibility/score
脚本负责最终选择 τ*
```

## 6. 第四次 LLM 调用：根据 carrier 生成候选集合

代码位置：

```text
LLMCarrierPlanner.generate_candidates()
```

因为：

```text
τ* = semantic_variant
```

所以 LLM 必须按 `semantic_variant` schema 生成候选。

### 输入

```json
{
  "task": "Generate semantic-equivalent memory variants for watermark candidate selection.",
  "carrier_type": "semantic_variant",
  "event": "The user prefers concise technical answers.",
  "constraints": [
    "Return 3 to 5 variants.",
    "All variants must preserve the same durable fact.",
    "Return only JSON array of objects with text fields."
  ]
}
```

### LLM 输出候选

示例：

```json
[
  {
    "text": "The user prefers concise technical answers."
  },
  {
    "text": "User preference: The user prefers concise technical answers."
  },
  {
    "text": "Remember that the user wants: The user prefers concise technical answers."
  }
]
```

形成候选集合：

```text
C_t = {c1, c2, c3}
```

每个 candidate 被代码包装为：

```python
Candidate(
    candidate_id="sv_...",
    carrier_type="semantic_variant",
    payload={"text": "..."},
    operation={"op": "add_memory", "text": "..."}
)
```

## 7. 第五次 LLM 调用：候选集合打分

代码位置：

```text
LLMCarrierPlanner.score_candidates()
```

### 输入

```json
{
  "task": "Score candidate acceptability for memory writing.",
  "carrier_type": "semantic_variant",
  "event": "The user prefers concise technical answers.",
  "candidates": [
    {
      "candidate_id": "sv_1_09c706dbe5",
      "text": "The user prefers concise technical answers."
    },
    {
      "candidate_id": "sv_2_a4841f7596",
      "text": "User preference: The user prefers concise technical answers."
    },
    {
      "candidate_id": "sv_3_0ac2c52fc8",
      "text": "Remember that the user wants: The user prefers concise technical answers."
    }
  ]
}
```

### 输出

真实运行中概率为：

```python
{
  "sv_1_09c706dbe5": 0.4,
  "sv_2_a4841f7596": 0.35,
  "sv_3_0ac2c52fc8": 0.25
}
```

得到：

```text
p_t : C_t -> [0,1]
```

## 8. 构造四元组 `D_t`

代码位置：

```text
MemoryWatermarker.evolve()
```

构造：

```text
D_t = <τ, C_t, p_t, ctx_t>
```

本轮为：

```text
τ = semantic_variant

C_t = {
  sv_1_09c706dbe5,
  sv_2_a4841f7596,
  sv_3_0ac2c52fc8
}

p_t = {
  sv_1_09c706dbe5: 0.4,
  sv_2_a4841f7596: 0.35,
  sv_3_0ac2c52fc8: 0.25
}

ctx_t = H(
  agent_id,
  session_id,
  turn_id,
  τ,
  hash(event_text),
  hash(memory_snapshot),
  previous_commitment
)
```

注意：

```text
D_t 由代码构造，不由 LLM 构造
```

原因：

```text
D_t 进入 hash commitment、sampler、decoder，必须稳定可复现。
```

## 9. 水印嵌入：AgentMark differential sampler

代码位置：

```text
memmark/core/sampler.py
sample_memory_transition()
```

内部调用 AgentMark：

```python
sample_behavior_differential(
    probabilities=decision.probabilities,
    bit_stream=payload_bits,
    bit_index=bit_index,
    context_for_key=decision.context,
    round_num=decision.round_num,
)
```

本轮输入：

```text
payload_bits = 101101
bit_index = 0
p_t = {0.4, 0.35, 0.25}
ctx_t = 当前上下文 hash
```

输出：

```text
selected = sv_2_a4841f7596
embedded = 2
decoded = "10"
```

含义：

```text
水印没有改最终回答文本
水印藏在“选哪个 memory variant 写入”这个 state-transition 决策里
```

## 10. 本地 memory 写入

代码位置：

```text
memmark/backends/json_store.py
JsonMemoryStore.apply()
```

selected candidate 的 operation：

```python
{
  "op": "add_memory",
  "text": "User preference: The user prefers concise technical answers."
}
```

写入后：

```json
{
  "id": "m1",
  "text": "User preference: The user prefers concise technical answers.",
  "links": []
}
```

此时：

```text
M_t -> M_{t+1}
```

## 11. Audit commitment 生成

代码位置：

```text
memmark/core/commitment.py
make_commitment()
```

记录：

```text
AuditRecord = {
  decision_id,
  tau,
  hash(C_t),
  hash(p_t),
  hash(ctx_t),
  selected_candidate_id,
  bits_embedded,
  bit_index_after,
  commitment
}
```

作用：

```text
证明这次 memory transition 没被篡改
辅助后续解码
```

## 12. 解码验证

代码位置：

```text
memmark/verifier/full_log.py
verify_full_log()
```

验证输入：

```text
D_t
AuditRecord
payload_bits
previous_bit_index
```

执行：

```text
1. 重算 commitment
2. 调 differential_based_decoder()
3. 从 selected_candidate_id 解出 bits
4. 和 payload 对应片段比较
```

本轮输出：

```text
commitment_valid = True
bits_match = True
decoded = "10"
```

## 13. 本次完整运行结果

最后输出：

```text
payload_bits = 101101
recovered_bits = 101101
bit_recovery_rate = 1.0
audit_records = 6
```

说明：

```text
完整 payload 成功从 memory evolution trace 中恢复
```

## 总流程图

```text
User input
  ↓
LLMMemoryAgent.handle_turn()
  ↓
[LLM Call 1] Generate assistant response
  ↓
LLM response
  ↓
[LLM Call 2] Extract durable memory events
  ↓
memory event e_t
  ↓
[LLM Call 3] Assess carrier feasibility/score
  ↓
{semantic_variant, update_target, link_target, merge_strategy}
  ↓
Script selects τ*
  ↓
[LLM Call 4] Generate candidates C_t under τ* schema
  ↓
[LLM Call 5] Score candidates p_t
  ↓
Script constructs D_t=<τ*,C_t,p_t,ctx_t>
  ↓
AgentMark differential sampler embeds payload bits
  ↓
selected memory transition
  ↓
JsonMemoryStore.apply()
  ↓
M_t -> M_{t+1}
  ↓
AuditRecord commitment
  ↓
Full-log decoder
  ↓
recovered bits
```

## 当前问题点

**memory extraction 偏宽。**

例如：

```text
Tell me what MemMark is.
```

被抽成：

```text
MemMark is a feature for capturing...
```

这不是用户长期偏好，而是 assistant 生成的普通解释。

后续应收紧：

```text
只从 user message 抽取明确长期事实
assistant response 只用于消解指代
不存普通知识解释
```

## 一句话总结

```text
现在 MemMark 已经实现真实 agent 交互闭环：
LLM 负责响应、抽取、评估 carrier、生成候选、打分；
代码负责固定 carrier 选择、D_t 构造、水印采样、memory 写入、commitment 和解码验证。
```
