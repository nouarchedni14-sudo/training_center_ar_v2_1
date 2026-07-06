from datetime import timedelta
import os
from pathlib import Path
from django.conf import settings
from django.db import models  # استيراد عناصر محددة من مكتبة/وحدة
from django.contrib.contenttypes.models import ContentType  # استيراد عناصر محددة من مكتبة/وحدة
from django.contrib.contenttypes.fields import GenericForeignKey  # استيراد عناصر محددة من مكتبة/وحدة


from .semester_utils import add_months, compute_semester_with_repeater, normalize_repeater_training_dates, resolve_session_year, compute_semester_for_trainee  # استيراد عناصر محددة من مكتبة/وحدة
from .evening_training_type import (
    EVENING_TRAINING_TYPE_CHOICES,
    EVENING_TRAINING_TYPE_CROSSING,
    clean_crossing_specialty_label,
    detect_evening_training_type,
    clamp_semester_for_evening_type,
)

from .model_access_audit import (
    ACCESS_PROFILE_AUDIT_FIELDS,
    ACCESS_PROFILE_AUDIT_LABELS,
    diff_access_snapshots,
    get_access_audit_field_label,
    get_access_audit_field_labels,
    serialize_access_profile_for_audit,
)


def format_registration_number(value):
    """Normalize registration numbers to a compact, consistent format.

    - converts Arabic numerals to ASCII digits
    - strips spaces, dashes, slashes and similar separators
    - uppercases latin suffix letters
    - keeps only alphanumeric characters
    """
    raw = str(value or "").strip()
    if not raw:
        return ""

    trans = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    normalized = raw.translate(trans).upper()

    cleaned = []
    for ch in normalized:
        if ch.isalnum():
            cleaned.append(ch)
    return "".join(cleaned)



def _program_media_folder_candidates_for_instance(instance):
    if instance.__class__.__name__ == "حضوري_أولي":
        return ["الحضوري أولي", "حضوري أولي", "الحضوري_أولي"]
    if instance.__class__.__name__ == "تمهين":
        return ["التمهين", "تمهين"]
    if instance.__class__.__name__ == "مسائي_ومعابر":
        if getattr(instance, "نوع_التكوين", "") == "معابر":
            return [
                "المعابر",
                "الدروس المسائيةوالمعابر",
                "الدروس المسائية والمعابر",
                "المسائية والمعابر",
                "مسائي ومعابر",
            ]
        return [
            "الدروس المسائية",
            "الدروس المسائيةوالمعابر",
            "الدروس المسائية والمعابر",
            "المسائية والمعابر",
            "مسائي ومعابر",
        ]
    return ["عام"]


def _program_media_folder_for_instance(instance):
    return _program_media_folder_candidates_for_instance(instance)[0]


def _safe_media_name(value):
    value = (value or "").strip()
    if not value:
        return "بدون_اسم"
    forbidden = '<>:"/\\|?*'
    for ch in forbidden:
        value = value.replace(ch, " ")
    value = " ".join(value.split())
    return value[:180] or "بدون_اسم"


def _specialty_media_folder_candidates(value):
    base = _safe_media_name(value or "بدون تخصص")
    variants = [base]
    compact = base.replace(" ", "")
    underscored = base.replace(" ", "_")
    for candidate in (compact, underscored):
        if candidate and candidate not in variants:
            variants.append(candidate)
    return variants


def _media_root_candidates():
    root = Path(settings.MEDIA_ROOT)
    candidates = [root / 'trainees', root]
    seen = set()
    ordered = []
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key not in seen:
            seen.add(key)
            ordered.append(candidate)
    return ordered


def _find_existing_media_url(program_folder, specialty, subfolder, base_name):
    program_candidates = program_folder if isinstance(program_folder, (list, tuple)) else [program_folder]
    specialty_candidates = _specialty_media_folder_candidates(specialty)
    subfolder_candidates = [subfolder]
    if subfolder == "صور":
        subfolder_candidates += ["photos", "photo", "Photo", "صور شخصية"]
    elif subfolder == "QR_Code":
        subfolder_candidates += ["qr", "QR", "qrcode", "QR Code"]

    for media_root in _media_root_candidates():
        for program_name in program_candidates:
            for specialty_name in specialty_candidates:
                for folder_name in subfolder_candidates:
                    root = media_root / program_name / specialty_name / folder_name
                    for ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'):
                        fp = root / f'{base_name}{ext}'
                        if fp.exists():
                            rel = fp.relative_to(settings.MEDIA_ROOT).as_posix()
                            return settings.MEDIA_URL.rstrip('/') + '/' + rel
    return ''


def _next_promotion_key(year, session_no):
    if session_no == 1:
        return year, 2
    return year + 1, 1


def _promotion_gap_days(exclude_pk=None, extra=None):
    qs = دفعة.objects.filter(مفعلة=True).order_by("السنة", "رقم_الدورة").only("id", "السنة", "رقم_الدورة", "تاريخ_الدخول_الرسمي")
    promotions = [p for p in qs if exclude_pk is None or p.pk != exclude_pk]
    if extra is not None:
        promotions.append(extra)
        promotions.sort(key=lambda p: (p.السنة, p.رقم_الدورة))
    gaps = {(1, 2): 224, (2, 1): 140}
    for prev, nxt in zip(promotions, promotions[1:]):
        key = (prev.رقم_الدورة, nxt.رقم_الدورة)
        gaps[key] = max(1, (nxt.تاريخ_الدخول_الرسمي - prev.تاريخ_الدخول_الرسمي).days)
    return gaps


def _build_promotion_starts(current):
    qs = دفعة.objects.filter(مفعلة=True).order_by("السنة", "رقم_الدورة").only("id", "السنة", "رقم_الدورة", "تاريخ_الدخول_الرسمي")
    promotion_dates = {(p.السنة, p.رقم_الدورة): p.تاريخ_الدخول_الرسمي for p in qs if p.pk != current.pk}
    promotion_dates[(current.السنة, current.رقم_الدورة)] = current.تاريخ_الدخول_الرسمي
    gaps = _promotion_gap_days(exclude_pk=current.pk, extra=current)

    starts = [current.تاريخ_الدخول_الرسمي]
    year = current.السنة
    session_no = current.رقم_الدورة
    current_date = current.تاريخ_الدخول_الرسمي
    for _ in range(4):
        year, next_session = _next_promotion_key(year, session_no)
        next_date = promotion_dates.get((year, next_session))
        if not next_date:
            next_date = current_date + timedelta(days=gaps.get((session_no, next_session), 180))
        starts.append(next_date)
        current_date = next_date
        session_no = next_session
    return starts
class دفعة(models.Model):
    اسم_الدفعة = models.CharField("اسم الدفعة", max_length=20, choices=[("فيفري", "فيفري"), ("سبتمبر", "سبتمبر")])
    رقم_الدورة = models.PositiveSmallIntegerField("رقم الدورة", choices=[(1, "1"), (2, "2")])
    السنة = models.PositiveIntegerField("السنة")
    تاريخ_الدخول_الرسمي = models.DateField("تاريخ الدخول الرسمي")
    بداية_السداسي_1 = models.DateField("بداية السداسي 1", null=True, blank=True)
    بداية_السداسي_2 = models.DateField("بداية السداسي 2", null=True, blank=True)
    بداية_السداسي_3 = models.DateField("بداية السداسي 3", null=True, blank=True)
    بداية_السداسي_4 = models.DateField("بداية السداسي 4", null=True, blank=True)
    بداية_السداسي_5 = models.DateField("بداية السداسي 5", null=True, blank=True)
    مفعلة = models.BooleanField("مفعلة", default=True)

    class Meta:
        verbose_name = "دفعة"
        verbose_name_plural = "الدفعات"
        ordering = ["-السنة", "-رقم_الدورة"]
        constraints = [
            models.UniqueConstraint(fields=["رقم_الدورة", "السنة"], name="trainees_unique_session_year_promotion")
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        expected_name = "فيفري" if self.رقم_الدورة == 1 else "سبتمبر"
        if self.اسم_الدفعة and self.اسم_الدفعة != expected_name:
            raise ValidationError({"اسم_الدفعة": f"رقم الدورة {self.رقم_الدورة} يجب أن يقابله {expected_name}."})

    def save(self, *args, **kwargs):
        if self.رقم_الدورة == 1:
            self.اسم_الدفعة = "فيفري"
        elif self.رقم_الدورة == 2:
            self.اسم_الدفعة = "سبتمبر"

        attrs = ["بداية_السداسي_1", "بداية_السداسي_2", "بداية_السداسي_3", "بداية_السداسي_4", "بداية_السداسي_5"]
        starts = _build_promotion_starts(self)
        for idx, attr in enumerate(attrs):
            setattr(self, attr, starts[idx])

        self.full_clean()
        result = super().save(*args, **kwargs)
        self._refresh_neighbor_promotions()
        return result

    def _refresh_neighbor_promotions(self):
        promotions = list(دفعة.objects.filter(مفعلة=True).order_by("السنة", "رقم_الدورة"))
        attrs = ["بداية_السداسي_1", "بداية_السداسي_2", "بداية_السداسي_3", "بداية_السداسي_4", "بداية_السداسي_5"]
        changed = []
        for promotion in promotions:
            starts = _build_promotion_starts(promotion)
            dirty = False
            for pos, attr in enumerate(attrs):
                value = starts[pos]
                if getattr(promotion, attr) != value:
                    setattr(promotion, attr, value)
                    dirty = True
            if dirty:
                changed.append(promotion)
        if changed:
            دفعة.objects.bulk_update(changed, attrs)

    def __str__(self):
        return f"{self.اسم_الدفعة} {self.السنة}"


def refresh_all_promotion_semester_starts():
    """أعد بناء بدايات السداسيات لكل الدفعات المفعلة.

    مهم بعد الاستيرادات القديمة أو بعد إضافة/تعديل دفعة؛ لأن زر إعادة حساب
    السداسيات وزر إعادة الربط يعتمدان على الحقول المخزنة داخل الدفعة.
    """
    attrs = ["بداية_السداسي_1", "بداية_السداسي_2", "بداية_السداسي_3", "بداية_السداسي_4", "بداية_السداسي_5"]
    promotions = list(دفعة.objects.filter(مفعلة=True).order_by("السنة", "رقم_الدورة"))
    changed = []
    for promotion in promotions:
        starts = _build_promotion_starts(promotion)
        dirty = False
        for pos, attr in enumerate(attrs):
            value = starts[pos]
            if getattr(promotion, attr) != value:
                setattr(promotion, attr, value)
                dirty = True
        if dirty:
            changed.append(promotion)
    if changed:
        دفعة.objects.bulk_update(changed, attrs, batch_size=200)
    return len(changed)



def cohort_start_dates_for_model(model_cls, extra_start_date=None, training_type=None):
    """تواريخ بدايات الدفعات الخاصة بنفس النمط/الجدول.

    لا نعتمد هنا على نموذج "دفعة" لأنه عام ولا يحتوي على النمط، وقد يخلط
    بين التمهين والحضوري والمسائي. نعتمد على تواريخ بداية التكوين الموجودة
    في نفس جدول المتكونين، مع إضافة تاريخ السجل الحالي عند الحفظ.
    عند جدول الدروس المسائية والمعابر نفصل حسب نوع التكوين حتى لا تختلط
    المعابر ذات السنة الواحدة مع الدروس المسائية ذات 5 سداسيات.
    """
    qs = model_cls.objects.exclude(تاريخ_بداية_التكوين__isnull=True)
    field_names = {f.name for f in model_cls._meta.get_fields()}
    if training_type and "نوع_التكوين" in field_names:
        qs = qs.filter(نوع_التكوين=training_type)
    dates = list(qs.values_list("تاريخ_بداية_التكوين", flat=True).distinct())
    if extra_start_date:
        dates.append(extra_start_date)
    return dates


class BaseTrainee(models.Model):  # تعريف كلاس (Class)
    الرقم_التعريفي = models.CharField("الرقم التعريفي", max_length=50, db_index=True, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    اللقب = models.CharField("اللقب", max_length=100)  # تعريف حقل/علاقة في نموذج Django
    الاسم = models.CharField("الاسم", max_length=100)  # تعريف حقل/علاقة في نموذج Django
    الاسم_بالأجنبية = models.CharField("الإسم الكامل باللغة الأجنبية", max_length=200, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django

    تاريخ_الميلاد = models.DateField("تاريخ الميلاد", null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    مفترض = models.BooleanField("مفترض", default=False)  # تعريف حقل/علاقة في نموذج Django
    البلدية = models.CharField("البلدية", max_length=120, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    الولاية = models.CharField("الولاية", max_length=120, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django

    التخصص = models.CharField("التخصص", max_length=200, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    رقم_التسجيل = models.CharField("رقم التسجيل", max_length=50, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    الدفعة = models.ForeignKey("دفعة", verbose_name="الدفعة", on_delete=models.SET_NULL, null=True, blank=True, related_name="%(class)s_trainees")
    تاريخ_بداية_التكوين = models.DateField("تاريخ بداية التكوين", null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    تاريخ_نهاية_التكوين = models.DateField("تاريخ نهاية التكوين", null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    السداسي = models.CharField("السداسي", max_length=50, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django

    الجنس = models.CharField("الجنس", max_length=10, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    الحالة = models.CharField("الحالة", max_length=120, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django

    تاريخ_الشطب = models.DateField("تاريخ الشطب", null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    رقم_الشطب = models.CharField("رقم/م-الشطب", max_length=80, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    رقم_مقرر_الفصل = models.CharField("رقم مقرر الفصل", max_length=120, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django

    رمز_التخصص = models.CharField("رمز التخصص", max_length=50, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    رقم_عقد_الميلاد = models.CharField("رقم عقد الميلاد", max_length=50, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django

    زمرة_الدم = models.CharField("زمرة الدم", max_length=10, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django

    اسم_الأب = models.CharField("إسم الأب", max_length=120, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    لقب_الأم = models.CharField("لقب الأم", max_length=120, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    اسم_الأم = models.CharField("إسم الأم", max_length=120, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django

    اسم_الأب_بالأجنبية = models.CharField("إسم الأب بالأجنبية", max_length=200, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    لقب_الأم_بالأجنبية = models.CharField("لقب الأم بالأجنبية", max_length=200, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    اسم_الأم_بالأجنبية = models.CharField("إسم الأم بالأجنبية", max_length=200, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django

    # تم حذف حقول (اللجنة التأديبية + الأرقام + العقوبات) و(الصورة) من النظام بالكامل حسب الطلب.

    البريد_الإلكتروني = models.EmailField("البريد الإلكتروني", null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    رقم_الهاتف = models.CharField("رقم الهاتف", max_length=30, db_index=True, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django

    النظام = models.CharField("النظام", max_length=120, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    رقم_التعريف_الوطني = models.CharField("ب-التعريف الوطنية", max_length=50, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    رقم_الضمان_الاجتماعي = models.CharField("رقم الضمان الاجتماعي", max_length=50, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django

    العنوان_بالعربية = models.CharField("العنوان بالعربية", max_length=255, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    بلدية_الإقامة_بالعربية = models.CharField("بلدية الإقامة بالعربية", max_length=120, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    ولاية_الإقامة_بالعربية = models.CharField("ولاية الإقامة بالعربية", max_length=120, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    العنوان_بالأجنبية = models.CharField("العنوان بالأجنبية", max_length=255, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    ولاية_الإقامة_بالأجنبية = models.CharField("ولاية الإقامة بالأجنبية", max_length=120, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django

    تاريخ_الإضافة = models.DateTimeField("تاريخ الإضافة", auto_now_add=True)  # تعريف حقل/علاقة في نموذج Django

    class Meta:  # تعريف كلاس (Class)
        abstract = True  # تعيين قيمة لمتغير/إعداد
        ordering = ["-تاريخ_الإضافة"]  # تعيين قيمة لمتغير/إعداد
        constraints = [  # تعيين قيمة لمتغير/إعداد
            models.UniqueConstraint(  # تعريف حقل/علاقة في نموذج Django
                fields=["الرقم_التعريفي", "رقم_التسجيل", "التخصص", "تاريخ_بداية_التكوين", "تاريخ_نهاية_التكوين"],  # تعيين قيمة لمتغير/إعداد
                name="%(app_label)s_%(class)s_uniq_trainee_course",  # تعيين قيمة لمتغير/إعداد
            )  # سطر كود لتنفيذ منطق/إعداد
        ]  # سطر كود لتنفيذ منطق/إعداد

    def save(self, *args, **kwargs):  # تعريف دالة (Function)
        # لا نسمح أبداً بوصول NULL إلى حقل مفترض في PostgreSQL.
        # هذا يحمي الإدخال اليدوي وأي مسار حفظ فردي.
        if getattr(self, "مفترض", None) is None:
            self.مفترض = False

        # فصل المعابر عن الدروس المسائية يتم داخل نفس الجدول،
        # مع تنظيف اسم التخصص إذا كانت كلمة معابر مكتوبة داخله.
        if self.__class__.__name__ == "مسائي_ومعابر":
            detected_without_default = detect_evening_training_type({
                "التخصص": self.التخصص,
                "النظام": self.النظام,
                "رمز_التخصص": self.رمز_التخصص,
                "تاريخ_بداية_التكوين": self.تاريخ_بداية_التكوين,
                "تاريخ_نهاية_التكوين": self.تاريخ_نهاية_التكوين,
            })
            if getattr(self, "نوع_التكوين", None) == "معابر" or detected_without_default == "معابر":
                self.نوع_التكوين = "معابر"
            else:
                self.نوع_التكوين = "مسائي"
            if self.التخصص:
                self.التخصص = clean_crossing_specialty_label(self.التخصص)

        # منطق +6 أشهر القديم ملغى. نُبقي النداء للتوافق فقط.
        normalize_repeater_training_dates(self)  # سطر كود لتنفيذ منطق/إعداد

        # اربط المتكون دائماً بالدفعة الصحيحة حسب رقم التسجيل،
        # ومع الأرقام غير القياسية نستعمل تاريخ بداية التكوين كحل آمن.
        # هذا يجعل تصحيح رقم التسجيل من صفحة المتكون يصحح الدفعة تلقائياً
        # حتى لو كان المتكون مرتبطاً سابقاً بدفعة خاطئة مثل 2053.
        if self.رقم_التسجيل or self.تاريخ_بداية_التكوين:
            رقم_الدورة, السنة = resolve_session_year(self.رقم_التسجيل, self.تاريخ_بداية_التكوين)
            if رقم_الدورة and السنة:
                try:
                    promotion = دفعة.objects.get(رقم_الدورة=رقم_الدورة, السنة=السنة, مفعلة=True)
                    if self.الدفعة_id != promotion.id:
                        self.الدفعة = promotion
                except دفعة.DoesNotExist:
                    pass

        # إعادة حساب السداسي دائماً داخل البرنامج حسب رزنامة الدفعة الفعلية
        # مع احترام تاريخ بداية/نهاية التكوين وحالة المعيد في التمهين.
        is_repeater = bool(getattr(self, "معيد", False))  # تعيين قيمة لمتغير/إعداد
        training_type = getattr(self, "نوع_التكوين", None) if self.__class__.__name__ == "مسائي_ومعابر" else None
        cohort_starts = cohort_start_dates_for_model(self.__class__, self.تاريخ_بداية_التكوين, training_type=training_type)
        self.السداسي = compute_semester_for_trainee(
            self.الدفعة,
            self.تاريخ_بداية_التكوين,
            self.تاريخ_نهاية_التكوين,
            is_repeater=is_repeater,
            cohort_starts=cohort_starts,
            original_end_date=getattr(self, "تاريخ_التكوين_السابق_للمعيدين", None),
        )
        if self.__class__.__name__ == "مسائي_ومعابر":
            self.السداسي = clamp_semester_for_evening_type(self.السداسي, getattr(self, "نوع_التكوين", None))
        return super().save(*args, **kwargs)  # إرجاع قيمة من الدالة


    @property  # سطر كود لتنفيذ منطق/إعداد
    def اللقب_والاسم(self):  # تعريف دالة (Function)
        return f"{self.اللقب} {self.الاسم}"  # إرجاع قيمة من الدالة

    @property
    def اسم_ملف_المتكون(self):
        return _safe_media_name(self.اللقب_والاسم)

    @property
    def مجلد_النمط_للوسائط(self):
        return _program_media_folder_for_instance(self)

    @property
    def مجلد_التخصص_للوسائط(self):
        return _safe_media_name(self.التخصص or "بدون تخصص")

    @property
    def رابط_الصورة(self):
        return _find_existing_media_url(self.مجلد_النمط_للوسائط, self.مجلد_التخصص_للوسائط, 'صور', self.اسم_ملف_المتكون)

    @property
    def رابط_qr_code(self):
        return _find_existing_media_url(self.مجلد_النمط_للوسائط, self.مجلد_التخصص_للوسائط, 'QR_Code', self.اسم_ملف_المتكون)

    def __str__(self):  # تعريف دالة (Function)
        return f"{self.الرقم_التعريفي} - {self.اللقب_والاسم}"  # إرجاع قيمة من الدالة

class حضوري_أولي(BaseTrainee):  # تعريف كلاس (Class)
    class Meta:  # تعريف كلاس (Class)
        verbose_name = "متكوّن (حضوري أولي)"  # تعيين قيمة لمتغير/إعداد
        verbose_name_plural = "حضوري أولي"  # تعيين قيمة لمتغير/إعداد

class تمهين(BaseTrainee):  # تعريف كلاس (Class)
    معيد = models.BooleanField("معيد", default=False)  # تعريف حقل/علاقة في نموذج Django
    تاريخ_التكوين_السابق_للمعيدين = models.DateField("تاريخ التكوين السابق للمعيدين", null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    المستخدم = models.CharField("المستخدم", max_length=120, null=True, blank=True)  # تعريف حقل/علاقة في نموذج Django
    class Meta:  # تعريف كلاس (Class)
        verbose_name = "متكوّن (عن طريق التمهين)"  # تعيين قيمة لمتغير/إعداد
        verbose_name_plural = "عن طريق التمهين"  # تعيين قيمة لمتغير/إعداد

class مسائي_ومعابر(BaseTrainee):  # تعريف كلاس (Class)
    نوع_التكوين = models.CharField(
        "نوع التكوين",
        max_length=20,
        choices=EVENING_TRAINING_TYPE_CHOICES,
        default="مسائي",
        db_index=True,
    )

    class Meta:  # تعريف كلاس (Class)
        verbose_name = "متكوّن (الدروس المسائية والمعابر)"  # تعيين قيمة لمتغير/إعداد
        verbose_name_plural = "الدروس المسائية والمعابر"  # تعيين قيمة لمتغير/إعداد


class كشفغياب(models.Model):
    PROGRAM_CHOICES = [
        ("initial", "حضوري أولي"),
        ("apprentice", "تمهين"),
        ("evening", "دروس مسائية"),
        ("crossing", "معابر"),
    ]

    WEEKDAY_CHOICES = [
        # تعتمد هذه القيم على ترقيم Python calendar حيث الإثنين = 0 والأحد = 6
        (6, "الأحد"),
        (0, "الإثنين"),
        (1, "الثلاثاء"),
        (2, "الأربعاء"),
        (3, "الخميس"),
        (4, "الجمعة"),
        (5, "السبت"),
    ]

    البرنامج = models.CharField("النمط", max_length=20, choices=PROGRAM_CHOICES)
    التخصص = models.CharField("التخصص", max_length=200, blank=True, default="")
    الدفعة = models.ForeignKey("دفعة", verbose_name="الدفعة", on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_sheets")
    الشهر = models.PositiveSmallIntegerField("الشهر")
    السنة = models.PositiveIntegerField("السنة")
    يوم_الدراسة_1 = models.PositiveSmallIntegerField("يوم الدراسة 1", choices=WEEKDAY_CHOICES, null=True, blank=True)
    يوم_الدراسة_2 = models.PositiveSmallIntegerField("يوم الدراسة 2", choices=WEEKDAY_CHOICES, null=True, blank=True)
    يوم_الدراسة_3 = models.PositiveSmallIntegerField("يوم الدراسة 3", choices=WEEKDAY_CHOICES, null=True, blank=True)
    يوم_الدراسة_4 = models.PositiveSmallIntegerField("يوم الدراسة 4", choices=WEEKDAY_CHOICES, null=True, blank=True)
    يوم_الدراسة_5 = models.PositiveSmallIntegerField("يوم الدراسة 5", choices=WEEKDAY_CHOICES, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_attendance_sheets", verbose_name="أنشأ بواسطة")
    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    updated_at = models.DateTimeField("تاريخ التحديث", auto_now=True)

    class Meta:
        verbose_name = "جدول غيابات"
        verbose_name_plural = "جداول الغيابات"
        ordering = ["-السنة", "-الشهر", "البرنامج", "التخصص"]
        constraints = [
            models.UniqueConstraint(
                fields=["البرنامج", "الدفعة", "التخصص", "الشهر", "السنة"],
                name="trainees_unique_attendance_sheet_per_scope",
            )
        ]

    def __str__(self):
        batch = f" - {self.الدفعة}" if self.الدفعة else ""
        specialty = f" - {self.التخصص}" if self.التخصص else ""
        return f"{self.get_البرنامج_display()}{specialty}{batch} - {self.الشهر:02d}/{self.السنة}"


class خليةغياب(models.Model):
    STATUS_CHOICES = [
        ("present", "حاضر"),
        ("absent", "غائب"),
        ("excused", "غائب بعذر"),
        ("late", "متأخر"),
    ]

    الكشف = models.ForeignKey("كشفغياب", on_delete=models.CASCADE, related_name="entries", verbose_name="الجدول")
    trainee_id = models.PositiveIntegerField("معرّف المتكوّن")
    التاريخ = models.DateField("التاريخ")
    رقم_الخانة = models.PositiveSmallIntegerField("رقم الخانة", default=1)
    الحالة = models.CharField("الحالة", max_length=20, choices=STATUS_CHOICES, default="present")
    ملاحظة = models.CharField("ملاحظة", max_length=255, blank=True, default="")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="attendance_entries", verbose_name="سجل بواسطة")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "خلية غياب"
        verbose_name_plural = "خلايا الغياب"
        ordering = ["التاريخ", "trainee_id", "رقم_الخانة"]
        constraints = [
            models.UniqueConstraint(fields=["الكشف", "trainee_id", "التاريخ", "رقم_الخانة"], name="trainees_unique_attendance_cell_slot"),
        ]
        indexes = [
            models.Index(fields=["الكشف", "التاريخ", "رقم_الخانة"]),
            models.Index(fields=["الكشف", "trainee_id", "التاريخ", "رقم_الخانة"]),
        ]

    def __str__(self):
        return f"{self.الكشف} / {self.trainee_id} / {self.التاريخ} / خانة {self.رقم_الخانة}"




class AttendanceAction(models.Model):
    ACTION_SOURCE_CHOICES = [
        ("daily", "غيابات بالأيام"),
        ("slots", "غيابات بالحصة"),
    ]

    ACTION_TYPE_CHOICES = [
        ("excuse_1", "الإعذار الأول"),
        ("excuse_2", "الإعذار الثاني"),
        ("excuse_3", "الإعذار الثالث"),
        ("summon", "الاستدعاء"),
    ]

    STATUS_CHOICES = [
        ("pending", "بانتظار الإكمال"),
        ("ready", "جاهز للطباعة"),
        ("issued", "تم الإصدار"),
        ("delivered", "تم التسليم"),
        ("cancelled", "ملغى"),
    ]

    ARCHIVE_STATE_CHOICES = [
        ("active", "نشط"),
        ("archived", "مؤرشف"),
    ]

    source = models.CharField("مصدر الإجراء", max_length=20, choices=ACTION_SOURCE_CHOICES, default="daily")
    program = models.CharField("النمط", max_length=20, choices=كشفغياب.PROGRAM_CHOICES)
    month = models.PositiveSmallIntegerField("الشهر")
    year = models.PositiveIntegerField("السنة")
    batch = models.ForeignKey("دفعة", verbose_name="الدفعة", on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_actions")
    specialty = models.CharField("التخصص وقت الإنشاء", max_length=200, blank=True, default="")

    trainee_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name="نوع المتكوّن")
    trainee_object_id = models.PositiveIntegerField("معرّف المتكوّن")
    trainee = GenericForeignKey("trainee_content_type", "trainee_object_id")

    trainee_name = models.CharField("اللقب والاسم", max_length=255)
    trainee_specialty = models.CharField("التخصص", max_length=200, blank=True, default="")
    trainee_address = models.CharField("العنوان", max_length=255, blank=True, default="")

    action_type = models.CharField("نوع الإجراء", max_length=20, choices=ACTION_TYPE_CHOICES)
    trigger_count = models.PositiveIntegerField("عدد الغيابات المحتسبة", default=0)
    threshold_value = models.PositiveIntegerField("العتبة المعتمدة", default=5)

    document_number = models.CharField("رقم الوثيقة", max_length=120, blank=True, default="")
    absence_start_date = models.DateField("تاريخ بداية الغياب", null=True, blank=True)
    send_date = models.DateField("تاريخ الإرسال / التحرير", null=True, blank=True)
    status = models.CharField("الحالة", max_length=20, choices=STATUS_CHOICES, default="pending")
    notes = models.TextField("ملاحظات", blank=True, default="")
    is_archived = models.BooleanField("مؤرشف", default=False)
    archived_at = models.DateTimeField("تاريخ الأرشفة", null=True, blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_attendance_actions", verbose_name="أُنشئ بواسطة")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_attendance_actions", verbose_name="آخر تعديل بواسطة")
    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    updated_at = models.DateTimeField("آخر تحديث", auto_now=True)

    class Meta:
        verbose_name = "إجراء غياب"
        verbose_name_plural = "إجراءات الغياب"
        ordering = ["-year", "-month", "program", "-created_at", "trainee_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "program", "year", "month", "batch", "specialty", "trainee_content_type", "trainee_object_id", "action_type"],
                name="trainees_unique_attendance_action_per_scope",
            )
        ]
        indexes = [
            models.Index(fields=["source", "program", "year", "month", "action_type"]),
            models.Index(fields=["source", "program", "status"]),
            models.Index(fields=["source", "program", "is_archived"]),
        ]

    def save(self, *args, **kwargs):
        self.trainee_name = (self.trainee_name or "").strip()
        self.trainee_specialty = (self.trainee_specialty or "").strip()
        self.trainee_address = (self.trainee_address or "").strip()
        self.specialty = (self.specialty or "").strip()
        if self.absence_start_date and self.send_date and self.status == "pending":
            self.status = "ready"
        super().save(*args, **kwargs)

    @property
    def source_label(self):
        return dict(self.ACTION_SOURCE_CHOICES).get(self.source, self.source or "")

    @property
    def archive_state(self):
        return "archived" if self.is_archived else "active"

    @property
    def archive_state_label(self):
        return "مؤرشف" if self.is_archived else "نشط"

    @property
    def document_title(self):
        return "الاستدعاء" if self.action_type == "summon" else "الإعذار"

    @property
    def action_stage_label(self):
        return {
            "excuse_1": "الأول",
            "excuse_2": "الثاني",
            "excuse_3": "الثالث",
            "summon": "",
        }.get(self.action_type, "")

    @property
    def document_heading(self):
        if self.action_type == "summon":
            return "الاستدعــاء"
        suffix = self.action_stage_label
        return f"الإعـــــــذار {suffix}".strip()

    @property
    def absence_start_date_display(self):
        return self.absence_start_date.strftime("%Y-%m-%d") if self.absence_start_date else "..........................."

    @property
    def send_date_display(self):
        return self.send_date.strftime("%Y-%m-%d") if self.send_date else "..........................."

    @property
    def action_rank(self):
        return {"excuse_1": 1, "excuse_2": 2, "excuse_3": 3, "summon": 4}.get(self.action_type, 0)

    def __str__(self):
        return f"{self.get_action_type_display()} - {self.trainee_name} - {self.month:02d}/{self.year}"


# ----------------------------
# Custom (Dynamic) Columns
# ----------------------------



class AttendanceActionDeletion(models.Model):
    ACTION_SOURCE_CHOICES = AttendanceAction.ACTION_SOURCE_CHOICES

    source = models.CharField("مصدر الإجراء", max_length=20, choices=ACTION_SOURCE_CHOICES, default="daily")
    program = models.CharField("النمط", max_length=20, choices=كشفغياب.PROGRAM_CHOICES)
    month = models.PositiveSmallIntegerField("الشهر")
    year = models.PositiveIntegerField("السنة")
    batch = models.ForeignKey("دفعة", verbose_name="الدفعة", on_delete=models.SET_NULL, null=True, blank=True, related_name="deleted_attendance_actions")
    specialty = models.CharField("التخصص وقت الحذف", max_length=200, blank=True, default="")
    trainee_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name="نوع المتكوّن")
    trainee_object_id = models.PositiveIntegerField("معرّف المتكوّن")
    action_type = models.CharField("نوع الإجراء", max_length=20, choices=AttendanceAction.ACTION_TYPE_CHOICES)
    deleted_at = models.DateTimeField("تاريخ الحذف", auto_now_add=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="deleted_attendance_actions", verbose_name="حُذف بواسطة")

    class Meta:
        verbose_name = "حذف إجراء غياب"
        verbose_name_plural = "سجل حذف إجراءات الغياب"
        constraints = [
            models.UniqueConstraint(
                fields=["source", "program", "year", "month", "batch", "specialty", "trainee_content_type", "trainee_object_id", "action_type"],
                name="trainees_unique_attendance_action_deletion_per_scope",
            )
        ]
        indexes = [
            models.Index(fields=["source", "program", "year", "month"]),
            models.Index(fields=["source", "program", "action_type"]),
        ]

    def __str__(self):
        return f"{self.program} - {self.action_type} - {self.month:02d}/{self.year}"


class DismissalDecision(models.Model):
    DECISION_SCOPE_CHOICES = [
        ("current", "الحاليين"),
        ("graduated", "المتخرجين"),
    ]

    STATUS_CHOICES = [
        ("draft", "مسودة"),
        ("ready", "جاهز للطباعة"),
        ("issued", "تم الإصدار"),
        ("cancelled", "ملغى"),
    ]

    program = models.CharField("النمط", max_length=20, choices=كشفغياب.PROGRAM_CHOICES)
    decision_scope = models.CharField("قسم مقرر الفصل", max_length=20, choices=DECISION_SCOPE_CHOICES, default="current")

    trainee_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name="نوع المتكوّن")
    trainee_object_id = models.PositiveIntegerField("معرّف المتكوّن")
    trainee = GenericForeignKey("trainee_content_type", "trainee_object_id")

    trainee_name = models.CharField("اسم المتكوّن وقت الإنشاء", max_length=255)
    birth_date = models.DateField("تاريخ الميلاد", null=True, blank=True)
    birth_place = models.CharField("مكان الميلاد", max_length=255, blank=True, default="")
    registration_number = models.CharField("رقم التسجيل", max_length=80, blank=True, default="")
    specialty = models.CharField("التخصص", max_length=200, blank=True, default="")
    training_start_date = models.DateField("بداية التربص", null=True, blank=True)
    training_end_date = models.DateField("نهاية التربص", null=True, blank=True)
    group_code = models.CharField("رمز الفرع / الفوج", max_length=120, blank=True, default="")
    semester = models.CharField("السداسي", max_length=80, blank=True, default="")
    removal_date = models.DateField("تاريخ الشطب", null=True, blank=True)
    removal_number = models.CharField("رقم الشطب", max_length=120, blank=True, default="")

    decision_number = models.CharField("رقم مقرر الفصل", max_length=120, blank=True, default="")
    disciplinary_record_number = models.CharField("رقم محضر اللجنة التأديبية", max_length=120, blank=True, default="")
    disciplinary_record_date = models.DateField("تاريخ محضر اللجنة التأديبية", null=True, blank=True)
    dismissal_start_date = models.DateField("تاريخ بداية الفصل", null=True, blank=True)
    decision_date = models.DateField("تاريخ تحرير المقرر", null=True, blank=True)
    status = models.CharField("حالة المقرر", max_length=20, choices=STATUS_CHOICES, default="draft")
    notes = models.TextField("ملاحظات", blank=True, default="")
    is_archived = models.BooleanField("مؤرشف", default=False)
    archived_at = models.DateTimeField("تاريخ الأرشفة", null=True, blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_dismissal_decisions", verbose_name="أُنشئ بواسطة")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_dismissal_decisions", verbose_name="آخر تعديل بواسطة")
    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    updated_at = models.DateTimeField("آخر تحديث", auto_now=True)

    class Meta:
        verbose_name = "مقرر فصل"
        verbose_name_plural = "مقررات الفصل"
        ordering = ["program", "decision_scope", "is_archived", "specialty", "trainee_name", "id"]
        indexes = [
            models.Index(fields=["program", "decision_scope", "status"]),
            models.Index(fields=["program", "specialty"]),
            models.Index(fields=["program", "decision_scope", "is_archived"]),
            models.Index(fields=["trainee_content_type", "trainee_object_id", "is_archived"]),
        ]

    @property
    def decision_year(self):
        d = self.decision_date or self.disciplinary_record_date or self.dismissal_start_date
        return d.year if d else ""

    @property
    def program_label(self):
        return dict(كشفغياب.PROGRAM_CHOICES).get(self.program, self.program)

    @property
    def scope_label(self):
        return dict(self.DECISION_SCOPE_CHOICES).get(self.decision_scope, self.decision_scope)

    def sync_snapshot_from_trainee(self, trainee):
        self.trainee_name = getattr(trainee, "اللقب_والاسم", str(trainee) or "")
        self.birth_date = getattr(trainee, "تاريخ_الميلاد", None)
        birth_parts = [getattr(trainee, "البلدية", "") or "", getattr(trainee, "الولاية", "") or ""]
        self.birth_place = " / ".join([p for p in birth_parts if p]).strip()
        self.registration_number = getattr(trainee, "رقم_التسجيل", "") or ""
        self.specialty = getattr(trainee, "التخصص", "") or ""
        self.training_start_date = getattr(trainee, "تاريخ_بداية_التكوين", None)
        self.training_end_date = getattr(trainee, "تاريخ_نهاية_التكوين", None)
        self.group_code = getattr(trainee, "رمز_التخصص", "") or self.group_code or ""
        self.semester = getattr(trainee, "السداسي", "") or ""
        self.removal_date = getattr(trainee, "تاريخ_الشطب", None)
        self.removal_number = getattr(trainee, "رقم_الشطب", "") or ""
        

        if not self.disciplinary_record_number and self.removal_number:
            self.disciplinary_record_number = self.removal_number

        if not self.disciplinary_record_date:
            self.disciplinary_record_date = self.removal_date
        if not self.dismissal_start_date:
            self.dismissal_start_date = self.disciplinary_record_date or self.removal_date
        if not self.decision_date:
            self.decision_date = self.disciplinary_record_date or self.removal_date

    def save(self, *args, **kwargs):
        if not self.disciplinary_record_number and self.removal_number:
            self.disciplinary_record_number = self.removal_number

        if self.disciplinary_record_date and not self.dismissal_start_date:
            self.dismissal_start_date = self.disciplinary_record_date
        if self.disciplinary_record_date and not self.decision_date:
            self.decision_date = self.disciplinary_record_date
        if self.decision_number and self.disciplinary_record_number and self.disciplinary_record_date and self.status == "draft":
            self.status = "ready"
        super().save(*args, **kwargs)

    @property
    def archive_state(self):
        return "archived" if self.is_archived else "active"

    @property
    def archive_state_label(self):
        return "مؤرشف" if self.is_archived else "نشط"

    def __str__(self):
        return f"مقرر فصل - {self.trainee_name} - {self.program_label}"




class SanctionRecord(models.Model):
    SANCTION_SCOPE_CHOICES = [
        ("current", "الحاليين"),
        ("graduated", "المتخرجين"),
    ]

    STATUS_CHOICES = [
        ("draft", "مسودة"),
        ("ready", "جاهزة للطباعة"),
        ("issued", "تم الإصدار"),
        ("delivered", "تم التسليم للمتكون"),
        ("cancelled", "ملغاة"),
    ]

    ARCHIVE_STATE_CHOICES = [
        ("active", "نشطة"),
        ("archived", "مؤرشفة"),
    ]

    program = models.CharField("النمط", max_length=20, choices=كشفغياب.PROGRAM_CHOICES)
    sanction_scope = models.CharField("قسم العقوبة", max_length=20, choices=SANCTION_SCOPE_CHOICES, default="current")

    trainee_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name="نوع المتكوّن")
    trainee_object_id = models.PositiveIntegerField("معرّف المتكوّن")
    trainee = GenericForeignKey("trainee_content_type", "trainee_object_id")

    trainee_name = models.CharField("اسم المتكوّن وقت الإنشاء", max_length=255)
    registration_number = models.CharField("رقم التسجيل", max_length=80, blank=True, default="")
    specialty = models.CharField("التخصص", max_length=200, blank=True, default="")
    group_code = models.CharField("رمز الفرع / الفوج", max_length=120, blank=True, default="")
    semester = models.CharField("السداسي", max_length=80, blank=True, default="")

    document_number = models.CharField("رقم العقوبة", max_length=120, blank=True, default="")
    sanction_text = models.CharField("العقوبة", max_length=255, blank=True, default="")
    disciplinary_record_number = models.CharField("رقم محضر اللجنة التأديبية", max_length=120, blank=True, default="")
    disciplinary_record_date = models.DateField("تاريخ محضر اللجنة التأديبية", null=True, blank=True)
    decision_date = models.DateField("تاريخ تحرير العقوبة", null=True, blank=True)
    status = models.CharField("حالة العقوبة", max_length=20, choices=STATUS_CHOICES, default="draft")
    notes = models.TextField("ملاحظات", blank=True, default="")

    is_archived = models.BooleanField("مؤرشفة", default=False)
    archived_at = models.DateTimeField("تاريخ الأرشفة", null=True, blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_sanction_records", verbose_name="أُنشئ بواسطة")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_sanction_records", verbose_name="آخر تعديل بواسطة")
    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    updated_at = models.DateTimeField("آخر تحديث", auto_now=True)

    class Meta:
        verbose_name = "عقوبة"
        verbose_name_plural = "العقوبات"
        ordering = ["program", "sanction_scope", "is_archived", "specialty", "trainee_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["program", "sanction_scope", "trainee_content_type", "trainee_object_id"],
                name="trainees_unique_sanction_record_per_trainee",
            )
        ]
        indexes = [
            models.Index(fields=["program", "sanction_scope", "status"]),
            models.Index(fields=["program", "sanction_scope", "is_archived"]),
            models.Index(fields=["program", "specialty"]),
        ]

    @property
    def document_year(self):
        d = self.decision_date or self.disciplinary_record_date
        return d.year if d else ""

    @property
    def program_label(self):
        return dict(كشفغياب.PROGRAM_CHOICES).get(self.program, self.program)

    @property
    def scope_label(self):
        return dict(self.SANCTION_SCOPE_CHOICES).get(self.sanction_scope, self.sanction_scope)

    @property
    def archive_state(self):
        return "archived" if self.is_archived else "active"

    @property
    def archive_state_label(self):
        return "مؤرشفة" if self.is_archived else "نشطة"

    def sync_snapshot_from_trainee(self, trainee):
        self.trainee_name = getattr(trainee, "اللقب_والاسم", str(trainee) or "")
        self.registration_number = getattr(trainee, "رقم_التسجيل", "") or ""
        self.specialty = getattr(trainee, "التخصص", "") or ""
        self.group_code = getattr(trainee, "رمز_التخصص", "") or self.group_code or ""
        self.semester = getattr(trainee, "السداسي", "") or ""

    def save(self, *args, **kwargs):
        if self.disciplinary_record_date and not self.decision_date:
            self.decision_date = self.disciplinary_record_date
        if self.document_number and self.sanction_text and self.disciplinary_record_number and self.disciplinary_record_date and self.status == "draft":
            self.status = "ready"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"عقوبة - {self.trainee_name} - {self.program_label}"



class SummonsRecord(models.Model):
    SUMMONS_SCOPE_CHOICES = [
        ("current", "الحاليين"),
        ("graduated", "المتخرجين"),
    ]

    SUMMONS_TYPE_CHOICES = [
        ("graduate_title", "عدم استلام عنوان مذكرة التخرج"),
        ("contract_termination", "فسخ العقد من المستخدم"),
        ("employer_absence", "غيابات المستخدم"),
        ("intermittent_absence", "الغيابات المتذبذبة"),
        ("specific_session_absence", "عدم حضور حصة معينة"),
        ("disciplinary_council", "المجلس التأديبي"),
        ("supervisor_absence", "استدعاء المؤطر"),
    ]

    STATUS_CHOICES = [
        ("draft", "مسودة"),
        ("ready", "جاهز للطباعة"),
        ("issued", "تم الإصدار"),
        ("delivered", "تم التسليم للمتكون"),
        ("cancelled", "ملغى"),
    ]

    program = models.CharField("النمط", max_length=20, choices=كشفغياب.PROGRAM_CHOICES)
    summons_scope = models.CharField("قسم الاستدعاء", max_length=20, choices=SUMMONS_SCOPE_CHOICES, default="current")
    summons_type = models.CharField("نوع الاستدعاء", max_length=40, choices=SUMMONS_TYPE_CHOICES, default="graduate_title")

    trainee_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name="نوع المتكوّن")
    trainee_object_id = models.PositiveIntegerField("معرّف المتكوّن")
    trainee = GenericForeignKey("trainee_content_type", "trainee_object_id")

    trainee_name = models.CharField("اسم المتكوّن وقت الإنشاء", max_length=255)
    registration_number = models.CharField("رقم التسجيل", max_length=80, blank=True, default="")
    address = models.CharField("العنوان", max_length=255, blank=True, default="")
    specialty = models.CharField("التخصص", max_length=200, blank=True, default="")
    group_code = models.CharField("رمز الفرع / الفوج", max_length=120, blank=True, default="")
    semester = models.CharField("السداسي", max_length=80, blank=True, default="")

    document_number = models.CharField("رقم الاستدعاء", max_length=120, blank=True, default="")
    issue_date = models.DateField("تاريخ تحرير الاستدعاء", null=True, blank=True)
    from_date = models.DateField("منذ تاريخ", null=True, blank=True)
    contract_termination_date = models.DateField("تاريخ فسخ العقد", null=True, blank=True)
    council_date = models.DateField("يوم المجلس", null=True, blank=True)
    council_time = models.CharField("ساعة المجلس", max_length=80, blank=True, default="")
    lesson_name = models.CharField("الحصة", max_length=160, blank=True, default="")
    notes = models.TextField("ملاحظات", blank=True, default="")
    status = models.CharField("حالة الاستدعاء", max_length=20, choices=STATUS_CHOICES, default="draft")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_summons_records", verbose_name="أُنشئ بواسطة")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_summons_records", verbose_name="آخر تعديل بواسطة")
    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    updated_at = models.DateTimeField("آخر تحديث", auto_now=True)

    class Meta:
        verbose_name = "استدعاء"
        verbose_name_plural = "الاستدعاءات"
        ordering = ["program", "summons_scope", "summons_type", "specialty", "trainee_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["program", "summons_scope", "summons_type", "trainee_content_type", "trainee_object_id"],
                name="trainees_unique_summons_per_type_trainee",
            )
        ]
        indexes = [
            models.Index(fields=["program", "summons_scope", "summons_type"]),
            models.Index(fields=["program", "status"]),
            models.Index(fields=["program", "specialty"]),
        ]

    @property
    def document_year(self):
        return self.issue_date.year if self.issue_date else ""

    @property
    def program_label(self):
        return dict(كشفغياب.PROGRAM_CHOICES).get(self.program, self.program)

    @property
    def type_label(self):
        return dict(self.SUMMONS_TYPE_CHOICES).get(self.summons_type, self.summons_type)

    @property
    def scope_label(self):
        return dict(self.SUMMONS_SCOPE_CHOICES).get(self.summons_scope, self.summons_scope)

    def sync_snapshot_from_trainee(self, trainee):
        self.trainee_name = getattr(trainee, "اللقب_والاسم", str(trainee) or "")
        self.registration_number = getattr(trainee, "رقم_التسجيل", "") or ""
        self.address = getattr(trainee, "العنوان_بالعربية", "") or getattr(trainee, "ولاية_الإقامة_بالعربية", "") or ""
        self.specialty = getattr(trainee, "التخصص", "") or ""
        self.group_code = getattr(trainee, "رمز_التخصص", "") or self.group_code or ""
        self.semester = getattr(trainee, "السداسي", "") or ""

    def save(self, *args, **kwargs):
        if self.document_number and self.issue_date and self.status == "draft":
            self.status = "ready"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"استدعاء - {self.get_summons_type_display()} - {self.trainee_name}"


class AttendanceStatSnapshot(models.Model):
    PROGRAM_CHOICES = كشفغياب.PROGRAM_CHOICES

    program = models.CharField("النمط", max_length=20, choices=PROGRAM_CHOICES)
    month = models.PositiveSmallIntegerField("الشهر")
    year = models.PositiveIntegerField("السنة")
    batch = models.ForeignKey("دفعة", verbose_name="الدفعة", on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_stat_snapshots")
    specialty = models.CharField("التخصص المطلوب", max_length=200, blank=True, default="")
    trainee_id = models.PositiveIntegerField("معرّف المتكوّن")
    trainee_name = models.CharField("اسم المتكوّن", max_length=255)
    trainee_specialty = models.CharField("تخصص المتكوّن", max_length=200, blank=True, default="")
    present_count = models.PositiveIntegerField("عدد الحضور", default=0)
    absent_count = models.PositiveIntegerField("عدد الغيابات", default=0)
    excused_count = models.PositiveIntegerField("عدد الغيابات بعذر", default=0)
    late_count = models.PositiveIntegerField("عدد التأخرات", default=0)
    total_recorded = models.PositiveIntegerField("المجموع المسجل", default=0)
    absence_rate = models.FloatField("نسبة الغياب", default=0)
    saved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="saved_attendance_stat_snapshots", verbose_name="حُفظ بواسطة")
    created_at = models.DateTimeField("تاريخ الحفظ", auto_now_add=True)
    updated_at = models.DateTimeField("آخر تحديث", auto_now=True)

    class Meta:
        verbose_name = "إحصائية غياب محفوظة"
        verbose_name_plural = "إحصائيات الغياب المحفوظة"
        ordering = ["-year", "-month", "program", "specialty", "trainee_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["program", "year", "month", "batch", "specialty", "trainee_id"],
                name="trainees_unique_attendance_stat_snapshot_per_scope",
            )
        ]
        indexes = [
            models.Index(fields=["program", "year", "month"]),
            models.Index(fields=["program", "batch", "specialty"]),
        ]

    def __str__(self):
        batch = f" - {self.batch}" if self.batch else ""
        specialty = f" - {self.specialty}" if self.specialty else ""
        return f"{self.get_program_display()}{specialty}{batch} - {self.month:02d}/{self.year} - {self.trainee_name}"


class UserAttendanceSummaryArchive(models.Model):
    """أرشيف تقارير متابعة الحضور والغيابات لدى المستخدم.

    نخزن صفوف التقرير كـ JSON حتى تبقى النسخة المؤرشفة ثابتة حتى لو تغيرت
    سجلات الغياب أو بيانات المتكون لاحقًا.
    """

    program = models.CharField("النمط", max_length=20, choices=كشفغياب.PROGRAM_CHOICES, default="apprentice")
    title = models.CharField("عنوان التقرير", max_length=255)
    filters_json = models.JSONField("الفلاتر المستعملة", default=dict, blank=True)
    rows_json = models.JSONField("صفوف التقرير", default=list, blank=True)
    row_count = models.PositiveIntegerField("عدد المتكونين", default=0)
    total_present = models.PositiveIntegerField("مجموع الحضور في الفترة", default=0)
    total_absent = models.PositiveIntegerField("مجموع الغيابات في الفترة", default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="user_attendance_summary_archives", verbose_name="أرشف بواسطة")
    created_at = models.DateTimeField("تاريخ الأرشفة", auto_now_add=True)

    class Meta:
        verbose_name = "أرشيف متابعة حضور وغيابات المستخدم"
        verbose_name_plural = "أرشيف متابعة الحضور والغيابات لدى المستخدم"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["program", "created_at"]),
        ]

    def __str__(self):
        return self.title


class CustomField(models.Model):  # تعريف كلاس (Class)
    PROGRAM_CHOICES = [  # تعيين قيمة لمتغير/إعداد
        ("all", "كل الأنماط"),  # سطر كود لتنفيذ منطق/إعداد
        ("initial", "حضوري أولي"),  # سطر كود لتنفيذ منطق/إعداد
        ("apprentice", "تمهين"),  # سطر كود لتنفيذ منطق/إعداد
        ("evening", "دروس مسائية"),  # سطر كود لتنفيذ منطق/إعداد
        ("crossing", "معابر"),  # سطر كود لتنفيذ منطق/إعداد
    ]  # سطر كود لتنفيذ منطق/إعداد

    FIELD_TYPE_CHOICES = [  # تعيين قيمة لمتغير/إعداد
        ("text", "نص"),  # سطر كود لتنفيذ منطق/إعداد
        ("number", "رقم"),  # سطر كود لتنفيذ منطق/إعداد
        ("date", "تاريخ"),  # سطر كود لتنفيذ منطق/إعداد
        ("boolean", "نعم / لا"),  # سطر كود لتنفيذ منطق/إعداد
    ]  # سطر كود لتنفيذ منطق/إعداد

    label = models.CharField("اسم العمود", max_length=150)  # تعريف حقل/علاقة في نموذج Django

    key = models.SlugField(  # تعريف حقل/علاقة في نموذج Django
        "المفتاح (فريد)",  # سطر كود لتنفيذ منطق/إعداد
        help_text="اسم داخلي فريد (بدون مسافات). مثال: رقم_ملف",  # تعيين قيمة لمتغير/إعداد
        max_length=80,  # تعيين قيمة لمتغير/إعداد
        unique=True,  # تعيين قيمة لمتغير/إعداد
        blank=True,  # تعيين قيمة لمتغير/إعداد
        editable=False,  # تعيين قيمة لمتغير/إعداد
    )  # سطر كود لتنفيذ منطق/إعداد

    program = models.CharField("النمط", max_length=20, choices=PROGRAM_CHOICES, default="all")  # تعريف حقل/علاقة في نموذج Django
    field_type = models.CharField("نوع الحقل", max_length=20, choices=FIELD_TYPE_CHOICES, default="text")  # تعريف حقل/علاقة في نموذج Django
    required = models.BooleanField("إجباري", default=False)  # تعريف حقل/علاقة في نموذج Django
    active = models.BooleanField("مفعل", default=True)  # تعريف حقل/علاقة في نموذج Django
    order = models.PositiveIntegerField("الترتيب", default=0)  # تعريف حقل/علاقة في نموذج Django

    def save(self, *args, **kwargs):  # تعريف دالة (Function)
        # Auto-generate key if missing: cf_<n>
        if not self.key:  # شرط (If)
            last = CustomField.objects.order_by("-id").first()  # تعيين قيمة لمتغير/إعداد
            next_number = (last.id + 1) if last else 1  # تعيين قيمة لمتغير/إعداد
            self.key = f"cf_{next_number}"  # تعيين قيمة لمتغير/إعداد

        # Auto-generate order if not provided
        if not self.order or self.order == 0:  # شرط (If)
            last_order = CustomField.objects.aggregate(models.Max("order"))["order__max"] or 0  # تعريف حقل/علاقة في نموذج Django
            self.order = last_order + 10  # تعيين قيمة لمتغير/إعداد

        super().save(*args, **kwargs)  # سطر كود لتنفيذ منطق/إعداد

    class Meta:
        verbose_name = "عمود إضافي"
        verbose_name_plural = "إضافة أعمدة"
        ordering = ["program", "order", "id"]

    def __str__(self):  # تعريف دالة (Function)
        return f"{self.label}"  # إرجاع قيمة من الدالة


class CustomFieldValue(models.Model):  # تعريف كلاس (Class)
    field = models.ForeignKey(CustomField, on_delete=models.CASCADE, related_name="values")  # تعريف حقل/علاقة في نموذج Django

    # Generic relation to any trainee model (حضوري_أولي/تمهين/مسائي_ومعابر)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)  # تعريف حقل/علاقة في نموذج Django
    object_id = models.PositiveIntegerField()  # تعريف حقل/علاقة في نموذج Django
    content_object = GenericForeignKey("content_type", "object_id")  # تعيين قيمة لمتغير/إعداد

    value_text = models.TextField(blank=True, default="")  # تعريف حقل/علاقة في نموذج Django
    created_at = models.DateTimeField(auto_now_add=True)  # تعريف حقل/علاقة في نموذج Django
    updated_at = models.DateTimeField(auto_now=True)  # تعريف حقل/علاقة في نموذج Django

    class Meta:  # تعريف كلاس (Class)
        unique_together = (("field", "content_type", "object_id"),)  # تعيين قيمة لمتغير/إعداد
        indexes = [  # تعيين قيمة لمتغير/إعداد
            models.Index(fields=["content_type", "object_id"]),  # تعريف حقل/علاقة في نموذج Django
            models.Index(fields=["field", "content_type", "object_id"]),  # تعريف حقل/علاقة في نموذج Django
        ]  # سطر كود لتنفيذ منطق/إعداد

    def __str__(self):  # تعريف دالة (Function)
        return f"{self.field.key}={self.value_text}"  # إرجاع قيمة من الدالة


from django.db.models.signals import post_save
from django.dispatch import receiver


class UserAccessProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="access_profile", verbose_name="المستخدم")
    access_enabled = models.BooleanField("الصلاحيات مفعلة", default=True)
    access_start_date = models.DateField("تاريخ بداية الصلاحية", null=True, blank=True)
    access_end_date = models.DateField("تاريخ نهاية الصلاحية", null=True, blank=True)
    ACCESS_TYPE_CHOICES = [
        ("permanent", "دائم"),
        ("temporary", "مؤقت"),
        ("trainee", "متربص"),
        ("shift", "مناوب"),
        ("visitor", "زائر"),
    ]

    access_type = models.CharField(
        "نوع الصلاحية",
        max_length=20,
        choices=ACCESS_TYPE_CHOICES,
        default="permanent",
    )

    access_start_time = models.TimeField(
        "وقت بداية السماح اليومي",
        null=True,
        blank=True,
    )

    access_end_time = models.TimeField(
        "وقت نهاية السماح اليومي",
        null=True,
        blank=True,
    )

    allowed_weekdays = models.CharField(
        "أيام الأسبوع المسموحة",
        max_length=50,
        blank=True,
        default="",
    )

    grace_period_days = models.PositiveIntegerField(
        "فترة السماح بالأيام",
        default=0,
    )

    suspended_reason = models.TextField(
        "سبب التعليق المؤقت",
        blank=True,
        default="",
    )

    ROLE_CODE_CHOICES = [
        ("general_manager", "مدير عام"),
        ("branch_manager", "مدير فرع"),
        ("registration_officer", "موظف تسجيل"),
        ("accountant", "محاسب"),
        ("trainer", "مكون / مدرب"),
        ("read_only", "مراقب"),
    ]
    role_code = models.CharField("الدور الجاهز", max_length=40, choices=ROLE_CODE_CHOICES, default="read_only")
    is_customized = models.BooleanField("تم تخصيص الصلاحيات يدويًا", default=False)

    can_access_admin_panel = models.BooleanField("يدخل لوحة الإدارة", default=False)
    can_manage_all_programs = models.BooleanField("نائب المدير: يدير كل الأنماط", default=False)

    initial_view = models.BooleanField("الحضوري: عرض", default=False)
    initial_add = models.BooleanField("الحضوري: إضافة", default=False)
    initial_change = models.BooleanField("الحضوري: تعديل", default=False)
    initial_delete = models.BooleanField("الحضوري: حذف", default=False)

    apprentice_view = models.BooleanField("التمهين: عرض", default=False)
    apprentice_add = models.BooleanField("التمهين: إضافة", default=False)
    apprentice_change = models.BooleanField("التمهين: تعديل", default=False)
    apprentice_delete = models.BooleanField("التمهين: حذف", default=False)

    evening_view = models.BooleanField("المسائي: عرض", default=False)
    evening_add = models.BooleanField("المسائي: إضافة", default=False)
    evening_change = models.BooleanField("المسائي: تعديل", default=False)
    evening_delete = models.BooleanField("المسائي: حذف", default=False)

    can_view_reports = models.BooleanField("عرض التقارير", default=False)
    can_export_data = models.BooleanField("تصدير البيانات", default=False)
    force_password_change = models.BooleanField("إجبار تغيير كلمة المرور عند أول دخول", default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "صلاحيات المستخدم"
        verbose_name_plural = "صلاحيات المستخدمين"

    def __str__(self):
        return f"صلاحيات {self.user.username}"

    def get_role_label(self):
        return dict(self.ROLE_CODE_CHOICES).get(self.role_code, self.role_code or "—")

    def has_active_access(self, on_date=None):
        from django.utils import timezone
        today = on_date or timezone.localdate()
        if not self.access_enabled:
            return False
        if self.access_start_date and today < self.access_start_date:
            return False
        if self.access_end_date and today > self.access_end_date:
            return False
        return True

    def access_status_message(self, on_date=None):
        from django.utils import timezone
        today = on_date or timezone.localdate()
        if not self.access_enabled:
            return "تم تعطيل الصلاحيات لهذا المستخدم."
        if self.access_start_date and today < self.access_start_date:
            return f"الصلاحيات ستبدأ بتاريخ {self.access_start_date:%Y-%m-%d}."
        if self.access_end_date and today > self.access_end_date:
            return f"انتهت صلاحية هذا المستخدم بتاريخ {self.access_end_date:%Y-%m-%d}."
        return "الصلاحيات مفعلة."

    def access_state_code(self, on_date=None):
        from django.utils import timezone
        # هذا الكود المختصر تستخدمه لوحة الإدارة لتحديد حالة الصلاحية الحالية بسرعة.
        today = on_date or timezone.localdate()
        if not self.access_enabled:
            return "disabled"
        if self.access_start_date and today < self.access_start_date:
            return "pending"
        if self.access_end_date and today > self.access_end_date:
            return "expired"
        return "active"

    def access_state_label(self, on_date=None):
        # نحول الكود الداخلي إلى نص عربي واضح لعرضه للمستخدم أو الإدارة.
        return {
            "disabled": "معطلة",
            "pending": "لم تبدأ بعد",
            "expired": "منتهية",
            "active": "نشطة",
        }.get(self.access_state_code(on_date=on_date), "غير معروفة")

    def days_until_expiry(self, on_date=None):
        from django.utils import timezone
        # نحسب عدد الأيام المتبقية حتى نهاية الصلاحية، وإذا لم توجد نهاية نرجع None.
        today = on_date or timezone.localdate()
        if not self.access_end_date:
            return None
        return (self.access_end_date - today).days

    def remaining_access_days(self, on_date=None):
        # هذه دالة توافقية لأن بعض ملفات الإدارة القديمة تستدعي هذا الاسم تحديدًا.
        return self.days_until_expiry(on_date=on_date)

    def is_expiring_within_days(self, days=7, on_date=None):
        # هذه الدالة تساعدنا في التنبيهات الإدارية لمعرفة الحسابات التي ستنتهي قريبًا.
        remaining = self.days_until_expiry(on_date=on_date)
        return remaining is not None and 0 <= remaining <= int(days)

    def expiry_urgency_label(self, on_date=None):
        # وسم مختصر يوضح درجة الاستعجال داخل لوحة الإدارة والتقارير.
        remaining = self.days_until_expiry(on_date=on_date)
        if remaining is None:
            return "مفتوحة"
        if remaining < 0:
            return "منتهية"
        if remaining == 0:
            return "تنتهي اليوم"
        if remaining <= 3:
            return "عاجلة جدًا"
        if remaining <= 7:
            return "قريبة"
        if remaining <= 15:
            return "مراقبة"
        return "مستقرة"

    def access_window_label(self):
        # نص عربي جاهز يصف نافذة بداية ونهاية الصلاحية.
        start_label = self.access_start_date.strftime("%Y-%m-%d") if self.access_start_date else "فوري"
        end_label = self.access_end_date.strftime("%Y-%m-%d") if self.access_end_date else "غير محدد"
        return f"من {start_label} إلى {end_label}"


    def get_access_state(self, on_date=None):
        # دالة توافقية مطلوبة من طبقة الصلاحيات القديمة.
        return self.access_state_code(on_date=on_date)

    def get_access_state_label(self, on_date=None):
        # دالة توافقية مطلوبة من بعض الشاشات القديمة.
        return self.access_state_label(on_date=on_date)

    def granted_programs(self):
        # نعيد نفس قائمة الملصقات القديمة حفاظًا على توافق الواجهات الحالية.
        return self.granted_program_labels()

    def current_daily_window_label(self):
        # وصف مبسط لنافذة السماح اليومية.
        if self.access_start_time and self.access_end_time:
            return f"يوميًا من {self.access_start_time.strftime('%H:%M')} إلى {self.access_end_time.strftime('%H:%M')}"
        if self.access_start_time:
            return f"يوميًا ابتداءً من {self.access_start_time.strftime('%H:%M')}"
        if self.access_end_time:
            return f"يوميًا حتى {self.access_end_time.strftime('%H:%M')}"
        return "بدون قيود يومية"

    def allowed_weekdays_display(self):
        # تحويل الأيام المخزنة كأرقام إلى نص عربي قابل للعرض.
        if not self.allowed_weekdays:
            return "كل الأيام"
        weekday_names = {
            '0': 'الاثنين',
            '1': 'الثلاثاء',
            '2': 'الأربعاء',
            '3': 'الخميس',
            '4': 'الجمعة',
            '5': 'السبت',
            '6': 'الأحد',
        }
        labels = []
        for raw in str(self.allowed_weekdays).split(','):
            code = raw.strip()
            if not code:
                continue
            labels.append(weekday_names.get(code, code))
        return '، '.join(labels) if labels else 'كل الأيام'

    def enabled_programs_count(self):
        # نحسب عدد الأنماط التي يملك المستخدم حق عرضها على الأقل.
        return sum([
            1 if self.initial_view else 0,
            1 if self.apprentice_view else 0,
            2 if self.evening_view else 0,
        ])

    def granted_programs_count(self):
        # اسم إضافي متوافق مع بعض ملفات الإدارة القديمة.
        return self.enabled_programs_count()

    def granted_program_labels(self):
        # نرجع قائمة أسماء الأنماط لأن الواجهة القديمة تستعمل join عليها.
        labels = []
        if any([self.initial_view, self.initial_add, self.initial_change, self.initial_delete]):
            labels.append("الحضوري الأولي")
        if any([self.apprentice_view, self.apprentice_add, self.apprentice_change, self.apprentice_delete]):
            labels.append("التمهين")
        if any([self.evening_view, self.evening_add, self.evening_change, self.evening_delete]):
            labels.append("الدروس المسائية")
            labels.append("المعابر")
        return labels

    def admin_permissions_summary(self):
        # ملخص عربي يشرح حالة الحساب داخل لوحة الإدارة
        parts = [f"الحالة الحالية: {self.access_state_label()}"]

        parts.append(f"نافذة الصلاحية: {self.access_window_label()}")

        programs = self.granted_program_labels()
        parts.append(
            "الأنماط المسموح بها: " +
            ("، ".join(programs) if programs else "لا توجد أنماط مفعلة")
        )

        extras = []
        if self.can_access_admin_panel:
            extras.append("دخول لوحة الإدارة")
        if self.can_manage_all_programs:
            extras.append("إدارة كل الأنماط")
        if self.can_view_reports:
            extras.append("عرض التقارير")
        if self.can_export_data:
            extras.append("تصدير البيانات")
        if self.force_password_change:
            extras.append("إجبار تغيير كلمة المرور")

        parts.append(
            "الامتيازات الإضافية: " +
            ("، ".join(extras) if extras else "لا توجد امتيازات إضافية")
        )

        return "\n".join(parts)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        user = self.user
        should_be_staff = bool(self.can_access_admin_panel or self.can_manage_all_programs or user.is_superuser)
        changed = False
        if user.is_staff != should_be_staff:
            user.is_staff = should_be_staff
            changed = True
        if changed:
            user.save(update_fields=["is_staff"])


class AccessAuditLog(models.Model):
    ACTION_CHOICES = [
        ("create", "إنشاء ملف صلاحيات"),
        ("update", "تعديل الصلاحيات"),
        ("delete", "حذف ملف الصلاحيات"),
        ("activate", "تفعيل الصلاحيات"),
        ("disable", "تعطيل الصلاحيات"),
        ("extend", "تمديد الصلاحية"),
        ("force_password_on", "تفعيل إجبار تغيير كلمة المرور"),
        ("force_password_off", "إلغاء إجبار تغيير كلمة المرور"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="performed_access_audit_logs",
        verbose_name="تم بواسطة",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="access_audit_logs",
        verbose_name="المستخدم المستهدف",
    )
    profile = models.ForeignKey(
        "UserAccessProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        verbose_name="ملف الصلاحيات",
    )
    action = models.CharField("نوع العملية", max_length=40, choices=ACTION_CHOICES, default="update")
    changed_fields = models.JSONField("الحقول المتغيرة", default=list, blank=True)
    before_data = models.JSONField("القيم قبل التغيير", default=dict, blank=True)
    after_data = models.JSONField("القيم بعد التغيير", default=dict, blank=True)
    notes = models.TextField("ملاحظات", blank=True, default="")
    created_at = models.DateTimeField("تاريخ العملية", auto_now_add=True)

    class Meta:
        verbose_name = "سجل تدقيق الصلاحيات"
        verbose_name_plural = "سجل تدقيق الصلاحيات"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        target = self.target_user.username if self.target_user else "بدون مستخدم"
        actor = self.actor.username if self.actor else "غير معروف"
        return f"{target} - {self.get_action_display()} - بواسطة {actor}"

    def changed_fields_labels(self):
        """عرض عربي مختصر للحقول التي تغيرت."""
        labels = [ACCESS_PROFILE_AUDIT_LABELS.get(name, name) for name in (self.changed_fields or [])]
        return "، ".join(labels) if labels else "—"

    def before_after_summary(self):
        """ملخص نصي قبل/بعد مفيد داخل لوحة الإدارة."""
        lines = []
        for field_name in self.changed_fields or []:
            label = ACCESS_PROFILE_AUDIT_LABELS.get(field_name, field_name)
            before_value = (self.before_data or {}).get(field_name, "—")
            after_value = (self.after_data or {}).get(field_name, "—")
            lines.append(f"{label}: {before_value} ← {after_value}")
        return "\n".join(lines) if lines else self.notes or "—"


class UserAccountAuditLog(models.Model):
    ACTION_CHOICES = [
        ("login_failed", "محاولة دخول فاشلة"),
        ("login_denied_window", "منع دخول بسبب نافذة الصلاحية"),
        ("access_enabled", "تفعيل الحساب"),
        ("access_disabled", "تعطيل الحساب"),
        ("access_window_changed", "تغيير نافذة الصلاحية"),
        ("role_changed", "تغيير الدور"),
        ("sensitive_update", "تحديث إعداد حساس"),
        ("password_force_enabled", "تفعيل إجبار تغيير كلمة المرور"),
        ("password_force_disabled", "إلغاء إجبار تغيير كلمة المرور"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="performed_sensitive_account_audits",
        verbose_name="تم بواسطة",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sensitive_account_audits",
        verbose_name="المستخدم المستهدف",
    )
    action = models.CharField("نوع العملية", max_length=40, choices=ACTION_CHOICES, default="sensitive_update")
    changed_fields = models.JSONField("الحقول المتغيرة", default=list, blank=True)
    before_data = models.JSONField("القيم قبل التغيير", default=dict, blank=True)
    after_data = models.JSONField("القيم بعد التغيير", default=dict, blank=True)
    notes = models.TextField("ملاحظات", blank=True, default="")
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)
    created_at = models.DateTimeField("تاريخ العملية", auto_now_add=True)

    class Meta:
        verbose_name = "سجل تدقيق الحسابات الحساسة"
        verbose_name_plural = "سجل تدقيق الحسابات الحساسة"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        target = self.target_user.username if self.target_user else "بدون مستخدم"
        actor = self.actor.username if self.actor else "غير معروف"
        return f"{target} - {self.get_action_display()} - بواسطة {actor}"




class ComprehensiveAuditLog(models.Model):
    ACTION_CHOICES = [
        ("screen_view", "فتح شاشة"),
        ("request", "طلب"),
        ("mutation", "عملية تغيير"),
        ("auth", "مصادقة"),
        ("error", "خطأ"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="comprehensive_audit_logs",
        verbose_name="المستخدم",
    )
    username_snapshot = models.CharField("اسم المستخدم وقت العملية", max_length=150, blank=True, default="")
    action = models.CharField("نوع السجل", max_length=20, choices=ACTION_CHOICES, default="request")
    method = models.CharField("الطريقة", max_length=10, blank=True, default="GET")
    status_code = models.PositiveSmallIntegerField("حالة الاستجابة", null=True, blank=True)
    success = models.BooleanField("نجحت العملية", default=True)
    screen_name = models.CharField("اسم الشاشة", max_length=255, blank=True, default="")
    view_name = models.CharField("اسم العرض", max_length=255, blank=True, default="")
    model_label = models.CharField("نوع الكيان", max_length=255, blank=True, default="")
    object_pk = models.CharField("معرف السجل", max_length=64, blank=True, default="")
    object_repr = models.CharField("وصف السجل", max_length=255, blank=True, default="")
    path = models.CharField("المسار", max_length=500, blank=True, default="")
    query_string = models.TextField("نص الاستعلام", blank=True, default="")
    details = models.TextField("تفاصيل", blank=True, default="")
    before_data = models.JSONField("القيم قبل التغيير", default=dict, blank=True)
    after_data = models.JSONField("القيم بعد التغيير", default=dict, blank=True)
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.TextField("المتصفح/العميل", blank=True, default="")
    session_key = models.CharField("الجلسة", max_length=64, blank=True, default="")
    created_at = models.DateTimeField("تاريخ العملية", auto_now_add=True)

    class Meta:
        verbose_name = "السجل الشامل للعمليات"
        verbose_name_plural = "السجل الشامل للعمليات"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["action", "success"]),
            models.Index(fields=["view_name"]),
            models.Index(fields=["model_label", "object_pk"]),
        ]

    def __str__(self):
        who = self.username_snapshot or (self.user.username if self.user else "غير معروف")
        target = self.object_repr or self.screen_name or self.view_name or self.path
        return f"{who} - {self.get_action_display()} - {target}"

class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ("login", "دخول"),
        ("logout", "خروج"),
        ("login_failed", "محاولة دخول فاشلة"),
        ("view", "عرض"),
        ("add", "إضافة"),
        ("change", "تعديل"),
        ("delete", "حذف"),
        ("export", "تصدير"),
        ("access_denied", "منع وصول"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="المستخدم")
    action = models.CharField("الإجراء", max_length=20, choices=ACTION_CHOICES)
    program = models.CharField("البرنامج", max_length=20, null=True, blank=True)
    object_repr = models.CharField("السجل", max_length=255, blank=True, default="")
    details = models.TextField("تفاصيل", blank=True, default="")
    path = models.CharField("المسار", max_length=255, blank=True, default="")
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)
    created_at = models.DateTimeField("التاريخ", auto_now_add=True)

    class Meta:
        verbose_name = "سجل النشاط"
        verbose_name_plural = "سجل النشاط"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        username = self.user.username if self.user else "غير معروف"
        return f"{username} - {self.get_action_display()} - {self.created_at:%Y-%m-%d %H:%M}"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_user_access_profile(sender, instance, created, **kwargs):
    # عند إنشاء مستخدم جديد ننشئ له ملف صلاحيات افتراضي مرة واحدة فقط.
    if created:
        profile, _ = UserAccessProfile.objects.get_or_create(
            user=instance,
            defaults={
                "access_enabled": True,
                "access_type": "permanent",
                "allowed_weekdays": "",
                "grace_period_days": 0,
                "suspended_reason": "",
            },
        )
    else:
        # عند تعديل المستخدم لاحقًا لا ننشئ سجلًا جديدًا، بل نعيد استخدام الموجود.
        profile, _ = UserAccessProfile.objects.get_or_create(user=instance)

    # إذا كان المستخدم superuser نعطيه الصلاحيات العليا تلقائيًا.
    if instance.is_superuser and not profile.can_manage_all_programs:
        profile.can_manage_all_programs = True
        profile.can_access_admin_panel = True
        profile.can_view_reports = True
        profile.can_export_data = True
        for field in [
            "initial_view", "initial_add", "initial_change", "initial_delete",
            "apprentice_view", "apprentice_add", "apprentice_change", "apprentice_delete",
            "evening_view", "evening_add", "evening_change", "evening_delete",
        ]:
            setattr(profile, field, True)
        profile.save()

SENSITIVE_ACCOUNT_FIELDS = [
    ("role_code", "الدور الجاهز"),
    ("access_enabled", "تفعيل الصلاحيات"),
    ("access_start_date", "تاريخ بداية الصلاحية"),
    ("access_end_date", "تاريخ نهاية الصلاحية"),
    ("access_start_time", "وقت بداية السماح اليومي"),
    ("access_end_time", "وقت نهاية السماح اليومي"),
    ("allowed_weekdays", "أيام الأسبوع المسموحة"),
    ("grace_period_days", "فترة السماح"),
    ("suspended_reason", "سبب التعليق المؤقت"),
    ("can_access_admin_panel", "دخول لوحة الإدارة"),
    ("can_manage_all_programs", "إدارة كل الأنماط"),
    ("can_view_reports", "عرض التقارير"),
    ("can_export_data", "تصدير البيانات"),
    ("force_password_change", "إجبار تغيير كلمة المرور"),
]
SENSITIVE_ACCOUNT_LABELS = {field: label for field, label in SENSITIVE_ACCOUNT_FIELDS}

def serialize_sensitive_account_state(profile):
    """تحويل الحالة الحساسة للحساب إلى قاموس صالح للتدقيق."""
    if not profile:
        return {}
    data = {}
    for field_name, _label in SENSITIVE_ACCOUNT_FIELDS:
        value = getattr(profile, field_name, None)
        if field_name == "role_code" and hasattr(profile, "get_role_label"):
            value = profile.get_role_label()
        elif hasattr(value, "isoformat"):
            value = value.isoformat()
        data[field_name] = value
    return data

def diff_sensitive_account_state(before, after):
    before = before or {}
    after = after or {}
    changed = []
    for field_name, _label in SENSITIVE_ACCOUNT_FIELDS:
        if before.get(field_name) != after.get(field_name):
            changed.append(field_name)
    return changed

from .attendance_slots_models import AttendanceSlotSheet, AttendanceSlotCell  # نماذج نظام الغياب الجديد بالحصة
