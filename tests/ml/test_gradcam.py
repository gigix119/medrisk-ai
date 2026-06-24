from __future__ import annotations

import numpy as np
import torch

from medrisk_ml.explainability.gradcam import GradCAM
from medrisk_ml.models.baseline_cnn import BaselineCNN, BaselineCNNConfig
from medrisk_ml.models.factory import get_target_layer

IMAGE_SIZE = 64


def test_heatmap_shape_matches_input() -> None:
    model = BaselineCNN(BaselineCNNConfig())
    model.eval()
    target_layer = get_target_layer(model, "baseline_cnn")
    input_tensor = torch.randn(1, 3, IMAGE_SIZE, IMAGE_SIZE)
    with GradCAM(model, target_layer) as cam:
        heatmap = cam.generate(input_tensor)
    assert heatmap.shape == (IMAGE_SIZE, IMAGE_SIZE)


def test_heatmap_is_finite_and_normalized() -> None:
    model = BaselineCNN(BaselineCNNConfig())
    model.eval()
    target_layer = get_target_layer(model, "baseline_cnn")
    input_tensor = torch.randn(1, 3, IMAGE_SIZE, IMAGE_SIZE)
    with GradCAM(model, target_layer) as cam:
        heatmap = cam.generate(input_tensor)
    assert np.all(np.isfinite(heatmap))
    assert heatmap.min() >= 0.0
    assert heatmap.max() <= 1.0


def test_negative_target_sign_runs_without_error() -> None:
    model = BaselineCNN(BaselineCNNConfig())
    model.eval()
    target_layer = get_target_layer(model, "baseline_cnn")
    input_tensor = torch.randn(1, 3, IMAGE_SIZE, IMAGE_SIZE)
    with GradCAM(model, target_layer) as cam:
        heatmap = cam.generate(input_tensor, target_sign=-1.0)
    assert np.all(np.isfinite(heatmap))


def test_hooks_are_removed_on_release() -> None:
    model = BaselineCNN(BaselineCNNConfig())
    target_layer = get_target_layer(model, "baseline_cnn")
    cam = GradCAM(model, target_layer)
    assert len(cam._hooks._handles) == 1
    cam.release()
    assert len(cam._hooks._handles) == 0
    # Releasing twice must not raise.
    cam.release()


def test_model_training_mode_is_restored_after_generate() -> None:
    model = BaselineCNN(BaselineCNNConfig())
    model.train()
    target_layer = get_target_layer(model, "baseline_cnn")
    input_tensor = torch.randn(1, 3, IMAGE_SIZE, IMAGE_SIZE)
    with GradCAM(model, target_layer) as cam:
        cam.generate(input_tensor)
    assert model.training is True


def test_rejects_batch_input() -> None:
    model = BaselineCNN(BaselineCNNConfig())
    target_layer = get_target_layer(model, "baseline_cnn")
    input_tensor = torch.randn(4, 3, IMAGE_SIZE, IMAGE_SIZE)
    with GradCAM(model, target_layer) as cam:
        try:
            cam.generate(input_tensor)
        except ValueError:
            return
    raise AssertionError("Expected ValueError for a batch with more than one image")


def test_constant_activation_produces_zero_heatmap_not_a_crash() -> None:
    # A model whose forward output does not depend on the target layer's gradients in a
    # meaningful spatial way still must not crash - zero/uniform gradients are degenerate
    # but valid input.
    model = BaselineCNN(BaselineCNNConfig(dropout=0.0))
    model.eval()
    target_layer = get_target_layer(model, "baseline_cnn")
    input_tensor = torch.zeros(1, 3, IMAGE_SIZE, IMAGE_SIZE)
    with GradCAM(model, target_layer) as cam:
        heatmap = cam.generate(input_tensor)
    assert np.all(np.isfinite(heatmap))
