from __future__ import annotations

import numpy as np
import pytest
import torch

from medrisk_ml.data.synthetic import SyntheticHistopathologyDataset

IMAGE_SIZE = 64


def test_same_seed_produces_identical_images() -> None:
    first = SyntheticHistopathologyDataset("train", num_samples=8, seed=42, image_size=IMAGE_SIZE)
    second = SyntheticHistopathologyDataset("train", num_samples=8, seed=42, image_size=IMAGE_SIZE)
    image_a, label_a, id_a = first[3]
    image_b, label_b, id_b = second[3]
    assert torch.equal(image_a, image_b)
    assert label_a == label_b
    assert id_a == id_b


def test_different_seed_produces_different_images() -> None:
    first = SyntheticHistopathologyDataset("train", num_samples=8, seed=1, image_size=IMAGE_SIZE)
    second = SyntheticHistopathologyDataset("train", num_samples=8, seed=2, image_size=IMAGE_SIZE)
    image_a, _, _ = first[0]
    image_b, _, _ = second[0]
    assert not torch.equal(image_a, image_b)


def test_correct_shape_and_dtype() -> None:
    dataset = SyntheticHistopathologyDataset("train", num_samples=4, seed=1, image_size=IMAGE_SIZE)
    image, label, sample_id = dataset[0]
    assert image.shape == (3, IMAGE_SIZE, IMAGE_SIZE)
    assert image.dtype == torch.float32
    assert isinstance(label, int)
    assert isinstance(sample_id, str)


def test_both_classes_present() -> None:
    dataset = SyntheticHistopathologyDataset("train", num_samples=16, seed=1, image_size=IMAGE_SIZE)
    labels = {dataset[i][1] for i in range(len(dataset))}
    assert labels == {0, 1}


def test_labels_are_balanced() -> None:
    dataset = SyntheticHistopathologyDataset("train", num_samples=20, seed=1, image_size=IMAGE_SIZE)
    labels = np.array([dataset[i][1] for i in range(len(dataset))])
    assert int(labels.sum()) == 10


def test_splits_remain_distinct() -> None:
    train = SyntheticHistopathologyDataset("train", num_samples=4, seed=99, image_size=IMAGE_SIZE)
    val = SyntheticHistopathologyDataset("val", num_samples=4, seed=99, image_size=IMAGE_SIZE)
    test = SyntheticHistopathologyDataset("test", num_samples=4, seed=99, image_size=IMAGE_SIZE)

    train_image, _, train_id = train[0]
    val_image, _, val_id = val[0]
    test_image, _, test_id = test[0]

    assert train_id != val_id != test_id
    assert not torch.equal(train_image, val_image)
    assert not torch.equal(val_image, test_image)


def test_index_out_of_range_raises() -> None:
    dataset = SyntheticHistopathologyDataset("train", num_samples=4, seed=1, image_size=IMAGE_SIZE)
    with pytest.raises(IndexError):
        dataset[100]
