#!/usr/bin/env bash
# v146b_gke_setup.sh — One-shot GKE test cluster setup for Mode E validation
#
# Reproduces the v1.4.6-B environment from scratch:
#   - GKE 1.35 cluster (2 nodes, default cgroup v2)
#   - GCE SA IAM: 5 roles (container.{developer,clusterAdmin} + AR.{r,w} + storage)
#   - GKE RBAC bootstrap: ClusterRoleBindings (email + numeric UID forms)
#   - kubectl context configured
#
# Idempotent — safe to re-run. Skips steps that are already done.
#
# Usage:
#   bash scripts/v146b_gke_setup.sh
#
# Prereqs:
#   - Run from a host with gcloud + kubectl + curl + jq installed
#   - User running this must have roles/owner on PROJECT (for RBAC bootstrap)
#   - GCE bastion instance must already exist (this script doesn't create it)
#
# Cleanup when done:
#   gcloud container clusters delete $CLUSTER --region=$REGION --project=$PROJECT --quiet

set -euo pipefail

# ============================================================================
# Configuration — edit these for your environment
# ============================================================================
PROJECT="${PROJECT:-claude-ttft-test}"
CLUSTER="${CLUSTER:-blockchain-bench-test}"
REGION="${REGION:-us-central1}"
SA_NAME="${SA_NAME:-gemini-cli-bot}"
SA_EMAIL="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
AR_REPO="${AR_REPO:-blockchain-bench}"
AR_LOCATION="${AR_LOCATION:-us-central1}"
NAMESPACE="${NAMESPACE:-blockchain-bench}"

# ============================================================================
# Helpers
# ============================================================================
log() { echo "[$(date +%H:%M:%S)] $*" >&2; }
ok()  { echo "  ✓ $*" >&2; }
warn(){ echo "  ⚠ $*" >&2; }

# ============================================================================
# 1. IAM — grant 5 roles to GCE SA (idempotent — gcloud no-ops if already bound)
# ============================================================================
log "Step 1/5: IAM role bindings on $SA_EMAIL"
ROLES=(
  "roles/container.developer"       # kubectl get/list/watch
  "roles/container.clusterAdmin"    # kubectl create CRB (still needs K5 bootstrap)
  "roles/artifactregistry.reader"   # docker pull (also bind on default Compute SA for GKE nodes!)
  "roles/artifactregistry.writer"   # docker push
  "roles/storage.admin"             # AR backing bucket (sometimes needed)
)
for role in "${ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="$role" \
    --condition=None \
    --quiet 2>&1 | tail -1
  ok "bound $role"
done

# Also bind AR.reader on default Compute SA (GKE nodes pull images using it)
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
DEFAULT_COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:$DEFAULT_COMPUTE_SA" \
  --role="roles/artifactregistry.reader" \
  --condition=None \
  --quiet 2>&1 | tail -1
ok "bound AR.reader on default Compute SA ($DEFAULT_COMPUTE_SA)"

# Invalidate token caches — IAM grants are cached 60s on GCE side
rm -f ~/.config/gcloud/access_tokens.db 2>/dev/null || true
ok "flushed local gcloud token cache"

# ============================================================================
# 2. AR repository (idempotent)
# ============================================================================
log "Step 2/5: Artifact Registry repository"
if gcloud artifacts repositories describe "$AR_REPO" \
     --location="$AR_LOCATION" --project="$PROJECT" &>/dev/null; then
  ok "AR repo $AR_REPO already exists"
else
  gcloud artifacts repositories create "$AR_REPO" \
    --repository-format=docker \
    --location="$AR_LOCATION" \
    --project="$PROJECT" \
    --description="blockchain-node-benchmark collector images"
  ok "created AR repo $AR_REPO"
fi

# ============================================================================
# 3. GKE cluster (idempotent — skip if exists)
# ============================================================================
log "Step 3/5: GKE cluster"
if gcloud container clusters describe "$CLUSTER" \
     --region="$REGION" --project="$PROJECT" &>/dev/null; then
  ok "cluster $CLUSTER already exists, skipping create"
else
  log "  creating cluster (5-10 min)..."
  gcloud container clusters create "$CLUSTER" \
    --region="$REGION" \
    --project="$PROJECT" \
    --num-nodes=1 \
    --machine-type=e2-standard-2 \
    --release-channel=regular \
    --enable-ip-alias \
    --workload-pool="${PROJECT}.svc.id.goog" \
    --quiet
  ok "created cluster $CLUSTER"
fi

# ============================================================================
# 4. kubectl context
# ============================================================================
log "Step 4/5: kubectl context"
gcloud container clusters get-credentials "$CLUSTER" \
  --region="$REGION" --project="$PROJECT"
ok "kubectl context set"

# ============================================================================
# 5. RBAC bootstrap (K5 chicken-and-egg fix)
# ============================================================================
log "Step 5/5: RBAC bootstrap — ClusterRoleBindings for SA (email + numeric UID)"

# Get SA numeric UID — GKE RBAC subject uses UID, NOT email, for some operations
SA_UID=$(gcloud iam service-accounts describe "$SA_EMAIL" \
           --project="$PROJECT" --format='value(uniqueId)')
ok "SA numeric UID: $SA_UID"

# Get cluster endpoint + CA cert for REST POST (we bypass kubectl because the
# SA doesn't have RBAC yet — this is the chicken-egg fix)
MASTER=$(gcloud container clusters describe "$CLUSTER" \
           --region="$REGION" --project="$PROJECT" --format='value(endpoint)')
gcloud container clusters describe "$CLUSTER" \
  --region="$REGION" --project="$PROJECT" \
  --format='value(masterAuth.clusterCaCertificate)' \
  | base64 -d > /tmp/gke_ca.crt
ok "master endpoint + CA cert fetched"

# Use OWNER ADC token (the user running this script) to bootstrap CRBs
# (Not the SA token — the SA can't grant itself RBAC. This is the whole point.)
OWNER_TOKEN=$(gcloud auth print-access-token)

post_crb() {
  local crb_name="$1"
  local subject_name="$2"
  local crb_json
  crb_json=$(cat <<EOF
{
  "apiVersion": "rbac.authorization.k8s.io/v1",
  "kind": "ClusterRoleBinding",
  "metadata": {"name": "$crb_name"},
  "roleRef": {"apiGroup": "rbac.authorization.k8s.io",
              "kind": "ClusterRole", "name": "cluster-admin"},
  "subjects": [{"kind": "User", "apiGroup": "rbac.authorization.k8s.io",
                "name": "$subject_name"}]
}
EOF
)
  local resp
  resp=$(curl -sS -X POST \
    "https://${MASTER}/apis/rbac.authorization.k8s.io/v1/clusterrolebindings" \
    --cacert /tmp/gke_ca.crt \
    -H "Authorization: Bearer ${OWNER_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$crb_json")
  if echo "$resp" | grep -q '"status":"Failure"'; then
    if echo "$resp" | grep -q '"reason":"AlreadyExists"'; then
      ok "$crb_name already exists"
    else
      warn "$crb_name CREATE FAILED:"
      echo "$resp" | jq . 2>/dev/null || echo "$resp"
      return 1
    fi
  else
    ok "created $crb_name → $subject_name"
  fi
}

post_crb "bootstrap-sa-cluster-admin-email" "$SA_EMAIL"
post_crb "bootstrap-sa-cluster-admin-uid" "$SA_UID"

# ============================================================================
# Done
# ============================================================================
log "✅ GKE setup complete"
echo "
Next steps:
  1. Build + push collector image:
       bash scripts/build_push_collector.sh v1.X
  2. Apply manifests:
       kubectl apply -f deploy/k8s/
  3. Run diag:
       POD=\$(kubectl -n $NAMESPACE get pods -o jsonpath='{.items[0].metadata.name}')
       kubectl -n $NAMESPACE exec \$POD -- bash /opt/blockchain-bench/scripts/s5_diag.sh

Cleanup when done:
  gcloud container clusters delete $CLUSTER --region=$REGION --project=$PROJECT --quiet
" >&2
