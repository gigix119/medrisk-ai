"""Pure unit tests for app.services.dataset.resolve_sample_image_path - no DB, no app.

`dataset_id: uuid.UUID`/`sample_id: uuid.UUID` are the only request-controlled values
anywhere in the dataset-sample image flow; `relative_path` always comes from a DB row. These
tests prove the path-traversal guard rejects a malicious `relative_path` even if a future bug
ever let one into the database - the HTTP route itself cannot express a traversal attempt
since it only accepts UUIDs.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.core.exceptions import ResourceNotFoundError
from app.models.dataset import Dataset
from app.models.dataset_sample import DatasetSample
from app.services.dataset import resolve_sample_image_path


def _dataset(**overrides: object) -> Dataset:
    defaults: dict[str, object] = {"id": uuid.uuid4(), "slug": "demo", "version": "1.0.0"}
    defaults.update(overrides)
    return Dataset(**defaults)  # type: ignore[arg-type]


def _sample(**overrides: object) -> DatasetSample:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "relative_path": "images/train/000000.png",
        "mime_type": "image/png",
    }
    defaults.update(overrides)
    return DatasetSample(**defaults)  # type: ignore[arg-type]


def test_normal_relative_path_resolves(tmp_path: Path) -> None:
    dataset = _dataset()
    sample = _sample()
    image_path = tmp_path / dataset.slug / dataset.version / sample.relative_path
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake-png-bytes")

    resolved = resolve_sample_image_path(dataset, sample, datasets_root=tmp_path)
    assert resolved == image_path.resolve()


def test_parent_traversal_in_relative_path_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "demo" / "1.0.0").mkdir(parents=True)
    secret = tmp_path / "secret.txt"
    secret.write_bytes(b"should never be reachable")

    dataset = _dataset()
    sample = _sample(relative_path="../../secret.txt")

    with pytest.raises(ResourceNotFoundError):
        resolve_sample_image_path(dataset, sample, datasets_root=tmp_path)


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    dataset_images_dir = tmp_path / "demo" / "1.0.0" / "images"
    dataset_images_dir.mkdir(parents=True)
    outside_target = tmp_path / "outside.png"
    outside_target.write_bytes(b"outside the dataset root")

    link = dataset_images_dir / "000000.png"
    try:
        link.symlink_to(outside_target)
    except OSError:
        pytest.skip("Symlink creation requires elevated privileges on this platform.")

    dataset = _dataset()
    sample = _sample(relative_path="images/000000.png")

    with pytest.raises(ResourceNotFoundError):
        resolve_sample_image_path(dataset, sample, datasets_root=tmp_path)


def test_missing_file_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "demo" / "1.0.0").mkdir(parents=True)

    dataset = _dataset()
    sample = _sample(relative_path="images/does-not-exist.png")

    with pytest.raises(ResourceNotFoundError):
        resolve_sample_image_path(dataset, sample, datasets_root=tmp_path)
