"""MedRisk AI Phase 3 inference runtime: loads a verified Phase 2 model bundle and serves
real-time histopathology predictions.

Educational/research code only - not a medical device. This package must never import
training-only dependencies (pandas, scikit-learn, matplotlib, tensorboard, h5py) so the
inference Docker image stays lean - see tests/inference/test_import_isolation.py.
"""

__version__ = "0.1.0"
