"""Idempotently seed the "Synthetic Histopathology Demonstration Dataset" registry entry and
its sample images.

Used by Docker Compose (`compose.yaml`) after migrations, before Uvicorn starts. Reuses
`medrisk_ml.data.synthetic.SyntheticHistopathologyDataset` directly (the same generator the
only model bundle in this repo was trained on) - image bytes are generated deterministically
from a fixed seed, so re-running this script never produces different files or new UUIDs for
unchanged samples. Refuses to run when ENVIRONMENT=production (this dataset is honestly
labeled synthetic/demonstrative; the repo's only model bundle cannot even load in production
per Settings.validate_production_model_policy, so seeding it there would be pointless).
"""

import asyncio
import io
import logging
import sys
from pathlib import Path
from typing import Any, cast

from PIL import Image

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.repositories import dataset as dataset_repo
from medrisk_ml.data.synthetic import SyntheticHistopathologyDataset
from medrisk_ml.utils.hashing import sha256_bytes, sha256_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("seed_dataset")

DATASET_SLUG = "synthetic-histopathology-demo"
DATASET_VERSION = "1.0.0"
GENERATOR_SEED = 42
IMAGE_SIZE = 96
CLASS_NAMES = ("negative", "positive")
SAMPLES_PER_SPLIT: dict[str, int] = {"train": 30, "val": 10, "test": 10}


def _identity(image: Image.Image) -> Any:
    """Used as `SyntheticHistopathologyDataset`'s `transform` so `__getitem__` hands back the
    PIL Image itself instead of running `T.ToTensor()` - simpler than a tensor round-trip when
    all this script wants to do is `.save()` the image to disk."""
    return image


def _class_distribution() -> dict[str, dict[str, int]]:
    distribution: dict[str, dict[str, int]] = {}
    for split, count in SAMPLES_PER_SPLIT.items():
        positives = count // 2
        distribution[split] = {"negative": count - positives, "positive": positives}
    return distribution


async def seed_dataset() -> None:
    settings = get_settings()

    if settings.ENVIRONMENT == "production":
        logger.info("ENVIRONMENT=production - skipping dataset seed.")
        return

    dataset_root = Path(settings.DATASETS_ROOT) / DATASET_SLUG / DATASET_VERSION
    images_root = dataset_root / "images"

    total_samples = sum(SAMPLES_PER_SPLIT.values())
    async with AsyncSessionLocal() as session:
        dataset = await dataset_repo.upsert_dataset(
            session,
            slug=DATASET_SLUG,
            name="Synthetic Histopathology Demonstration Dataset",
            version=DATASET_VERSION,
            description=(
                "A small, fully synthetic collection of generated image patches used to "
                "demonstrate the research inference pipeline end to end. These are NOT real "
                "tissue samples and carry no medical meaning."
            ),
            source_name="Generated in-repo (medrisk_ml.data.synthetic.SyntheticHistopathologyDataset)",
            source_url=None,
            license_name="Project-internal synthetic data (no external license applies)",
            license_url=None,
            citation=None,
            intended_use=(
                "Demonstrating the dataset-driven research inference flow (dataset -> sample "
                "-> ground truth -> prediction -> explanation) for engineering review."
            ),
            prohibited_use=(
                "Must not be used, cited, or represented as real histopathology data, for "
                "medical research, diagnosis, or any clinical purpose."
            ),
            modality="histopathology_patch",
            task_type="binary_classification",
            classes=list(CLASS_NAMES),
            sample_count=total_samples,
            image_width=IMAGE_SIZE,
            image_height=IMAGE_SIZE,
            image_channels=3,
            split_names=list(SAMPLES_PER_SPLIT.keys()),
            class_distribution=_class_distribution(),
            preprocessing_summary="None - images are generated already at the model's native input size.",
            known_limitations=(
                "Images are procedurally generated noise patterns, not real tissue - they "
                "carry no histological structure beyond a synthetic bright-region marker for "
                "the positive class. Model performance on this dataset says nothing about "
                "performance on real histopathology data."
            ),
            ethical_notes=(
                "No human subjects, patient data, or biological material of any kind was "
                "used to produce this dataset. It exists solely to exercise the inference "
                "pipeline safely."
            ),
            is_synthetic=True,
            is_public=True,
            is_active=True,
        )
        await session.commit()

        seeded = 0
        for split, count in SAMPLES_PER_SPLIT.items():
            generator = SyntheticHistopathologyDataset(
                split=split,  # type: ignore[arg-type]
                num_samples=count,
                seed=GENERATOR_SEED,
                image_size=IMAGE_SIZE,
                transform=_identity,  # bypass ToTensor: keep the PIL Image itself
            )
            split_dir = images_root / split
            split_dir.mkdir(parents=True, exist_ok=True)

            for index in range(count):
                # `_identity` makes `__getitem__` actually return a PIL Image here, despite
                # its declared `torch.Tensor` element type (the dataset's own generic param).
                image, label, _generator_sample_id = generator[index]
                filename = f"{index:06d}.png"
                image_path = split_dir / filename

                checksum = _write_if_changed(cast(Image.Image, image), image_path)

                await dataset_repo.upsert_sample(
                    session,
                    dataset_id=dataset.id,
                    sample_key=f"synthetic_{split}_{index:06d}",
                    split=split,
                    filename=filename,
                    relative_path=f"images/{split}/{filename}",
                    ground_truth_label=CLASS_NAMES[label],
                    class_index=label,
                    width=IMAGE_SIZE,
                    height=IMAGE_SIZE,
                    mime_type="image/png",
                    checksum_sha256=checksum,
                    source_reference=None,
                    license_reference=None,
                    is_synthetic=True,
                    metadata_json={
                        "seed": GENERATOR_SEED,
                        "generator": "medrisk_ml.data.synthetic",
                    },
                    notes=None,
                )
                seeded += 1
        await session.commit()

    logger.info("Seeded dataset %s (%d samples).", DATASET_SLUG, seeded)


def _write_if_changed(image: Image.Image, path: Path) -> str:
    """Write the PNG only if the file doesn't already match what generation would produce
    again - this (not a delete-then-reinsert) is the idempotency mechanism for image bytes,
    so re-running the script never assigns new identity to unchanged samples."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    data = buffer.getvalue()

    if path.is_file():
        existing_checksum = sha256_file(path)
        if existing_checksum == sha256_bytes(data):
            return existing_checksum

    path.write_bytes(data)
    return sha256_file(path)


def main() -> None:
    asyncio.run(seed_dataset())
    sys.exit(0)


if __name__ == "__main__":
    main()
