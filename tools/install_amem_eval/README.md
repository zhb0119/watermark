# Install A-mem (eval-repo version)

A-mem 有两份发行:

1. **SDK** — `agiresearch/A-mem`,pip-installable,但 `AgenticMemorySystem` 砍掉了 `find_related_memories_raw`。
2. **Eval repo** — `WujiangXu/AgenticMemory`,A-mem 论文 LoCoMo eval 用的版本,有 `find_related_memories_raw`。部分 revision 没有 `setup.py`,不能直接 pip install。

我们 QA path(`memmark/backends/amem_store.py:_qa_amem_robust`)按 `test_advanced_robust.py` 协议跑,需要 `_raw`。所以**装 eval 版**。

## 一行命令

从 watermark 仓库根目录:

```bash
python tools/install_amem_eval/install.py
```

会做四件事:
1. `git clone https://github.com/WujiangXu/AgenticMemory.git ../A-mem`
2. 把本目录下 `setup.py` 复制到 `../A-mem/`
   - 新版 `agentic_memory/` 包结构: 保留原包,不覆盖
   - 旧版 `memory_layer.py` 平铺结构: 额外复制 `agentic_memory/` shim
3. `pip uninstall -y agentic-memory`(如果之前装过 SDK)
4. `pip install ../A-mem`

成功输出:

```
AgenticMemorySystem source: memory_layer
  find_related_memories:     True
  find_related_memories_raw: True
✅ Install OK
```

新版包结构的成功输出也可能是:

```
AgenticMemorySystem source: agentic_memory.memory_system
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

# 已经 clone 过、只想补 setup.py + 装
python tools/install_amem_eval/install.py --no-clone
```

## 手动分步(给不愿意跑脚本的)

```bash
# 1. clone eval repo
git clone https://github.com/WujiangXu/AgenticMemory.git ../A-mem

# 2. 把 setup.py 复制进去(从 watermark 仓库根)
cp tools/install_amem_eval/setup.py                 ../A-mem/

# 3. 卸 SDK 装 eval
pip uninstall -y agentic-memory
pip install ../A-mem
```

只有当 `../A-mem/memory_layer.py` 存在且 `../A-mem/agentic_memory/memory_system.py` 不存在时,才需要复制 `agentic_memory/` shim。

## Windows PowerShell 版

```powershell
git clone https://github.com/WujiangXu/AgenticMemory.git ..\A-mem
Copy-Item tools\install_amem_eval\setup.py                  ..\A-mem\
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

或:

```
source: agentic_memory.memory_system
raw: True
```

判断标准只有一个: `raw: True`。

## 修复已被旧脚本覆盖的 clone

如果看到:

```
ModuleNotFoundError: No module named 'memory_layer'
```

说明旧脚本把新版 repo 的 `agentic_memory/memory_system.py` 覆盖成了旧 shim。修复方式:

```powershell
Remove-Item -Recurse -Force ..\A-mem
python tools\install_amem_eval\install.py
```

如果你想保留 clone,也可以在 `..\A-mem` 内执行 `git restore agentic_memory\__init__.py agentic_memory\memory_system.py`,再重跑安装脚本。

## 为什么必须是 eval 版

我们 `amem_store.py:_qa_amem_robust` 走 A-mem 论文 robust 协议(`test_advanced_robust.py:111-112`):

```python
keywords = self.generate_query_llm(question)
raw_context = self.retrieve_memory(keywords, k=self.retrieve_k)  # = find_related_memories_raw
```

SDK 版没 `_raw`,我们代码里有 fallback 到 `find_related_memories`,但格式略不同(多 `memory_id:n5\t` 前缀,少 link neighbor 展开)。**只在装 eval 版时才完全对齐 A-mem 论文 LoCoMo eval 数字**。
