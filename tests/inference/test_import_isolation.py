"""Guards the inference Docker image's dependency footprint: importing medrisk_inference
(or any of the medrisk_ml submodules it reuses) must never pull in training-only packages.

If this test fails, something in medrisk_inference started importing a medrisk_ml module
that itself imports pandas/scikit-learn/matplotlib/tensorboard/h5py/PyYAML/tqdm - all of
which are absent from requirements-inference.txt on purpose (see that file's header
comment). Fix the import, don't add the package to requirements-inference.txt.
"""

from __future__ import annotations

import subprocess
import sys

_FORBIDDEN_MODULE_PREFIXES = (
    "pandas",
    "sklearn",
    "matplotlib",
    "tensorboard",
    "h5py",
    "yaml",
)
# Not checked: tqdm. It's a real transitive dependency of torch itself (imported by
# torch/torchvision internals, e.g. torch.hub's download progress bar) regardless of
# anything medrisk_inference does, and is small enough not to matter for image size.

_MEDRISK_INFERENCE_SUBMODULES = (
    "medrisk_inference.bundle",
    "medrisk_inference.cli",
    "medrisk_inference.config",
    "medrisk_inference.decision",
    "medrisk_inference.exceptions",
    "medrisk_inference.explanation",
    "medrisk_inference.image_validation",
    "medrisk_inference.preprocessing",
    "medrisk_inference.runtime",
    "medrisk_inference.service",
    "medrisk_inference.types",
    "medrisk_inference.utils",
)


def test_importing_medrisk_inference_does_not_load_training_only_packages() -> None:
    """Runs in a fresh subprocess so already-imported modules in the test session (pytest
    itself, other test files) can't mask a real transitive-import problem."""
    import_statements = "; ".join(f"import {module}" for module in _MEDRISK_INFERENCE_SUBMODULES)
    script = (
        f"{import_statements}\n"
        "import sys\n"
        f"forbidden = {_FORBIDDEN_MODULE_PREFIXES!r}\n"
        "leaked = sorted(\n"
        "    name for name in sys.modules\n"
        "    if any(name == f or name.startswith(f + '.') for f in forbidden)\n"
        ")\n"
        "print('LEAKED:' + ','.join(leaked))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    leaked_line = next(line for line in result.stdout.splitlines() if line.startswith("LEAKED:"))
    leaked = [name for name in leaked_line.removeprefix("LEAKED:").split(",") if name]
    assert leaked == [], f"medrisk_inference imports pulled in training-only modules: {leaked}"
