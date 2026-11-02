"""One-command safe Cloudflare TurAgent AI initial administrator setup.
Run from the folder containing wrangler.jsonc and package.json.
Does not print or save the bootstrap token or admin password.
"""
from __future__ import annotations

import getpass
import json
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

URL = 'https://turagent-ai.amerikankanal063.workers.dev'


def main():
    if not Path('wrangler.jsonc').is_file() or not Path('package.json').is_file():
        print('XATO: Avval Cloudflare v6 loyiha papkasini oching (wrangler.jsonc va package.json kerak).')
        return 1

    print('TURAGENT AI — ADMIN YARATISHNI TUZATISH')
    print('Eski maxfiy tokenni almashtiramiz; yangi token hech qayerga chiqarilmaydi.')
    name = input('Administrator ismi: ').strip()
    email = input('Administrator emaili: ').strip()
    password = getpass.getpass('Yangi admin paroli (kamida 12 belgi, ekranda ko‘rinmaydi): ')
    confirmation = getpass.getpass('Admin parolini takrorlang: ')
    if len(name) < 2 or '@' not in email or len(password) < 12 or password != confirmation:
        print('XATO: Ism, email yoki parol noto‘g‘ri; parollar bir xil va kamida 12 belgili bo‘lishi kerak.')
        return 1

    token = secrets.token_urlsafe(40)
    print('Cloudflare Worker uchun maxfiy token xavfsiz ravishda yangilanmoqda...')
    try:
        update = subprocess.run(
            ['npx.cmd', 'wrangler', 'secret', 'put', 'ADMIN_SETUP_TOKEN'],
            input=token + '\n', text=True, capture_output=True, timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        print('XATO: Wrangler ishga tushmadi. npm.cmd install va npx.cmd wrangler whoami ni tekshiring.')
        return 1
    if update.returncode != 0 or 'Success' not in (update.stdout + update.stderr):
        print('XATO: Cloudflare secret yangilanmadi. Wrangler hisobingizni tekshiring.')
        print('Wrangler exit code:', update.returncode)
        return 1

    print('Token yangilandi. Admin yaratilmoqda...')
    payload = json.dumps({'token': token, 'name': name, 'email': email, 'password': password}).encode()
    request = urllib.request.Request(
        URL + '/api/admin/bootstrap', data=payload, method='POST',
        headers={'Content-Type': 'application/json', 'Origin': URL, 'X-Turagent-Request': '1'},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                result = json.load(response)
                if response.status == 201 and result.get('ok'):
                    print('MUVAFFAQIYAT: Admin yaratildi!')
                    print('Sayt:', URL)
                    print('Saytga kirib o‘z admin emailingiz va parolingiz bilan login qiling.')
                    return 0
                print('Kutilmagan HTTP natija:', response.status)
                return 1
        except urllib.error.HTTPError as error:
            try:
                detail = json.load(error).get('error', '')
            except Exception:
                detail = ''
            if error.code == 403 and detail == 'Invalid admin setup token' and attempt < 2:
                print('Cloudflare secret tarqalishini kutib qayta tekshirilmoqda...')
                time.sleep(3)
                continue
            print('XATO: HTTP', error.code, '-', detail or 'API xatosi')
            if error.code == 409:
                print('Admin allaqachon mavjud bo‘lishi mumkin; yangi admin yaratish shart emas.')
            elif error.code == 403:
                print('Cloudflare Worker tokeni bilan API tokeni mos kelmadi. Worker name va wrangler config tekshiring.')
            return 1
        except Exception as error:
            print('XATO: Serverga ulanib bo‘lmadi:', type(error).__name__)
            return 1
    return 1


if __name__ == '__main__':
    sys.exit(main())
