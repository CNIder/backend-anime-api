#!/usr/bin/env bash
set -euo pipefail

IMAGE_PREFIX="${IMAGE_PREFIX:-phase7}"
IMAGE_TAG="${IMAGE_TAG:-ci}"

ANALYTICS_IMAGE="${IMAGE_PREFIX}-analytics:${IMAGE_TAG}"

echo "Building ${ANALYTICS_IMAGE}"
docker build -t "${ANALYTICS_IMAGE}" phase_7/analytics

echo "Skipping full recommendations image build locally."
echo "Reason: the recommendations image installs ML dependencies and is too heavy for local CI validation."
echo "The recommendations service is validated by pytest in smoke mode."
