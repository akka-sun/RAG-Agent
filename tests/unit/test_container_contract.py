import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]


def test_compose_does_not_persist_or_shadow_the_image_virtualenv() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    for service_name in ("api", "worker"):
        volumes = compose["services"][service_name]["volumes"]
        assert all(not volume.endswith(":/app/.venv") for volume in volumes)

    assert "api_venv" not in compose["volumes"]


def test_dockerfile_builds_locked_virtualenv_outside_bind_mount() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "UV_PROJECT_ENVIRONMENT=/opt/venv" in dockerfile
    assert "COPY pyproject.toml uv.lock ./" in dockerfile
    assert "uv sync --locked --no-install-project --group dev --group test" in dockerfile


def test_pyright_uses_the_dockerfile_virtualenv() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    expected = re.search(r"UV_PROJECT_ENVIRONMENT=(?P<path>\S+)", dockerfile)

    assert expected is not None
    expected_path = Path(expected.group("path"))

    assert pyproject["tool"]["pyright"]["venvPath"] == str(expected_path.parent)
    assert pyproject["tool"]["pyright"]["venv"] == expected_path.name


def test_worker_healthcheck_allows_arq_startup_overhead() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    healthcheck = compose["services"]["worker"]["healthcheck"]

    assert healthcheck["timeout"] == "20s"
    assert healthcheck["interval"] == "30s"
