from django import forms
from django.core.exceptions import ValidationError
from .models import حضوري_أولي, تمهين, مسائي_ومعابر, دفعة, AttendanceAction, DismissalDecision, SanctionRecord, UserAccessProfile
from trainees.services.role_service import (
    PERMISSION_FIELDS,
    role_defaults_snapshot,
)


DATE_INPUT_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
]

ISO_DATE_WIDGET = forms.DateInput(
    format="%Y-%m-%d",
    attrs={
        "type": "text",
        "placeholder": "2025-10-05",
        "dir": "ltr",
        "inputmode": "numeric",
        "autocomplete": "off",
    },
)


class BaseArabicDatesModelForm(forms.ModelForm):
    class Meta:
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.DateField):
                field.localize = False
                field.widget.is_localized = False
                field.widget = forms.DateInput(
                    format="%Y-%m-%d",
                    attrs={
                        "type": "text",
                        "placeholder": "2025-10-05",
                        "dir": "ltr",
                        "inputmode": "numeric",
                        "autocomplete": "off",
                    },
                )
                field.input_formats = DATE_INPUT_FORMATS
                field.error_messages.update({
                    "invalid": "أدخل تاريخًا صحيحًا بصيغة مثل 2025-10-05 أو 05-10-2025.",
                    "required": "هذا الحقل مطلوب.",
                })


class BaseTraineeForm(BaseArabicDatesModelForm):
    class Meta(BaseArabicDatesModelForm.Meta):
        fields = "__all__"


class InitialTraineeForm(BaseTraineeForm):
    class Meta(BaseTraineeForm.Meta):
        model = حضوري_أولي


class ApprenticeTraineeForm(BaseTraineeForm):
    class Meta(BaseTraineeForm.Meta):
        model = تمهين


class EveningTraineeForm(BaseTraineeForm):
    class Meta(BaseTraineeForm.Meta):
        model = مسائي_ومعابر


class PromotionAdminForm(BaseArabicDatesModelForm):
    """نموذج الدفعة داخل لوحة الإدارة.

    عند تعديل دفعة قديمة خاطئة مثل سنة 2053 إلى سنة موجودة فعلاً مثل 2025،
    لا نريد ظهور خطأ غامض بسبب القيد الفريد. نسمح للنموذج بالمرور،
    ثم يقوم PromotionAdmin بدمج الدفعة الخاطئة داخل الدفعة الصحيحة.
    """

    class Meta(BaseArabicDatesModelForm.Meta):
        model = دفعة
        fields = "__all__"

    def _duplicate_target(self):
        session_no = self.cleaned_data.get("رقم_الدورة") if hasattr(self, "cleaned_data") else None
        year_value = self.cleaned_data.get("السنة") if hasattr(self, "cleaned_data") else None
        if not session_no or not year_value:
            return None
        qs = دفعة.objects.filter(رقم_الدورة=session_no, السنة=year_value)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        return qs.first()

    def validate_unique(self):
        target = self._duplicate_target()
        if target and self.instance and self.instance.pk:
            # حالة تعديل دفعة موجودة إلى سنة/دورة موجودة: سنقوم بالدمج في admin.py.
            self.merge_target = target
            return
        if target:
            self.add_error(
                "السنة",
                f"يوجد سابقًا دفعة بنفس رقم الدورة والسنة: {target}. السطر: رقم الدورة + السنة. افتح الدفعة الموجودة أو عدّل بياناتها بدل إنشاء نسخة ثانية.",
            )
            return
        return super().validate_unique()


FORM_BY_PROGRAM = {
    "initial": InitialTraineeForm,
    "apprentice": ApprenticeTraineeForm,
    "evening": EveningTraineeForm,
    "crossing": EveningTraineeForm,
}
MODEL_BY_PROGRAM = {
    "initial": حضوري_أولي,
    "apprentice": تمهين,
    "evening": مسائي_ومعابر,
    "crossing": مسائي_ومعابر,
}


class AttendanceActionForm(BaseArabicDatesModelForm):
    class Meta(BaseArabicDatesModelForm.Meta):
        model = AttendanceAction
        fields = ["document_number", "absence_start_date", "send_date", "status", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
        }


class DismissalDecisionForm(BaseArabicDatesModelForm):
    class Meta(BaseArabicDatesModelForm.Meta):
        model = DismissalDecision
        fields = [
            "decision_number",
            "disciplinary_record_number",
            "disciplinary_record_date",
            "dismissal_start_date",
            "decision_date",
            "group_code",
            "status",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }



class SanctionRecordForm(BaseArabicDatesModelForm):
    class Meta(BaseArabicDatesModelForm.Meta):
        model = SanctionRecord
        fields = [
            "document_number",
            "sanction_text",
            "disciplinary_record_number",
            "disciplinary_record_date",
            "decision_date",
            "group_code",
            "semester",
            "status",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class UserAccessProfileAdminForm(BaseArabicDatesModelForm):
    # هذا الحقل ليس محفوظًا في قاعدة البيانات، بل نستخدمه لعرض ملخص مباشر داخل لوحة الإدارة.
    permissions_preview = forms.CharField(
        label="ملخص الصلاحيات",
        required=False,
        disabled=True,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    class Meta(BaseArabicDatesModelForm.Meta):
        model = UserAccessProfile
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        help_texts = {
            "access_enabled": "عند إلغاء هذا الخيار يتوقف المستخدم عن الاستفادة من أي صلاحية حتى لو كانت بقية الخيارات مفعلة.",
            "access_type": "اختر نوع الصلاحية مثل دائم أو مؤقت أو زائر.",
            "access_start_time": "يمكن تركه فارغًا إذا لم يوجد وقت بداية يومي.",
            "access_end_time": "يمكن تركه فارغًا إذا لم يوجد وقت نهاية يومي.",
            "allowed_weekdays": "أدخل أرقام الأيام المسموحة مفصولة بفواصل. الأحد=6، الإثنين=0، الثلاثاء=1، الأربعاء=2، الخميس=3، الجمعة=4، السبت=5.",
            "grace_period_days": "عدد الأيام الإضافية المسموحة بعد تاريخ النهاية.",
            "suspended_reason": "عند كتابة سبب هنا يعتبر الحساب معلقًا مؤقتًا حتى إزالة السبب.",
            "access_start_date": "يمكن تركه فارغًا إذا كنت تريد بدء الصلاحيات فورًا.",
            "access_end_date": "يمكن تركه فارغًا إذا كانت الصلاحيات مفتوحة المدة.",
            "can_access_admin_panel": "يسمح لهذا المستخدم بدخول لوحة الإدارة المخصصة للمشرفين.",
            "can_manage_all_programs": "يعطي المستخدم قدرة إدارة جميع الأنماط دون الحاجة لتفعيل كل نمط منفصلًا.",
            "force_password_change": "يجبر المستخدم على تغيير كلمة المرور مباشرة بعد تسجيل دخوله القادم.",
        }

        for field_name, help_text in help_texts.items():
            if field_name in self.fields:
                self.fields[field_name].help_text = help_text

        instance = getattr(self, "instance", None)
        if "permissions_preview" in self.fields:
            if instance and getattr(instance, "pk", None):
                self.fields["permissions_preview"].initial = instance.admin_permissions_summary()
            else:
                self.fields["permissions_preview"].initial = "سيظهر هنا ملخص الصلاحيات بعد حفظ المستخدم لأول مرة."

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get("access_start_date")
        end_date = cleaned.get("access_end_date")
        start_time = cleaned.get("access_start_time")
        end_time = cleaned.get("access_end_time")
        allowed_weekdays = (cleaned.get("allowed_weekdays") or "").strip()
        grace_period_days = cleaned.get("grace_period_days")

        # نمنع حفظ نافذة صلاحيات غير منطقية يكون فيها تاريخ النهاية قبل البداية.
        if start_date and end_date and end_date < start_date:
            raise ValidationError("تاريخ نهاية الصلاحية يجب أن يكون بعد أو مساويًا لتاريخ البداية.")

        if start_time and end_time and start_time == end_time:
            raise ValidationError("وقت النهاية لا ينبغي أن يساوي وقت البداية حرفيًا. اترك أحد الحقلين فارغًا إذا لم تكن تريد تقييدًا كاملًا.")

        if grace_period_days is not None and grace_period_days < 0:
            raise ValidationError("فترة السماح يجب أن تكون صفرًا أو أكثر.")

        if allowed_weekdays:
            normalized = allowed_weekdays.replace("،", ",").replace(" ", "")
            for part in normalized.split(","):
                if not part:
                    continue
                if not part.isdigit() or int(part) < 0 or int(part) > 6:
                    raise ValidationError("أيام الأسبوع المسموحة يجب أن تكون أرقامًا من 0 إلى 6 فقط ومفصولة بفواصل.")

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)

        defaults = role_defaults_snapshot(instance.role_code)
        instance.is_customized = any(
            getattr(instance, field_name, False) != defaults.get(field_name, False)
            for field_name in PERMISSION_FIELDS
        )

        if commit:
            instance.save()
            self.save_m2m()

        return instance

