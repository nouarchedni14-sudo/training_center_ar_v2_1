import json

import os

from django import forms

from .models import CentralOffice, Commune, Wilaya
from .organization import (
    build_database_name,
    build_data_dir,
    build_office_alias,
    build_office_code,
    build_office_display_name,
    build_office_id,
    build_office_name,
    build_server_id,
    normalize_establishment_number,
    normalize_establishment_type,
)


DEFAULT_FEATURE_FLAGS = {
    "trainees_add": True,
    "trainees_edit": True,
    "trainees_delete": False,
    "reports_export": True,
    "attendance": True,
    "media_upload": True,
    "admin_panel": False,
}


class CentralOfficeControlForm(forms.ModelForm):
    """نموذج تحكم المطور في المكتب من الخادم المركزي."""

    feature_flags_text = forms.CharField(
        label="الخصائص المفعلة JSON",
        required=False,
        widget=forms.Textarea(attrs={"rows": 9, "dir": "ltr", "style": "font-family: Consolas, monospace;"}),
        help_text='مثال: {"trainees_add": true, "trainees_delete": false}',
    )

    class Meta:
        model = CentralOffice
        fields = [
            "office_code",
            "office_alias",
            "office_name",
            "office_display_name",
            "wilaya",
            "commune",
            "establishment_type",
            "establishment_number",
            "server_id",
            "is_active",
            "allow_push",
            "allow_pull",
            "pull_enabled",
            "office_api_url",
            "license_status",
            "license_expires_at",
            "license_plan",
            "max_users",
            "feature_flags_text",
            "disabled_reason",
            "control_notes",
            "notes",
        ]
        widgets = {
            "license_expires_at": forms.DateInput(attrs={"type": "date"}),
            "disabled_reason": forms.Textarea(attrs={"rows": 3}),
            "control_notes": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        flags = self.instance.feature_flags or DEFAULT_FEATURE_FLAGS
        self.fields["feature_flags_text"].initial = json.dumps(flags, ensure_ascii=False, indent=2)

    def clean_office_code(self):
        return (self.cleaned_data.get("office_code") or "").strip() or None

    def clean_feature_flags_text(self):
        raw = (self.cleaned_data.get("feature_flags_text") or "").strip()
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except Exception as exc:
            raise forms.ValidationError(f"صيغة JSON غير صحيحة: {exc}") from exc
        if not isinstance(value, dict):
            raise forms.ValidationError('يجب أن تكون الخصائص كائن JSON مثل {"feature": true}.')
        return value

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.feature_flags = self.cleaned_data.get("feature_flags_text") or {}
        if commit:
            obj.save()
        return obj

from .models import CentralUpdateRelease


class CentralUpdateReleaseForm(forms.ModelForm):
    package_file = forms.FileField(
        label="رفع ملف التحديث ZIP / EXE / MSI",
        required=False,
        help_text="اختياري: إذا رفعت ملفًا هنا سيحفظه الخادم المركزي ويجعله قابلًا للتنزيل من المكاتب بدون رابط خارجي.",
    )

    allowed_office_ids_text = forms.CharField(
        label="المكاتب المسموحة",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "dir": "ltr", "style": "font-family: Consolas, monospace;"}),
        help_text="اكتب Office ID واحدًا في كل سطر. يُستعمل فقط إذا لم يكن خيار إرسال لكل المكاتب مفعّلًا.",
    )
    blocked_office_ids_text = forms.CharField(
        label="المكاتب المستثناة",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "dir": "ltr", "style": "font-family: Consolas, monospace;"}),
        help_text="اكتب Office ID واحدًا في كل سطر لمنع مكتب معين من هذا التحديث.",
    )

    class Meta:
        model = CentralUpdateRelease
        fields = [
            "version", "title", "channel", "update_type", "download_url",
            "checksum_sha256", "file_size_bytes", "release_notes",
            "is_active", "is_required", "rollout_all_offices",
            "allowed_office_ids_text", "blocked_office_ids_text", "min_current_version",
        ]
        widgets = {
            "release_notes": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["allowed_office_ids_text"].initial = "\n".join(self.instance.allowed_office_ids or [])
        self.fields["blocked_office_ids_text"].initial = "\n".join(self.instance.blocked_office_ids or [])

    def clean_package_file(self):
        uploaded = self.cleaned_data.get("package_file")
        if not uploaded:
            return uploaded
        name = str(getattr(uploaded, "name", "") or "").lower()
        if not name.endswith((".zip", ".exe", ".msi")):
            raise forms.ValidationError("ملف التحديث يجب أن يكون ZIP أو EXE أو MSI.")
        return uploaded

    @staticmethod
    def _lines_to_list(raw: str):
        return [x.strip() for x in (raw or "").splitlines() if x.strip()]

    def clean_allowed_office_ids_text(self):
        return self._lines_to_list(self.cleaned_data.get("allowed_office_ids_text") or "")

    def clean_blocked_office_ids_text(self):
        return self._lines_to_list(self.cleaned_data.get("blocked_office_ids_text") or "")

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.allowed_office_ids = self.cleaned_data.get("allowed_office_ids_text") or []
        obj.blocked_office_ids = self.cleaned_data.get("blocked_office_ids_text") or []
        if commit:
            obj.save()
        return obj




def _normalize_office_data_dir_for_form(value: str, suffix: str) -> str:
    raw = str(value or "").strip().strip('"').strip("'") or rf"C:\TrainingCenterData_{suffix}"
    raw = os.path.expandvars(os.path.expanduser(raw)).replace("/", "\\")
    if not os.path.isabs(raw):
        raw = os.path.join("C:\\", raw.lstrip("\\/"))
    return os.path.normpath(raw)



def _next_local_port(default_start: int = 8003) -> int:
    used = {8000, 8002, 9000}
    for office in CentralOffice.objects.all():
        try:
            flags = office.feature_flags or {}
            port = int(flags.get("local_port") or 0)
            if port:
                used.add(port)
        except Exception:
            continue
    port = int(default_start or 8003)
    while port in used:
        port += 1
    return port


def _next_establishment_number(commune, establishment_type: str, start: str = "01") -> str:
    etype = normalize_establishment_type(establishment_type)
    try:
        start_int = max(1, int(normalize_establishment_number(start) or "01"))
    except Exception:
        start_int = 1
    if not commune or not etype:
        return normalize_establishment_number(start_int)
    wilaya_code = getattr(getattr(commune, "wilaya", None), "code", "") or ""
    commune_code = getattr(commune, "code", "") or ""
    existing_codes = set(CentralOffice.objects.filter(commune=commune, establishment_type=etype).values_list("office_code", flat=True))
    existing_numbers = set(CentralOffice.objects.filter(commune=commune, establishment_type=etype).values_list("establishment_number", flat=True))
    for i in range(start_int, 1000):
        candidate = normalize_establishment_number(i)
        code = build_office_code(wilaya_code, commune_code, etype, candidate)
        if candidate not in existing_numbers and code not in existing_codes and not CentralOffice.objects.filter(office_code=code).exists():
            return candidate
    return normalize_establishment_number(start_int)


class CentralOfficeCreateForm(forms.ModelForm):
    """نموذج إضافة مؤسسة/مكتب رسمي من لوحة المطور المركزية.

    عند اختيار الولاية والبلدية ونوع المؤسسة والرقم، يولّد النموذج تلقائيًا:
    OFFICE_CODE / OFFICE_ID / SERVER_ID / مجلد البيانات / قاعدة البيانات.
    """

    wilaya = forms.ModelChoiceField(
        label="الولاية",
        queryset=Wilaya.objects.none(),
        required=False,
        help_text="اختر الولاية بعد استيراد Algeria Cities. يمكن تركها فارغة لإنشاء مكتب قديم يدويًا.",
    )
    commune = forms.ModelChoiceField(
        label="البلدية",
        queryset=Commune.objects.none(),
        required=False,
        help_text="اختر البلدية. الكود الرسمي للمؤسسة سيعتمد على كود البلدية مثل 03801.",
    )
    establishment_type = forms.ChoiceField(
        label="نوع المؤسسة",
        choices=[("", "—")]+CentralOffice.ESTABLISHMENT_CHOICES,
        required=False,
        help_text="مثال: INSFP أو CFPA أو ANNEXE.",
    )
    establishment_number = forms.CharField(
        label="رقم المؤسسة داخل نفس البلدية",
        required=False,
        initial="01",
        max_length=4,
        help_text="إذا كانت في نفس البلدية مؤسستان من نفس النوع: 01، 02، 03...",
    )

    generate_token = forms.BooleanField(
        label="إنشاء رمز مزامنة تلقائيًا",
        required=False,
        initial=True,
        help_text="اتركه مفعّلًا حتى ينشئ الخادم المركزي رمزًا سريًا للمكتب.",
    )
    auto_prepare_local = forms.BooleanField(
        label="تجهيز المكتب كاملًا على هذا الجهاز",
        required=False,
        initial=False,
        help_text="ينشئ قاعدة البيانات ومجلد المكتب وملف .env وملفات التشغيل، ثم يشغّل migrations و init_office_identity.",
    )
    local_port = forms.IntegerField(
        label="منفذ المكتب المحلي",
        required=False,
        min_value=1024,
        max_value=65535,
        help_text="مثال: 8003 للمكتب الجديد. 8000 لوهران و8002 لمستغانم.",
    )
    local_database = forms.CharField(
        label="اسم قاعدة البيانات المحلية",
        required=False,
        max_length=80,
        help_text="مثال: training_center_tissemsilt",
    )
    local_data_dir = forms.CharField(
        label="مجلد بيانات المكتب",
        required=False,
        max_length=255,
        help_text=r"مثال رسمي: C:\TrainingCenterData_DZ38_03801_INSFP01",
    )
    office_id = forms.CharField(label="OFFICE_ID", required=False, max_length=80, help_text="اتركه فارغًا ليولده النظام رسميًا من OFFICE_CODE.")
    office_name = forms.CharField(label="OFFICE_NAME", required=False, max_length=150, help_text="اسم تقني لاتيني. اتركه فارغًا ليولده النظام.")
    server_id = forms.CharField(label="SERVER_ID", required=False, max_length=80, help_text="اتركه فارغًا ليولده النظام.")
    office_alias = forms.CharField(label="OFFICE_ALIAS", required=False, max_length=60, help_text="اختصار بشري مثل DZ38-TIS-INSFP01. اتركه فارغًا ليولده النظام.")
    office_display_name = forms.CharField(label="الاسم الرسمي الظاهر", required=False, max_length=255, help_text="الاسم العربي الكامل للمؤسسة كما يظهر في الوثائق.")

    class Meta:
        model = CentralOffice
        fields = [
            "wilaya",
            "commune",
            "establishment_type",
            "establishment_number",
            "office_code",
            "office_alias",
            "office_id",
            "office_name",
            "office_display_name",
            "server_id",
            "is_active",
            "allow_push",
            "allow_pull",
            "pull_enabled",
            "office_api_url",
            "license_status",
            "license_expires_at",
            "license_plan",
            "max_users",
            "notes",
        ]
        widgets = {
            "license_expires_at": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "office_code": "مثال رسمي: DZ38-03801-INSFP01. لا تغيره بعد بدء المزامنة.",
            "office_id": "مثال: office_dz38_03801_insfp01. لا تغيره بعد بدء العمل.",
            "server_id": "مثال: server_dz38_03801_insfp01_main.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["wilaya"].queryset = Wilaya.objects.filter(is_active=True).order_by("code")

        wilaya_id = None
        if self.data:
            wilaya_id = self.data.get("wilaya")
        if not wilaya_id and self.initial:
            wilaya_id = self.initial.get("wilaya")
        if wilaya_id:
            self.fields["commune"].queryset = Commune.objects.filter(is_active=True, wilaya_id=wilaya_id).select_related("wilaya").order_by("code")
        else:
            self.fields["commune"].queryset = Commune.objects.none()

        # يسمح هذا بإضافة مكتب قديم يدويًا، لكن عند ملء بيانات المؤسسة الرسمية ستُولد القيم تلقائيًا.
        self.fields["office_code"].required = False
        self.fields["office_id"].required = False
        self.fields["office_name"].required = False
        self.fields["server_id"].required = False

        readonly_generated = [
            "establishment_number", "office_code", "office_alias", "office_id", "office_name",
            "server_id", "local_port", "local_database", "local_data_dir",
        ]
        for name in readonly_generated:
            if name in self.fields:
                self.fields[name].widget.attrs.update({"readonly": "readonly", "dir": "ltr", "class": "generated-field"})
        if "office_display_name" in self.fields:
            self.fields["office_display_name"].widget.attrs.update({"data-autofill-display": "1"})

    @staticmethod
    def _safe_suffix(value: str) -> str:
        raw = (value or "office").strip().lower().replace("office-", "")
        return "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in raw) or "office"

    def clean(self):
        cleaned = super().clean()
        wilaya = cleaned.get("wilaya")
        commune = cleaned.get("commune")
        etype = normalize_establishment_type(cleaned.get("establishment_type")) if cleaned.get("establishment_type") else ""
        number = normalize_establishment_number(cleaned.get("establishment_number") or "01")
        if commune and wilaya and commune.wilaya_id != wilaya.id:
            raise forms.ValidationError("البلدية المختارة لا تنتمي إلى الولاية المختارة.")
        if commune and not wilaya:
            cleaned["wilaya"] = commune.wilaya
            wilaya = commune.wilaya

        # عند توفر بيانات رسمية كافية، نبني الهوية الرسمية تلقائيًا ونضمن عدم تكرار الرقم داخل نفس البلدية والنوع.
        if commune and etype:
            user_typed_code = (cleaned.get("office_code") or "").strip()
            generated_code = build_office_code(wilaya.code, commune.code, etype, number)
            if not user_typed_code or CentralOffice.objects.filter(office_code=generated_code).exists():
                number = _next_establishment_number(commune, etype, number)
                generated_code = build_office_code(wilaya.code, commune.code, etype, number)
            office_code = generated_code
            cleaned["establishment_number"] = number
            cleaned["office_code"] = office_code
            cleaned["office_alias"] = build_office_alias(wilaya.code, commune.name_latin, etype, number)
            cleaned["office_name"] = build_office_name(commune.name_latin, etype, number)
            cleaned["office_id"] = build_office_id(office_code)
            cleaned["server_id"] = build_server_id(office_code)
            if not cleaned.get("office_display_name"):
                cleaned["office_display_name"] = build_office_display_name(commune.name_ar, etype, number)
            cleaned["local_database"] = build_database_name(office_code)
            cleaned["local_data_dir"] = build_data_dir(office_code)
        else:
            office_id = cleaned.get("office_id") or "office-new"
            suffix = self._safe_suffix(office_id)
            cleaned["office_id"] = office_id
            if not cleaned.get("server_id"):
                cleaned["server_id"] = f"server-{suffix}-01"
            if not cleaned.get("office_name"):
                cleaned["office_name"] = suffix
            if not cleaned.get("local_database"):
                cleaned["local_database"] = f"training_center_{suffix.replace('-', '_')}"
            if not cleaned.get("local_data_dir"):
                cleaned["local_data_dir"] = rf"C:\TrainingCenterData_{suffix}"

        if not cleaned.get("local_port"):
            cleaned["local_port"] = _next_local_port()
        cleaned["local_data_dir"] = _normalize_office_data_dir_for_form(cleaned.get("local_data_dir"), self._safe_suffix(cleaned.get("office_id")))
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        # حقول النموذج الرسمية ليست كلها ضمن model fields تلقائيًا في كل الحالات، لذلك نضمن تعيينها هنا.
        for field in ["office_code", "office_alias", "office_id", "office_name", "office_display_name", "server_id", "establishment_type", "establishment_number"]:
            if field in self.cleaned_data:
                setattr(obj, field, self.cleaned_data.get(field) or (None if field == "office_code" else ""))
        obj.wilaya = self.cleaned_data.get("wilaya")
        obj.commune = self.cleaned_data.get("commune")
        if commit:
            obj.save()
        return obj




class CentralOfficeUserProvisionForm(forms.Form):
    """إنشاء مستخدم محلي داخل مكتب محدد عبر حدث مزامنة من الخادم المركزي."""

    office = forms.ModelChoiceField(
        label="المكتب الهدف",
        queryset=CentralOffice.objects.none(),
        help_text="اختر المكتب الذي سيُنشأ داخله هذا المستخدم بعد تشغيل عامل المزامنة في المكتب.",
    )
    username = forms.CharField(label="اسم المستخدم", max_length=150)
    password = forms.CharField(label="كلمة المرور", widget=forms.PasswordInput(render_value=True))
    email = forms.EmailField(label="البريد الإلكتروني", required=False)
    first_name = forms.CharField(label="الاسم", required=False, max_length=150)
    last_name = forms.CharField(label="اللقب", required=False, max_length=150)
    is_active = forms.BooleanField(label="مفعّل", required=False, initial=True)
    notes = forms.CharField(label="ملاحظات", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["office"].queryset = CentralOffice.objects.filter(is_active=True).order_by("office_id")

class CentralOfficeUserEditForm(CentralOfficeUserProvisionForm):
    """نموذج تعديل مستخدم مرتبط بمكتب. كلمة المرور اختيارية عند التعديل."""
    password = forms.CharField(label="كلمة المرور الجديدة", required=False, widget=forms.PasswordInput(render_value=True), help_text="اتركها فارغة إذا كنت لا تريد تغيير كلمة المرور في المكتب المحلي.")
