# Phase 5 Deployment Instructions

## Overview

This deployment package contains the cloud deployment material for group 12 António Caldeira's Phase 5 contribution to the anime API project.

The deployed services are:

- **Analytics service**
- **Recommendations service**

Both services are containerized and deployed to **Google Kubernetes Engine (GKE)**, using **BigQuery** as the cloud data source.

The deployment includes:

- Kubernetes namespace
- Kubernetes service account
- Deployments and Services for both microservices
- Ingress for external access through a cloud load balancer
- Horizontal Pod Autoscalers (HPA)
- resource requests and limits
- liveness, readiness, and startup probes

---

## Folder structure

```text
phase_5/
├── analytics/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── recommendations/
│   ├── app.py
│   ├── Dockerfile
│   └── requirements.txt
├── k8s/
│   ├── base/
│   │   ├── namespace.yaml
│   │   ├── serviceaccount.yaml
│   │   └── ingress.yaml
│   ├── analytics/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── hpa.yaml
│   └── recommendations/
│       ├── deployment.yaml
│       ├── service.yaml
│       └── hpa.yaml
└── instructions.md
```

---

## Prerequisites

The following tools/services are required:

- Google Cloud project
- GKE API enabled
- BigQuery API enabled
- IAM Credentials API enabled
- Artifact Registry API enabled
- `gcloud`
- `kubectl`
- `docker`

The GCP project used in this deployment is:

```text
temp-488519
```

The GKE zone used is:

```text
europe-west1-b
```

The Artifact Registry repository used is:

```text
anime-repo
```

The BigQuery dataset and table used are:

```text
anime_intel_dataset
anime_intel
```

---

## 1. Build and push container images

### Analytics

From the `analytics/` folder:

```bash
docker build -t analytics-bq .
docker tag analytics-bq europe-west1-docker.pkg.dev/temp-488519/anime-repo/analytics-bq:phase5
docker push europe-west1-docker.pkg.dev/temp-488519/anime-repo/analytics-bq:phase5
```

### Recommendations

From the `recommendations/` folder:

```bash
docker build -t recommendations-bq .
docker tag recommendations-bq europe-west1-docker.pkg.dev/temp-488519/anime-repo/recommendations-bq:phase5-v3
docker push europe-west1-docker.pkg.dev/temp-488519/anime-repo/recommendations-bq:phase5-v3
```

---

## 2. Create the GKE cluster

Create the cluster:

```bash
gcloud container clusters create anime-cluster --zone=europe-west1-b --machine-type=e2-standard-2 --num-nodes=2
```

Get cluster credentials:

```bash
gcloud container clusters get-credentials anime-cluster --zone=europe-west1-b
kubectl get nodes
```

---

## 3. Configure Workload Identity for BigQuery access

Set variables:

```bash
PROJECT_ID=temp-488519
CLUSTER_NAME=anime-cluster
CLUSTER_ZONE=europe-west1-b
NODE_POOL=default-pool
NAMESPACE=anime-api
KSA_NAME=anime-api-sa
GSA_NAME=anime-api-gsa
GSA_EMAIL=${GSA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com
```

Enable Workload Identity on the cluster:

```bash
gcloud container clusters update $CLUSTER_NAME \
  --zone=$CLUSTER_ZONE \
  --workload-pool=${PROJECT_ID}.svc.id.goog
```

Update the node pool to use the GKE metadata server:

```bash
gcloud container node-pools update $NODE_POOL \
  --cluster=$CLUSTER_NAME \
  --zone=$CLUSTER_ZONE \
  --workload-metadata=GKE_METADATA
```

Enable IAM Credentials API:

```bash
gcloud services enable iamcredentials.googleapis.com --project=$PROJECT_ID
```

Create the Google service account if it does not already exist:

```bash
gcloud iam service-accounts create $GSA_NAME --project=$PROJECT_ID
```

Grant BigQuery permissions:

```bash
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${GSA_EMAIL}" \
  --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${GSA_EMAIL}" \
  --role="roles/bigquery.dataViewer"
```

Allow the Kubernetes service account to impersonate the Google service account:

```bash
gcloud iam service-accounts add-iam-policy-binding $GSA_EMAIL \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:${PROJECT_ID}.svc.id.goog[${NAMESPACE}/${KSA_NAME}]"
```

---

## 4. Apply Kubernetes manifests

Go to the `k8s/` folder and apply the manifests.

### Base resources

```bash
kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/base/serviceaccount.yaml
kubectl annotate serviceaccount anime-api-sa \
  -n anime-api \
  iam.gke.io/gcp-service-account=anime-api-gsa@temp-488519.iam.gserviceaccount.com \
  --overwrite
```

### Analytics resources

```bash
kubectl apply -f k8s/analytics/deployment.yaml
kubectl apply -f k8s/analytics/service.yaml
kubectl apply -f k8s/analytics/hpa.yaml
```

### Recommendations resources

```bash
kubectl apply -f k8s/recommendations/deployment.yaml
kubectl apply -f k8s/recommendations/service.yaml
kubectl apply -f k8s/recommendations/hpa.yaml
```

### Ingress

```bash
kubectl apply -f k8s/base/ingress.yaml
```

---

## 5. Verify the deployment

Check all main resources:

```bash
kubectl get deployments -n anime-api
kubectl get pods -n anime-api
kubectl get svc -n anime-api
kubectl get ingress -n anime-api
kubectl get hpa -n anime-api
```

Expected result:

- `analytics` deployment available
- `recommendations` deployment available
- both pods `1/1 Running`
- ingress has an external IP
- HPA objects exist for both services

---

## 6. External access and testing

Get the external IP:

```bash
kubectl get ingress -n anime-api
```

Example external IP used during testing:

```text
34.117.101.123
```

### Test analytics externally

```bash
curl http://34.117.101.123/analytics/anime
```

### Test recommendations externally

```bash
curl -X POST http://34.117.101.123/recommendations \
  -H "Content-Type: application/json" \
  -d '{"anime_name":"Naruto"}'
```

---

## 7. Internal/local testing with port-forward

### Analytics

```bash
kubectl port-forward -n anime-api service/analytics 18081:80
```

In another terminal:

```bash
curl http://127.0.0.1:18081/health
curl http://127.0.0.1:18081/analytics/anime
```

### Recommendations

```bash
kubectl port-forward -n anime-api service/recommendations 18082:80
```

In another terminal:

```bash
curl http://127.0.0.1:18082/health
curl -X POST http://127.0.0.1:18082/recommendations \
  -H "Content-Type: application/json" \
  -d '{"anime_name":"Naruto"}'
```

---

## 8. Notes on recommendations service

The recommendations service is much heavier than the analytics service because it:

- loads a sentence-transformer model
- queries BigQuery
- builds an in-memory embedding index

To make the service cloud-friendly, the embedding index is built **in the background** after startup. This allows:

- the pod to pass health checks sooner
- the service to become healthy without blocking startup
- recommendation requests to return a temporary `503` response while the index is still loading

Health check example while loading:

```json
{
  "status": "ok",
  "catalog_size": 0,
  "index_ready": false,
  "index_loading": true,
  "index_error": null
}
```

Health check example after loading finishes:

```json
{
  "status": "ok",
  "catalog_size": 24905,
  "index_ready": true,
  "index_loading": false,
  "index_error": null
}
```

---

## 9. Rolling updates and rollback

### Rolling updates

Kubernetes Deployments are used to manage service updates.

Useful commands:

```bash
kubectl rollout status deployment analytics -n anime-api
kubectl rollout status deployment recommendations -n anime-api
```

### Rollout history

```bash
kubectl rollout history deployment analytics -n anime-api
kubectl rollout history deployment recommendations -n anime-api
```

### Rollback

Rollback to the previous revision:

```bash
kubectl rollout undo deployment analytics -n anime-api
kubectl rollout undo deployment recommendations -n anime-api
```

Rollback to a specific revision:

```bash
kubectl rollout undo deployment analytics --to-revision=2 -n anime-api
```

---

## 10. Resource utilization and autoscaling

Both services include:

- CPU/memory requests and limits
- HPA definitions based on CPU utilization

Check HPA status:

```bash
kubectl get hpa -n anime-api
```

This deployment was tuned to be as cost-effective as possible while still allowing both services to run successfully on the selected GKE cluster.

---

## 12. Deliverable notes

This deployment package contains only the files required to:

- build the service images
- configure cloud authentication
- deploy to GKE
- expose the services
- test the deployment

A Git tag/release named **Phase 5** should also be created in the group member branch after deployment is prepared and tested.