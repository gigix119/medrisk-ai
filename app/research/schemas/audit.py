"""Dataset quality / leakage audit read schemas (Phase 7).

`summary` is kept as a generic `dict` rather than a fully-modeled nested schema - the master
spec's own list of possible quality/leakage findings is large and dataset-type-dependent
(see docs/PHASE_7_PROGRESS.md), and the actual structure is produced once, by
`app.research.services.dataset_quality_service`/`leakage_audit_service`, which is the single
source of truth for its shape.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.research.domain.enums import AuditStatus


class DatasetQualityAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    status: AuditStatus
    summary: dict
    created_at: datetime


class DatasetLeakageAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    status: AuditStatus
    summary: dict
    created_at: datetime
