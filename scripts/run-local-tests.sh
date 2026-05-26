#!/usr/bin/env bash
set -euo pipefail

export RECOMMENDATIONS_MODE=smoke
python -m compileall phase_7/analytics phase_7/recommendations
python -m pytest
