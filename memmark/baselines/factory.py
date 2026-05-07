"""Convenience factory for baseline configurations.

`build_baseline(name, **wm_kwargs)` returns a configured
`MemoryWatermarker`. The actual sampler logic lives inside
`memmark.core.sampler.sample_memory_transition`; this factory just
picks the `sampler_mode` flag.
"""

from __future__ import annotations

from typing import Any

from memmark.sdk.memory_watermarker import MemoryWatermarker


_BASELINE_TO_MODE = {
    "watermark": "watermark",
    "signed_metadata_only": "signed_metadata_only",
    "signed-metadata-only": "signed_metadata_only",
    "random_replace": "random_replace",
    "random-replace": "random_replace",
    "no_watermark": "no_watermark",
    "no-watermark": "no_watermark",
}


def build_baseline(name: str, **kwargs: Any) -> MemoryWatermarker:
    if name not in _BASELINE_TO_MODE:
        raise ValueError(
            f"Unknown baseline: {name!r}. "
            f"Choose from {sorted(_BASELINE_TO_MODE)}."
        )
    kwargs["sampler_mode"] = _BASELINE_TO_MODE[name]
    return MemoryWatermarker(**kwargs)
