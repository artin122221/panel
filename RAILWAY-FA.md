# پنل پاسارگارد + نود روی Railway (یک سرویس، بدون دامنه و سرتیفیکیت)

پنل و نود و Xray همه داخل یک سرویس Railway هستند. کانفیگ VLESS روی WebSocket از همان آدرس HTTPS خود Railway رد می‌شود.
نسخه‌ها پایدارند: پنل v5.6.0 و نود v0.5.7.

## فایل‌هایی که باید در مخزن (فورک شما) آپلود شوند
همه در صفحه‌ی اصلی مخزن، نه داخل پوشه:

1. `Dockerfile` (جای قدیمی)
2. `main.py` (جای قدیمی)
3. `start.sh` (جای قدیمی)
4. `railway.json` (جدید)
5. `railway_bootstrap.py` (جدید)
6. `railway_prepare.py` (جدید)
7. `railway-nginx.conf` (جدید)

## مرحله ۱: Railway
1. New Project ← Deploy from GitHub repo ← مخزن خودتان.
2. سرویس ← Volumes ← مسیر: `/var/lib/pasarguard`
3. Variables ← این دو تا:
   - `OWNER_USERNAME` = اسم ادمین
   - `OWNER_PASSWORD` = رمز قوی
4. Settings ← Networking ← **Generate Domain**.
5. **یک بار Redeploy بزنید** (Deployments ← سه‌نقطه‌ی آخرین دیپلوی ← Redeploy). این برای این است که آدرس دامنه به برنامه برسد و هاست و گروه خودکار ساخته شوند.

## مرحله ۲: داخل پنل
1. `https://اسم-شما.up.railway.app/dashboard/` را باز کنید و وارد شوید.
2. بخش نودها: باید یک نود به اسم `Railway-Node` ببینید و وضعیتش «متصل» باشد.
3. یک کاربر بسازید و گروه `Railway-Group` را به او بدهید.
4. در تنظیمات اشتراک (subscription) آدرس `https://اسم-شما.up.railway.app` را بگذارید.
5. لینک اشتراک کاربر را در برنامه‌ی v2ray (مثل v2rayNG) وارد کنید.

## اگر نود «متصل» نشد
در Railway ← Deployments ← Deploy Logs را باز کنید و متن خطا را بفرستید. خطوطی که با `[bootstrap]` یا `[prepare]` شروع می‌شوند مهم‌اند.

## نکته‌ها
- فقط VLESS روی WebSocket ساخته شده است. UDP (Hysteria و WireGuard) روی Railway کار نمی‌کند.
- این نسخه روی Railway آزمایش نشده است، چون من Docker نداشتم.
- قوانین Railway درباره‌ی پروکسی و VPN را بخوانید. ممکن است حساب بسته شود.
