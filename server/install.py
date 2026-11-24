"""Erstinstallation von All Mail Master (AMM) in der Google Cloud Shell.

Aufruf in der Cloud Shell, im Ordner server/:
    python3 install.py

Das Skript führt dich Schritt für Schritt durch:
  1. prüft, dass ein Google-Cloud-Projekt gewählt ist
  2. schaltet die nötigen Google-Dienste ein
  3. erzeugt ein geheimes Token für die Verbindungsadresse
  4. fragt deine Postfächer ab (Passwörter werden nicht angezeigt)
  5. veröffentlicht den Server und zeigt dir die Adresse für Claude

Später erneut die Adresse anzeigen:  python3 install.py --adresse
Weiteres Postfach eintragen:         python3 add_account.py
"""

import json
import secrets
import sys

import amm_tools as t


def adresse_zeigen():
    werte = t.lese_env()
    if not werte.get("MAILMASTER_TOKEN"):
        t.abbrechen("Es läuft noch kein Dienst. Zuerst: python3 install.py")
    t.zeige_verbindungsadresse(werte)


def main():
    if "--adresse" in sys.argv:
        adresse_zeigen()
        return

    projekt = t.gcloud("config", "get-value", "project", check=False).stdout.strip()
    if not projekt or projekt == "(unset)":
        t.abbrechen("Es ist noch kein Google-Cloud-Projekt gewählt.\n"
                    "Wähle oben in der Cloud Shell dein Projekt oder gib ein:\n"
                    "    gcloud config set project DEINE-PROJEKT-ID")
    if t.lese_env().get("MAILMASTER_TOKEN"):
        t.abbrechen("In diesem Projekt läuft schon ein Dienst.\n"
                    "Adresse anzeigen:        python3 install.py --adresse\n"
                    "Postfach hinzufügen:     python3 add_account.py")

    print(f"All Mail Master (AMM) wird im Projekt '{projekt}' eingerichtet.")
    print("Das dauert insgesamt einige Minuten. Das Veröffentlichen allein bis zu etwa fünf.\n")

    print("Schritt 1 von 3: Google-Dienste einschalten ...")
    t.gcloud("services", "enable", "run.googleapis.com", "cloudbuild.googleapis.com",
             "artifactregistry.googleapis.com")

    print("\nSchritt 2 von 3: Postfächer eintragen")
    print("Gib jede Adresse und ihr Passwort (bei Gmail, Yahoo, WEB.DE und GMX ein App-Passwort) ein.")
    konten = []
    while True:
        konto = t.konto_abfragen([k["user"] for k in konten])
        if konto is None:
            break
        konten.append(konto)
        print(f"Eingetragen: {konto['user']}. Du kannst jetzt ein weiteres Postfach angeben.")
    if not konten:
        t.abbrechen("Kein Postfach eingetragen. Nichts wurde veröffentlicht.")

    werte = {
        "MAILMASTER_TOKEN": secrets.token_urlsafe(32),
        "MAILMASTER_ACCOUNTS": json.dumps(konten),
        "MAILMASTER_CHAT_FREIGABE": "1",
    }

    print(f"\nSchritt 3 von 3: Server veröffentlichen ({len(konten)} Postfach/Postfächer) ...")
    t.veroeffentlichen(werte)
    t.zeige_verbindungsadresse(werte)
    print("\nNächste Schritte in Claude:")
    print("  1. Einstellungen → Konnektoren → Benutzerdefinierten Konnektor hinzufügen")
    print("  2. Name: All Mail Master. Adresse: die Adresse von oben. Authentifizierung: keine.")
    print("  3. Neuen Chat öffnen und fragen: Liste meine Postfächer auf.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAbgebrochen. Es wurde nichts verändert, was nicht schon veröffentlicht war.")
