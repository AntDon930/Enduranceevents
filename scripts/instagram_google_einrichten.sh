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
# Den Schlüssel OHNE den Knopf „Token generieren“ holen (der verlangt jedes
# Mal eine frische Anmeldung bei Instagram; scheitert sie, kommt man nie zu
# „Zulassen“). Das Skript gibt einen Link aus, den man in einem Browser
# öffnet, in dem man bei Instagram schon angemeldet ist:
#
#     bash scripts/instagram_google_einrichten.sh --anmelden
#
# Dafür muss in der Meta-App unter „Business-Login-Einstellungen“ die
# OAuth-Weiterleitungs-URI https://endurance-events.de/ eingetragen sein,
# und das Skript fragt einmal nach dem Instagram-App-Geheimcode (wird nicht
# gespeichert).
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
# Die Instagram-App-ID der Meta-App „AusdauerMaschine Content“ – keine
# Geheimzahl, sie steht in jedem Anmeldelink.
IG_APP_ID="2082109586511982"
# Muss GENAU so (mit Schrägstrich) in der Meta-App unter
# „Business-Login-Einstellungen“ → OAuth-Weiterleitungs-URIs stehen.
WEITERLEITUNG="https://endurance-events.de/"

modus="alles"
[ "${1:-}" = "--schluessel" ] && modus="schluessel"
[ "${1:-}" = "--anmelden" ] && modus="anmelden"

gcloud config set project "$PROJEKT" >/dev/null 2>&1

schluessel_hinterlegen() {
  echo
  echo "Instagram-Schlüssel hinterlegen"
  echo "  (developers.facebook.com → deine App → Instagram → API-Einrichtung mit"
  echo "   Instagram-Business-Login → „Token generieren“ beim Konto ausdauermaschine;"
  echo "   klappt die Anmeldung dort nicht: Abbrechen mit Strg+C, dann"
  echo "   bash $0 --anmelden)"
  local schluessel
  read -r -s -p "  Schlüssel einfügen und Enter drücken (die Eingabe bleibt unsichtbar): " schluessel
  echo
  ablegen "$schluessel"
}

# Holt den Schlüssel über einen eigenen Anmeldelink statt über „Token
# generieren“: Code aus der Weiterleitung → kurzer Schlüssel → 60 Tage.
anmelden() {
  local link adresse code geheim antwort kurz lang
  link="$(IG_APP_ID="$IG_APP_ID" WEITERLEITUNG="$WEITERLEITUNG" python3 -c 'import os, urllib.parse
print("https://www.instagram.com/oauth/authorize?" + urllib.parse.urlencode({
    "enable_fb_login": "0", "force_reauth": "false",
    "client_id": os.environ["IG_APP_ID"], "redirect_uri": os.environ["WEITERLEITUNG"],
    "response_type": "code",
    "scope": "instagram_business_basic,instagram_business_content_publish"}))')"
  echo
  echo "Anmeldung über einen eigenen Link"
  echo
  # Erst der Geheimcode, dann der Link: Der Code aus dem Link gilt nur kurz
  # und nur einmal – so ist er beim Tausch so frisch wie möglich.
  echo "  1. Den Instagram-App-Geheimcode holen: developers.facebook.com → deine App →"
  echo "     API-Einrichtung mit Instagram-Business-Login → oben „Instagram-App-Geheimcode“"
  echo "     → Anzeigen → kopieren. Er hat 32 Zeichen (Zahlen und a–f), wird nur für"
  echo "     den Tausch gebraucht und nicht gespeichert."
  local versuch=0 roh
  geheim=""
  while [ -z "$geheim" ] && [ "$versuch" -lt 3 ]; do
    versuch=$((versuch + 1))
    read -r -s -p "     Geheimcode einfügen und Enter drücken (die Eingabe bleibt unsichtbar): " roh
    echo
    # Aus dem Eingefügten die 32-stellige Folge nehmen – beim Kopieren auf
    # dem iPad kommt gern Text daneben mit (Beschriftung, Knopf, doppelt).
    geheim="$(ROH="$roh" python3 -c 'import os, re
laeufe = re.findall(r"[0-9a-fA-F]{32,}", os.environ["ROH"])
treffer = set()
for l in laeufe:
    if len(l) == 32:
        treffer.add(l.lower())
    elif len(l) % 32 == 0 and len(set(l[i:i + 32] for i in range(0, len(l), 32))) == 1:
        treffer.add(l[:32].lower())
print(treffer.pop() if len(treffer) == 1 else "")')"
    if [ -z "$geheim" ]; then
      roh="$(printf '%s' "$roh" | tr -d '[:space:]')"
      if [ -z "$roh" ]; then
        echo "     Es ist nichts angekommen – mit ⌘V einfügen (oder lange tippen → „Einsetzen“)." >&2
      else
        echo "     Angekommen sind ${#roh} Zeichen, darin steckt kein eindeutiger Geheimcode" >&2
        echo "     (32 Zeichen, nur Zahlen und a–f). Im Meta-Feld nur den Code markieren." >&2
      fi
    fi
  done
  roh=""
  if [ -z "$geheim" ]; then
    echo "  Nichts geändert." >&2
    return 1
  fi
  echo "     Geheimcode erhalten (${geheim:0:4}…${geheim: -2}, 32 Zeichen)."
  echo
  echo "  2. Diesen Link in dem Browser öffnen, in dem du bei Instagram als"
  echo "     ausdauermaschine angemeldet bist, und „Zulassen“ antippen:"
  echo
  echo "     $link"
  echo
  echo "  3. Danach öffnet sich endurance-events.de. Die GANZE Adresse aus der"
  echo "     Adresszeile kopieren (sie enthält „?code=…“) und hierher zurück."
  echo "     Jeder Code gilt nur EINMAL – für einen neuen Versuch den Link neu öffnen."
  echo
  # Sichtbar: Der Code gilt nur kurz, nur einmal und nur zusammen mit dem
  # Geheimcode – und so sieht man, ob das Einfügen geklappt hat.
  read -r -p "     Adresse einfügen und Enter drücken: " adresse
  code="$(ADRESSE="$adresse" python3 -c 'import os, urllib.parse
a = os.environ["ADRESSE"].strip()
q = urllib.parse.parse_qs(urllib.parse.urlparse(a).query) if "code=" in a else {"code": [a]}
print(q.get("code", [""])[0].split("#")[0].strip())')"
  if [ -z "$code" ]; then
    if [ -z "$adresse" ]; then
      echo "  Es ist nichts angekommen – das Einfügen hat nicht geklappt." >&2
      echo "  In der Cloud Shell mit ⌘V einfügen (oder lange tippen → „Einsetzen“)." >&2
    else
      echo "  In der Adresse steht kein „code=“. Kopiert werden muss die Adresse, auf der" >&2
      echo "  Instagram nach „Zulassen“ landet (endurance-events.de/?code=…)." >&2
    fi
    echo "  Nichts geändert. Noch einmal: bash $0 --anmelden" >&2
    return 1
  fi
  echo "     Code erhalten (${#code} Zeichen), tausche …"
  antwort="$(curl -sS -X POST "https://api.instagram.com/oauth/access_token" \
    --form-string "client_id=${IG_APP_ID}" --form-string "client_secret=${geheim}" \
    --form-string "grant_type=authorization_code" --form-string "redirect_uri=${WEITERLEITUNG}" \
    --form-string "code=${code}" || true)"
  kurz="$(printf '%s' "$antwort" | python3 -c 'import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    d = {}
if isinstance(d.get("data"), list) and d["data"]:
    d = d["data"][0]
print(d.get("access_token", ""))')"
  if [ -z "$kurz" ]; then
    echo "  Instagram hat den Code nicht getauscht:" >&2
    printf '%s' "$antwort" | python3 -c 'import json, sys
try:
    d = json.load(sys.stdin)
    print("  ", d.get("error_message") or (d.get("error") or {}).get("message") or d)
except Exception:
    print("   keine lesbare Antwort")' >&2
    echo "  Häufigste Gründe: Code schon einmal benutzt oder zu alt (Link neu öffnen, neue" >&2
    echo "  Adresse nehmen), Geheimcode einer anderen App, Weiterleitungs-URI in der App" >&2
    echo "  nicht genau ${WEITERLEITUNG}. Noch einmal: bash $0 --anmelden" >&2
    return 1
  fi
  antwort="$(curl -sS -G "https://graph.instagram.com/access_token" \
    --data-urlencode "grant_type=ig_exchange_token" --data-urlencode "client_secret=${geheim}" \
    --data-urlencode "access_token=${kurz}" || true)"
  lang="$(printf '%s' "$antwort" | python3 -c 'import json, sys
try:
    print(json.load(sys.stdin).get("access_token", ""))
except Exception:
    print("")')"
  geheim=""
  if [ -z "$lang" ]; then
    echo "  Der kurze Schlüssel ließ sich nicht in einen 60-Tage-Schlüssel tauschen." >&2
    return 1
  fi
  echo "  Schlüssel für 60 Tage erhalten."
  ablegen "$lang"
}

# Prüft einen Schlüssel bei Instagram und legt ihn in den Tresor.
ablegen() {
  local schluessel="$1" antwort
  schluessel="$(printf '%s' "$schluessel" | tr -d '[:space:]')"
  if [ -z "$schluessel" ]; then
    echo "  Kein Schlüssel eingegeben – nichts geändert." >&2
    return 1
  fi
  echo "  Schlüssel erhalten (${#schluessel} Zeichen), prüfe bei Instagram …"
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
  # Das Veröffentlichungslimit liest nur ein Schlüssel MIT der Berechtigung
  # instagram_business_content_publish – fehlt sie, scheitert erst der
  # erste echte Beitrag. Deshalb hier schon warnen.
  local konto limit
  konto="$(printf '%s' "$antwort" | python3 -c 'import json,sys; print(json.load(sys.stdin)["user_id"])')"
  limit="$(curl -sS -H "Authorization: Bearer ${schluessel}" \
    "https://graph.instagram.com/${IG_VERSION}/${konto}/content_publishing_limit?fields=quota_usage" || true)"
  if printf '%s' "$limit" | python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if "data" in d else 1)' 2>/dev/null; then
    echo "  Der Schlüssel darf Beiträge veröffentlichen."
  else
    echo "  ACHTUNG: Der Schlüssel darf offenbar KEINE Beiträge veröffentlichen." >&2
    echo "  In der App unter „Berechtigungen und Features“ instagram_business_content_publish" >&2
    echo "  hinzufügen, den Schlüssel neu generieren und dann: bash $0 --schluessel" >&2
  fi
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

if [ "$modus" = "schluessel" ]; then
  schluessel_hinterlegen
  exit $?
fi
if [ "$modus" = "anmelden" ]; then
  anmelden
  exit $?
fi

echo "1/6 Google-Dienste einschalten …"
gcloud services enable iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  secretmanager.googleapis.com storage.googleapis.com cloudresourcemanager.googleapis.com
# Erst nach dem Einschalten fragen: die Projektnummer kommt aus dem
# Cloud Resource Manager.
NUMMER="$(gcloud projects describe "$PROJEKT" --format='value(projectNumber)')"

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
# Ohne das weist Google die Freigabe für allUsers ab, falls der Speicher
# „öffentlichen Zugriff verhindern" trägt (in der Konsole voreingestellt).
gcloud storage buckets update "gs://${BUCKET}" --no-public-access-prevention >/dev/null
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
