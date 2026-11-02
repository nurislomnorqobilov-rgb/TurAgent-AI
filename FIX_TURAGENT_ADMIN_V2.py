"""TurAgent AI Cloudflare: create the first admin safely on Windows.

Run from the folder containing wrangler.jsonc and package.json:
    python FIX_TURAGENT_ADMIN_V2.py

No third-party Python packages. Token and password are never printed or saved.
"""
from __future__ import annotations

import getpass
import json
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_URL = "https://turagent-ai.amerikankanal063.workers.dev"
WORKER_NAME = "turagent-ai"


def put_secret(token: str) -> tuple[bool, str]:
    """Use bytes pipes to avoid cp1252 UnicodeDecodeError on Windows.

    The secret is passed through stdin, not command-line arguments.
    """
    try:
        cp = subprocess.run(
            ["npx.cmd", "wrangler", "secret", "put", "ADMIN_SETUP_TOKEN", "--name", WORKER_NAME],
            input=(token + "\n").encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )
    except FileNotFoundError:
        return False, "npx.cmd topilmadi. Node.js/npm va loyiha papkasini tekshiring."
    except subprocess.TimeoutExpired:
        return False, "Wrangler 120 soniyada tugamadi; Cloudflare aloqa holatini tekshiring."
    except OSError as exc:
        return False, f"Wrangler ishga tushmadi: {type(exc).__name__}"
    # Decode robustly even when Wrangler emits UTF-8 emoji on a cp1252 console.
    output = (cp.stdout or b"").decode("utf-8", errors="replace")
    errors = (cp.stderr or b"").decode("utf-8", errors="replace")
    if cp.returncode != 0:
        # Deliberately do not print raw Wrangler logs, which could include private values.
        return False, f"Wrangler exit code {cp.returncode}; 'npx.cmd wrangler whoami' ni tekshiring."
    # Wrangler writes an explicit confirmation when the secret was uploaded.
    if not (re.search(r"Success", output, re.I) or re.search(r"Success", errors, re.I)):
        return False, "Wrangler xato kod qaytarmadi, lekin secret yuklanganini tasdiqlamadi."
    return True, "Secret Cloudflare'ga yuklandi."


def create_admin(url: str, token: str, name: str, email: str, password: str) -> bool:
    body = json.dumps({"token": token, "name": name, "email": email, "password": password}).encode("utf-8")
    url = url.rstrip("/")
    for attempt in range(1, 5):
        req = urllib.request.Request(
            url + "/api/admin/bootstrap",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Turagent-Request": "1",
                "Origin": url,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as res:
                result = json.loads(res.read().decode("utf-8"))
                if res.status == 201 and result.get("ok") is True:
                    print("\nMUVAFFAQIYAT: Administrator yaratildi!")
                    print("Sayt:", url)
                    print("Saytga email va admin parolingiz orqali kiring.")
                    return True
                print("XATO: Kutilmagan HTTP status:", res.status)
                return False
        except urllib.error.HTTPError as ex:
            try:
                response = json.loads(ex.read().decode("utf-8", errors="replace"))
                detail = str(response.get("error", ""))[:180]
            except (ValueError, UnicodeError):
                detail = ""
            if ex.code == 403 and detail == "Invalid admin setup token" and attempt < 4:
                print(f"Secret yangi Worker versiyasiga tarqalishini kutyapmiz ({attempt}/3)...")
                time.sleep(3 * attempt)
                continue
            print(f"XATO: HTTP {ex.code}: {detail or 'Server so‘rovni rad etdi'}")
            if ex.code == 409:
                print("Administrator allaqachon yaratilgan yoki bu email ro‘yxatdan o‘tgan.")
            elif ex.code == 403:
                print("Token mos emas. Wrangler loyihasi, Worker nomi va secret ulanishini tekshiring.")
            return False
        except (urllib.error.URLError, TimeoutError, OSError) as ex:
            print("XATO: Cloudflare API ga ulanib bo‘lmadi:", type(ex).__name__)
            return False
    return False


def main() -> int:
    if not Path("wrangler.jsonc").exists() or not Path("package.json").exists():
        print("XATO: wrangler.jsonc va package.json joylashgan Cloudflare loyiha papkasiga kiring.")
        return 1
    print("TurAgent AI — ADMIN SETUP (Windows UTF-8 tuzatildi)")
    print("Yangi token avtomatik yaratiladi va hech qayerga chiqarilmaydi.")
    name = input("Admin ismi: ").strip()
    email = input("Admin email: ").strip()
    password = getpass.getpass("Admin paroli (12+ belgi, yashirin): ")
    confirmation = getpass.getpass("Admin parolini takrorlang: ")
    if len(name) < 2 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(password) < 12 or password != confirmation:
        print("XATO: Ism, email yoki parol noto‘g‘ri. Parollar bir xil va 12+ belgili bo‘lsin.")
        return 1
    token = secrets.token_urlsafe(40)
    print("Cloudflare ADMIN_SETUP_TOKEN yangilanmoqda...")
    ok, explanation = put_secret(token)
    print(explanation)
    if not ok:
        return 1
    print("Admin yaratilmoqda...")
    return 0 if create_admin(DEFAULT_URL, token, name, email, password) else 1


if __name__ == "__main__":
    raise SystemExit(main())
