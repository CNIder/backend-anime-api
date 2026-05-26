from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
K8S_DIR = REPO_ROOT / "phase_7" / "k8s"


def load_yaml_documents():
    documents = []

    for path in sorted(K8S_DIR.rglob("*.yaml")):
        with path.open("r", encoding="utf-8") as file:
            for document in yaml.safe_load_all(file):
                if document:
                    document["_source_file"] = str(path.relative_to(REPO_ROOT))
                    documents.append(document)

    return documents


def documents_by_kind(kind):
    return [document for document in load_yaml_documents() if document.get("kind") == kind]


def test_expected_kubernetes_resources_exist():
    kinds = {document.get("kind") for document in load_yaml_documents()}

    assert "Deployment" in kinds
    assert "Service" in kinds


def test_expected_istio_resources_exist_if_istio_files_are_present():
    documents = load_yaml_documents()
    kinds = {document.get("kind") for document in documents}
    source_text = "\n".join(Path(document["_source_file"]).name.lower() for document in documents)

    if "istio" in source_text or "virtualservice" in source_text or "destinationrule" in source_text:
        assert "VirtualService" in kinds or "DestinationRule" in kinds


def test_deployments_have_labels_selectors_and_container_ports():
    deployments = documents_by_kind("Deployment")
    assert deployments, "Expected at least one Deployment manifest"

    for deployment in deployments:
        metadata = deployment.get("metadata", {})
        spec = deployment.get("spec", {})
        selector = spec.get("selector", {}).get("matchLabels", {})
        template = spec.get("template", {})
        template_labels = template.get("metadata", {}).get("labels", {})
        containers = template.get("spec", {}).get("containers", [])

        assert metadata.get("name"), f"{deployment['_source_file']} Deployment needs metadata.name"
        assert selector, f"{deployment['_source_file']} Deployment needs spec.selector.matchLabels"
        assert template_labels, f"{deployment['_source_file']} Deployment needs pod template labels"
        assert selector.items() <= template_labels.items(), (
            f"{deployment['_source_file']} selector labels must match pod template labels"
        )
        assert containers, f"{deployment['_source_file']} Deployment needs at least one container"

        for container in containers:
            assert container.get("name"), f"{deployment['_source_file']} container needs name"
            assert container.get("image"), f"{deployment['_source_file']} container needs image"
            assert container.get("ports"), f"{deployment['_source_file']} container should declare ports"


def test_services_have_selectors_and_ports():
    services = documents_by_kind("Service")
    assert services, "Expected at least one Service manifest"

    for service in services:
        spec = service.get("spec", {})

        assert service.get("metadata", {}).get("name"), f"{service['_source_file']} Service needs metadata.name"
        assert spec.get("selector"), f"{service['_source_file']} Service needs spec.selector"
        assert spec.get("ports"), f"{service['_source_file']} Service needs spec.ports"

        for port in spec["ports"]:
            assert port.get("port"), f"{service['_source_file']} Service port needs port"
            assert port.get("targetPort"), f"{service['_source_file']} Service port needs targetPort"


def test_istio_virtual_services_have_hosts_and_routes():
    virtual_services = documents_by_kind("VirtualService")

    for virtual_service in virtual_services:
        spec = virtual_service.get("spec", {})

        assert virtual_service.get("metadata", {}).get("name")
        assert spec.get("hosts"), f"{virtual_service['_source_file']} VirtualService needs hosts"
        assert spec.get("http") or spec.get("tcp"), (
            f"{virtual_service['_source_file']} VirtualService needs http or tcp routes"
        )


def test_istio_destination_rules_have_host():
    destination_rules = documents_by_kind("DestinationRule")

    for destination_rule in destination_rules:
        spec = destination_rule.get("spec", {})

        assert destination_rule.get("metadata", {}).get("name")
        assert spec.get("host"), f"{destination_rule['_source_file']} DestinationRule needs spec.host"
