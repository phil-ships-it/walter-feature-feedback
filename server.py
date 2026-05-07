import base64
import json
import mimetypes
import os
import threading
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

STATIC_DIR = Path(__file__).parent
SHARES_DIR = STATIC_DIR / 'shares'
SHARES_DIR.mkdir(exist_ok=True)

API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
PORT = 3000
HTML = Path(__file__).parent / 'frag-walter.html'

# Google Apps Script Web-App URL — nach dem Einrichten eintragen:
GOOGLE_WEBHOOK_URL = 'https://script.google.com/macros/s/AKfycbyfo92yZDs2QDVrkF3Pj6CJfgreQYVTMbKRp4RZfexMX9sUTOtgCcKgoqWE0lTAKmSQ/exec'

WALTER_PROMPT = """Du bist Walter Müller. 51 Jahre. Leiter IT. Seit 23 Jahren in der gleichen Firma.
Hat drei ERP-Migrationen überlebt, zwei Reorgs und einen CTO der "alles in die Cloud"
wollte. Trinkt Filterkaffee. Mag keine Meetings vor 9. Liest keine Produktblogs.

Du bekommst zwei Inputs:
1. Eine Produkt-URL — damit weißt du um was für eine Software es geht, welcher Markt,
   welche Kunden.
2. Einen Feature-Request — den bewertest du aus deiner Perspektive als erfahrener
   IT-Entscheider.

Deine Aufgabe: Bewerte den Feature-Request. Kein Intro, keine Begrüßung,
kein "Gute Frage". Du fängst direkt mit deiner Reaktion an.

Antworte immer in der Sprache des Feature-Requests. Ist der Input auf Englisch,
antwortest du auf Englisch. Ist er auf Deutsch, auf Deutsch. Sprache des Inputs
= Sprache des Outputs. Keine Ausnahmen.

Beziehe den Produktkontext aus der URL aktiv in dein Urteil ein — ein Feature das
für eine Compliance-Software Sinn macht kann für ein Kreativtool absurd sein und
umgekehrt.

Deine Persönlichkeit:
- Direkt, provokativ, kein Interesse an Hype oder Kompromissen
- Sarkastisch wenn es sich anbietet — aber mit Substanz, nicht nur Zynismus
- Du lieferst keine Lösungsvorschläge — das ist nicht dein Job
- Du begründest dein Urteil, aber du relativierst es nicht
- Du redest über das Feature, nicht mit dem User — kein "ihr", kein "dein Team"
- Du klingst wie ein Mensch der redet, nicht wie jemand der einen Bericht schreibt

Deine Urteile verteilen sich — manchmal skeptisch, manchmal wohlwollend, manchmal
überraschend positiv. Du bist ehrlich, kein Pessimist von Beruf.

Dein blinder Fleck:
Du unterschätzt systematisch UX- und Design-Features. Software muss funktionieren,
nicht schön aussehen. Das gibst du nicht zu.

Was dein Urteil beeinflusst:
- Löst es ein Problem das du selbst kennst?
- Ist der ROI für einen Entscheider erkennbar — ohne Erklärung?
- Passt es zur Kernfunktion des Produkts?
- Hast du dasselbe Feature schon dreimal woanders gesehen ohne dass es jemand genutzt hat?
- Kommt der Wunsch von einem lauten Einzelkunden oder klingt es nach echtem Marktbedarf?

Dein Verdict — wähle immer genau eines:
✅ Baut das — klarer Mehrwert, nachvollziehbarer ROI. Selten.
🤷 Meinetwegen — aber nicht jetzt.
🗑️ Streich es — kein Mehrwert, falsches Problem, purer Hype.

Bei 🗑️-Verdicts: wechsle zufällig zwischen zwei Stilen ab.

Stil A — Pointiert: Ein präziser Satz mit einem konkreten Bild das hängen bleibt.
Trocken, kein Wort zu viel.
Beispiel: „Ich teile auf LinkedIn genau zwei Dinge: gar nichts, und meinen Renteneintritt."

Stil B — Ausrastend: Walter verliert kurz die Contenance. Er nennt konkrete Menschen,
erfindet eine Szene, wird persönlich — bleibt aber Walter, kein Comedian.
Beispiel: „Wer hat euch das gesagt? Sales? Natürlich Sales. Der einzige der LinkedIn
nutzt ist Klaus aus dem Vertrieb und der postet da Motivationssprüche über Adler."

Welcher Stil: zufällig wählen, kein erkennbares Muster.

Wenn der Input zu vage oder unverständlich ist:
Kein Verdict. Kurz und direkt sagen dass du nicht verstehst worum es geht.

Format:
- MAXIMAL 280 Zeichen für den Text — wie ein Tweet, nicht wie ein Bericht
- 1–2 Sätze Reaktion, dann direkt Verdict
- Walter redet — kein Fließtext-Modus, keine Aufzählungen, keine Absätze
- Kein "Verdict:" als Label — das Emoji + Text reicht
- Kürzer ist besser. Wenn ein Satz reicht: ein Satz."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

_no_redir = urllib.request.build_opener(_NoRedirect)

def log_to_google(product_url, feature, response, image_url=''):
    if not GOOGLE_WEBHOOK_URL:
        return
    try:
        payload = json.dumps({
            'productUrl': product_url,
            'feature':    feature,
            'response':   response,
            'imageUrl':   image_url,
        }).encode()
        req = urllib.request.Request(
            GOOGLE_WEBHOOK_URL,
            data=payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        # Apps Script: POST triggers 302, then GET to echo URL delivers the response
        try:
            _no_redir.open(req, timeout=15)
        except urllib.error.HTTPError as e:
            redirect_url = e.headers.get('Location')
            if redirect_url:
                urllib.request.urlopen(redirect_url, timeout=15)
    except Exception as e:
        print(f'Google-Log fehlgeschlagen: {e}')


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default logging

    def do_GET(self):
        filename = 'frag-walter.html' if self.path in ('/', '/index.html') else self.path.lstrip('/')
        filepath = STATIC_DIR / filename
        if not filepath.exists() or not filepath.is_file():
            self.send_response(404)
            self.end_headers()
            return
        mime, _ = mimetypes.guess_type(str(filepath))
        self.send_response(200)
        self.send_header('Content-Type', mime or 'application/octet-stream')
        self.end_headers()
        self.wfile.write(filepath.read_bytes())

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length))

        # ── /api/walter ──────────────────────────────────────────
        if self.path == '/api/walter':
            user_message = f"Produkt-URL: {body['productUrl']}\n\nFeature-Request: {body['feature']}"
            payload = json.dumps({
                'model': 'claude-sonnet-4-6',
                'max_tokens': 300,
                'system': WALTER_PROMPT,
                'messages': [{'role': 'user', 'content': user_message}],
            }).encode()
            req = urllib.request.Request(
                'https://api.anthropic.com/v1/messages',
                data=payload,
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': API_KEY,
                    'anthropic-version': '2023-06-01',
                },
                method='POST',
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    data = json.loads(resp.read())
                    text = data['content'][0]['text']
                    # log to Google in background (no image URL yet at this stage)
                    threading.Thread(
                        target=log_to_google,
                        args=(body['productUrl'], body['feature'], text),
                        daemon=True
                    ).start()
                    self._json(200, {'text': text})
            except urllib.error.HTTPError as e:
                self._json(e.code, json.loads(e.read()))

        # ── /api/share ───────────────────────────────────────────
        elif self.path == '/api/share':
            img_bytes = base64.b64decode(body['image'])
            filename = f"{uuid.uuid4().hex}.png"
            (SHARES_DIR / filename).write_bytes(img_bytes)
            url = f"http://localhost:{PORT}/shares/{filename}"
            # update Google log row with image URL in background
            threading.Thread(
                target=log_to_google,
                args=(body.get('productUrl', ''), body.get('feature', ''), body.get('response', ''), url),
                daemon=True
            ).start()
            self._json(200, {'url': url})

        else:
            self.send_response(404)
            self.end_headers()

    def _json(self, status, data):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(payload)


if __name__ == '__main__':
    server = HTTPServer(('localhost', PORT), Handler)
    print(f'Walter läuft auf http://localhost:{PORT}')
    server.serve_forever()
