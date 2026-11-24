"""Gemeinsame Hilfen für install.py und add_account.py (laufen in der Google Cloud Shell).

Nichts davon läuft auf dem Server selbst. Der Server besteht nur aus app.py.
"""

import getpass
import imaplib
import json
import os
import re
import smtplib
import ssl
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

DIENST, REGION = "mailmaster", "us-central1"
ORDNER = Path(__file__).resolve().parent

# Hinweise je Anbieter. Die Anbieter ändern ihre Seiten gelegentlich, deshalb nur als Wegweiser.
ANBIETER = {
    "gmail.com": ("Gmail", "https://myaccount.google.com/apppasswords",
                  "Gmail braucht ein App-Passwort. Dafür muss die Bestätigung in zwei Schritten eingeschaltet sein."),
    "googlemail.com": ("Gmail", "https://myaccount.google.com/apppasswords",
                       "Gmail braucht ein App-Passwort. Dafür muss die Bestätigung in zwei Schritten eingeschaltet sein."),
    "yahoo.com": ("Yahoo", "https://login.yahoo.com/account/security",
                  "Yahoo braucht ein App-Passwort (Kontosicherheit → App-Passwort erstellen)."),
    "yahoo.de": ("Yahoo", "https://login.yahoo.com/account/security",
                 "Yahoo braucht ein App-Passwort (Kontosicherheit → App-Passwort erstellen)."),
    "web.de": ("WEB.DE", "https://web.de",
               "WEB.DE: In den Einstellungen IMAP aktivieren und ein App-Passwort anlegen (Sicherheit)."),
    "gmx.de": ("GMX", "https://gmx.net",
               "GMX: In den Einstellungen POP3/IMAP-Zugriff erlauben und ein App-Passwort anlegen."),
    "gmx.net": ("GMX", "https://gmx.net",
                "GMX: In den Einstellungen POP3/IMAP-Zugriff erlauben und ein App-Passwort anlegen."),
    "freenet.de": ("Freenet", "https://webmail.freenet.de",
                   "Freenet: Meist funktioniert das normale Passwort. Nur dein eigenes verwenden."),
}


def gcloud(*args, check=True):
    """Führt gcloud aus und gibt das Ergebnis zurück (Ausgabe wird aufgefangen)."""
    return subprocess.run(["gcloud", *args], capture_output=True, text=True, check=check)


class _NurHttps(urllib.request.HTTPRedirectHandler):
    """Folgt Weiterleitungen nur auf https. Verhindert, dass eine Konfiguration über http geladen wird."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith("https://"):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OEFFNER = urllib.request.build_opener(_NurHttps)

# Bekannte Anbieter: deren Server dürfen auch dann genutzt werden, wenn sie nicht zur Mail-Domain gehören
BEKANNTE_ANBIETER = ("gmail.com", "google.com", "googlemail.com", "yahoo.com", "yahoo.de", "web.de", "gmx.net",
                     "gmx.de", "freenet.de", "mx.freenet.de", "outlook.com", "office365.com", "icloud.com",
                     "t-online.de", "ionos.de", "1und1.de", "strato.de", "mailbox.org", "posteo.de")


def vertrauenswuerdig(host, domain):
    """Gehört der Server zur Mail-Domain oder zu einem bekannten Anbieter?"""
    host, domain = host.lower().rstrip("."), domain.lower()
    zulaessig = (domain,) + BEKANNTE_ANBIETER
    return any(host == z or host.endswith("." + z) for z in zulaessig)


def lade_xml(url):
    """Lädt eine Konfigurationsdatei des Anbieters. Zu große Dateien und solche mit Entitäts-Deklarationen
    (Angriffe wie XXE oder Billion Laughs) werden abgelehnt, bevor sie ausgewertet werden.
    Weiterleitungen sind nur auf https erlaubt."""
    try:
        with _OEFFNER.open(url, timeout=8) as antwort:
            if not antwort.geturl().lower().startswith("https://"):
                return None
            daten = antwort.read(200_000 + 1)
        if len(daten) > 200_000 or b"<!doctype" in daten.lower() or b"<!entity" in daten.lower():
            return None
        return ET.fromstring(daten)
    except Exception:
        return None


def server_aus_xml(wurzel):
    imap = wurzel.find(".//incomingServer[@type='imap']")
    smtp = wurzel.find(".//outgoingServer[@type='smtp']")
    if imap is None or not imap.findtext("hostname"):
        return None
    ergebnis = {"host": imap.findtext("hostname"), "port": int(imap.findtext("port") or 993)}
    if smtp is not None and smtp.findtext("hostname"):
        ergebnis["smtp_host"] = smtp.findtext("hostname")
        ergebnis["smtp_port"] = int(smtp.findtext("port") or 587)
        ergebnis["smtp_starttls"] = (smtp.findtext("socketType") or "").upper() != "SSL"
    return ergebnis


def erkenne_server(domain):
    """Findet IMAP- und SMTP-Server wie Thunderbird (öffentliche Konfigurationsdateien), sonst imap.<domain>."""
    quellen = [
        f"https://autoconfig.thunderbird.net/v1.1/{domain}",
        f"https://autoconfig.{domain}/mail/config-v1.1.xml",
        f"https://{domain}/.well-known/autoconfig/mail/config-v1.1.xml",
    ]
    for url in quellen:
        wurzel = lade_xml(url)
        if wurzel is not None:
            gefunden = server_aus_xml(wurzel)
            if gefunden:
                gefunden.setdefault("smtp_host", f"smtp.{domain}")
                gefunden.setdefault("smtp_port", 587)
                gefunden.setdefault("smtp_starttls", True)
                return gefunden
    return {"host": f"imap.{domain}", "port": 993,
            "smtp_host": f"smtp.{domain}", "smtp_port": 587, "smtp_starttls": True}


def teste_imap(server, adresse, passwort):
    """Gibt None zurück, wenn die Anmeldung klappt, sonst die Fehlermeldung."""
    try:
        imap = imaplib.IMAP4_SSL(server["host"], server["port"], ssl_context=ssl.create_default_context())
        imap.login(adresse, passwort)
        imap.logout()
        return None
    except Exception as fehler:
        return str(fehler)


def teste_smtp(server, adresse, passwort):
    try:
        kontext = ssl.create_default_context()
        if server.get("smtp_starttls", True):
            with smtplib.SMTP(server["smtp_host"], server.get("smtp_port", 587), timeout=20) as smtp:
                smtp.starttls(context=kontext)
                smtp.login(adresse, passwort)
        else:
            with smtplib.SMTP_SSL(server["smtp_host"], server.get("smtp_port", 465), context=kontext, timeout=20) as smtp:
                smtp.login(adresse, passwort)
        return None
    except Exception as fehler:
        return str(fehler)


def konto_abfragen(vorhandene=()):
    """Fragt ein Postfach ab. Leere Adresse = fertig (gibt None zurück). Das Passwort wird nicht angezeigt."""
    while True:
        adresse = input("\nE-Mail-Adresse (leer lassen, wenn du fertig bist): ").strip()
        if not adresse:
            return None
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", adresse):
            print("Das sieht nicht wie eine E-Mail-Adresse aus. Bitte noch einmal.")
            continue
        if adresse in vorhandene:
            print("Dieses Postfach ist schon eingetragen.")
            continue
        domain = adresse.split("@")[1].lower()
        if domain in ANBIETER:
            name, seite, hinweis = ANBIETER[domain]
            print(f"\n{hinweis}\nSeite beim Anbieter: {seite}")
        else:
            print("\nFalls dein Anbieter ein App-Passwort verlangt, erstelle zuerst eines. "
                  "Das Passwort bleibt bei dir und kommt nie in den Chat.")
        print("Server werden gesucht ...")
        server = erkenne_server(domain)
        print(f"Gefunden: {server['host']} (Empfangen), {server['smtp_host']} (Senden)")
        fremd = [h for h in (server["host"], server["smtp_host"]) if not vertrauenswuerdig(h, domain)]
        if fremd:
            print(f"\nACHTUNG: {', '.join(fremd)} gehört weder zu {domain} noch zu einem bekannten Anbieter.")
            print("Dein Passwort würde an diesen Server geschickt. Fahre nur fort, wenn du ihn kennst, "
                  "zum Beispiel weil dein Hoster ihn nennt.")
            if not input("Diesem Server das Passwort schicken? (j/n): ").strip().lower().startswith("j"):
                print("Dieses Postfach wird übersprungen.")
                continue
        passwort = getpass.getpass(f"Passwort für {adresse} (wird nicht angezeigt): ")
        if not passwort:
            print("Kein Passwort eingegeben.")
            continue
        fehler = teste_imap(server, adresse, passwort)
        if fehler:
            print(f"Anmeldung fehlgeschlagen: {fehler}")
            if input("Nochmal versuchen? (j/n): ").strip().lower().startswith("j"):
                continue
            print("Dieses Postfach wird übersprungen.")
            continue
        warnung = teste_smtp(server, adresse, passwort)
        if warnung:
            print(f"Empfangen klappt, Senden nicht sicher: {warnung}\n"
                  "Das Postfach wird trotzdem eingetragen. Senden kann später noch scheitern.")
        else:
            print("Empfangen und Senden: Anmeldung klappt.")
        konto = {"label": adresse, "user": adresse, "password": passwort}
        konto.update(server)
        return konto


def lese_env():
    """Liest die Einstellungen des laufenden Dienstes. Leeres Wörterbuch, wenn es den Dienst noch nicht gibt."""
    ergebnis = gcloud("run", "services", "describe", DIENST, "--region", REGION, "--format", "json", check=False)
    if ergebnis.returncode != 0:
        return {}
    env = json.loads(ergebnis.stdout)["spec"]["template"]["spec"]["containers"][0].get("env", [])
    return {e["name"]: e.get("value", "") for e in env}


def dienst_adresse():
    ergebnis = gcloud("run", "services", "describe", DIENST, "--region", REGION,
                      "--format", "value(status.url)", check=False)
    return ergebnis.stdout.strip() if ergebnis.returncode == 0 else ""


def veroeffentlichen(werte):
    """Veröffentlicht app.py mit diesen Einstellungen. JSON ist gültiges YAML, so bleiben Sonderzeichen erhalten."""
    fd, pfad = tempfile.mkstemp(suffix=".yaml")
    try:
        with os.fdopen(fd, "w") as f:
            for name, wert in werte.items():
                f.write(f"{name}: {json.dumps(wert)}\n")
        subprocess.run(["gcloud", "run", "deploy", DIENST, "--source", str(ORDNER), "--region", REGION,
                        "--allow-unauthenticated", "--max-instances", "1", "--memory", "256Mi",
                        "--env-vars-file", pfad], check=True)
    finally:
        os.remove(pfad)


def zeige_verbindungsadresse(werte):
    adresse = dienst_adresse()
    token = werte.get("MAILMASTER_TOKEN", "")
    if not adresse or not token:
        print("Die Adresse konnte nicht ermittelt werden.")
        return
    print("\n" + "=" * 60)
    print("Diese Adresse trägst du in Claude als Konnektor ein:\n")
    print(f"   {adresse}/mcp/{token}\n")
    print("Sie ist wie ein Passwort: Nur in Claude eintragen, nicht in Chats,")
    print("E-Mails oder Screenshots. Wer sie kennt, kommt an deine Postfächer.")
    print("Später erneut anzeigen: python3 install.py --adresse")
    print("=" * 60)


def abbrechen(text):
    print(text)
    sys.exit(1)
