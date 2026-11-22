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
# Der Weg seit dem 20.11.2026 – Unified login (App „Clip Engine“, eigene
# Konfiguration für Endurance): Das Skript gibt einen Anmeldelink aus, man
# meldet sich als ausdauermaschine an, kopiert die Adresse mit „?code=“
# zurück, und der Schlüssel (System-User, läuft nie ab) landet samt
# Instagram-Konto-Id im Tresor:
#
#     bash scripts/instagram_google_einrichten.sh --anmelden
#
# Dafür muss https://endurance-events.de/ als Redirect URL registriert sein,
# und das Skript fragt einmal nach dem App-Geheimcode (wird nicht gespeichert).
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
# Seit dem 20.11.2026: Unified login in der App „Clip Engine“ (die alte App
# „AusdauerMaschine Content“ ist mit dem gelöschten Facebook-Profil weg;
# „API setup with Instagram login is not available for newer apps“).
# App-ID und die eigene Konfiguration für Endurance – beides keine
# Geheimzahlen, sie stehen in jedem Anmeldelink. Die Konfiguration der
# Clip Engine (1629221798979418) NICHT ändern.
META_APP_ID="${META_APP_ID:-1135841785970940}"
META_CONFIG_ID="${META_CONFIG_ID:-1612032490129415}"
# Muss GENAU so (mit Schrägstrich) in der App unter „API setup with Unified
# login“ → Redirect URL registriert sein.
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

# Unified login: Anmeldelink (facebook.com/dialog/oauth mit config_id) →
# Code aus der Weiterleitung → System-User-Schlüssel (läuft nie ab) bei
# graph.facebook.com → Instagram-Konto-Id → beides als JSON in den Tresor.
anmelden() {
  local link adresse code geheim antwort token
  link="$(META_APP_ID="$META_APP_ID" META_CONFIG_ID="$META_CONFIG_ID" WEITERLEITUNG="$WEITERLEITUNG" python3 -c 'import os, secrets, urllib.parse
print("https://www.facebook.com/dialog/oauth?" + urllib.parse.urlencode({
    "client_id": os.environ["META_APP_ID"], "config_id": os.environ["META_CONFIG_ID"],
    "redirect_uri": os.environ["WEITERLEITUNG"], "response_type": "code",
    "override_default_response_type": "true", "state": secrets.token_hex(8)}))')"
  echo
  echo "Anmeldung über Unified login (App ${META_APP_ID}, Konfiguration ${META_CONFIG_ID})"
  echo
  echo "  1. Den App-Geheimcode holen: developers.facebook.com → App „Clip Engine“ →"
  echo "     App settings → Basic → „App secret“ → Show → kopieren. 32 Zeichen (Zahlen"
  echo "     und a–f), nur für den Tausch gebraucht, wird nicht gespeichert."
  local versuch=0 roh
  geheim=""
  while [ -z "$geheim" ] && [ "$versuch" -lt 3 ]; do
    versuch=$((versuch + 1))
    read -r -s -p "     Geheimcode einfügen und Enter drücken (die Eingabe bleibt unsichtbar): " roh
    echo
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
      echo "     Kein eindeutiger Geheimcode erkannt (32 Zeichen, nur Zahlen und a–f)." >&2
    fi
  done
  roh=""
  if [ -z "$geheim" ]; then
    echo "  Nichts geändert." >&2
    return 1
  fi
  echo "     Geheimcode erhalten (${geheim:0:4}…${geheim: -2})."
  echo
  # Wie beim alten Weg: eine kurze Seite im Video-Speicher, die man
  # EINTIPPT und die selbst weiterleitet (ein angetippter Meta-Link öffnet
  # auf dem iPad gern eine App statt der Anmeldeseite).
  local seite kurzlink=""
  seite="$(mktemp)"
  LINK="$link" python3 - > "$seite" <<'PY'
import html, json, os
l = os.environ["LINK"]
print("<!doctype html><html lang=de><meta charset=utf-8>"
      "<meta name=viewport content='width=device-width,initial-scale=1'>"
      "<meta name=robots content=noindex>"
      f"<meta http-equiv=refresh content='0;url={html.escape(l, quote=True)}'>"
      "<title>Weiter zur Anmeldung</title>"
      "<body style='font:18px sans-serif;padding:24px'>Weiter zur Anmeldung …"
      f"<script>location.replace({json.dumps(l)})</script>")
PY
  if gcloud storage cp "$seite" "gs://${BUCKET}/ig.html" --content-type=text/html \
       --cache-control=no-store >/dev/null 2>&1; then
    kurzlink="storage.googleapis.com/${BUCKET}/ig.html"
  fi
  rm -f "$seite"
  echo "  2. In Safari einen neuen Tab öffnen und diese Adresse oben EINTIPPEN:"
  echo
  echo "        ${kurzlink:-$link}"
  echo
  echo "     → „Mit Instagram fortfahren“ (bzw. Instagram wählen), als ausdauermaschine"
  echo "     anmelden, das Konto ausdauermaschine auswählen, alles erlauben."
  [ -n "$kurzlink" ] && echo "     (Langer Link, falls nötig: $link )"
  echo
  echo "  3. Danach öffnet sich endurance-events.de. Die GANZE Adresse aus der"
  echo "     Adresszeile kopieren (sie enthält „?code=…“) und hierher zurück."
  echo
  # Fragt, bis die Adresse wirklich von endurance-events.de kommt – wer hier
  # versehentlich den Anmeldelink einfügt, soll nicht von vorn anfangen müssen.
  while :; do
    read -r -p "     Adresse einfügen und Enter drücken: " adresse
    case "$adresse" in
      *code=*) break ;;
      "") echo "  Abgebrochen – nichts geändert." >&2; return 1 ;;
      *) echo "     Das ist nicht die Adresse nach der Anmeldung. Die Adresse aus Schritt 2 gehört in"
         echo "     einen NEUEN BROWSER-TAB; hierher kommt erst die Adresse von endurance-events.de"
         echo "     mit „?code=…“. (Leere Eingabe bricht ab.)" ;;
    esac
  done
  code="$(ADRESSE="$adresse" python3 -c 'import os, urllib.parse
a = os.environ["ADRESSE"].strip()
q = urllib.parse.parse_qs(urllib.parse.urlparse(a).query) if "code=" in a else {"code": [a]}
print(q.get("code", [""])[0].split("#")[0].strip())')"
  if [ -z "$code" ]; then
    echo "  In der Adresse steht kein „code=“ – nichts geändert. Noch einmal: bash $0 --anmelden" >&2
    return 1
  fi
  echo "     Code erhalten (${#code} Zeichen), tausche …"
  antwort="$(curl -sS -G "https://graph.facebook.com/${IG_VERSION}/oauth/access_token" \
    --data-urlencode "client_id=${META_APP_ID}" --data-urlencode "client_secret=${geheim}" \
    --data-urlencode "redirect_uri=${WEITERLEITUNG}" --data-urlencode "code=${code}" || true)"
  token="$(printf '%s' "$antwort" | python3 -c 'import json, sys
try:
    print(json.load(sys.stdin).get("access_token", ""))
except Exception:
    print("")')"
  if [ -z "$token" ]; then
    echo "  Meta hat den Code nicht getauscht:" >&2
    printf '%s' "$antwort" | python3 -c 'import json, sys
try:
    d = json.load(sys.stdin); print("  ", (d.get("error") or {}).get("message") or d)
except Exception:
    print("   keine lesbare Antwort")' >&2
    echo "  Häufigste Gründe: Code schon benutzt oder zu alt, Geheimcode einer anderen App," >&2
    echo "  Weiterleitung nicht genau ${WEITERLEITUNG}. Noch einmal: bash $0 --anmelden" >&2
    geheim=""
    return 1
  fi
  echo "  Schlüssel erhalten. Suche das Instagram-Konto …"
  # Zwei Wege zur Konto-Id: die zugewiesenen Instagram-Konten des
  # System-Users, sonst die Ziel-Ids der Berechtigung instagram_basic aus
  # debug_token (braucht den App-Zugang app_id|geheim).
  local konten
  konten="$( { curl -sS -G "https://graph.facebook.com/${IG_VERSION}/me/assigned_instagram_accounts" \
      --data-urlencode "fields=id,username" --data-urlencode "access_token=${token}" || true; echo; \
    curl -sS -G "https://graph.facebook.com/${IG_VERSION}/debug_token" \
      --data-urlencode "input_token=${token}" --data-urlencode "access_token=${META_APP_ID}|${geheim}" || true; } \
    | python3 -c 'import json, sys
ids = []
for zeile in sys.stdin.read().splitlines():
    try:
        d = json.loads(zeile)
    except Exception:
        continue
    for k in d.get("data", []) if isinstance(d.get("data"), list) else []:
        if k.get("id"): ids.append(str(k["id"]))
    daten = d.get("data") if isinstance(d.get("data"), dict) else {}
    for g in daten.get("granular_scopes", []):
        if g.get("scope") in ("instagram_basic", "instagram_content_publish"):
            ids += [str(i) for i in g.get("target_ids", [])]
print(" ".join(dict.fromkeys(ids)))')"
  geheim=""
  local ig_id="" kandidat name
  for kandidat in $konten; do
    name="$(curl -sS -G "https://graph.facebook.com/${IG_VERSION}/${kandidat}" \
      --data-urlencode "fields=username" --data-urlencode "access_token=${token}" \
      | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("username",""))
except Exception: print("")')"
    if [ -n "$name" ]; then
      echo "     Konto ${kandidat}: @${name}"
      if [ "$name" = "ausdauermaschine" ] || [ -z "$ig_id" ]; then ig_id="$kandidat"; fi
    fi
  done
  if [ -z "$ig_id" ]; then
    echo "  Kein Instagram-Konto gefunden, auf das der Schlüssel zugreifen darf." >&2
    echo "  Vermutlich fehlt in der Konfiguration business_management oder das Konto wurde" >&2
    echo "  bei der Anmeldung nicht ausgewählt. Nichts geändert." >&2
    return 1
  fi
  gcloud storage rm "gs://${BUCKET}/ig.html" >/dev/null 2>&1 || true
  ablegen_unified "$token" "$ig_id"
}

# Prüft einen Unified-login-Schlüssel und legt ihn als JSON in den Tresor.
ablegen_unified() {
  local token="$1" ig_id="$2" limit wert
  limit="$(curl -sS -G "https://graph.facebook.com/${IG_VERSION}/${ig_id}/content_publishing_limit" \
    --data-urlencode "fields=quota_usage" --data-urlencode "access_token=${token}" || true)"
  if printf '%s' "$limit" | python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if "data" in d else 1)' 2>/dev/null; then
    echo "  Der Schlüssel darf Beiträge veröffentlichen."
  else
    echo "  ACHTUNG: Das Veröffentlichungslimit ließ sich nicht lesen – vielleicht fehlt" >&2
    echo "  instagram_content_publish. Antwort: $(printf '%s' "$limit" | head -c 300)" >&2
  fi
  wert="$(TOKEN="$token" IG_ID="$ig_id" python3 -c 'import json, os
print(json.dumps({"art": "unified", "token": os.environ["TOKEN"], "ig_id": os.environ["IG_ID"]}))')"
  printf '%s' "$wert" | gcloud secrets versions add "$SECRET" --data-file=- >/dev/null
  local neueste
  neueste="$(gcloud secrets versions list "$SECRET" --filter='state:enabled' --sort-by='~createTime' --format='value(name.basename())' | head -1)"
  for v in $(gcloud secrets versions list "$SECRET" --filter='state:enabled' --format='value(name.basename())'); do
    if [ "$v" != "$neueste" ]; then
      gcloud secrets versions destroy "$v" --secret="$SECRET" --quiet >/dev/null
    fi
  done
  echo "  Im Tresor abgelegt (Fassung ${neueste##*/}, Konto-Id ${ig_id}); ältere Fassungen vernichtet."
  echo "  Der Schlüssel läuft nicht ab – nichts weiter zu tun."
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
