"""Minimal setup for installing the WujiangXu/AgenticMemory eval repo.

The eval repo ships its core in flat modules (``memory_layer.py``,
``memory_layer_robust.py``, etc.) instead of a Python package. This
setup.py installs:

  * the flat modules as top-level ``py_modules`` (so
    ``import memory_layer`` works), and
  * a thin ``agentic_memory`` shim package that re-exports
    ``memory_layer``'s public API under the SDK module path
    ``agentic_memory.memory_system`` — keeps drop-in compat with code
    that previously installed the agiresearch/A-mem SDK.

After installing this on top of a clone of WujiangXu/AgenticMemory:

    >>> from agentic_memory.memory_system import AgenticMemorySystem
    >>> hasattr(AgenticMemorySystem, "find_related_memories_raw")
    True

(The agiresearch SDK only exposes ``find_related_memories``; the eval
repo's class additionally has ``find_related_memories_raw`` which the
A-mem paper's LoCoMo eval (test_advanced_robust.py) uses.)
"""

from setuptools import setup


setup(
    name="agentic-memory",
    version="0.0.2",
    description=(
        "WujiangXu/AgenticMemory eval-repo install (provides"
        " find_related_memories_raw); shimmed under the SDK module path."
    ),
    py_modules=[
        "memory_layer",
        "memory_layer_robust",
        "utils",
        "llm_text_parsers",
        "load_dataset",
    ],
    packages=["agentic_memory"],
    package_dir={"agentic_memory": "agentic_memory"},
    install_requires=[
        "rank_bm25",
        "sentence-transformers",
        "scikit-learn",
        "transformers",
        "nltk",
        "litellm",
        "openai",
        "requests",
        "chromadb",
    ],
    python_requires=">=3.9",
)
