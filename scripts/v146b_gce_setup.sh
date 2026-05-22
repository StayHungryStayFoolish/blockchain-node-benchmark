#!/usr/bin/env bash
# v146b_gce_setup.sh — One-shot GCE bastion setup for blockchain-bench-test
#
# Creates a fresh GCE instance with everything needed to build collector images
# and deploy to GKE. Run this BEFORE v146b_gke_setup.sh.
#
# Produces:
#   - GCE e2-standard-2 in us-central1-f, Debian 12 (bookworm)
#   - SA gemini-cli-bot bound to instance (scopes: cloud-platform)
#   - Installed: docker, gcloud, kubectl, gke-gcloud-auth-plugin, jq, curl, git
#   - docker configured for AR registry us-central1-docker.pkg.dev
#   - ~/.kube/ and ~/.config/gcloud/ ready (auth happens via instance SA)
#
# Idempotent — checks `gcloud compute instances describe` first.
#
# Usage:
#   bash scripts/v146b_gce_setup.sh
#
# Cleanup when done:
#   gcloud compute instances delete $INSTANCE --zone=$ZONE --project=$PROJECT --quiet

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================
PROJECT="${PROJECT:-claude-ttft-test}"
INSTANCE="${INSTANCE:-blockchain-bench-bastion}"
ZONE="${ZONE:-us-central1-f}"
SA_NAME="${SA_NAME:-gemini-cli-bot}"
SA_EMAIL="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
MACHINE_TYPE="${MACHINE_TYPE:-e2-standard-2}"
IMAGE_FAMILY="${IMAGE_FAMILY:-debian-12}"
IMAGE_PROJECT="${IMAGE_PROJECT:-debian-cloud}"
DISK_SIZE_GB="${DISK_SIZE_GB:-50}"

# ============================================================================
# Helpers
# ============================================================================
log() { echo "[$(date +%H:%M:%S)] $*" >&2; }
ok()  { echo "  ✓ $*" >&2; }

# ============================================================================
# 1. Verify SA exists (we don't create the SA — it's project-level, persists)
# ============================================================================
log "Step 1/4: Verify SA $SA_EMAIL exists"
if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT" &>/dev/null; then
  log "  ⚠ SA $SA_EMAIL does not exist — create it first:"
  echo "    gcloud iam service-accounts create $SA_NAME --project=$PROJECT \\"
  echo "      --display-name='Gemini CLI bot for blockchain-bench-test'"
  exit 1
fi
ok "SA exists"

# ============================================================================
# 2. Create GCE instance (idempotent)
# ============================================================================
log "Step 2/4: GCE instance $INSTANCE"
if gcloud compute instances describe "$INSTANCE" \
     --zone="$ZONE" --project="$PROJECT" &>/dev/null; then
  STATUS=$(gcloud compute instances describe "$INSTANCE" \
             --zone="$ZONE" --project="$PROJECT" --format='value(status)')
  if [[ "$STATUS" == "TERMINATED" ]]; then
    log "  instance exists but stopped, starting..."
    gcloud compute instances start "$INSTANCE" --zone="$ZONE" --project="$PROJECT"
  fi
  ok "instance $INSTANCE exists (status: $STATUS)"
else
  log "  creating instance (1-2 min)..."
  gcloud compute instances create "$INSTANCE" \
    --project="$PROJECT" \
    --zone="$ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --image-family="$IMAGE_FAMILY" \
    --image-project="$IMAGE_PROJECT" \
    --boot-disk-size="${DISK_SIZE_GB}GB" \
    --boot-disk-type=pd-balanced \
    --service-account="$SA_EMAIL" \
    --scopes=cloud-platform \
    --metadata=enable-oslogin=TRUE \
    --tags=blockchain-bench
  ok "created instance"
fi

# ============================================================================
# 3. Wait for SSH ready (instance can be RUNNING but SSH not yet up)
# ============================================================================
log "Step 3/4: Wait for SSH ready"
for i in {1..30}; do
  if gcloud compute ssh "$INSTANCE" --zone="$ZONE" --project="$PROJECT" \
       --tunnel-through-iap --command='echo ready' --quiet 2>/dev/null \
       | grep -q ready; then
    ok "SSH ready"
    break
  fi
  [[ $i -eq 30 ]] && { log "✗ SSH timeout after 30 tries"; exit 1; }
  sleep 5
done

# ============================================================================
# 4. Provision software (idempotent — checks before installing)
# ============================================================================
log "Step 4/4: Provision software on instance"

# Write provision script locally, scp + run (avoids quoting hell)
PROVISION=$(mktemp)
cat > "$PROVISION" <<'PROVISION_EOF'
#!/usr/bin/env bash
set -euo pipefail

log() { echo "  [provision] $*"; }

# 4.1 — apt baseline
log "apt: install baseline tools"
sudo apt-get update -qq
sudo apt-get install -y -qq \
  ca-certificates curl gnupg lsb-release jq git tar gzip apt-transport-https

# 4.2 — docker (idempotent)
if ! command -v docker &>/dev/null; then
  log "install docker"
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg \
    | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
  sudo apt-get update -qq
  sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io
  sudo usermod -aG docker "$USER"
else
  log "docker already installed"
fi

# 4.3 — gcloud + components (gcloud is usually preinstalled on GCE)
if ! command -v gcloud &>/dev/null; then
  log "install gcloud"
  echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] \
        https://packages.cloud.google.com/apt cloud-sdk main" \
    | sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list > /dev/null
  curl https://packages.cloud.google.com/apt/doc/apt-key.gpg \
    | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
  sudo apt-get update -qq
  sudo apt-get install -y -qq google-cloud-cli
fi

# 4.4 — kubectl + gke-gcloud-auth-plugin
log "install kubectl + gke-gcloud-auth-plugin"
sudo apt-get install -y -qq kubectl google-cloud-cli-gke-gcloud-auth-plugin

# 4.5 — docker auth for Artifact Registry
log "configure docker for AR"
# 'sudo' because docker socket may not be group-permission'd yet (first run)
sudo gcloud auth configure-docker us-central1-docker.pkg.dev --quiet

# 4.6 — verify
log "verify versions"
docker --version
gcloud version --format='value(\"Google Cloud SDK\")' 2>/dev/null \
  || gcloud version | head -1
kubectl version --client | head -1
gke-gcloud-auth-plugin --version | head -1
jq --version

echo "  ✓ provision complete"
PROVISION_EOF

# scp + run
gcloud compute scp "$PROVISION" "$INSTANCE":/tmp/provision.sh \
  --zone="$ZONE" --project="$PROJECT" --tunnel-through-iap --quiet
gcloud compute ssh "$INSTANCE" --zone="$ZONE" --project="$PROJECT" \
  --tunnel-through-iap --quiet --command='bash /tmp/provision.sh'
rm -f "$PROVISION"
ok "software provisioned"

# ============================================================================
# Done
# ============================================================================
log "✅ GCE bastion setup complete"
echo "
Next steps:
  1. Run GKE setup from your local machine (or this bastion):
       bash scripts/v146b_gke_setup.sh
  2. SSH to bastion to build/push images:
       gcloud compute ssh $INSTANCE --zone=$ZONE --project=$PROJECT --tunnel-through-iap

Cleanup when done with the whole environment:
  gcloud container clusters delete blockchain-bench-test --region=us-central1 --project=$PROJECT --quiet
  gcloud compute instances delete $INSTANCE --zone=$ZONE --project=$PROJECT --quiet
" >&2
