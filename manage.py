#!/usr/bin/env python
import os, sys  # استيراد مكتبة/وحدة بايثون
def main():  # تعريف دالة (Function)
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'training_center.settings')  # سطر كود لتنفيذ منطق/إعداد
    from django.core.management import execute_from_command_line  # استيراد عناصر محددة من مكتبة/وحدة
    execute_from_command_line(sys.argv)  # سطر كود لتنفيذ منطق/إعداد
if __name__ == '__main__':  # شرط (If)
    main()  # سطر كود لتنفيذ منطق/إعداد
