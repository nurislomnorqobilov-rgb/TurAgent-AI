# TurAgent AI v5.2 — Windows'da yangilash va ishga tushirish

## 1. ZIP ichidagi to‘g‘ri papkani ochish

ZIPdan ajratganingizdan so‘ng `TurAgent-AI` papkasiga kiring. Shu papkada `START_WINDOWS.bat`, `.env.example`, `server`, `public`, `tests` bo‘lishi shart. VS Code orqali **shu ichki** `TurAgent-AI` papkasini oching.

## 2. Oldingi loyihadan konfiguratsiyani saqlash

Shaxsiy `.env` faylingizni eski loyihadan yangi `TurAgent-AI` papkasiga nusxalang. ZIP ichida maxfiy kalitlar bo‘lmaydi. `.env` bo‘lmasa `.env.example` ni `.env` deb nusxalab, kerakli maydonlarni to‘ldiring.

AI uchun `.env`da quyidagilar mavjud bo‘lishi kerak:

```
GEMINI_API_KEY=YOUR_OWN_KEY
GEMINI_MODEL=gemini-3.5-flash-lite
```

**API kalitni hech kimga yubormang.** Ishlab turgan `.env` faylingizni bekorga o‘zgartirmang.

## 3. Oldingi serverni to‘xtatish

Eski v5.1 terminalida `Ctrl+C` bosing. 8000-portda eski server qolib ketmasin.

## 4. Yangi serverni ishga tushirish

VS Code terminalida:

```powershell
.\START_WINDOWS.bat
```

Brauzer: http://localhost:8000

Yangi kod darhol ko‘rinmasa `Ctrl+F5` bosib yangilang.

## 5. Testlar

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Kutiladigan yakun: `Ran 12 tests` / `OK` (mahalliy muhitda PostgreSQL qo‘shimcha sozlamalarsiz ishlamaydi — lokal testda SQLite qo‘llanadi).

## 6. AI chatdagi jonli yozilishni tekshirish

Pastdagi AI yordamchi tugmasini bosing. Oddiy erkin savol bering, masalan: "TurAgent AI sayohat paketlarini qanday bron qilaman?". Gemini API haqiqiy stream javob qaytarsa, matn kelgan bo‘laklari bilan ketma-ket chiqariladi.

Tayyor tezkor savollar Google'ga yuborilmaydi; ular saytdagi tasdiqlangan javoblarni tezkor yozish animatsiyasida ko‘rsatadi. Internet/API stream ishlamagan holatlarda haqiqiy AI javobi kafolatlanmaydi va foydalanuvchiga xatolik xabari ko‘rsatiladi.

## 7. Tasvir va video haqida

V5.1 dagi haqiqiy sayohat videosi CDN havolasi saqlangan. Agar video chiqmasa internet aloqasini tekshiring yoki eski loyihadagi `DOWNLOAD_REAL_VIDEO_WINDOWS.bat` orqali bir marta kompyuterga ko‘chiring.

## 8. Boshqa xatolar

Terminaldan faqat maxfiy bo‘lmagan HTTP/xatolik matnini yuboring. Hech qachon `.env`, API key, parol, session cookie yoki Authorization headerni ko‘chirmang.

Barcha yangilanishlar ro‘yxati: `UI_HISOBOT_V52.md`.
