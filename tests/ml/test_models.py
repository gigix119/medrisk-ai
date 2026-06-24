from __future__ import annotations

import pytest
import torch

from medrisk_ml.models.baseline_cnn import BaselineCNN, BaselineCNNConfig
from medrisk_ml.models.factory import (
    UnknownArchitectureError,
    build_model,
    count_parameters,
    get_target_layer,
)
from medrisk_ml.models.resnet import build_resnet18

IMAGE_SIZE = 64


def test_baseline_cnn_forward_shape() -> None:
    model = BaselineCNN(BaselineCNNConfig())
    output = model(torch.randn(4, 3, IMAGE_SIZE, IMAGE_SIZE))
    assert output.shape == (4, 1)


def test_resnet18_forward_shape_without_pretrained_weights() -> None:
    # pretrained=False - no network access, no weight download.
    model = build_resnet18(pretrained=False, freeze_backbone=False)
    output = model(torch.randn(2, 3, IMAGE_SIZE, IMAGE_SIZE))
    assert output.shape == (2, 1)


def test_baseline_cnn_backward_pass_populates_gradients() -> None:
    model = BaselineCNN(BaselineCNNConfig())
    output = model(torch.randn(2, 3, IMAGE_SIZE, IMAGE_SIZE))
    loss = output.sum()
    loss.backward()
    grads = [p.grad for p in model.parameters() if p.requires_grad]
    assert grads
    assert all(g is not None for g in grads)


def test_resnet18_frozen_backbone_only_trains_head() -> None:
    model = build_resnet18(pretrained=False, freeze_backbone=True)
    trainable_names = {name for name, p in model.named_parameters() if p.requires_grad}
    frozen_names = {name for name, p in model.named_parameters() if not p.requires_grad}
    assert trainable_names
    assert all(name.startswith("fc.") for name in trainable_names)
    assert frozen_names
    assert not any(name.startswith("fc.") for name in frozen_names)


def test_resnet18_unfreeze_from_layer() -> None:
    model = build_resnet18(pretrained=False, freeze_backbone=True, unfreeze_from_layer="layer4")
    assert all(p.requires_grad for p in model.layer4.parameters())
    assert all(p.requires_grad for p in model.fc.parameters())
    assert not any(p.requires_grad for p in model.layer1.parameters())


def test_count_parameters_trainable_le_total() -> None:
    model = build_resnet18(pretrained=False, freeze_backbone=True)
    total, trainable = count_parameters(model)
    assert total > 0
    assert 0 < trainable <= total


def test_factory_builds_baseline_cnn() -> None:
    model, metadata = build_model("baseline_cnn", dropout=0.2, image_size=IMAGE_SIZE)
    assert metadata.architecture == "baseline_cnn"
    assert metadata.output_shape == (1,)
    output = model(torch.randn(1, 3, IMAGE_SIZE, IMAGE_SIZE))
    assert output.shape == (1, 1)


def test_factory_builds_resnet18() -> None:
    model, metadata = build_model("resnet18", pretrained=False, image_size=IMAGE_SIZE)
    assert metadata.architecture == "resnet18"
    output = model(torch.randn(1, 3, IMAGE_SIZE, IMAGE_SIZE))
    assert output.shape == (1, 1)


def test_factory_rejects_unknown_architecture() -> None:
    with pytest.raises(UnknownArchitectureError):
        build_model("not_a_real_architecture")  # type: ignore[arg-type]


def test_get_target_layer_for_each_architecture() -> None:
    baseline_model, _ = build_model("baseline_cnn", image_size=IMAGE_SIZE)
    resnet_model, _ = build_model("resnet18", pretrained=False, image_size=IMAGE_SIZE)
    assert get_target_layer(baseline_model, "baseline_cnn") is baseline_model.features[-1]
    assert get_target_layer(resnet_model, "resnet18") is resnet_model.layer4
