# Phase 7 Deployment Instructions

Deployment steps for the Anime API cloud implementation of phase 7 by student António Caldeira, 47904.

This deploys:

- Analytics FastAPI service
- Recommendations FastAPI service
- BigQuery-backed analytics and user choice scoring
- Ranked recommendations with `user_choice_score`
- Recommendation index progress endpoint/page
- GKE Deployments, Services, HPA, ConfigMap, Workload Identity
- Istio Gateway, VirtualServices, strict mTLS, AuthorizationPolicy
- Optional observability add-ons: Kiali, Prometheus, Grafana

Side note: Restarting the recommendations pod during Istio sidecar injection causes the recommendation embedding index to build twice. To avoid this, skip
pre-Istio recommendations validation. Validate only analytics before installing Istio, then install Istio, restart the pods, and validate recommendations
through the Istio ingress gateway using /recommendations/index-progress-page.

## 1. Set Variables

Run from any terminal:

```bash
WORKSPACE_DIR=/mnt/c/Users/tntma/Work/Cloud_Computing
PHASE7_DIR=${WORKSPACE_DIR}/backend-anime-api-Project1/phase_7
PROJECT_ID=temp-488519
REGION=europe-west1
ZONE=europe-west1-b
CLUSTER_NAME=anime-cluster
NODE_POOL=default-pool
REPO=anime-repo
NAMESPACE=anime-api
KSA_NAME=anime-api-sa
GSA_NAME=anime-api-gsa
GSA_EMAIL=${GSA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com
ANALYTICS_TAG=phase7-user-choice
RECOMMENDATIONS_TAG=phase7-user-choice-ranked-progress

cd ${PHASE7_DIR}
```

## 2. Enable APIs

```bash
gcloud config set project ${PROJECT_ID}

gcloud services enable \
  container.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  bigquery.googleapis.com \
  iamcredentials.googleapis.com \
  --project=${PROJECT_ID}
```

## 3. Create GKE Cluster

```bash
gcloud container clusters create ${CLUSTER_NAME} \
  --zone=${ZONE} \
  --machine-type=e2-standard-2 \
  --num-nodes=2 \
  --scopes=cloud-platform \
  --workload-pool=${PROJECT_ID}.svc.id.goog \
  --project=${PROJECT_ID}

gcloud container clusters get-credentials ${CLUSTER_NAME} \
  --zone=${ZONE} \
  --project=${PROJECT_ID}

kubectl get nodes
```

If the cluster already exists, enable Workload Identity before continuing:

```bash
gcloud container clusters update ${CLUSTER_NAME} \
  --zone=${ZONE} \
  --workload-pool=${PROJECT_ID}.svc.id.goog \
  --project=${PROJECT_ID}

gcloud container node-pools update ${NODE_POOL} \
  --cluster=${CLUSTER_NAME} \
  --zone=${ZONE} \
  --workload-metadata=GKE_METADATA \
  --project=${PROJECT_ID}
```

If the existing node pool lacks `cloud-platform` scope, create a new pool:

```bash
gcloud container node-pools create wi-pool \
  --cluster=${CLUSTER_NAME} \
  --zone=${ZONE} \
  --machine-type=e2-standard-2 \
  --num-nodes=2 \
  --scopes=cloud-platform \
  --workload-metadata=GKE_METADATA \
  --project=${PROJECT_ID}
```

## 4. Configure BigQuery Access

```bash
gcloud iam service-accounts create ${GSA_NAME} \
  --project=${PROJECT_ID}

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${GSA_EMAIL}" \
  --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${GSA_EMAIL}" \
  --role="roles/bigquery.dataViewer"
```

## 5. Build and Push Images

Uses Cloud Build, so local Docker is not required.

```bash
cd ${PHASE7_DIR}/analytics
gcloud builds submit . \
  --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/analytics-bq:${ANALYTICS_TAG} \
  --project=${PROJECT_ID}

cd ${PHASE7_DIR}/recommendations
gcloud builds submit . \
  --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/recommendations-bq:${RECOMMENDATIONS_TAG} \
  --project=${PROJECT_ID}
```

## 6. Deploy Kubernetes Resources

```bash
cd ${PHASE7_DIR}

kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/base/serviceaccount.yaml
kubectl apply -f k8s/base/configmap.yaml

gcloud iam service-accounts add-iam-policy-binding ${GSA_EMAIL} \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:${PROJECT_ID}.svc.id.goog[${NAMESPACE}/${KSA_NAME}]"

kubectl annotate serviceaccount ${KSA_NAME} \
  -n ${NAMESPACE} \
  iam.gke.io/gcp-service-account=${GSA_EMAIL} \
  --overwrite

kubectl apply -f k8s/analytics/deployment.yaml
kubectl apply -f k8s/analytics/service.yaml
kubectl apply -f k8s/analytics/hpa.yaml

kubectl apply -f k8s/recommendations/deployment.yaml
kubectl apply -f k8s/recommendations/service.yaml
kubectl apply -f k8s/recommendations/hpa.yaml
```

Wait for rollout:

```bash
kubectl rollout status deployment/analytics -n ${NAMESPACE}
kubectl rollout status deployment/recommendations -n ${NAMESPACE}
kubectl get pods -n ${NAMESPACE}
```

## 7. Validate Before Istio

```bash
kubectl port-forward -n ${NAMESPACE} service/analytics 18081:80
```

In another terminal:

```bash
curl http://127.0.0.1:18081/health
curl -X POST http://127.0.0.1:18081/analytics/anime/user-choice-score \
  -H "Content-Type: application/json" \
  -d '{"anime_name":"Naruto"}'
```

Recommendations:

```bash
kubectl port-forward -n ${NAMESPACE} service/recommendations 18082:80
```

In another terminal:

```bash
curl http://127.0.0.1:18082/recommendations/index-status
curl -X POST http://127.0.0.1:18082/recommendations \
  -H "Content-Type: application/json" \
  -d '{"anime_name":"Naruto"}'
```

Progress page:

```text
http://127.0.0.1:18082/recommendations/index-progress-page
```

## 8. Install Istio

```bash
cd ${WORKSPACE_DIR}
curl -L https://istio.io/downloadIstio | sh -

ISTIO_DIR=$(ls -td ${WORKSPACE_DIR}/istio-* | head -1)
cd ${ISTIO_DIR}
export PATH=${ISTIO_DIR}/bin:$PATH

istioctl install --set profile=default -y
kubectl get pods -n istio-system
```

Enable sidecars:

```bash
kubectl label namespace ${NAMESPACE} istio-injection=enabled --overwrite
kubectl rollout restart deployment/analytics -n ${NAMESPACE}
kubectl rollout restart deployment/recommendations -n ${NAMESPACE}

kubectl rollout status deployment/analytics -n ${NAMESPACE}
kubectl rollout status deployment/recommendations -n ${NAMESPACE}
kubectl get pods -n ${NAMESPACE}
```

Expected pods: `2/2` ready.

## 9. Apply Istio Policies

Confirm ingress gateway service account:

```bash
INGRESS_GATEWAY_SA=$(kubectl get deployment istio-ingressgateway -n istio-system \
  -o jsonpath='{.spec.template.spec.serviceAccountName}')
echo ${INGRESS_GATEWAY_SA}
```

If it is not `istio-ingressgateway-service-account`, update `k8s/istio/authorization-policies.yaml`.

Apply Istio resources:

```bash
cd ${PHASE7_DIR}

kubectl apply -f k8s/istio/gateway.yaml
kubectl apply -f k8s/istio/virtualservice-public.yaml
kubectl apply -f k8s/istio/virtualservice-internal.yaml
kubectl apply -f k8s/istio/destinationrules.yaml
kubectl apply -f k8s/istio/mtls.yaml
kubectl apply -f k8s/istio/authorization-policies.yaml

istioctl analyze -n ${NAMESPACE}
istioctl proxy-status
```

## 10. Test Through Istio

```bash
ISTIO_IP=$(kubectl get svc istio-ingressgateway -n istio-system \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

curl http://${ISTIO_IP}/analytics/anime
curl http://${ISTIO_IP}/recommendations/index-status
curl -X POST http://${ISTIO_IP}/recommendations \
  -H "Content-Type: application/json" \
  -d '{"anime_name":"Naruto"}'
```

Expected recommendations output includes:

- `input_anime`
- ranked `recommendations`
- `user_choice_score`
- `genres`
- `studios`

## 11. Observability

```bash
cd ${ISTIO_DIR}
kubectl apply -f samples/addons

kubectl rollout status deployment/kiali -n istio-system
kubectl rollout status deployment/prometheus -n istio-system
kubectl rollout status deployment/grafana -n istio-system
```

Generate traffic:

```bash
for i in $(seq 1 20); do
  curl -s -X POST http://${ISTIO_IP}/recommendations \
    -H "Content-Type: application/json" \
    -d '{"anime_name":"Naruto"}' > /dev/null
done
```

Open dashboards:

```bash
istioctl dashboard kiali
istioctl dashboard grafana
```

## 12. Final Checks

```bash
kubectl get pods -n ${NAMESPACE}
kubectl get hpa -n ${NAMESPACE}
istioctl analyze -n ${NAMESPACE}
istioctl proxy-status
```

Final expected state:

- analytics and recommendations pods are `2/2`
- Istio ingress gateway exposes the API
- recommendations calls analytics internally
- strict mTLS is enabled
- AuthorizationPolicy is applied
- Kiali/Grafana show service traffic

## 13. Cleanup

To avoid resource consumption when not using cluster:

```bash
gcloud container clusters delete ${CLUSTER_NAME} \
  --zone=${ZONE} \
  --project=${PROJECT_ID}
```
