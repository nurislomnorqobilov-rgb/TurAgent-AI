# TurAgent AI v5 — Windows 11 uchun 0 dan ishga tushirish

**Versiya:** v5 UI/AI improvements. **Kompyuter:** 4 GB RAMli Windows 11; mahalliy sinov uchun Docker shart emas. Saytning haqiqiy to‘lovlari yo‘q (Payme/Click/Visa faqat SIMULYATSIYA). Google OAuth/Gemini/SMTP tashqi kalitlarisiz faol bo‘lmaydi.

## 1) ZIP faylni ajratish

1. `TurAgent-AI-v5-Premium-Updated.zip` faylini Windows `Downloads` papkasiga yuklab oling.
2. Right click → **Extract All**.
3. Ichidagi `TurAgent-AI` papkasini VS Code → **File → Open Folder** bilan oching.
4. Papkaning to‘g‘ri ekanini tekshiring: `START_WINDOWS.bat`, `public`, `server`, `.env.example` ko‘rinadi.

PowerShell terminalida hozirgi papkani `pwd`, fayllarni `dir` bilan ko‘ring. Agar terminal ZIP tashqi papkasida bo‘lsa, `cd .\TurAgent-AI` yozing.

## 2) Python tekshirish

VS Code terminalida:

```powershell
python --version
```

**Python 3.11+** talab qilinadi. Windows Python bo‘lmasa python.org’dan o‘rnating (odatda ~100–150 MB install; qo‘shimcha paketlar lokal test uchun kerak emas).

## 3) `.env` faylini yaratish

`.env.example` faylidan loyiha bosh papkasida `.env` nusxa yarating. `.env`ni e’lon qilmang, hech kimga yubormang. Eski loyihadan ko‘chirilgan `.env` ham shu papkaning o‘zida bo‘lishi kerak, `server/` ichida emas.

Lokal test uchun minimal qiymatlar:

```dotenv
PUBLIC_URL=http://localhost:8000
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.8-flash
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
NOTIFY_EMAIL=assalomualaykum@gmail.com
```

`POSTGRES_PASSWORD` va `ADMIN_SETUP_TOKEN` uchun kuchli, **ikki xil** maxfiy qiymatni terminalda yarating:

```powershell
python -c "import secrets;print('POSTGRES_PASSWORD='+secrets.token_urlsafe(32));print('ADMIN_SETUP_TOKEN='+secrets.token_urlsafe(32))"
```

Ko‘rsatilgan qiymatlarni `.env`ga qo‘ying, terminal natijasini boshqalar bilan ulashmang.

## 4) Lokal serverni ishga tushirish

Loyiha bosh papkasidagi VS Code PowerShell terminalida:

```powershell
.\START_WINDOWS.bat
```

Yoki `.bat` faylini ikki marta bosing. Brauzerda: **http://localhost:8000**. Terminalni yopinganda server to‘xtaydi. Agar `START_WINDOWS.bat not recognized` desa, terminalingizda `dir` bilan fayl mavjudligini tekshiring (tashqi papkada emas, ichki `TurAgent-AI` papkasida bo‘lishingiz kerak).

`Ctrl+C` — serverni to‘xtatish. Port 8000 boshqa eski loyiha tomonidan ishlatilsa, avval eski terminalni to‘xtating. Yangilangan faylni ko‘rish uchun brauzerda `Ctrl+F5` bosing.

**Lokal test ma’lumotlari** `local-dev.sqlite3` ichida saqlanadi. Uni o‘chirish ro‘yxatdan o‘tgan sinov akkauntlari va bronlarni yo‘qotadi. Production’da PostgreSQL ishlatiladi, SQLite avtomatik PostgreSQLga ko‘chmaydi.

## 5) Gemini AI ulash

1. Rasmiy sahifa: https://aistudio.google.com/api-keys . O‘z hisobingiz vakolatlariga ko‘ra API kalit yarating yoki bor kalitni oling.
2. `.env`ga shuni kiriting: `GEMINI_API_KEY=...` (faqat kalitning o‘zi, qo‘shtirnoqsiz).
3. `GEMINI_MODEL=gemini-3.8-flash` qoldiring yoki hisobingiz uchun ishlaydigan modelni belgilang; boshqa mavjud zaxira modellarni server sinab ko‘radi.
4. **Serverni qayta ishga tushiring** (`Ctrl+C` → `.\START_WINDOWS.bat`).
5. Kalit borligini oshkor qilmay tekshirish uchun: `.\CHECK_SETUP_WINDOWS.bat` yoki `python server\check_setup.py`.
6. Tekshiruv dasturi avval model ro‘yxatini ko‘radi, so‘ng **haqiqiy qisqa AI so‘rovi** yuborib uning HTTP statusini ko‘rsatadi. **Kalitni terminalga chiqarmaydi**.
7. Saytdagi **AI yordamchi** → 3 ta tayyor savol internet bo‘lmasa ham FAQ asosida javob beradi. O‘zingiz yozgan savollar esa haqiqiy Gemini API'ga yuboriladi.

Agar Gemini ishlamasa:
- `401/403`: API kalit turi, ruxsati, cheklovi yoki hisob regionini tekshiring. 2026-yil siyosatlariga ko‘ra eski unrestricted standard kalit rad etilishi mumkin; AI Studio kalit turini tekshiring.
- `404`: model hisobingiz uchun mavjud emas; `CHECK_SETUP_WINDOWS.bat` sizga qaysi model ko‘rinayotganini aytadi.
- `429`: Google bepul reja limiti tugagan; modelni almashtirish umumiy limitni aylanib o‘tmaydi.
- `DNS/TLS/network`: internet, Windows proxy/firewall, antivirus yoki servisga ulanish muammosi; server kodi uni o‘zi bartaraf etmaydi.
- `.env` o‘zgartirilgach serverni qayta ishga tushirish shart.

Gemini rasmiy model ro‘yxati: https://ai.google.dev/gemini-api/docs/models
Gemini kalit rasmiy hujjati: https://ai.google.dev/gemini-api/docs/api-key

## 6) Google orqali kirish uchun kalitlarni olish

1. https://console.cloud.google.com/ sahifasida o‘zingiz boshqaradigan Cloud loyihasini tanlang/yarating.
2. **Google Auth Platform → Branding** bo‘limida dastur nomi `TurAgent AI`, qo‘llab-quvvatlovchi email va test holatlarini sozlang.
3. **Clients → Create client → Web application**.
4. Authorized JavaScript origins: `http://localhost:8000`.
5. **Authorized redirect URIs:** `http://localhost:8000/auth/google/callback` (aynan bir xil bo‘lsin).
6. Google bergan **Client ID** va **Client Secret** ni `.env`ga qo‘ying:

```dotenv
GOOGLE_CLIENT_ID=...apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=...
```

7. `PUBLIC_URL=http://localhost:8000`. Serverni qayta ishga tushiring. OAuth consent Testing holatida bo‘lsa, ruxsat etilgan test foydalanuvchilarini qo‘shish kerak bo‘lishi mumkin.
8. Domain bilan hostingga chiqqanda HTTPS domeningizni origins va callbackga ham qo‘shing; `PUBLIC_URL`ni shu domenga o‘zgartiring.

Rasmiy qo‘llanma: https://developers.google.com/identity/openid-connect/openid-connect

## 7) Gmail SMTP uchun kerakli ma’lumotlar

Gmail’ni ishlatish uchun Google hisobingizda kerakli himoya va ruxsatlar bo‘lishi lozim:
1. Google Account → Security → **2-Step Verification**ni yoqing.
2. https://myaccount.google.com/apppasswords sahifasida mavjud bo‘lsa, alohida **App password** yarating (bu asosiy Gmail parolingiz emas). Ba’zi hisoblarda bu funksiya mavjud emas.
3. `.env`ga:

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=assalomualaykum@gmail.com
SMTP_PASSWORD=GOOGLE_APP_PASSWORD
SMTP_FROM=assalomualaykum@gmail.com
NOTIFY_EMAIL=assalomualaykum@gmail.com
```

4. **`GOOGLE_APP_PASSWORD`**ni haqiqiy App password bilan almashtiring. Uni chatga yubormang.
5. Serverni qayta ishga tushiring. SMTP ulanishi bo‘lmasa xabarlar bazaga saqlanadi, ammo email real yuborilmaydi.

Rasmiy qo‘llanma: https://support.google.com/mail/answer/185833?hl=en

## 8) Administratorni yaratish

1. `.env`da `ADMIN_SETUP_TOKEN` maxfiy qiymati to‘ldirilgan bo‘lsin.
2. Lokal server ishlasin.
3. Yangi terminalda:

```powershell
.\CREATE_ADMIN_WINDOWS.bat
```

4. Dastur so‘ragan administrator email, ism va alohida parolni o‘z kompyuteringizda kiriting.
5. Oddiy kirish sahifasida admin email bilan kirib `http://localhost:8000/#/admin` manzilini oching.

Admin yaratish tokenini boshqa odam bilan bo‘lishmang.

## 9) Sinovlar

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Barcha testlar `OK` bilan tugashi kerak. Sinov kalitlari jonli Gemini yoki Google OAuth o‘rnini bosmaydi. Dizaynni Windows Chrome’da tekshirish: bosh sahifa, `#/tours`, `#/register`, `#/admin`, til va tema o‘zgartirish, 3 ta AI tayyor savol, real API kalit bilan erkin savol.

## 10) Hosting uchun PostgreSQL (keyinchalik)

Docker Desktop bo‘lmasa ham lokal sayt ishlaydi. Hostingda PostgreSQL ishlatish uchun `.env`ga to‘liq DB credential, `PUBLIC_URL=https://...` qo‘yiladi; Docker mavjud serverda:

```bash
docker compose up --build -d
```

Ishlab chiqarish uchun HTTPS, zaxira nusxalar, konfiguratsiya, himoyalangan admin va xavfsizlik tekshiruvi zarur. Demo to‘lovlar haqiqiy pul qabul qilmaydi.

### Video haqida ochiq izoh

Yangi `hero-premium.mp4` — yuqori aniqlikdagi Santorini manzarasi asosida yaratilgan **kinematik kamerali animatsion MP4**, 1280×720, 24 fps. Bu alohida suratlarni harakatlantirishdan yasalgan video, haqiqiy kamera bilan olingan sayohat footage emas. Haqiqiy footage kerak bo‘lsa tegishli huquqga ega MP4 faylni `public/assets/hero-premium.mp4` joyiga qo‘yishingiz mumkin. 12–20 s H.264 MP4, 1280×720/1920×1080, muted autoplay va 1–8 MB kabi siqishni tavsiya qilamiz. `hero-poster.webp` fallback qoladi.

Rasmlar: Eski dizayn skrinshotidan olingan ayrim past aniqlikdagi rasmlar keskinlashtirildi va katta o‘lchamlarga moslashtirildi; bunday qayta ishlash manba suratning yo‘q bo‘lgan tafsilotlarini tiklay olmaydi. Barcha asosiy rasmlar mahalliy fayllar va tur ID bilan moslanadi; tijoratga chiqarishdan oldin tegishli manzilning litsenziyalangan haqiqiy fotosuratlari bilan yangilash tavsiya qilinadi.
