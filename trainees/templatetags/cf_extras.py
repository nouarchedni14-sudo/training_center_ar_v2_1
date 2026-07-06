from django import template  # استيراد عناصر محددة من مكتبة/وحدة

register = template.Library()  # تعيين قيمة لمتغير/إعداد

@register.filter  # سطر كود لتنفيذ منطق/إعداد
def get_item(d, key):  # تعريف دالة (Function)
    if not d:  # شرط (If)
        return ""  # إرجاع قيمة من الدالة
    return d.get(key, "")  # إرجاع قيمة من الدالة
