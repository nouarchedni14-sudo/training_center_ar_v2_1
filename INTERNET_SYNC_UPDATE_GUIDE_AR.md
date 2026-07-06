# تشغيل المزامنة والتحديثات عبر الإنترنت

هذه الملاحظات خاصة عندما تكون المكاتب خارج المؤسسة وتريد ربطها بخادم مركزي عبر الإنترنت.

## 1) الخادم المركزي على الإنترنت

الأفضل تشغيل الخادم المركزي خلف نطاق HTTPS مثل:

```env
CENTRAL_PUBLIC_URL=https://updates.example.com
DJANGO_ALLOWED_HOSTS=updates.example.com,127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://updates.example.com,http://127.0.0.1:9000,http://localhost:9000
BEHIND_REVERSE_PROXY=1
SESSION_COOKIE_SECURE=1
CSRF_COOKIE_SECURE=1
```

إذا كان الخادم داخل شبكة محلية فقط، استعمل مثل:

```env
CENTRAL_PUBLIC_URL=http://ADEM:9000
```

## 2) كل مكتب خارجي

في ملف `.env` الخاص بالمكتب يجب أن تكون القيم مثل:

```env
CENTRAL_URL=https://updates.example.com
CENTRAL_SYNC_ENABLED=1
SYNC_WORKER_ENABLED=1
IN_PROCESS_SYNC_WORKER_ENABLED=1
SYNC_TRACKING_ENABLED=1
SYNC_APPLY_INBOX_ENABLED=1
ALLOW_REMOTE_UPDATES=1
```

ويجب أن تكون لكل مكتب هوية مستقلة:

```env
OFFICE_ID=office-tissemsilt
SERVER_ID=server-tissemsilt-01
SYNC_TOKEN=token-from-central
```

## 3) الفرق بين LAN والإنترنت

- `http://ADEM:9000` يعمل داخل نفس الشبكة أو VPN فقط.
- `https://updates.example.com` يعمل من أي مكتب خارجي لديه إنترنت.
- بدون إنترنت يمكن دائمًا استعمال صفحة التحديث المحلي ورفع ملف ZIP.

## 4) الأمان

لا تفتح الخادم المركزي للإنترنت بدون HTTPS وتوكنات قوية. يفضّل استعمال Reverse Proxy مثل Nginx أو Cloudflare Tunnel أو VPN.
