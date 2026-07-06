import os  # استيراد مكتبة/وحدة بايثون
from django.core.asgi import get_asgi_application  # استيراد عناصر محددة من مكتبة/وحدة
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'training_center.settings')  # سطر كود لتنفيذ منطق/إعداد
application = get_asgi_application()  # تعيين قيمة لمتغير/إعداد
