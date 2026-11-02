# TurAgent AI Cloudflare v6 — test va o'zgarishlar

## Migratsiya

Cloudflare Workers Runtime uchun to'liq JavaScript API yozildi; eski `server/app.py` production server sifatida ishlatilmaydi. Frontend v5.2 ko'rinishi, logo, responsive dizayn, til tugmalari, sayohat kartalari, sevimlilar va AI chat interfeysi saqlangan.

## Cloudflare API funksiyalari

1. D1 jadval va urug' ma'lumotlari (9 tur, 4 maqola)
2. PBKDF2 orqali email/parol ro'yxatdan o'tish
3. Cookie sessiyalari va CSRF himoyasi
4. Google OAuth callback konfiguratsiyasi
5. Profil va sevimlilar
6. Guest / user bronlar, narx hisoblash serverda
7. Demo to'lov muvaffaqiyatli/rad etilgan holatlar
8. Admin bootstrap, tour CRUD, blog, statusni o'zgartirish
9. Murojaatlar va newsletter
10. Gemini JSON va oqimli SSE so'rovlar
11. Resend HTTP API asosida ixtiyoriy email
12. Cloudflare Workers Static Assets va real video manziliga yo'naltirish
13. Rate limits D1 jadvalida, kunlik scheduled cleanup

## Mahalliy avtomatik tekshiruv

Worker funksiyasiga Request yuborib, D1 SQL bindingini SQLite bridge orqali taqlid qilish usulida tekshirildi. Alohida quyidagi testlar muvaffaqiyatli o'tdi:

- Public katalog, maqolalar, config, health
- Akkaunt ro'yxatdan o'tish, login/logout, CSRF
- Sevimlilar, bron, takroriy demo to'lovni rad etish
- Guest bron maxfiy tokeni, contact/newsletter
- Administrator yaratish va tur yangilash
- Mock Gemini SSE oqimi

**Cheklovlar:** Wrangler/npm o'rnatilishi ushbu muhitda tarmoq muammosi sabab yakunlanmadi. Haqiqiy Workers+D1 deployment testi shu sabab bajarilmadi. Real Google, Gemini, Resend servislariga maxfiy kalitsiz jonli so'rov yuborilmadi. Backend sintaksisi Node.js 22 bilan tekshirildi. Har bir funksiyani haqiqiy Cloudflare domenida qayta sinash shart.
