# TurAgent AI v5.1 — haqiqiy video va xatolarni tuzatish

## Nima o‘zgardi?

- **Hero video endi haqiqiy 17 soniyalik Pexels Santorini footage**: `https://www.pexels.com/video/people-enjoying-the-sunset-view-at-santorini-6554717/`.
- Video manbasi: `https://videos.pexels.com/video-files/6554717/6554717-hd_1920_1080_30fps.mp4`.
- Oldingi bitta rasm silkinadigan soxta `hero-premium.mp4` o‘chirildi.
- Sayt real videoni to‘g‘ridan-to‘g‘ri internetdan o‘qiydi. Internet bo‘lmasa, tiniq poster ko‘rsatiladi.
- `DOWNLOAD_REAL_VIDEO_WINDOWS.bat` yordamida haqiqiy videoni bir martalik yuklab olib, offline ham ishlatish mumkin. Bu ixtiyoriy, hajmi internetga bog‘liq.
- Tanlangan tur va yo‘nalishlar uchun eski kichik mahalliy rasm o‘rniga mos davlatning yuqori aniqlikdagi Unsplash/Commons suratlari birinchi ko‘rsatiladi. Internet yo‘q bo‘lsa mahalliy avvalgi rasmlar fallback bo‘lib qoladi.
- Italy/Amalfi uchun Santorini rasmi emas, Amalfi Coast manzarasi qo‘yildi.
- Blog rasmlari ham yuqori aniqlikdagi versiyalardan yuklanadi.
- Test serveriga `.env`dagi real Gemini API kalitlari aralashib ketishiga yo‘l qo‘yilmaydi.
- HTTP HEAD media so‘rovlari qo‘llab-quvvatlandi.

## Windowsda ishga tushirish

1. Yangi ZIPni **alohida papka**ga Extract All qiling.
2. VS Code'da **ichidagi `TurAgent-AI` papkasini oching** (`server`, `public`, `tests`, `START_WINDOWS.bat` shu yerda).
3. Eski serverni terminalda `Ctrl+C` bilan to‘xtating.
4. Oldingi loyiha `.env` faylingizni yangi papkaga qo‘ying. Hech kimga API kalitini yubormang.
5. VS Code terminali to‘g‘ri papkada ekanini tekshiring: `dir START_WINDOWS.bat`.
6. ` .\START_WINDOWS.bat ` buyrug‘ini ishga tushiring.
7. Brauzerda `http://localhost:8000` oching va Ctrl+F5 bosing.

Agar videoni lokal faylga yuklamoqchi bo‘lsangiz, bir marta ` .\DOWNLOAD_REAL_VIDEO_WINDOWS.bat ` ishlating va serverni yangilang.

## Testlar

```
python -m unittest discover -s tests -p "test_*.py" -v
```

**MUHIM:** `TurAgent-AI-Premium-Demo` eski papkasida testni ishga tushirmang. U yerda `test_backend.py` eski API'ga tegishli va hozirgi loyiha bilan aralashsa `TypeError: NoneType` xatosi chiqadi. `dir` natijasida `test_backend.py` bor bo‘lsa, yangi ZIP ichidagi alohida papkaga o'tganingizni tekshiring.

Yangi testlar `GEMINI_API_KEY`ni faqat test jarayonida bo‘sh qiladi, real `.env`ga tegmaydi. Bu test vaqtida Gemini'ga internet so‘rovi yuborilishining oldini oladi.

## Gemini alohida tekshiruvi

```
.\CHECK_SETUP_WINDOWS.bat
```

U haqiqiy Google serverga ulanib xato kodini tekshiradi. Agar tarmoq, 403 (ruxsat), 404 (model) yoki 429 (kvota) bo‘lsa, sayt kodi buni sehrli tarzda tuzata olmaydi; Google AI Studio API kaliti loyihasi va limitini tekshirish kerak. `gemini-3.8-flash` rasmiy model nomi, lekin akkauntdagi ruxsat va Free Tier mavjudligi farq qilishi mumkin.

**API kalitini, `.env` faylini yoki terminaldagi secretlarni hech qachon boshqalar bilan bo‘lishmang.**

## Media litsenziyalari

Pexels video: https://www.pexels.com/license/ (muallif Dimitris Mourousiadis).
Unsplash photos: https://unsplash.com/license; Commons Amalfi photo: https://commons.wikimedia.org/wiki/File:Amalfi_Coast,_Amalfi,_Italy_(Unsplash_QVU_5fjXWe0).jpg.

**Cheklovlar:** haqiqiy videoning CDN manzili va yuqori aniqlikdagi tasvirlarni yuklash uchun internet kerak. Dasturdagi Gemini va Google OAuth haqiqiy kalitlar va tarmoqsiz ishlamaydi; bu xizmatlarning jonli natijasi bu muhittda sinovdan o‘tkazilmadi. To‘lovlar demo holatida qoladi.
