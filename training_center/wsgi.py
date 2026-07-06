import os  # استيراد مكتبة/وحدة بايثون
from django.core.wsgi import get_wsgi_application  # استيراد عناصر محددة من مكتبة/وحدة
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'training_center.settings_lan')  # سطر كود لتنفيذ منطق/إعداد
application = get_wsgi_application()  # تعيين قيمة لمتغير/إعداد
