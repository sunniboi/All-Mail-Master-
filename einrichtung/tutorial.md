# All Mail Master (AMM) einrichten

<walkthrough-tutorial-duration duration="20"></walkthrough-tutorial-duration>

## Willkommen

Diese Anleitung führt dich durch die Einrichtung deines eigenen All Mail Master Servers. Er läuft in deinem Google-Cloud-Projekt. Die Befehle unten kannst du mit einem Klick in das Terminal übernehmen.

**Wichtig:** Passwörter und die Verbindungsadresse gibst du nur hier im Terminal oder in Claude ein, nie in einen Chat.

Du brauchst vorher ein Google-Cloud-Projekt mit verknüpfter Abrechnung und, je nach Anbieter, ein App-Passwort für deine Postfächer. Die Schritte dafür stehen auf der Einrichtungsseite.

Klicke auf **Weiter**.

## Projekt wählen

Prüfe, welches Projekt aktiv ist:

```bash
gcloud config get-value project
```

Wenn dort nichts oder das falsche Projekt steht, setze es (ersetze `DEINE-PROJEKT-ID`):

```bash
gcloud config set project DEINE-PROJEKT-ID
```

## In den Ordner wechseln

Das Programm liegt schon in diesem Ordner. Wechsle dorthin:

```bash
cd ~/cloudshell_open/*/server 2>/dev/null || cd ~/claude-mailmaster/server
```

## Installation starten

Das Skript schaltet die nötigen Google-Dienste ein, fragt deine Postfächer ab und veröffentlicht den Server.

```bash
python3 install.py
```

Es fragt dich nacheinander:

- deine E-Mail-Adresse (die Server findet es selbst)
- das Passwort (beim Tippen erscheint nichts, das ist normal)
- weitere Adressen, oder Enter ohne Eingabe, wenn du fertig bist

Das Veröffentlichen dauert einige Minuten.

## In Claude verbinden

Am Ende zeigt das Skript eine lange Adresse an. Sie ist wie ein Passwort.

1. Öffne in Claude **Einstellungen → Konnektoren**.
2. Wähle **Benutzerdefinierten Konnektor hinzufügen**.
3. Name: `All Mail Master`. Adresse: die lange Adresse. Authentifizierung: keine.

Die Adresse später erneut anzeigen:

```bash
python3 install.py --adresse
```

## Testen

Öffne einen neuen Chat in Claude und schreibe: **Liste meine Postfächer auf.**

Gesendet wird erst, wenn du im Chat „absenden“ schreibst.

## Fertig

Weitere Postfächer trägst du später so ein:

```bash
python3 add_account.py
```
