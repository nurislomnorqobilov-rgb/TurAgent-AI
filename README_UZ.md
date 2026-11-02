# TurAgent AI v6.1 — Cloudflare autentifikatsiyasi uchun tuzatish

## Sabab
Cloudflare Workers logida `NotSupportedError Pbkdf2 failed: iteration counts above 100000 are not supported (requested 210000)` ko‘rsatilgan. Oldingi `src/index.js` 210000 iteratsiyani talab qilgan.

## Nimalar o‘zgardi
`src/index.js` faylida `PASSWORD_PBKDF2_ITERATIONS=100_000` aniq konstanta sifatida o‘rnatildi va `passwordHash` undan foydalanadigan bo‘ldi. Natijada ro‘yxatdan o‘tish, login, admin bootstrap va parolni tiklashda bir xil qiymat ishlatiladi. Avval hech bir muvaffaqiyatli akkaunt yaratila olmagan bo‘lsa, ma’lumotlarni ko‘chirish talab qilinmaydi.

## Qanday o‘rnatiladi
1. O‘zingizning Cloudflare v6 loyihangizda `src/index.js` faylidan nusxa oling.
2. Ushbu patch ichidagi `src/index.js` faylini loyihangizdagi `src/index.js` o‘rniga qo‘ying.
3. Hech qachon haqiqiy `wrangler.jsonc`, `.env`, `.dev.vars`, `node_modules`, D1 bazasini yoki Wrangler secrets ma’lumotlarini bu patch bilan almashtirmang.
4. VS Code terminalida `npm.cmd run check` va `npm.cmd test` buyruqlarini bajaring.
5. `npm.cmd run deploy` bilan Workers'ga chiqarib, sinab ko‘ring.
6. `npx.cmd wrangler tail turagent-ai --format pretty` orqali real xatolarni kuzating.

## Xavfsizlik haqida muhim eslatma
100000 PBKDF2 iteratsiya Cloudflare runtime texnik cheklovini hisobga olgan vaqtinchalik moslik yechimidir. Bu parol hosil qilish uchun zamonaviy yuqori work-factor tavsiyalaridan past bo‘lishi mumkin. Ommaviy, haqiqiy mijozli production tizimda boshqariladigan autentifikatsiya xizmati yoki mos password-hashing yechimi va kuchli rate-limiting ishlatilishi afzal. Workers Free rejasidagi CPU cheklovi tufayli joylashtirilgandan keyingi jonli test muhim.
