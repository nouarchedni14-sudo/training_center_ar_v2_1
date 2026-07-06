import calendar  # استيراد مكتبة/وحدة بايثون
import re  # استيراد مكتبة/وحدة بايثون
from django.contrib import admin  # استيراد عناصر محددة من مكتبة/وحدة
from django.db.models import Q  # استيراد عناصر محددة من مكتبة/وحدة
from django.utils import timezone  # استيراد عناصر محددة من مكتبة/وحدة


_REMOVED_KEYWORDS = [  # تعيين قيمة لمتغير/إعداد
    "مشطوب",  # سطر كود لتنفيذ منطق/إعداد
    "شطب",  # سطر كود لتنفيذ منطق/إعداد
    "مفصول",  # سطر كود لتنفيذ منطق/إعداد
    "فصل",  # سطر كود لتنفيذ منطق/إعداد
    "متوقف",  # سطر كود لتنفيذ منطق/إعداد
    "موقوف",  # سطر كود لتنفيذ منطق/إعداد
    "توقف",  # سطر كود لتنفيذ منطق/إعداد
    "منقطع",  # سطر كود لتنفيذ منطق/إعداد
    "انسحب",  # سطر كود لتنفيذ منطق/إعداد
]  # سطر كود لتنفيذ منطق/إعداد

_ACTIVE_KEYWORDS = [  # تعيين قيمة لمتغير/إعداد
    "نشط",  # سطر كود لتنفيذ منطق/إعداد
    "مواصل",  # سطر كود لتنفيذ منطق/إعداد
    "يدرس",  # سطر كود لتنفيذ منطق/إعداد
    "مستمر",  # سطر كود لتنفيذ منطق/إعداد
]  # سطر كود لتنفيذ منطق/إعداد


_AR_DIACRITICS = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED]")  # تعيين قيمة لمتغير/إعداد
_TATWEEL = "\u0640"  # تعيين قيمة لمتغير/إعداد


def _norm_ar(s: str) -> str:  # تعريف دالة (Function)
    s = str(s or "").strip()  # تعيين قيمة لمتغير/إعداد
    if not s:  # شرط (If)
        return ""  # إرجاع قيمة من الدالة
    # remove tatweel + diacritics
    s = s.replace(_TATWEEL, "")  # تعيين قيمة لمتغير/إعداد
    s = _AR_DIACRITICS.sub("", s)  # تعيين قيمة لمتغير/إعداد
    # normalize alef variants + ya/taa marbuta
    s = (s.replace("أ", "ا")  # تعيين قيمة لمتغير/إعداد
           .replace("إ", "ا")  # سطر كود لتنفيذ منطق/إعداد
           .replace("آ", "ا")  # سطر كود لتنفيذ منطق/إعداد
           .replace("ى", "ي")  # سطر كود لتنفيذ منطق/إعداد
           .replace("ة", "ه"))  # سطر كود لتنفيذ منطق/إعداد
    # collapse spaces
    s = re.sub(r"\s+", " ", s)  # تعيين قيمة لمتغير/إعداد
    return s  # إرجاع قيمة من الدالة


def status_group(value: str) -> str:  # تعريف دالة (Function)
    # سطر كود لتنفيذ منطق/إعداد
    """Return canonical group label for a raw status text."""
    v = _norm_ar(value)  # تعيين قيمة لمتغير/إعداد
    if not v:  # شرط (If)
        return ""  # إرجاع قيمة من الدالة
    # If any 'removed' keyword is present -> مشطوب
    for k in _REMOVED_KEYWORDS:  # حلقة تكرار (For)
        if _norm_ar(k) in v:  # شرط (If)
            return "مشطوب"  # إرجاع قيمة من الدالة
    for k in _ACTIVE_KEYWORDS:  # حلقة تكرار (For)
        if _norm_ar(k) in v:  # شرط (If)
            return "نشط"  # إرجاع قيمة من الدالة
    return value.strip()  # إرجاع قيمة من الدالة


def q_removed(field_name: str = "الحالة") -> Q:  # تعريف دالة (Function)
    q = Q()  # تعيين قيمة لمتغير/إعداد
    for k in _REMOVED_KEYWORDS:  # حلقة تكرار (For)
        q |= Q(**{f"{field_name}__icontains": k})  # تعيين قيمة لمتغير/إعداد
    return q  # إرجاع قيمة من الدالة


def q_active(field_name: str = "الحالة") -> Q:  # تعريف دالة (Function)
    # تعيين قيمة لمتغير/إعداد
    """Active = كل من ليس مشطوباً (أي نستبعد كلمات الشطب/التوقف/الفصل...)."""
    return ~q_removed(field_name)  # إرجاع قيمة من الدالة


def _subtract_one_month(d):  # تعريف دالة (Function)
    month = d.month - 1  # تعيين قيمة لمتغير/إعداد
    year = d.year  # تعيين قيمة لمتغير/إعداد
    if month == 0:  # شرط (If)
        month = 12  # تعيين قيمة لمتغير/إعداد
        year -= 1  # تعيين قيمة لمتغير/إعداد
    day = min(d.day, calendar.monthrange(year, month)[1])  # تعيين قيمة لمتغير/إعداد
    return d.replace(year=year, month=month, day=day)  # إرجاع قيمة من الدالة


def q_recent_removed(status_field: str = "الحالة", date_field: str = "تاريخ_الشطب") -> Q:  # تعريف دالة (Function)
    cutoff = _subtract_one_month(timezone.localdate())  # تعيين قيمة لمتغير/إعداد
    return q_removed(status_field) & Q(**{f"{date_field}__isnull": False}) & Q(**{f"{date_field}__gt": cutoff})  # إرجاع قيمة من الدالة


def q_counted_removed(status_field: str = "الحالة", date_field: str = "تاريخ_الشطب") -> Q:  # تعريف دالة (Function)
    cutoff = _subtract_one_month(timezone.localdate())  # تعيين قيمة لمتغير/إعداد
    return q_removed(status_field) & (Q(**{f"{date_field}__isnull": True}) | Q(**{f"{date_field}__lte": cutoff}))  # إرجاع قيمة من الدالة



class UnifiedStatusFilter(admin.SimpleListFilter):  # تعريف كلاس (Class)
    title = "الحالة (موحّدة)"  # تعيين قيمة لمتغير/إعداد
    # تعيين قيمة لمتغير/إعداد
    parameter_name = "status_group"  # used in querystring

    def lookups(self, request, model_admin):  # تعريف دالة (Function)
        return (  # إرجاع قيمة من الدالة
            ("active", "نشط"),  # سطر كود لتنفيذ منطق/إعداد
            ("removed", "مشطوب / متوقف / مفصول"),  # سطر كود لتنفيذ منطق/إعداد
            ("recent_removed", "مشطوب حديثًا"),  # سطر كود لتنفيذ منطق/إعداد
            ("other", "أخرى"),  # سطر كود لتنفيذ منطق/إعداد
            ("empty", "فارغ"),  # سطر كود لتنفيذ منطق/إعداد
        )  # سطر كود لتنفيذ منطق/إعداد

    def queryset(self, request, queryset):  # تعريف دالة (Function)
        v = self.value()  # تعيين قيمة لمتغير/إعداد
        if not v:  # شرط (If)
            return queryset  # إرجاع قيمة من الدالة

        field_name = "الحالة"  # تعيين قيمة لمتغير/إعداد
        if v == "active":  # شرط (If)
            return queryset.filter(q_active(field_name))  # إرجاع قيمة من الدالة
        if v == "removed":  # شرط (If)
            return queryset.filter(q_counted_removed(field_name, "تاريخ_الشطب"))  # إرجاع قيمة من الدالة
        if v == "recent_removed":  # شرط (If)
            return queryset.filter(q_recent_removed(field_name, "تاريخ_الشطب"))  # إرجاع قيمة من الدالة
        if v == "empty":  # شرط (If)
            return queryset.filter(Q(**{f"{field_name}__isnull": True}) | Q(**{f"{field_name}__exact": ""}))  # إرجاع قيمة من الدالة
        if v == "other":  # شرط (If)
            return queryset.exclude(q_active(field_name)).exclude(q_counted_removed(field_name, "تاريخ_الشطب")).exclude(q_recent_removed(field_name, "تاريخ_الشطب")).exclude(  # إرجاع قيمة من الدالة
                Q(**{f"{field_name}__isnull": True}) | Q(**{f"{field_name}__exact": ""})  # سطر كود لتنفيذ منطق/إعداد
            )  # سطر كود لتنفيذ منطق/إعداد
        return queryset  # إرجاع قيمة من الدالة
