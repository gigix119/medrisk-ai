"""Active model metadata endpoint."""

from fastapi import APIRouter

from app.api.dependencies import ActiveHistopathologyModelDep, CurrentUserDep
from app.schemas.model_deployment import (
    ActiveModelResponse,
    InputContractSchema,
    ReviewPolicySchema,
)

router = APIRouter()


@router.get(
    "/active",
    response_model=ActiveModelResponse,
    summary="Metadata for the currently active histopathology model",
)
async def get_active_model(
    _current_user: CurrentUserDep, active_model: ActiveHistopathologyModelDep
) -> ActiveModelResponse:
    runtime = active_model.runtime
    manifest = runtime.manifest
    review_policy = runtime.review_policy

    return ActiveModelResponse(
        module="histopathology",
        model_id=manifest.model_id,
        model_name=manifest.model_name,
        version=manifest.model_version,
        architecture=manifest.architecture,
        dataset_name=manifest.dataset_name,
        dataset_mode=manifest.dataset_mode,
        synthetic_only=manifest.synthetic_only,
        eligible_for_demo=manifest.eligible_for_demo,
        input_contract=InputContractSchema(
            input_height=manifest.input_height,
            input_width=manifest.input_width,
            input_channels=manifest.input_channels,
        ),
        class_names=manifest.class_names,
        positive_class=manifest.positive_class,
        threshold=runtime.threshold,
        review_policy=(
            ReviewPolicySchema(
                negative_probability_max=review_policy.negative_probability_max,
                positive_probability_min=review_policy.positive_probability_min,
            )
            if review_policy
            else None
        ),
        calibration_enabled=bool(runtime.calibration),
        activated_at=active_model.activated_at,
    )
