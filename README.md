# 📚 Dars Jadvali Telegram Boti — FINP-S-1323U

## O'rnatish

### 1. Kutubxonalarni o'rnatish
```bash
pip install -r requirements.txt
```

### 2. Bot tokenini sozlash
`bot.py` faylini oching va quyidagi qatorni toping:
```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
```
`YOUR_BOT_TOKEN_HERE` o'rniga @BotFather dan olgan tokeningizni kiriting.

### 3. Botni ishga tushirish
```bash
python bot.py
```

### 4. Birinchi marta ishlatish
Telegram da botingizni oching va `/start` bosing.
Bu sizning Chat ID ni saqlaydi va eslatmalar avtomatik rejalashtiriladi.

---

## Komandalar

| Komanda | Tavsif |
|---------|--------|
| `/start` | Botni ishga tushirish |
| `/bugun` | Bugungi darslar |
| `/jadval` | Barcha darslar |
| `/hafta` | Kelgusi 7 kun |
| `/keyingidars` | Keyingi dars |
| `/yordam` | Yordam |

---

## Xususiyatlar

- ✅ Dars boshlanishidan **15 daqiqa oldin** avtomatik eslatma
- ✅ Zoom havolasi to'g'ridan to'g'ri xabarda
- ✅ Inline tugma orqali Zoom ga kirish
- ✅ Barcha darslar jadvali
- ✅ Toshkent vaqti (UTC+5)

---

## Server da ishlatish (Railway / Timeweb)

```bash
# Screen yoki tmux ichida ishlatish
screen -S dars_bot
python bot.py
# Ctrl+A, D — fonda qoldirish
```

Yoki `systemd` service sifatida sozlash mumkin.
