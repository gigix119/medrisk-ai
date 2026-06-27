# Coverage config for the `ml` CI job (medrisk_ml only - see .github/workflows/ci.yml).
#
# Deliberately separate from pyproject.toml's [tool.coverage.*] (used by the `test` job):
# that config sets `concurrency = ["greenlet"]`, required to trace coverage correctly across
# SQLAlchemy's async-to-sync greenlet switches in app/medrisk_inference. medrisk_ml has no
# async DB code and the `ml` job's environment never installs greenlet, so reusing that config
# here would make coverage.py fail before any test runs (ConfigError: concurrency=greenlet).
[run]
branch = true

[report]
show_missing = true
skip_empty = true
exclude_lines =
    pragma: no cover
    if TYPE_CHECKING:
    raise NotImplementedError
    def __repr__
