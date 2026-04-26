# Deploy Review & Forum Services - Fase 5

## Serviços

* Review Service → porta interna: 5001
* Forum Service → porta interna: 5002

---

## Pré-requisitos

* Cluster Kubernetes (GKE) ativo
* `kubectl` configurado:

No terminal:
kubectl get nodes

* Imagens Docker já publicadas no Artifact Registry:

  * `forum-service`
  * `review-service`

---

## Namespace

Todos os recursos são criados no namespace:

artur-matos

## Deploy

kubectl apply -f namespace.yaml
kubectl apply -f review-deployment.yaml
kubectl apply -f forum-deployment.yaml
kubectl apply -f hpa.yaml
# Opcional (exposição externa)
kubectl apply -f ingress.yaml

---

## Verificar estado

kubectl get pods -n artur-matos
kubectl get svc -n artur-matos
kubectl get hpa -n artur-matos
kubectl get ingress -n artur-matos

Para mais detalhe:

kubectl describe pod <pod-name> -n artur-matos
kubectl logs <pod-name> -n artur-matos

---

## Testes

### Teste interno (dentro do cluster)

kubectl run test -n artur-matos --image=busybox -it --rm -- sh

Dentro do container:

wget -qO- http://review-service
wget -qO- http://forum-service

---

## Teste externo (Ingress)

kubectl get ingress -n artur-matos

Depois:

curl http://<EXTERNAL-IP>/reviews
curl http://<EXTERNAL-IP>/forum #ainda tenho de alterar o ingress.yaml

---

## Rollback


kubectl rollout undo deployment/review-service -n artur-matos
kubectl rollout undo deployment/forum-service -n artur-matos


---

## Autoscaling

Os serviços utilizam HPA baseado em CPU:

* min replicas: 2
* max replicas: 10
* target CPU: 70%

Ver estado:

kubectl get hpa -n artur-matos

---

## Notas

* Apenas os serviços necessários são expostos via Ingress
* Comunicação interna feita via `ClusterIP`
* Dados em memória (não persistentes)
