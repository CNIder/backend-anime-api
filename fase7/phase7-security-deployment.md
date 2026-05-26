# Phase 7 – Deployment Guide (RBAC + Secrets)

## 1. Create Namespace

Create a file named `namespace.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: artur-matos
```

Apply:

```bash
kubectl apply -f namespace.yaml
```

---

# 2. Create Kubernetes Secret

Create the directory:

```bash
mkdir -p secrets
```

Create the file `secrets/app-secret.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secret
  namespace: artur-matos
type: Opaque
stringData:
  API_KEY: "my-secret-api-key"
```

Apply:

```bash
kubectl apply -f secrets/app-secret.yaml
```

Verify:

```bash
kubectl get secrets -n artur-matos
```

---

# 3. Configure RBAC

Create the directory:

```bash
mkdir -p rbac
```

---

## 3.1 ServiceAccount

Create `rbac/serviceaccount.yaml`:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-sa
  namespace: artur-matos
```

Apply:

```bash
kubectl apply -f rbac/serviceaccount.yaml
```

---

## 3.2 Role

Create `rbac/role.yaml`:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: artur-matos
  name: secret-reader
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get"]
```

Apply:

```bash
kubectl apply -f rbac/role.yaml
```

---

## 3.3 RoleBinding

Create `rbac/rolebinding.yaml`:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: secret-reader-binding
  namespace: artur-matos
subjects:
- kind: ServiceAccount
  name: app-sa
  namespace: artur-matos
roleRef:
  kind: Role
  name: secret-reader
  apiGroup: rbac.authorization.k8s.io
```

Apply:

```bash
kubectl apply -f rbac/rolebinding.yaml
```

---

# 4. Configure Deployments

## 4.1 Add ServiceAccount

Inside the deployment YAML:

```yaml
spec:
  serviceAccountName: app-sa
```

---

## 4.2 Mount Secret Volume

Inside the container definition:

```yaml
volumeMounts:
- name: secret-volume
  mountPath: /etc/secrets
  readOnly: true
```

---

## 4.3 Define Secret Volume

Inside the pod spec:

```yaml
volumes:
- name: secret-volume
  secret:
    secretName: app-secret
```

---

# 5. Deploy Services

Apply forum-service:

```bash
kubectl apply -f deployments/forum-deployment.yaml
```

Apply review-service:

```bash
kubectl apply -f deployments/review-deployment.yaml
```

---

# 6. Verify Pods

Check pod status:

```bash
kubectl get pods -n artur-matos
```

Pods should be in:

```text
Running
```

---

# 7. Verify Secret Access

Enter a pod:

```bash
kubectl exec -it <POD_NAME> -n artur-matos -- sh
```

List mounted secrets:

```bash
ls /etc/secrets
```

Read secret content:

```bash
cat /etc/secrets/API_KEY
```

Expected output:

```text
my-secret-api-key
```

---

# 8. Security Features Implemented

The deployment implements:

* Kubernetes Secrets
* RBAC (Role-Based Access Control)
* ServiceAccounts
* Controlled access to sensitive data
* Namespace isolation

This security model follows Kubernetes cloud-native best practices.
