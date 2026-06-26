"""Integration tests for dataset quality/leakage audits (Phase 7).

`seeded_dataset` (tests/integration/conftest.py) uses placeholder checksums ("0"*64 /
"1"*64) that deliberately do not match the real bytes written to disk - useful here as a
genuine checksum-mismatch fixture, not a bug to work around. A second, internally-consistent
dataset is built locally for the "clean dataset" and "cross-split leakage" cases.
"""

from __future__ import annotations

import hashlib
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import dataset as dataset_repo
from tests.conftest import TEST_DATASETS_ROOT
from tests.integration.conftest import AuthTokens, SeededDataset


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def _build_clean_dataset(
    db_session: AsyncSession, *, splits: dict[str, list[tuple[str, bytes]]]
) -> uuid.UUID:
    """Writes real files with matching checksums for each (split -> [(sample_key, content)])
    entry, so the quality audit has nothing to flag and the leakage audit can be pointed at
    deliberately overlapping content across splits when the caller wants that."""
    slug = f"clean-dataset-{uuid.uuid4().hex[:8]}"
    version = "1.0.0"
    image_root = TEST_DATASETS_ROOT / slug / version / "images"
    image_root.mkdir(parents=True)

    all_split_names = list(splits.keys())
    dataset = await dataset_repo.upsert_dataset(
        db_session,
        slug=slug,
        name="Clean fixture dataset",
        version=version,
        description="Fixture dataset with internally-consistent checksums.",
        source_name="test-fixture",
        source_url=None,
        license_name="N/A",
        license_url=None,
        citation=None,
        intended_use="Testing only.",
        prohibited_use="N/A",
        modality="histopathology_patch",
        task_type="binary_classification",
        classes=["negative", "positive"],
        sample_count=sum(len(v) for v in splits.values()),
        image_width=8,
        image_height=8,
        image_channels=3,
        split_names=all_split_names,
        class_distribution={},
        preprocessing_summary=None,
        known_limitations="Synthetic test fixture.",
        ethical_notes="No real data involved.",
        is_synthetic=True,
        is_public=True,
        is_active=True,
    )

    for split, entries in splits.items():
        for index, (sample_key, content) in enumerate(entries):
            label = "negative" if index % 2 == 0 else "positive"
            filename = f"{sample_key}.bin"
            (image_root / filename).write_bytes(content)
            await dataset_repo.upsert_sample(
                db_session,
                dataset_id=dataset.id,
                sample_key=sample_key,
                split=split,
                filename=filename,
                relative_path=f"images/{filename}",
                ground_truth_label=label,
                class_index=0 if label == "negative" else 1,
                width=8,
                height=8,
                mime_type="application/octet-stream",
                checksum_sha256=_sha256(content),
                source_reference=None,
                license_reference=None,
                is_synthetic=True,
                metadata_json=None,
                notes=None,
            )
    await db_session.commit()
    return dataset.id


async def test_quality_audit_passes_on_internally_consistent_dataset(
    client: AsyncClient, superuser_auth_tokens: AuthTokens, db_session: AsyncSession
) -> None:
    dataset_id = await _build_clean_dataset(
        db_session, splits={"train": [("a", b"AAA"), ("b", b"BBB")]}
    )
    response = await client.post(
        f"/api/v1/research/datasets/{dataset_id}/quality-audit",
        headers=superuser_auth_tokens.auth_header,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "passed"
    assert body["summary"]["missing_file_count"] == 0
    assert body["summary"]["checksum_mismatch_count"] == 0


async def test_quality_audit_detects_checksum_mismatch(
    client: AsyncClient, superuser_auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    """`seeded_dataset`'s checksums ("0"*64 / "1"*64) never match the real PNG bytes - the
    audit must surface this as a critical, FAILED finding, not silently ignore it."""
    response = await client.post(
        f"/api/v1/research/datasets/{seeded_dataset.dataset_id}/quality-audit",
        headers=superuser_auth_tokens.auth_header,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert body["summary"]["checksum_mismatch_count"] == 2
    codes = [f["code"] for f in body["summary"]["findings"]]
    assert "CHECKSUM_MISMATCH" in codes


async def test_quality_audit_get_before_any_run_returns_404(
    client: AsyncClient, auth_tokens: AuthTokens, seeded_dataset: SeededDataset
) -> None:
    response = await client.get(
        f"/api/v1/research/datasets/{seeded_dataset.dataset_id}/quality",
        headers=auth_tokens.auth_header,
    )
    assert response.status_code == 404


async def test_quality_audit_get_returns_latest_after_post(
    client: AsyncClient, superuser_auth_tokens: AuthTokens, db_session: AsyncSession
) -> None:
    dataset_id = await _build_clean_dataset(db_session, splits={"train": [("a", b"AAA")]})
    post_response = await client.post(
        f"/api/v1/research/datasets/{dataset_id}/quality-audit",
        headers=superuser_auth_tokens.auth_header,
    )
    get_response = await client.get(
        f"/api/v1/research/datasets/{dataset_id}/quality", headers=superuser_auth_tokens.auth_header
    )
    assert get_response.status_code == 200
    assert get_response.json()["id"] == post_response.json()["id"]


async def test_leakage_audit_reports_incomplete_without_subject_identifier(
    client: AsyncClient, superuser_auth_tokens: AuthTokens, db_session: AsyncSession
) -> None:
    dataset_id = await _build_clean_dataset(
        db_session, splits={"train": [("a", b"AAA")], "test": [("b", b"BBB")]}
    )
    response = await client.post(
        f"/api/v1/research/datasets/{dataset_id}/leakage-audit",
        headers=superuser_auth_tokens.auth_header,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "incomplete"
    assert body["summary"]["group_level_overlap"]["evaluated"] is False


async def test_leakage_audit_detects_cross_split_checksum_overlap(
    client: AsyncClient, superuser_auth_tokens: AuthTokens, db_session: AsyncSession
) -> None:
    """Same byte content registered under both train and test must be flagged critical -
    the strongest possible exact-duplicate leakage signal."""
    duplicated_content = b"identical-bytes-in-two-splits"
    dataset_id = await _build_clean_dataset(
        db_session,
        splits={
            "train": [("train-sample", duplicated_content)],
            "test": [("test-sample", duplicated_content)],
        },
    )
    response = await client.post(
        f"/api/v1/research/datasets/{dataset_id}/leakage-audit",
        headers=superuser_auth_tokens.auth_header,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert body["summary"]["cross_split_checksum_overlap_count"] == 1
    codes = [f["code"] for f in body["summary"]["findings"]]
    assert "CROSS_SPLIT_CHECKSUM_OVERLAP" in codes
