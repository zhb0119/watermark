# Install A-mem (eval-repo version)

A-mem 有两份发行:

1. **SDK** — `agiresearch/A-mem`,pip-installable,但 `AgenticMemorySystem` 砍掉了 `find_related_memories_raw`。
2. **Eval repo** — `WujiangXu/AgenticMemory`,A-mem 论文 LoCoMo eval 用的版本,有 `find_related_memories_raw`,但**不能直接 pip install**(没 setup.py)。

我们 QA path(`memmark/backends/amem_store.py:_qa_amem_robust`)按 `test_advanced_robust.py` 协议跑,需要 `_raw`。所以**装 eval 版**。

## 一行命令

从 watermark 仓库根目录:

```bash
python tools/install_amem_eval/install.py
```

会做四件事:
1. `git clone https://github.com/WujiangXu/AgenticMemory.git ../A-mem`
2. 把本目录下 `setup.py` + `agentic_memory/` shim 复制到 `../A-mem/`
3. `pip uninstall -y agentic-memory`(如果之前装过 SDK)
4. `pip install ../A-mem`

成功输出:

```
AgenticMemorySystem source: memory_layer
  find_related_memories:     True
  find_related_memories_raw: True
✅ Install OK
```

## 选项

```bash
# 改 clone 目标路径(默认 ../A-mem,相对当前目录)
python tools/install_amem_eval/install.py --target /path/to/A-mem

# macOS Homebrew Python 需要 --break-system-packages
python tools/install_amem_eval/install.py --break-system-packages

# 已经 clone 过、只想拷 shim + 装
python tools/install_amem_eval/install.py --no-clone
```

## 手动分步(给不愿意跑脚本的)

```bash
# 1. clone eval repo
git clone https://github.com/WujiangXu/AgenticMemory.git ../A-mem

# 2. 把 shim 复制进去(从 watermark 仓库根)
cp tools/install_amem_eval/setup.py                 ../A-mem/
mkdir -p                                              ../A-mem/agentic_memory
cp tools/install_amem_eval/agentic_memory/__init__.py    ../A-mem/agentic_memory/
cp tools/install_amem_eval/agentic_memory/memory_system.py ../A-mem/agentic_memory/

# 3. 卸 SDK 装 eval
pip uninstall -y agentic-memory
pip install ../A-mem
```

## Windows PowerShell 版

```powershell
git clone https://github.com/WujiangXu/AgenticMemory.git ..\A-mem
Copy-Item tools\install_amem_eval\setup.py                  ..\A-mem\
New-Item -ItemType Directory -Force ..\A-mem\agentic_memory | Out-Null
Copy-Item tools\install_amem_eval\agentic_memory\*.py       ..\A-mem\agentic_memory\
pip uninstall -y agentic-memory
pip install ..\A-mem
```

或直接 `python tools\install_amem_eval\install.py`(Python 脚本跨平台)。

## 验证

```bash
python -c "from agentic_memory.memory_system import AgenticMemorySystem; \
           print('source:', AgenticMemorySystem.__module__); \
           print('raw:', hasattr(AgenticMemorySystem, 'find_related_memories_raw'))"
```

期望:
```
source: memory_layer
raw: True
```

如果 `source: agentic_memory.memory_system` —— 装的是 SDK,不是 eval。重跑安装。

## 为什么必须是 eval 版

我们 `amem_store.py:_qa_amem_robust` 走 A-mem 论文 robust 协议(`test_advanced_robust.py:111-112`):

```python
keywords = self.generate_query_llm(question)
raw_context = self.retrieve_memory(keywords, k=self.retrieve_k)  # = find_related_memories_raw
```

SDK 版没 `_raw`,我们代码里有 fallback 到 `find_related_memories`,但格式略不同(多 `memory_id:n5\t` 前缀,少 link neighbor 展开)。**只在装 eval 版时才完全对齐 A-mem 论文 LoCoMo eval 数字**。
