from __future__ import annotations  # استيراد عناصر محددة من مكتبة/وحدة

import calendar  # استيراد مكتبة/وحدة بايثون
from datetime import date, timedelta  # استيراد عناصر محددة من مكتبة/وحدة
from typing import Optional, Tuple  # استيراد عناصر محددة من مكتبة/وحدة


_AR_ORDINAL = {  # تعيين قيمة لمتغير/إعداد
    1: "الأول",  # سطر كود لتنفيذ منطق/إعداد
    2: "الثاني",  # سطر كود لتنفيذ منطق/إعداد
    3: "الثالث",  # سطر كود لتنفيذ منطق/إعداد
    4: "الرابع",  # سطر كود لتنفيذ منطق/إعداد
    5: "الخامس",  # سطر كود لتنفيذ منطق/إعداد
}  # سطر كود لتنفيذ منطق/إعداد


def _add_months(d: date, months: int) -> date:  # تعريف دالة (Function)
    # سطر كود لتنفيذ منطق/إعداد
    """Add months to a date (keeps day when possible, otherwise clamps to month end)."""
    y = d.year + (d.month - 1 + months) // 12  # تعيين قيمة لمتغير/إعداد
    m = (d.month - 1 + months) % 12 + 1  # تعيين قيمة لمتغير/إعداد
    last_day = calendar.monthrange(y, m)[1]  # تعيين قيمة لمتغير/إعداد
    return date(y, m, min(d.day, last_day))  # إرجاع قيمة من الدالة


def compute_semester(  # تعريف دالة (Function)
    start_date: Optional[date],  # سطر كود لتنفيذ منطق/إعداد
    end_date: Optional[date],  # سطر كود لتنفيذ منطق/إعداد
    today: Optional[date] = None,  # تعيين قيمة لمتغير/إعداد
) -> Optional[str]:  # سطر كود لتنفيذ منطق/إعداد
    # سطر كود لتنفيذ منطق/إعداد
    """حساب السداسي داخل البرنامج (بدقة حدود السداسيات كما في التقسيم اليدوي).

    القواعد:  # سطر كود لتنفيذ منطق/إعداد
    - توجد 5 سداسيات فقط (الأول..الخامس).  # سطر كود لتنفيذ منطق/إعداد
    - كل سداسي = 6 أشهر ابتداءً من تاريخ بداية التكوين.  # تعيين قيمة لمتغير/إعداد
    - حدود السداسي i:  # سطر كود لتنفيذ منطق/إعداد
        start_i = start_date + 6*(i-1) أشهر  # تعيين قيمة لمتغير/إعداد
        end_i   = (start_date + 6*i أشهر) - يوم واحد  # تعيين قيمة لمتغير/إعداد
      مع مراعاة عدم تجاوز تاريخ نهاية التكوين الفعلي إن وُجد.  # سطر كود لتنفيذ منطق/إعداد
    - يُحدد السداسي حسب تاريخ اليوم، لكن إذا تجاوز اليوم تاريخ نهاية التكوين  # سطر كود لتنفيذ منطق/إعداد
      نعتمد تاريخ نهاية التكوين (أي لا نتجاوز آخر سداسي فعلي داخل المدة).  # سطر كود لتنفيذ منطق/إعداد

    المخرجات:  # سطر كود لتنفيذ منطق/إعداد
    - نص عربي: "الأول" "الثاني" "الثالث" "الرابع" "الخامس"  # سطر كود لتنفيذ منطق/إعداد
    # سطر كود لتنفيذ منطق/إعداد
    """
    if not start_date:  # شرط (If)
        return None  # إرجاع قيمة من الدالة

    ref = today or date.today()  # تعيين قيمة لمتغير/إعداد
    if end_date and ref > end_date:  # شرط (If)
        ref = end_date  # تعيين قيمة لمتغير/إعداد
    if ref < start_date:  # شرط (If)
        ref = start_date  # تعيين قيمة لمتغير/إعداد

    # ابحث عن السداسي الذي يقع فيه ref ضمن فترات 6 أشهر
    last_valid_semester = 1  # تعيين قيمة لمتغير/إعداد
    for sem in range(1, 6):  # حلقة تكرار (For)
        sem_start = _add_months(start_date, 6 * (sem - 1))  # تعيين قيمة لمتغير/إعداد
        sem_next_start = _add_months(start_date, 6 * sem)  # تعيين قيمة لمتغير/إعداد
        sem_end = sem_next_start - timedelta(days=1)  # تعيين قيمة لمتغير/إعداد

        # إذا لدينا نهاية تكوين فعلية، لا تتجاوزها
        if end_date:  # شرط (If)
            if sem_start > end_date:  # شرط (If)
                break  # سطر كود لتنفيذ منطق/إعداد
            sem_end = min(sem_end, end_date)  # تعيين قيمة لمتغير/إعداد

        last_valid_semester = sem  # تعيين قيمة لمتغير/إعداد

        if sem_start <= ref <= sem_end:  # شرط (If)
            return _AR_ORDINAL.get(sem, "الخامس")  # إرجاع قيمة من الدالة

    # إذا لم نجد (مثلاً ref يساوي نهاية المدة بعد كبتها)، رجّع آخر سداسي صالح
    return _AR_ORDINAL.get(last_valid_semester, "الخامس")  # إرجاع قيمة من الدالة


def compute_semester_with_repeater(  # تعريف دالة (Function)
    start_date: Optional[date],  # سطر كود لتنفيذ منطق/إعداد
    end_date: Optional[date],  # سطر كود لتنفيذ منطق/إعداد
    is_repeater: bool = False,  # تعيين قيمة لمتغير/إعداد
    today: Optional[date] = None,  # تعيين قيمة لمتغير/إعداد
) -> Optional[str]:  # سطر كود لتنفيذ منطق/إعداد
    # سطر كود لتنفيذ منطق/إعداد
    """حساب السداسي.

    حالة المعيد تُعالج الآن عبر تمديد تاريخ نهاية التكوين 6 أشهر
    وحفظ تاريخ النهاية الأصلي في حقل "تاريخ التكوين السابق للمعيدين".
    لذلك لا نخصم أي سداسي إضافي هنا.
    """
    return compute_semester(start_date, end_date, today=today)  # إرجاع قيمة من الدالة


def compute_semester_number(  # تعريف دالة (Function)
    start_date: Optional[date],  # سطر كود لتنفيذ منطق/إعداد
    end_date: Optional[date],  # سطر كود لتنفيذ منطق/إعداد
    today: Optional[date] = None,  # تعيين قيمة لمتغير/إعداد
) -> Optional[int]:  # سطر كود لتنفيذ منطق/إعداد
    # سطر كود لتنفيذ منطق/إعداد
    """Return semester number 1..5 (or None). Useful for internal logic."""
    if not start_date:  # شرط (If)
        return None  # إرجاع قيمة من الدالة
    label = compute_semester(start_date, end_date, today=today)  # تعيين قيمة لمتغير/إعداد
    for k, v in _AR_ORDINAL.items():  # حلقة تكرار (For)
        if v == label:  # شرط (If)
            return k  # إرجاع قيمة من الدالة
    return None  # إرجاع قيمة من الدالة


def add_months(d: date, months: int) -> date:  # تعريف دالة (Function)
    # سطر كود لتنفيذ منطق/إعداد
    """Public helper: add months to a date."""
    return _add_months(d, months)  # إرجاع قيمة من الدالة


# ---------------------------------------------------------------------------
# حساب السداسي حسب دفعات نفس النمط
# ---------------------------------------------------------------------------
# الفرق الأدنى المقبول بين بدايتين رسميتين. هذا يمنع اعتبار فروق أيام قليلة
# أو تواريخ عقود فردية كأنها دفعة جديدة.
_MIN_OFFICIAL_COHORT_GAP_DAYS = 120
# إذا كان الفرق كبيراً جداً نعتبر أن الدفعة التالية غير موجودة، ونستكمل 6 أشهر.
_MAX_OFFICIAL_COHORT_GAP_DAYS = 300


def _clean_cohort_dates(cohort_starts):
    """رتّب تواريخ بدايات الدفعات واحذف الفراغات والتكرار."""
    result = []
    seen = set()
    for value in sorted([d for d in (cohort_starts or []) if d]):
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def build_semester_starts_from_cohorts(start_date: Optional[date], cohort_starts=None, max_semesters: int = 5):
    """ابنِ بدايات السداسيات بطريقة موحّدة.

    القاعدة المعتمدة:
    1) السداسي الأول يبدأ من تاريخ بداية تكوين المتكون نفسه.
    2) إذا وُجدت دفعة رسمية لاحقة من نفس النمط وفي مجال زمني معقول، فهي بداية السداسي التالي.
       مثال: 08-10-2024 ثم 23-02-2025 => السداسي الثاني يبدأ 23-02-2025.
    3) إذا لم توجد دفعة لاحقة مناسبة، نستكمل من آخر بداية سداسي + 6 أشهر.
       مثال: 15-02-2026 ولا توجد دفعة بعدها => السداسي الثاني يبدأ 15-08-2026.
    4) لا نخلط دفعات أنماط أخرى؛ يجب تمرير تواريخ دفعات نفس الجدول/النمط فقط.
    """
    if not start_date:
        return []

    official_dates = _clean_cohort_dates(cohort_starts)
    starts = [start_date]

    while len(starts) < max_semesters:
        current = starts[-1]
        chosen = None
        for candidate in official_dates:
            if candidate <= current:
                continue
            gap_days = (candidate - current).days
            if gap_days < _MIN_OFFICIAL_COHORT_GAP_DAYS:
                # تاريخ قريب جداً: غالباً ليس دفعة سداسية جديدة بل اختلاف إدخال/عقد.
                continue
            if gap_days <= _MAX_OFFICIAL_COHORT_GAP_DAYS:
                chosen = candidate
            break

        if chosen is None:
            chosen = _add_months(current, 6)

        if chosen <= current:
            chosen = _add_months(current, 6)
        starts.append(chosen)

    return starts[:max_semesters]


def compute_semester_from_starts(
    starts,
    end_date: Optional[date] = None,
    is_repeater: bool = False,
    today: Optional[date] = None,
    original_end_date: Optional[date] = None,
) -> Optional[str]:
    """حوّل قائمة بدايات السداسيات إلى تسمية السداسي الحالي.

    منطق المعيد:
    - قبل نهاية التكوين الأصلية أو في يومها: يكون المعيد ناقص سداسي واحد عن مجموعته.
      مثال: المجموعة في الخامس => المعيد في الرابع.
    - بعد نهاية التكوين الأصلية وخلال 6 أشهر الإضافية: يصعد المعيد إلى الخامس.
      مثال: نهاية أصلية 07-04-2026، ابتداءً من 08-04-2026 يصبح المعيد في الخامس.

    ملاحظة: end_date للمعيد يكون عادةً هو النهاية بعد التمديد، أما original_end_date
    فهو حقل "تاريخ التكوين السابق للمعيدين" الذي يحفظ النهاية الأصلية.
    """
    starts = [d for d in (starts or []) if d]
    if not starts:
        return None

    ref = today or date.today()
    if ref < starts[0]:
        ref = starts[0]
    if end_date and ref > end_date:
        ref = end_date

    current = 1
    for idx, start in enumerate(starts, start=1):
        if ref >= start:
            current = idx
        else:
            break

    if is_repeater:
        original_end = original_end_date
        # احتياط: إذا لم يُمرَّر تاريخ النهاية الأصلي وكان تاريخ النهاية الحالي
        # هو نهاية ممددة، نقدّر النهاية الأصلية بطرح 6 أشهر.
        if not original_end and end_date:
            original_end = _add_months(end_date, -6)

        if original_end and ref > original_end:
            # المعيد دخل فترة 6 أشهر الإضافية بعد انتهاء مجموعته الأصلية.
            current = 5
        else:
            # قبل انتهاء المجموعة الأصلية يبقى المعيد متأخراً بسداسي واحد.
            current -= 1

    current = max(1, min(current, 5))
    return _AR_ORDINAL.get(current, 'الخامس')



def _effective_semester_starts(raw_starts, start_date: Optional[date] = None):
    """Return 5 usable semester start dates.

    The stored promotion fields can be stale after old imports. Sometimes they
    contain the current promotion and then jump directly to a promotion one year
    later, so 2024-10-08 can incorrectly become: 2024-10-08, 2025-10-05,
    2026-04-05... and the trainee appears in the third semester instead of the
    fourth.

    Rules:
    - keep increasing official promotion starts when they are reasonable;
    - if there is a very large gap (about a full year), insert a 6-month
      boundary before the next official start;
    - complete the rest by 6-month steps.
    """
    cleaned = []
    for value in raw_starts or []:
        if not value:
            continue
        if cleaned and value <= cleaned[-1]:
            continue
        cleaned.append(value)

    anchor = start_date or (cleaned[0] if cleaned else None)
    if not anchor:
        return []

    starts = [anchor]
    for candidate in cleaned:
        if candidate <= starts[-1]:
            continue

        # A gap close to a year usually means the immediate next promotion was
        # not stored in the old database fields. Add a 6-month boundary first.
        while len(starts) < 5:
            expected = _add_months(starts[-1], 6)
            gap_days = (candidate - starts[-1]).days
            if gap_days <= 300 or expected >= candidate:
                break
            starts.append(expected)

        if len(starts) >= 5:
            break
        if candidate > starts[-1]:
            starts.append(candidate)

    while len(starts) < 5:
        starts.append(_add_months(starts[-1], 6))

    return starts[:5]


def normalize_repeater_training_dates(obj) -> bool:  # تعريف دالة (Function)
    """ضبط تواريخ المعيدين في التمهين.

    المطلوب:
    - نسخ تاريخ نهاية التكوين الأصلي إلى حقل تاريخ التكوين السابق للمعيدين.
    - إضافة 6 أشهر إلى تاريخ نهاية التكوين الحالي.
    - تنفيذ العملية مرة واحدة فقط، وعدم التمديد المتكرر عند كل حفظ.
    """
    if not getattr(obj, "معيد", False):
        return False
    if not hasattr(obj, "تاريخ_التكوين_السابق_للمعيدين"):
        return False

    end_date = getattr(obj, "تاريخ_نهاية_التكوين", None)
    previous_end = getattr(obj, "تاريخ_التكوين_السابق_للمعيدين", None)
    if not end_date:
        return False

    changed = False
    if not previous_end:
        setattr(obj, "تاريخ_التكوين_السابق_للمعيدين", end_date)
        setattr(obj, "تاريخ_نهاية_التكوين", _add_months(end_date, 6))
        return True

    expected_end = _add_months(previous_end, 6)
    if end_date != expected_end:
        setattr(obj, "تاريخ_نهاية_التكوين", expected_end)
        changed = True
    return changed



def normalize_registration_number(value: str) -> str:
    """تطبيع رقم التسجيل قبل التحليل.

    - يحول الأرقام العربية إلى أرقام ASCII
    - يحذف المسافات والفواصل والشرطات والرموز المشابهة
    - يبقي فقط الأحرف والأرقام
    - يحول الأحرف اللاتينية إلى uppercase
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



def infer_session_year_from_start_date(start_date: Optional[date]) -> Tuple[Optional[int], Optional[int]]:
    """استنتاج رقم الدورة والسنة من تاريخ بداية التكوين عند تعذر التحليل من رقم التسجيل."""
    if not start_date:
        return None, None
    session_no = 1 if start_date.month <= 6 else 2
    return session_no, start_date.year



def resolve_session_year(registration_number: str, start_date: Optional[date] = None) -> Tuple[Optional[int], Optional[int]]:
    """استخرج رقم الدورة والسنة مع fallback آمن إلى تاريخ البداية."""
    session_no, year_value = parse_session_year_from_registration(registration_number)
    if session_no and year_value:
        return session_no, year_value
    return infer_session_year_from_start_date(start_date)



def parse_session_year_from_registration(registration_number: str):
    """استخرج رقم الدورة والسنة من رقم التسجيل بدون تفسير الأرقام الزائدة خطأً.

    السبب العملي للتشديد:
    رقم مثل 00452253R كان يُفسَّر سابقًا على أنه الدورة 2 سنة 2053 لأن آخر
    ثلاثة أرقام هي 253. هذا خطأ؛ الرقم القياسي يجب أن ينتهي ببنية واضحة:
    - 225R        => الدورة 2، السنة 2025
    - 12025R      => الدورة 1، السنة 2025
    - 0045225R    => أربعة أرقام تسلسلية + 225R
    أما إذا كان الطول غير قياسي مثل 00452253R فنرفض تحليله، وبعدها
    resolve_session_year يستعمل تاريخ بداية التكوين كحل آمن.
    """
    import re

    raw = (registration_number or "").strip()
    if not raw:
        return None, None

    compact = normalize_registration_number(raw)
    if not compact:
        return None, None

    def _year_from_token(token: str):
        if not token:
            return None
        if len(token) == 4 and token.startswith("20"):
            value = int(token)
            return value if 2000 <= value <= 2099 else None
        if len(token) == 2:
            value = 2000 + int(token)
            return value if 2000 <= value <= 2099 else None
        return None

    def _finalize(session_token: str, year_token: str):
        if not session_token or not year_token:
            return None, None
        try:
            session_no = int(session_token)
        except Exception:
            return None, None
        if session_no not in (1, 2):
            return None, None
        year_value = _year_from_token(year_token)
        if not year_value:
            return None, None
        return session_no, year_value

    # 1) النمط المتصل مع لاحقة حرفية. لا نستعمل search حتى لا نلتقط آخر 3 أرقام
    # من رقم أطول فيه رقم زائد مثل 00452253R.
    m = re.fullmatch(r"(\d+)([A-Z]+)", compact)
    if m:
        digits = m.group(1)
        # الشكل القياسي عندكم غالباً: رقم تسلسلي + رقم الدورة + آخر رقمين من السنة + حرف
        # أمثلة: 225R ، 38224R ، 038224R ، 0038224R ، 0045225R
        if len(digits) in (3, 5, 6, 7):
            session_no, year_value = _finalize(digits[-3], digits[-2:])
            if session_no and year_value:
                return session_no, year_value

        # دعم احتياطي لصيغة مختصرة واضحة مثل 12025R أو 22025R
        if len(digits) == 5 and digits[0] in {"1", "2"} and digits[1:3] == "20":
            return _finalize(digits[0], digits[1:])

        # أي طول آخر غير قياسي، مثل 00452253R، لا نفسّره كسنة 2053؛
        # سنترك resolve_session_year يستعمل تاريخ بداية التكوين.
        return None, None

    # 2) صيغة مفصولة بمسافات/شرطات/مائلة مثل 2/25 أو 2-2025.
    # هنا الفصل واضح، لذلك نقبلها.
    normalized = raw.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")).upper()
    m = re.search(r"(?:^|[^0-9])([12])\s*[-/ ]\s*(20\d{2}|\d{2})(?:\s*[A-Z]+)?\s*$", normalized)
    if m:
        return _finalize(m.group(1), m.group(2))

    # 3) صيغة مفصولة إلى مجموعات أرقام في آخر السلسلة فقط: ... 2 25R
    groups = re.findall(r"\d+|[A-Z]+", normalized)
    digit_groups = [g for g in groups if g.isdigit()]
    if len(digit_groups) >= 2 and digit_groups[-2] in {"1", "2"}:
        year_token = digit_groups[-1]
        if len(year_token) in (2, 4):
            return _finalize(digit_groups[-2], year_token)

    return None, None




def compute_semester_for_trainee(
    promotion,
    start_date: Optional[date],
    end_date: Optional[date],
    is_repeater: bool = False,
    today: Optional[date] = None,
    cohort_starts=None,
    original_end_date: Optional[date] = None,
) -> Optional[str]:
    """احسب السداسي للمتكون.

    المنطق الجديد لا يعتمد مباشرة على حقول بداية_السداسي داخل نموذج "دفعة"
    لأنها عامة ولا تحمل النمط، وهذا كان يخلط بين التمهين والحضوري/المسائي.

    عند تمرير cohort_starts يجب أن تكون تواريخ بدايات الدفعات الخاصة بنفس
    النمط/الجدول فقط، ثم تُطبّق القاعدة:
    - نستعمل الدفعة اللاحقة إذا كانت موجودة ومناسبة زمنياً؛
    - إذا لم توجد، نكمل +6 أشهر من آخر بداية سداسي.
    """
    if not start_date:
        return None

    if cohort_starts is not None:
        starts = build_semester_starts_from_cohorts(start_date, cohort_starts)
        return compute_semester_from_starts(
            starts,
            end_date=end_date,
            is_repeater=is_repeater,
            today=today,
            original_end_date=original_end_date,
        )

    # احتياط آمن: إذا لم تُمرَّر رزنامة نفس النمط لا نستعمل رزنامة الدفعة العامة
    # حتى لا نخلط الأنماط؛ نرجع إلى حساب 6 أشهر من تاريخ بداية تكوين المتكون.
    starts = build_semester_starts_from_cohorts(start_date, [])
    return compute_semester_from_starts(
        starts,
        end_date=end_date,
        is_repeater=is_repeater,
        today=today,
        original_end_date=original_end_date,
    )

def clear_promotion_cache() -> None:
    """Compatibility hook for old migrations.

    The previous implementation used an in-memory promotion cache, but the
    current code no longer keeps that cache. We keep this no-op function so
    historical migrations that import it continue to run safely.
    """
    return None


def compute_semester_from_promotion(promotion, today: Optional[date] = None) -> Optional[str]:
    """حساب السداسي انطلاقاً من رزنامة الدفعة."""
    if not promotion:
        return None

    ref = today or date.today()
    starts = [
        getattr(promotion, 'بداية_السداسي_1', None),
        getattr(promotion, 'بداية_السداسي_2', None),
        getattr(promotion, 'بداية_السداسي_3', None),
        getattr(promotion, 'بداية_السداسي_4', None),
        getattr(promotion, 'بداية_السداسي_5', None),
    ]
    starts = _effective_semester_starts(starts)
    if not starts:
        return None
    if ref < starts[0]:
        return _AR_ORDINAL[1]
    current = 1
    for idx, start in enumerate(starts, start=1):
        if ref >= start:
            current = idx
        else:
            break
    current = min(current, 5)
    return _AR_ORDINAL.get(current, 'الخامس')
