from pathlib import Path
import yaml


def test_phase7_yaml_files_parse():
    repo_root = Path(__file__).resolve().parents[3]
    yaml_files = sorted((repo_root / "phase_7" / "k8s").rglob("*.yaml"))
    assert yaml_files, "Expected phase_7/k8s YAML files"

    for yaml_file in yaml_files:
        with yaml_file.open("r", encoding="utf-8") as handle:
            documents = list(yaml.safe_load_all(handle))
        assert documents, f"{yaml_file} did not contain YAML documents"
