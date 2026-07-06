from django import template  # استيراد عناصر محددة من مكتبة/وحدة
from datetime import date, datetime  # استيراد عناصر محددة من مكتبة/وحدة

register = template.Library()  # تعيين قيمة لمتغير/إعداد

@register.filter  # سطر كود لتنفيذ منطق/إعداد
def attr(obj, name):  # تعريف دالة (Function)
    # سطر كود لتنفيذ منطق/إعداد
    """Safe attribute getter used by dynamic table.

    Enforces consistent display:  # سطر كود لتنفيذ منطق/إعداد
    - Dates/datetimes => YYYY-MM-DD  # تعيين قيمة لمتغير/إعداد
    - Booleans        => نعم / لا  # تعيين قيمة لمتغير/إعداد
    # سطر كود لتنفيذ منطق/إعداد
    """
    v = getattr(obj, name, "")  # تعيين قيمة لمتغير/إعداد
    # Show booleans explicitly (False should not become empty)
    if isinstance(v, bool):  # شرط (If)
        return "نعم" if v else "لا"  # إرجاع قيمة من الدالة
    if v is None or v == "":  # شرط (If)
        return ""  # إرجاع قيمة من الدالة
    # Normalize all dates/datetimes to YYYY-MM-DD (no localization / month names)
    # Special case: if birth date is assumed (مفترض=True) show year only
    if name == "تاريخ_الميلاد" and getattr(obj, "مفترض", False) and isinstance(v, (date, datetime)):  # شرط (If)
        try:  # سطر كود لتنفيذ منطق/إعداد
            yy = v.year if isinstance(v, date) else v.date().year  # تعيين قيمة لمتغير/إعداد
            return f"{yy:04d}"  # إرجاع قيمة من الدالة
        except Exception:  # سطر كود لتنفيذ منطق/إعداد
            pass  # سطر كود لتنفيذ منطق/إعداد
    if isinstance(v, datetime):  # شرط (If)
        return v.date().strftime("%Y-%m-%d")  # إرجاع قيمة من الدالة
    if isinstance(v, date):  # شرط (If)
        return v.strftime("%Y-%m-%d")  # إرجاع قيمة من الدالة
    # Normalize phone number display: if 9 digits, prefix with 0
    if name == "رقم_الهاتف":  # شرط (If)
        s = str(v).strip()  # تعيين قيمة لمتغير/إعداد
        if s.isdigit() and len(s) == 9:  # شرط (If)
            return "0" + s  # إرجاع قيمة من الدالة
    return v  # إرجاع قيمة من الدالة
