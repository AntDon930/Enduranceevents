#!/usr/bin/env bash
# scripts/instagram_google_einrichten.sh
# ======================================
#
# EINMAL in der Google Cloud Shell ausführen (shell.cloud.google.com, als
# Inhaber des Firebase-Projekts angemeldet):
#
#     cd ~/Enduranceevents && git pull && bash scripts/instagram_google_einrichten.sh
#
# Richtet im Google-Projekt hinter Firebase alles ein, was das automatische
# Posten über die Anmeldung mit Instagram braucht (scripts/insta_posten.py,
# README „Instagram", Einrichtung):
#
#   1. die nötigen Google-Dienste
#   2. ein Dienstkonto „instagram-reel" – OHNE Schlüsseldatei
#   3. einen Speicher für das Video, bis Instagram es abgeholt hat
#      (Objekte öffentlich lesbar, nicht auflistbar, nach einem Tag weg)
#   4. einen Tresor für den Instagram-Schlüssel (Secret Manager)
#   5. die Anmeldung für GitHub (Workload Identity): NUR der Workflow
#      instagram.yml aus AntDon930/Enduranceevents bekommt Zugang
#   6. fragt den Instagram-Schlüssel ab (die Eingabe bleibt unsichtbar),
#      prüft ihn bei Instagram und legt ihn in den Tresor
#
# Mehrfach ausführen schadet nicht – was schon steht, bleibt stehen.
# Nur den Schlüssel neu hinterlegen (abgelaufen, neu erzeugt):
#
#     bash scripts/instagram_google_einrichten.sh --schluessel
#
# Die Namen hier stehen genauso in .github/workflows/instagram.yml und
# scripts/insta_posten.py; test_instagram vergleicht sie.

set -euo pipefail

PROJEKT="endurance-5177a"
REPO="AntDon930/Enduranceevents"
DIENSTKONTO_NAME="instagram-reel"
DIENSTKONTO="${DIENSTKONTO_NAME}@${PROJEKT}.iam.gserviceaccount.com"
BUCKET="endurance-5177a-instagram"
# us-central1: dort fallen Speicher und Abruf unter das kostenlose
# Kontingent von Google Cloud. Im Speicher liegt nur das Video, das
# ohnehin gleich öffentlich auf Instagram steht.
BUCKET_ORT="us-central1"
SECRET="instagram-token"
POOL="github"
ANBIETER="enduranceevents"
IG_VERSION="v25.0"

nur_schluessel=0
[ "${1:-}" = "--schluessel" ] && nur_schluessel=1

gcloud config set project "$PROJEKT" >/dev/null 2>&1
NUMMER="$(gcloud projects describe "$PROJEKT" --format='value(projectNumber)')"

schluessel_hinterlegen() {
  echo
  echo "Instagram-Schlüssel hinterlegen"
  echo "  (developers.facebook.com → deine App → Instagram → API-Einrichtung mit"
  echo "   Instagram-Business-Login → „Token generieren“ beim Konto ausdauermaschine)"
  local schluessel antwort
  read -r -s -p "  Schlüssel einfügen und Enter drücken (die Eingabe bleibt unsichtbar): " schluessel
  echo
  schluessel="$(printf '%s' "$schluessel" | tr -d '[:space:]')"
  if [ -z "$schluessel" ]; then
    echo "  Kein Schlüssel eingegeben – nichts geändert." >&2
    return 1
  fi
  antwort="$(curl -sS -H "Authorization: Bearer ${schluessel}" \
    "https://graph.instagram.com/${IG_VERSION}/me?fields=user_id,username" || true)"
  if ! printf '%s' "$antwort" | python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if d.get("user_id") else 1)' 2>/dev/null; then
    echo "  Instagram nimmt den Schlüssel nicht an:" >&2
    printf '%s' "$antwort" | python3 -c 'import json,sys
try:
    d = json.load(sys.stdin)
    print("  ", (d.get("error") or {}).get("message", d))
except Exception:
    print("   keine lesbare Antwort")' >&2
    echo "  Nichts geändert. Schlüssel in der App neu erzeugen und das Skript noch einmal starten." >&2
    return 1
  fi
  printf '%s' "$antwort" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("  Instagram kennt den Schlüssel: @%s (Konto-Id %s)" % (d.get("username"), d.get("user_id")))'
  printf '%s' "$schluessel" | gcloud secrets versions add "$SECRET" --data-file=- >/dev/null
  local neueste
  neueste="$(gcloud secrets versions list "$SECRET" --filter='state:enabled' --sort-by='~createTime' --format='value(name.basename())' | head -1)"
  for v in $(gcloud secrets versions list "$SECRET" --filter='state:enabled' --format='value(name.basename())'); do
    if [ "$v" != "$neueste" ]; then
      gcloud secrets versions destroy "$v" --secret="$SECRET" --quiet >/dev/null
    fi
  done
  echo "  Im Tresor abgelegt (Fassung ${neueste##*/}); ältere Fassungen vernichtet."
}

if [ "$nur_schluessel" = "1" ]; then
  schluessel_hinterlegen
  exit $?
fi

echo "1/6 Google-Dienste einschalten …"
gcloud services enable iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  secretmanager.googleapis.com storage.googleapis.com cloudresourcemanager.googleapis.com

echo "2/6 Dienstkonto ${DIENSTKONTO} …"
if ! gcloud iam service-accounts describe "$DIENSTKONTO" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$DIENSTKONTO_NAME" \
    --display-name="Instagram-Reel (GitHub Actions, ohne Schlüsseldatei)"
fi

echo "3/6 Speicher gs://${BUCKET} …"
if ! gcloud storage buckets describe "gs://${BUCKET}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET}" --location="$BUCKET_ORT" --uniform-bucket-level-access
fi
regel="$(mktemp)"
echo '{"rule": [{"action": {"type": "Delete"}, "condition": {"age": 1}}]}' > "$regel"
gcloud storage buckets update "gs://${BUCKET}" --lifecycle-file="$regel" >/dev/null
rm -f "$regel"
# legacyObjectReader: jeder kann ein Objekt mit bekanntem Namen lesen,
# aber niemand kann auflisten, was im Speicher liegt.
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member=allUsers --role=roles/storage.legacyObjectReader >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${DIENSTKONTO}" --role=roles/storage.objectAdmin >/dev/null

echo "4/6 Tresor ${SECRET} …"
if ! gcloud secrets describe "$SECRET" >/dev/null 2>&1; then
  gcloud secrets create "$SECRET" --replication-policy=automatic >/dev/null
fi
gcloud secrets add-iam-policy-binding "$SECRET" \
  --member="serviceAccount:${DIENSTKONTO}" --role=roles/secretmanager.secretAccessor >/dev/null
gcloud secrets add-iam-policy-binding "$SECRET" \
  --member="serviceAccount:${DIENSTKONTO}" --role=roles/secretmanager.secretVersionManager >/dev/null

echo "5/6 Anmeldung für GitHub (Workload Identity) …"
if ! gcloud iam workload-identity-pools describe "$POOL" --location=global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL" --location=global --display-name="GitHub Actions"
fi
if ! gcloud iam workload-identity-pools providers describe "$ANBIETER" --location=global \
     --workload-identity-pool="$POOL" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "$ANBIETER" --location=global \
    --workload-identity-pool="$POOL" --display-name="Enduranceevents" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.workflow_ref=assertion.workflow_ref" \
    --attribute-condition="assertion.repository == '${REPO}' && assertion.workflow_ref.startsWith('${REPO}/.github/workflows/instagram.yml@')"
fi
gcloud iam service-accounts add-iam-policy-binding "$DIENSTKONTO" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${NUMMER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${REPO}" >/dev/null

echo "6/6 Instagram-Schlüssel …"
if gcloud secrets versions list "$SECRET" --filter='state:enabled' --format='value(name.basename())' | grep -q .; then
  echo "  Im Tresor liegt schon ein Schlüssel – bleibt. Neu hinterlegen: bash $0 --schluessel"
else
  schluessel_hinterlegen
fi

echo
echo "Fertig. Für den Workflow (stehen schon in .github/workflows/instagram.yml):"
echo "  workload_identity_provider: projects/${NUMMER}/locations/global/workloadIdentityPools/${POOL}/providers/${ANBIETER}"
echo "  service_account:            ${DIENSTKONTO}"
echo "Probelauf: GitHub → Actions → „Instagram-Reel“ → Run workflow (ohne Haken „posten“)."
