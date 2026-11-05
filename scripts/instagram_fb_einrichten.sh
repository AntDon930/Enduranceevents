#!/usr/bin/env bash
# scripts/instagram_fb_einrichten.sh
# ==================================
#
# EINMAL in der Google Cloud Shell ausführen (shell.cloud.google.com),
# NACHDEM scripts/instagram_google_einrichten.sh gelaufen ist:
#
#     cd ~/Enduranceevents && git fetch origin claude/clubs-feature-map-kycnmi \
#       && git checkout claude/clubs-feature-map-kycnmi && git pull \
#       && bash scripts/instagram_fb_einrichten.sh
#
# Wozu: Die Clubs posten ihre Termine oft nur auf Instagram. Metas
# Schnittstelle „Business Discovery" liest die öffentlichen Beiträge anderer
# Business-/Creator-Konten – aber nur mit der Anmeldung über FACEBOOK (eine
# Facebook-Seite, mit der das Instagram-Konto ausdauermaschine verknüpft
# ist). Vom Nutzer am 26.10.2026 so entschieden („Wir müssen unbedingt die
# Sachen auf Instagram auch automatisch auslesen!“). Das Posten bleibt
# davon unberührt (Anmeldung über Instagram, instagram_google_einrichten.sh).
#
# Das Skript fragt (Eingaben unsichtbar):
#   1. die Facebook-App-ID und den App-Geheimcode der Meta-App
#      (App-Einstellungen → Allgemein; NICHT die Instagram-App-ID),
#   2. einen kurzen Nutzer-Schlüssel aus dem Graph API Explorer mit den
#      Rechten instagram_basic, instagram_manage_insights,
#      pages_show_list, pages_read_engagement.
# Es tauscht ihn gegen einen langen Schlüssel, holt daraus den
# SEITEN-Schlüssel der Seite, an der ausdauermaschine hängt (läuft nicht
# ab), prüft Business Discovery an einem Club und legt Schlüssel und
# Instagram-Konto-Id in den Google-Tresor (Secret „instagram-fb-token“).
# Ausgegeben wird kein Schlüssel.

set -euo pipefail

PROJEKT="endurance-5177a"
DIENSTKONTO="instagram-reel@${PROJEKT}.iam.gserviceaccount.com"
SECRET="instagram-fb-token"
VERSION="v25.0"
KONTO="ausdauermaschine"
PROBE="cozy.runclub"

gcloud config set project "$PROJEKT" >/dev/null 2>&1

read -rp  "Facebook-App-ID: " APP_ID
read -rsp "App-Geheimcode (unsichtbar): " APP_GEHEIM; echo
read -rsp "Kurzer Nutzer-Schlüssel aus dem Graph API Explorer (unsichtbar): " KURZ; echo

echo "1/4 Tausche gegen einen langen Schlüssel …"
LANGER="$(APP_ID="$APP_ID" APP_GEHEIM="$APP_GEHEIM" KURZ="$KURZ" VERSION="$VERSION" python3 - <<'PY'
import json, os, sys, urllib.parse, urllib.request
q = urllib.parse.urlencode({"grant_type": "fb_exchange_token", "client_id": os.environ["APP_ID"],
    "client_secret": os.environ["APP_GEHEIM"], "fb_exchange_token": os.environ["KURZ"]})
try:
    d = json.load(urllib.request.urlopen(f"https://graph.facebook.com/{os.environ['VERSION']}/oauth/access_token?{q}", timeout=30))
except Exception as ex:
    body = getattr(ex, "read", lambda: b"")().decode(errors="replace")
    sys.stderr.write("Tausch abgelehnt: " + (json.loads(body).get("error", {}).get("message", body[:200]) if body.startswith("{") else str(type(ex).__name__)) + "\n")
    sys.exit(1)
print(d["access_token"])
PY
)"

echo "2/4 Suche die Facebook-Seite mit @${KONTO} …"
ERG="$(LANG_T="$LANGER" VERSION="$VERSION" KONTO="$KONTO" python3 - <<'PY'
import json, os, sys, urllib.parse, urllib.request
q = urllib.parse.urlencode({"fields": "name,access_token,instagram_business_account{id,username}"})
req = urllib.request.Request(f"https://graph.facebook.com/{os.environ['VERSION']}/me/accounts?{q}",
                             headers={"Authorization": "Bearer " + os.environ["LANG_T"]})
d = json.load(urllib.request.urlopen(req, timeout=30))
for s in d.get("data", []):
    ig = s.get("instagram_business_account") or {}
    if (ig.get("username") or "").lower() == os.environ["KONTO"]:
        print(json.dumps({"token": s["access_token"], "ig_user_id": ig["id"], "seite": s.get("name")}))
        sys.exit(0)
namen = [s.get("name") for s in d.get("data", [])]
sys.stderr.write(f"Keine Seite mit verknüpftem @{os.environ['KONTO']} gefunden. Seiten mit Zugriff: {namen}\n"
                 "→ Instagram-Konto in den Seiten-Einstellungen verknüpfen und im Explorer pages_show_list erlauben.\n")
sys.exit(1)
PY
)"
echo "   Seite: $(printf '%s' "$ERG" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["seite"], "– Instagram-Konto-Id", d["ig_user_id"])')"

echo "3/4 Probe: Business Discovery für @${PROBE} …"
ERG="$ERG" VERSION="$VERSION" PROBE="$PROBE" python3 - <<'PY'
import json, os, sys, urllib.parse, urllib.request
e = json.loads(os.environ["ERG"])
q = urllib.parse.urlencode({"fields": f"business_discovery.username({os.environ['PROBE']}){{username,media.limit(3){{timestamp,caption,media_url}}}}"})
req = urllib.request.Request(f"https://graph.facebook.com/{os.environ['VERSION']}/{e['ig_user_id']}?{q}",
                             headers={"Authorization": "Bearer " + e["token"]})
try:
    d = json.load(urllib.request.urlopen(req, timeout=30))
except Exception as ex:
    body = getattr(ex, "read", lambda: b"")().decode(errors="replace")
    sys.stderr.write("Probe abgelehnt: " + body[:300] + "\n")
    sys.exit(1)
m = d["business_discovery"]["media"]["data"]
print(f"   OK: {len(m)} Beiträge gelesen, jüngster vom {m[0]['timestamp'][:10] if m else '–'}, Bild-Adresse {'ja' if m and m[0].get('media_url') else 'nein'}")
PY

echo "4/4 Lege den Schlüssel in den Tresor (${SECRET}) …"
if ! gcloud secrets describe "$SECRET" >/dev/null 2>&1; then
  gcloud secrets create "$SECRET" --replication-policy=automatic >/dev/null
fi
gcloud secrets add-iam-policy-binding "$SECRET" \
  --member="serviceAccount:${DIENSTKONTO}" --role=roles/secretmanager.secretAccessor >/dev/null
printf '%s' "$ERG" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(json.dumps({"token": d["token"], "ig_user_id": d["ig_user_id"]}), end="")' \
  | gcloud secrets versions add "$SECRET" --data-file=- >/dev/null
echo "Fertig. Der Montagslauf in instagram.yml liest ab jetzt die Club-Profile."
