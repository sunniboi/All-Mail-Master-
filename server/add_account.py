"""Trägt ein weiteres Postfach in einen laufenden All Mail Master (AMM) ein.

Aufruf in der Cloud Shell, im Ordner server/:
    python3 add_account.py

Das Skript fragt Adresse und Passwort ab (das Passwort wird nicht angezeigt),
testet die Anmeldung und aktualisiert den Dienst. Andere Postfächer und
Einstellungen bleiben unverändert.
"""

import json
import sys

import amm_tools as t


def main():
    werte = t.lese_env()
    if not werte.get("MAILMASTER_TOKEN"):
        t.abbrechen("Es läuft noch kein Dienst. Zuerst: python3 install.py")
    konten = json.loads(werte.get("MAILMASTER_ACCOUNTS", "[]"))
    neu = []
    while True:
        konto = t.konto_abfragen([k["user"] for k in konten + neu])
        if konto is None:
            break
        neu.append(konto)
        print(f"Vorgemerkt: {konto['user']}.")
    if not neu:
        t.abbrechen("Kein neues Postfach angegeben. Nichts wurde geändert.")
    werte["MAILMASTER_ACCOUNTS"] = json.dumps(konten + neu)
    print(f"\n{len(neu)} Postfach/Postfächer werden eingetragen, der Dienst wird aktualisiert ...")
    t.veroeffentlichen(werte)
    print("Fertig. In Claude den Konnektor trennen, neu verbinden und einen neuen Chat starten.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        sys.exit(1)
