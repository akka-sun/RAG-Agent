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
