ملفات ضبط إنشاء .env تلقائيًا مع اكتشاف Google Chrome

استبدل الملفات في نفس المسارات داخل المشروع:
- launcher/lan_server.py
- training_center/settings_lan.py
- CREATE_NEW_OFFICE.ps1
- .env.lan.example
- .env.example

ما الذي تغير؟
1) CREATE_NEW_OFFICE.ps1 صار يبحث عن chrome.exe تلقائيًا عند إنشاء مكتب جديد ويكتب CHROME_EXE_PATH داخل ملف .env للمكتب.
2) launcher/lan_server.py صار يضيف مفاتيح المتصفح تلقائيًا لأي .env قديم إذا كانت ناقصة:
   AUTO_OPEN_BROWSER=1
   PREFER_CHROME_BROWSER=1
   AUTO_OPEN_BROWSER_URL=http://127.0.0.1:<port>
   AUTO_OPEN_BROWSER_DELAY_SECONDS=2
   AUTO_OPEN_BROWSER_TIMEOUT_SECONDS=45
   CHROME_EXE_PATH=... إذا وجد Google Chrome
3) training_center/settings_lan.py صار يقرأ C:\TrainingCenterData_Tissemsilt\.env عند تشغيل الأمر مع APP_DATA_DIR فقط.

بعد الاستبدال:
- أوقف سيرفر 8003.
- شغله من جديد.
- سيتم تحديث ملف C:\TrainingCenterData_Tissemsilt\.env تلقائيًا إذا كانت مفاتيح Chrome ناقصة.
