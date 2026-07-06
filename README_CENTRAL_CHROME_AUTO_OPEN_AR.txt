ضبط فتح لوحة المطور المركزية 9000 في Google Chrome

الملفات المعدلة:
- START_CENTRAL_SERVER_9000.bat
- setup_central_server.bat
- tools/open_preferred_browser.ps1
- .env.central.example

ما الذي تغير؟
1) عند تشغيل START_CENTRAL_SERVER_9000.bat سيتم فتح الرابط http://127.0.0.1:9000/ في Google Chrome أولًا.
2) إذا لم يجد Chrome، يستعمل المتصفح الافتراضي كخطة احتياطية.
3) setup_central_server.bat يكتب مفاتيح المتصفح داخل C:\TrainingCenterCentralData\.env:
   AUTO_OPEN_BROWSER=1
   PREFER_CHROME_BROWSER=1
   AUTO_OPEN_BROWSER_URL=http://127.0.0.1:9000/
   CHROME_EXE_PATH=... إذا وجد Chrome
4) ملف tools/open_preferred_browser.ps1 يبحث عن Chrome في:
   - CHROME_EXE_PATH من .env
   - Windows Registry
   - Program Files
   - Program Files (x86)
   - LOCALAPPDATA
   - PATH

بعد الاستبدال:
- أغلق سيرفر 9000 إن كان يعمل.
- شغل START_CENTRAL_SERVER_9000.bat من جديد.
- يجب أن يفتح Chrome تلقائيًا على لوحة المطور.
