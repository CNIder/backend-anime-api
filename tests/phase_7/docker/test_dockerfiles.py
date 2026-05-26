from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SERVICES = ["analytics", "recommendations"]


def dockerfile_path(service):
    return REPO_ROOT / "phase_7" / service / "Dockerfile"


def dockerfile_text(service):
    return dockerfile_path(service).read_text(encoding="utf-8").lower()


def test_each_phase7_service_has_dockerfile():
    for service in SERVICES:
        path = dockerfile_path(service)
        assert path.exists(), f"Expected Dockerfile for {service}: {path}"


def test_dockerfiles_use_python_base_image():
    for service in SERVICES:
        text = dockerfile_text(service)
        assert "from python:" in text, f"{service} Dockerfile should use a Python base image"


def test_dockerfiles_copy_and_install_requirements():
    for service in SERVICES:
        text = dockerfile_text(service)

        assert "requirements.txt" in text, f"{service} Dockerfile should copy requirements.txt"
        assert "pip install" in text, f"{service} Dockerfile should install Python dependencies"


def test_dockerfiles_copy_application_code():
    for service in SERVICES:
        text = dockerfile_text(service)

        assert "copy" in text, f"{service} Dockerfile should copy application code"
        assert "app.py" in text or "copy . ." in text, (
            f"{service} Dockerfile should copy app.py or the service directory"
        )


def test_dockerfiles_expose_or_run_expected_service_port():
    expected_ports = {
        "analytics": "8080",
        "recommendations": "8080",
    }

    for service, port in expected_ports.items():
        text = dockerfile_text(service)
        assert port in text, f"{service} Dockerfile should reference port {port}"


def test_dockerfiles_define_start_command():
    for service in SERVICES:
        text = dockerfile_text(service)

        assert "cmd" in text or "entrypoint" in text, (
            f"{service} Dockerfile should define CMD or ENTRYPOINT"
        )
        assert "uvicorn" in text, f"{service} Dockerfile should start the FastAPI app with uvicorn"
