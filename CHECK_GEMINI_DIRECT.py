"""TurAgent AI Gemini direct diagnostic, Python 3.11 standard library only.
Run in the project root alongside .env; never prints or saves the API key.
"""
import json
import os
import pathlib
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent

def read_dotenv(path):
    vals = {}
    if not path.exists():
        return vals
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        vals[key] = value
    return vals

def safe_message(payload, key):
    try:
        msg = str(json.loads(payload.decode('utf-8', 'replace')).get('error', {}).get('message', ''))
    except Exception:
        return '(xato matni JSON formatida kelmadi)'
    # Avoid echoing any credentials even if provider returns them in an error.
    msg = msg.replace(key, '[HIDDEN]')
    return ' '.join(msg.split())[:320] or '(Google xato tafsilotini yubormadi)'

def request(model, key):
    # A tiny, deliberately simple prompt separates basic Google access from
    # long site-specific prompts or authentication/session handling.
    url = ('https://generativelanguage.googleapis.com/v1beta/models/'
           + urllib.parse.quote(model, safe='') + ':generateContent')
    body = {'contents': [{'role': 'user', 'parts': [{'text': 'Reply with just the word OK.'}]}],
            'generationConfig': {'maxOutputTokens': 80}}
    req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'),
                                 method='POST', headers={
                                     'x-goog-api-key': key,
                                     'Content-Type': 'application/json',
                                     'User-Agent': 'TurAgent-Diagnostic/1.0'})
    print(f'\nModel: {model} — Google API ga qisqa savol yuborilmoqda ...', flush=True)
    try:
        with urllib.request.urlopen(req, timeout=18) as resp:
            data = json.load(resp)
        text = ''.join(part.get('text', '') for cand in data.get('candidates', [])
                       for part in cand.get('content', {}).get('parts', [])
                       if isinstance(part, dict))
        print('HTTP: 200 OK')
        print('JAVOB:', 'BOR' if text.strip() else 'BO\'SH', flush=True)
        return 'ok' if text.strip() else 'empty'
    except urllib.error.HTTPError as exc:
        code = exc.code
        try:
            msg = safe_message(exc.read(4096), key)
        finally:
            exc.close()
        print('HTTP:', code)
        print('GOOGLE XABARI:', msg)
        if code == 503:
            print('SABAB: Google modeli vaqtincha mavjud emas / server yuklangan bo\'lishi mumkin.')
        elif code == 429:
            print('SABAB: API so\'rov limiti yoki kvotasi tugagan.')
        elif code in (401, 403):
            print('SABAB: API kaliti ruxsati, loyiha yoki hisob cheklovi.')
        elif code == 404:
            print('SABAB: model bu kalit yoki API versiyasida mavjud emas.')
        elif code == 400:
            print('SABAB: model yoki API so\'rov parametrlari mos kelmayapti.')
        else:
            print('SABAB: Google so\'rovni rad etdi; yuqoridagi xabarni tekshir.')
        return str(code)
    except (TimeoutError, socket.timeout) as exc:
        print('NATIJA: TIMEOUT — 18 soniya ichida API javob bermadi.')
        return 'timeout'
    except urllib.error.URLError as exc:
        print('NATIJA: NETWORK ERROR')
        print('XATO TURI:', type(exc.reason).__name__)
        return 'network'
    except OSError as exc:
        print('NATIJA: OS/NETWORK ERROR:', type(exc).__name__)
        return 'network'

def main():
    vals = read_dotenv(ROOT / '.env')
    key = os.environ.get('GEMINI_API_KEY') or vals.get('GEMINI_API_KEY', '')
    model = os.environ.get('GEMINI_MODEL') or vals.get('GEMINI_MODEL', 'gemini-3.8-flash')
    print('TurAgent AI — BEVOSITA GEMINI DIAGNOSTIKASI')
    print('Loyiha papkasi:', ROOT.name)
    print('.env mavjud:', 'HA' if (ROOT / '.env').is_file() else 'YO\'Q')
    print('API kaliti:', 'MAVJUD' if key else 'YO\'Q (maxfiy qiymat ko\'rsatilmaydi)')
    print('Tanlangan model:', model)
    if not key:
        print('XULOSA: .env dagi GEMINI_API_KEY ni tekshir.')
        return
    first = request(model, key)
    if first == 'ok':
        print('\nXULOSA: Google API bevosita ishladi. Sayt AI ishlamasa, backend so\'rov formatini yoki server konfiguratsiyasini tekshirish kerak.')
    elif first in ('503', 'timeout'):
        alternative = 'gemini-3.5-flash-lite' if model != 'gemini-3.5-flash-lite' else 'gemini-3.8-flash'
        print('\nIkkinchi model bilan taqqoslash:')
        second = request(alternative, key)
        if second == 'ok':
            print(f'\nXULOSA: Muammo birinchi model/server yukida. Sinov uchun .env da GEMINI_MODEL={alternative} qilib ko\'r.')
        else:
            print('\nXULOSA: Ikkala model natijasiga qarab tarmoq, hisob ruxsati, kvota yoki Google serveri tekshiriladi.')
    else:
        print('\nXULOSA: Yuqoridagi HTTP/status xabari Google API rad etish sababini ko\'rsatadi.')
    print('ESLATMA: Kalit, .env, Cookie va Authorization headerlarni hech kimga yuborma.')

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nTekshiruv foydalanuvchi tomonidan to\'xtatildi.')
    except Exception as exc:
        print('DIAGNOSTIKA XATOSI:', type(exc).__name__)
