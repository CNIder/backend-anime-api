# CI/CD Stage 1: Repository Workflow

## Stable or integration branch
The integration branch for the repository output is Antonio-Caldeira / António-Caldeira. Direct unreviewed commits to that branch should be avoided once the CI/CD workflow is in place.

## Branch naming
Use short branch names that describe the work:
- feature/analytics-tests
- feature/recommendations-tests
- feature/ci-workflow
- fix/recommendations-health

## Pull request rule
Changes should be merged through pull requests. A pull request should explain:
- what changed
- which service or folder is affected
- how the change was checked
- whether deployment is required

## Source paths for this CI/CD phase
- phase_7/analytics/
- phase_7/recommendations/
- phase_7/k8s/
- .github/workflows/

## Future CI/CD events
- push: run fast validation
- pull_request: run CI checks before merge
- merge to the integration branch: build and publish images
- manual workflow: deploy to GKE
