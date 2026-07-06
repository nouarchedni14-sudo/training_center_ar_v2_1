import uuid

from django.db import models
from django.utils import timezone


class OfficeIdentity(models.Model):
    """هوية خادم المكتب المحلي ضمن تصميم المزامنة المركزية."""

    MODE_LOCAL_OFFICE = "local_office"
    MODE_CENTRAL = "central_server"

    MODE_CHOICES = [
        (MODE_LOCAL_OFFICE, "خادم مكتب محلي"),
        (MODE_CENTRAL, "خادم مركزي"),
    ]

    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    mode = models.CharField("نمط التشغيل", max_length=30, choices=MODE_CHOICES, default=MODE_LOCAL_OFFICE)
    office_id = models.CharField("معرف المكتب", max_length=80, unique=True)
    office_name = models.CharField("اسم المكتب", max_length=150, blank=True)
    server_id = models.CharField("معرف خادم المكتب", max_length=80, unique=True)
    central_url = models.URLField("رابط الخادم المركزي", blank=True)
    sync_token = models.CharField("رمز المزامنة", max_length=255, blank=True)
    sync_enabled = models.BooleanField("تفعيل الاتصال بالخادم المركزي", default=False)
    last_checked_at = models.DateTimeField("آخر فحص", null=True, blank=True)
    notes = models.TextField("ملاحظات", blank=True)
    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    updated_at = models.DateTimeField("آخر تعديل", auto_now=True)

    class Meta:
        verbose_name = "هوية المزامنة للمكتب"
        verbose_name_plural = "هوية المزامنة للمكتب"

    def __str__(self) -> str:
        return f"{self.office_name or self.office_id} / {self.server_id}"

    @staticmethod
    def new_office_id(prefix: str = "office") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def new_server_id(prefix: str = "server") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    def mark_checked(self):
        self.last_checked_at = timezone.now()
        self.save(update_fields=["last_checked_at", "updated_at"])


class SyncState(models.Model):
    """آخر حالة مزامنة مع الخادم المركزي."""

    DIRECTION_PUSH = "push"
    DIRECTION_PULL = "pull"
    DIRECTION_CHOICES = [
        (DIRECTION_PUSH, "إرسال"),
        (DIRECTION_PULL, "استقبال"),
    ]

    direction = models.CharField("الاتجاه", max_length=20, choices=DIRECTION_CHOICES)
    scope = models.CharField("النطاق", max_length=120, default="global")
    last_cursor = models.CharField("آخر مؤشر", max_length=200, blank=True)
    last_event_at = models.DateTimeField("وقت آخر حدث", null=True, blank=True)
    last_success_at = models.DateTimeField("آخر نجاح", null=True, blank=True)
    last_error_at = models.DateTimeField("آخر خطأ", null=True, blank=True)
    last_error = models.TextField("نص آخر خطأ", blank=True)
    extra = models.JSONField("معلومات إضافية", default=dict, blank=True)
    updated_at = models.DateTimeField("آخر تحديث", auto_now=True)

    class Meta:
        verbose_name = "حالة المزامنة"
        verbose_name_plural = "حالات المزامنة"
        unique_together = [("direction", "scope")]
        ordering = ["direction", "scope"]

    def __str__(self):
        return f"{self.direction}:{self.scope}"


class SyncOutbox(models.Model):
    """التغييرات المحلية التي ستُرسل لاحقًا إلى الخادم المركزي."""

    STATUS_PENDING = "pending"
    STATUS_SENDING = "sending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_PENDING, "ينتظر الإرسال"),
        (STATUS_SENDING, "قيد الإرسال"),
        (STATUS_SENT, "تم الإرسال"),
        (STATUS_FAILED, "فشل"),
        (STATUS_SKIPPED, "متجاوز"),
    ]

    OP_CREATE = "create"
    OP_UPDATE = "update"
    OP_DELETE = "delete"
    OP_SNAPSHOT = "snapshot"
    OP_CHOICES = [
        (OP_CREATE, "إنشاء"),
        (OP_UPDATE, "تعديل"),
        (OP_DELETE, "حذف"),
        (OP_SNAPSHOT, "لقطة"),
    ]

    event_id = models.UUIDField("معرف الحدث", default=uuid.uuid4, unique=True, editable=False)
    office_id = models.CharField("معرف المكتب", max_length=80)
    server_id = models.CharField("معرف الخادم", max_length=80)
    app_label = models.CharField("التطبيق", max_length=100)
    model_name = models.CharField("النموذج", max_length=100)
    object_pk = models.CharField("معرف السجل", max_length=200)
    operation = models.CharField("نوع العملية", max_length=20, choices=OP_CHOICES)
    payload = models.JSONField("البيانات", default=dict, blank=True)
    changed_fields = models.JSONField("الحقول المعدلة", default=list, blank=True)
    payload_hash = models.CharField("بصمة البيانات", max_length=64, blank=True)
    idempotency_key = models.CharField("مفتاح منع التكرار", max_length=220, unique=True)
    status = models.CharField("الحالة", max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    attempts = models.PositiveIntegerField("عدد المحاولات", default=0)
    last_attempt_at = models.DateTimeField("آخر محاولة", null=True, blank=True)
    sent_at = models.DateTimeField("وقت الإرسال", null=True, blank=True)
    error_message = models.TextField("رسالة الخطأ", blank=True)
    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    updated_at = models.DateTimeField("آخر تحديث", auto_now=True)

    class Meta:
        verbose_name = "صندوق الإرسال"
        verbose_name_plural = "صندوق الإرسال"
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["app_label", "model_name", "object_pk"]),
            models.Index(fields=["office_id", "server_id"]),
        ]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.operation} {self.app_label}.{self.model_name}:{self.object_pk} ({self.status})"


class SyncInbox(models.Model):
    """التغييرات القادمة من الخادم المركزي قبل تطبيقها محليًا في المراحل القادمة."""

    STATUS_RECEIVED = "received"
    STATUS_APPLIED = "applied"
    STATUS_CONFLICT = "conflict"
    STATUS_FAILED = "failed"
    STATUS_IGNORED = "ignored"
    STATUS_CHOICES = [
        (STATUS_RECEIVED, "تم الاستقبال"),
        (STATUS_APPLIED, "تم التطبيق"),
        (STATUS_CONFLICT, "تعارض"),
        (STATUS_FAILED, "فشل"),
        (STATUS_IGNORED, "متجاهل"),
    ]

    event_id = models.UUIDField("معرف الحدث", unique=True)
    source_office_id = models.CharField("المكتب المصدر", max_length=80)
    source_server_id = models.CharField("الخادم المصدر", max_length=80, blank=True)
    app_label = models.CharField("التطبيق", max_length=100)
    model_name = models.CharField("النموذج", max_length=100)
    object_pk = models.CharField("معرف السجل", max_length=200)
    operation = models.CharField("نوع العملية", max_length=20)
    payload = models.JSONField("البيانات", default=dict, blank=True)
    central_cursor = models.CharField("مؤشر الخادم المركزي", max_length=200, blank=True)
    status = models.CharField("الحالة", max_length=20, choices=STATUS_CHOICES, default=STATUS_RECEIVED)
    received_at = models.DateTimeField("وقت الاستقبال", default=timezone.now)
    applied_at = models.DateTimeField("وقت التطبيق", null=True, blank=True)
    error_message = models.TextField("رسالة الخطأ", blank=True)

    class Meta:
        verbose_name = "صندوق الاستقبال"
        verbose_name_plural = "صندوق الاستقبال"
        indexes = [
            models.Index(fields=["status", "received_at"]),
            models.Index(fields=["app_label", "model_name", "object_pk"]),
            models.Index(fields=["source_office_id", "source_server_id"]),
        ]
        ordering = ["received_at"]

    def __str__(self):
        return f"{self.operation} {self.app_label}.{self.model_name}:{self.object_pk} ({self.status})"


class SyncConflict(models.Model):
    """سجل التعارضات المحتملة بين نسخ المكاتب."""

    STATUS_OPEN = "open"
    STATUS_RESOLVED = "resolved"
    STATUS_IGNORED = "ignored"
    STATUS_CHOICES = [
        (STATUS_OPEN, "مفتوح"),
        (STATUS_RESOLVED, "محلول"),
        (STATUS_IGNORED, "متجاهل"),
    ]

    conflict_id = models.UUIDField("معرف التعارض", default=uuid.uuid4, unique=True, editable=False)
    app_label = models.CharField("التطبيق", max_length=100)
    model_name = models.CharField("النموذج", max_length=100)
    object_pk = models.CharField("معرف السجل", max_length=200)
    local_event_id = models.UUIDField("حدث محلي", null=True, blank=True)
    remote_event_id = models.UUIDField("حدث بعيد", null=True, blank=True)
    reason = models.CharField("السبب", max_length=200)
    local_payload = models.JSONField("البيانات المحلية", default=dict, blank=True)
    remote_payload = models.JSONField("البيانات البعيدة", default=dict, blank=True)
    resolution = models.TextField("طريقة الحل", blank=True)
    status = models.CharField("الحالة", max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    resolved_at = models.DateTimeField("تاريخ الحل", null=True, blank=True)

    class Meta:
        verbose_name = "تعارض مزامنة"
        verbose_name_plural = "تعارضات المزامنة"
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["app_label", "model_name", "object_pk"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.app_label}.{self.model_name}:{self.object_pk} - {self.status}"




class Wilaya(models.Model):
    """ولاية جزائرية مستوردة من ملف Algeria Cities.

    الكود يبقى نصًا من رقمين حتى لا تضيع الأصفار الأولى.
    """

    code = models.CharField("كود الولاية", max_length=2, unique=True)
    name_ar = models.CharField("الولاية بالعربية", max_length=120)
    name_latin = models.CharField("الولاية باللاتينية", max_length=120, blank=True)
    is_active = models.BooleanField("نشطة", default=True)

    class Meta:
        verbose_name = "ولاية"
        verbose_name_plural = "الولايات"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name_ar}"


class Commune(models.Model):
    """بلدية جزائرية مرتبطة بولاية.

    الكود الرسمي المعتمد في المشروع يكون دائمًا من 5 أرقام مثل 03801.
    """

    code = models.CharField("كود البلدية", max_length=5, unique=True)
    wilaya = models.ForeignKey(Wilaya, on_delete=models.PROTECT, related_name="communes", verbose_name="الولاية")
    name_ar = models.CharField("البلدية بالعربية", max_length=160)
    name_latin = models.CharField("البلدية باللاتينية", max_length=160, blank=True)
    is_active = models.BooleanField("نشطة", default=True)

    class Meta:
        verbose_name = "بلدية"
        verbose_name_plural = "البلديات"
        ordering = ["wilaya__code", "code"]
        indexes = [models.Index(fields=["wilaya", "code"]), models.Index(fields=["name_ar"])]

    def __str__(self):
        return f"{self.code} - {self.name_ar}"


class CentralOffice(models.Model):
    """مكتب مسجل في الخادم المركزي ويسمح له بالدفع والسحب عبر API والتحكم المركزي."""

    LICENSE_ACTIVE = "active"
    LICENSE_EXPIRED = "expired"
    LICENSE_SUSPENDED = "suspended"
    LICENSE_TRIAL = "trial"
    LICENSE_CHOICES = [
        (LICENSE_ACTIVE, "نشط"),
        (LICENSE_TRIAL, ""),
        (LICENSE_EXPIRED, "منتهي"),
        (LICENSE_SUSPENDED, "موقوف"),
    ]

    ESTABLISHMENT_INSFP = "INSFP"
    ESTABLISHMENT_CFPA = "CFPA"
    ESTABLISHMENT_ANNEXE = "ANNEXE"
    ESTABLISHMENT_DIRECTION = "DIRECTION"
    ESTABLISHMENT_OTHER = "OTHER"
    ESTABLISHMENT_CHOICES = [
        (ESTABLISHMENT_INSFP, "معهد وطني متخصص INSFP"),
        (ESTABLISHMENT_CFPA, "مركز التكوين المهني والتمهين CFPA"),
        (ESTABLISHMENT_ANNEXE, "ملحقة ANNEXE"),
        (ESTABLISHMENT_DIRECTION, "مديرية / إدارة DIRECTION"),
        (ESTABLISHMENT_OTHER, "أخرى"),
    ]

    office_id = models.CharField("معرف المكتب", max_length=80, unique=True)
    office_code = models.CharField("الكود الرسمي للمؤسسة", max_length=40, unique=True, null=True, blank=True, db_index=True, help_text="مثال: DZ38-03801-INSFP01")
    office_alias = models.CharField("اختصار بشري للمؤسسة", max_length=60, blank=True, help_text="مثال: DZ38-TIS-INSFP01")
    office_name = models.CharField("اسم المكتب التقني", max_length=150, blank=True)
    office_display_name = models.CharField("الاسم الرسمي الظاهر للمؤسسة", max_length=255, blank=True)
    wilaya = models.ForeignKey(Wilaya, on_delete=models.PROTECT, null=True, blank=True, related_name="offices", verbose_name="الولاية")
    commune = models.ForeignKey(Commune, on_delete=models.PROTECT, null=True, blank=True, related_name="offices", verbose_name="البلدية")
    establishment_type = models.CharField("نوع المؤسسة", max_length=30, choices=ESTABLISHMENT_CHOICES, blank=True, default="")
    establishment_number = models.CharField("رقم المؤسسة داخل البلدية", max_length=4, blank=True, default="01", help_text="يبقى نصًا مثل 01 أو 02 حتى لا يضيع الصفر.")
    server_id = models.CharField("معرف آخر خادم", max_length=80, blank=True)
    office_api_url = models.URLField("رابط خادم المكتب للسحب", blank=True, help_text="مثال: http://192.168.1.20:8000")
    pull_enabled = models.BooleanField("السماح للمطور بسحب السجلات", default=True)
    last_pull_at = models.DateTimeField("آخر سحب من المطور", null=True, blank=True)
    last_pull_cursor = models.CharField("آخر مؤشر سحب", max_length=200, blank=True, default="0")
    last_pull_error = models.TextField("آخر خطأ في السحب", blank=True)
    sync_token = models.CharField("رمز المزامنة", max_length=255)
    is_active = models.BooleanField("مفعل", default=True)
    allow_push = models.BooleanField("السماح بالإرسال", default=True)
    allow_pull = models.BooleanField("السماح بالاستقبال", default=True)
    license_status = models.CharField("حالة الترخيص", max_length=40, choices=LICENSE_CHOICES, default=LICENSE_ACTIVE)
    license_expires_at = models.DateField("انتهاء الترخيص", null=True, blank=True)
    license_plan = models.CharField("نوع الترخيص", max_length=80, blank=True, default="standard")
    max_users = models.PositiveIntegerField("عدد المستخدمين المسموح", default=5)
    feature_flags = models.JSONField("الخصائص المفعلة", default=dict, blank=True)
    disabled_reason = models.TextField("سبب التعطيل", blank=True)
    control_notes = models.TextField("ملاحظات المطور", blank=True)
    last_seen_at = models.DateTimeField("آخر اتصال", null=True, blank=True)
    notes = models.TextField("ملاحظات", blank=True)
    created_at = models.DateTimeField("تاريخ التسجيل", auto_now_add=True)
    updated_at = models.DateTimeField("آخر تحديث", auto_now=True)

    class Meta:
        verbose_name = "مكتب مركزي"
        verbose_name_plural = "المكاتب المركزية"
        ordering = ["office_code", "office_id"]

    def __str__(self):
        label = self.office_display_name or self.office_name or self.office_code or self.office_id
        return f"{label} ({'مفعل' if self.is_active else 'معطل'})"

    @property
    def official_label(self) -> str:
        return self.office_display_name or self.office_name or self.office_code or self.office_id

    @property
    def effective_office_code(self) -> str:
        return self.office_code or self.office_id

    def save(self, *args, **kwargs):
        if self.office_code == "":
            self.office_code = None
        super().save(*args, **kwargs)

    @property
    def is_license_expired(self) -> bool:
        return bool(self.license_expires_at and self.license_expires_at < timezone.localdate())

    @property
    def effective_license_status(self) -> str:
        if not self.is_active:
            return "disabled"
        if self.is_license_expired:
            return self.LICENSE_EXPIRED
        return self.license_status

    @property
    def license_valid(self) -> bool:
        return self.is_active and not self.is_license_expired and self.license_status in {self.LICENSE_ACTIVE, self.LICENSE_TRIAL}

    def mark_pulled(self, cursor: str | int | None = None, error: str = ""):
        self.last_pull_at = timezone.now()
        self.last_pull_error = error[:4000] if error else ""
        update_fields = ["last_pull_at", "last_pull_error", "updated_at"]
        if cursor is not None:
            self.last_pull_cursor = str(cursor)
            update_fields.append("last_pull_cursor")
        self.save(update_fields=update_fields)

    def mark_seen(self, server_id: str | None = None):
        self.last_seen_at = timezone.now()
        update_fields = ["last_seen_at", "updated_at"]
        if server_id and self.server_id != server_id:
            self.server_id = server_id
            update_fields.append("server_id")
        self.save(update_fields=update_fields)




class OrganizationUnit(models.Model):
    """إدارة أو مديرية فرعية أو مصلحة داخل مؤسسة واحدة.

    هذه الوحدات لا تدخل في OFFICE_CODE؛ فهي هيكل داخلي مستقل لكل مؤسسة.
    """

    TYPE_GENERAL = "general"
    TYPE_SUBDIRECTORATE = "subdirectorate"
    TYPE_SERVICE = "service"
    TYPE_POSITION = "position"
    TYPE_CHOICES = [
        (TYPE_GENERAL, "إدارة عامة"),
        (TYPE_SUBDIRECTORATE, "مديرية فرعية"),
        (TYPE_SERVICE, "مصلحة"),
        (TYPE_POSITION, "منصب / مسؤولية"),
    ]

    office = models.ForeignKey(CentralOffice, on_delete=models.CASCADE, related_name="organization_units", verbose_name="المؤسسة")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="children", verbose_name="الوحدة الأب")
    unit_code = models.CharField("كود الوحدة", max_length=80)
    name_ar = models.CharField("اسم الوحدة بالعربية", max_length=255)
    unit_type = models.CharField("نوع الوحدة", max_length=30, choices=TYPE_CHOICES, default=TYPE_SERVICE)
    order = models.PositiveIntegerField("الترتيب", default=0)
    is_active = models.BooleanField("نشطة", default=True)
    notes = models.TextField("ملاحظات", blank=True)
    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    updated_at = models.DateTimeField("آخر تعديل", auto_now=True)

    class Meta:
        verbose_name = "وحدة إدارية"
        verbose_name_plural = "الوحدات الإدارية"
        ordering = ["office__office_code", "order", "id"]
        unique_together = [("office", "unit_code")]
        indexes = [models.Index(fields=["office", "unit_code"]), models.Index(fields=["office", "parent", "order"])]

    def __str__(self):
        return f"{self.office.effective_office_code} / {self.name_ar}"


class CentralDeviceRegistration(models.Model):
    """طلب ربط جهاز مستقل بالخادم المركزي قبل منحه رمز المزامنة.

    الجهاز يُثبَّت بدون SYNC_TOKEN. عند أول تشغيل يرسل SERVER_ID وبصمة طلب.
    المطوّر يراجع الطلب من اللوحة المركزية ويختار المكتب، ثم يحصل الجهاز على إعداداته.
    """

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "بانتظار موافقة المطوّر"),
        (STATUS_APPROVED, "معتمد"),
        (STATUS_REJECTED, "مرفوض"),
    ]

    server_id = models.CharField("معرف الجهاز", max_length=100, unique=True)
    request_secret = models.CharField("سر طلب الربط", max_length=255)
    device_token = models.CharField("رمز الجهاز بعد الاعتماد", max_length=255, blank=True)
    hostname = models.CharField("اسم الجهاز", max_length=180, blank=True)
    device_label = models.CharField("تسمية الجهاز", max_length=180, blank=True)
    lan_ip = models.GenericIPAddressField("IP الجهاز", null=True, blank=True)
    app_version = models.CharField("نسخة البرنامج", max_length=50, blank=True)
    central_url = models.URLField("رابط المركز كما يراه الجهاز", blank=True)
    status = models.CharField("الحالة", max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    assigned_office = models.ForeignKey(
        CentralOffice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="device_registrations",
        verbose_name="المكتب المعتمد",
    )
    requested_at = models.DateTimeField("وقت أول طلب", default=timezone.now)
    last_seen_at = models.DateTimeField("آخر اتصال قبل الاعتماد", null=True, blank=True)
    approved_at = models.DateTimeField("وقت الاعتماد", null=True, blank=True)
    config_delivered_at = models.DateTimeField("وقت تسليم الإعدادات للجهاز", null=True, blank=True)
    notes = models.TextField("ملاحظات", blank=True)

    class Meta:
        verbose_name = "جهاز ينتظر الربط"
        verbose_name_plural = "الأجهزة بانتظار الربط"
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.hostname or self.server_id} - {self.get_status_display()}"

    def approve_for_office(self, office: CentralOffice):
        self.assigned_office = office
        self.status = self.STATUS_APPROVED
        self.approved_at = timezone.now()
        if not self.device_token:
            from .services import generate_sync_token
            self.device_token = generate_sync_token()
        self.save(update_fields=["assigned_office", "status", "approved_at", "device_token"])


class CentralSyncEvent(models.Model):
    """حدث مزامنة مخزن في الخادم المركزي بعد استقباله من أحد المكاتب."""

    central_event_id = models.UUIDField("معرف مركزي", default=uuid.uuid4, unique=True, editable=False)
    source_event_id = models.UUIDField("معرف الحدث الأصلي", unique=True)
    source_office_id = models.CharField("المكتب المصدر", max_length=80)
    source_server_id = models.CharField("الخادم المصدر", max_length=80, blank=True)
    app_label = models.CharField("التطبيق", max_length=100)
    model_name = models.CharField("النموذج", max_length=100)
    object_pk = models.CharField("معرف السجل", max_length=200)
    operation = models.CharField("نوع العملية", max_length=20)
    payload = models.JSONField("البيانات", default=dict, blank=True)
    changed_fields = models.JSONField("الحقول المعدلة", default=list, blank=True)
    payload_hash = models.CharField("بصمة البيانات", max_length=64, blank=True)
    received_at = models.DateTimeField("وقت الاستقبال المركزي", default=timezone.now)
    source_created_at = models.DateTimeField("وقت إنشاء الحدث في المكتب", null=True, blank=True)
    is_deleted = models.BooleanField("محذوف منطقيًا", default=False)
    extra = models.JSONField("معلومات إضافية", default=dict, blank=True)

    class Meta:
        verbose_name = "حدث مزامنة مركزي"
        verbose_name_plural = "أحداث المزامنة المركزية"
        indexes = [
            models.Index(fields=["id"]),
            models.Index(fields=["source_office_id", "source_server_id"]),
            models.Index(fields=["app_label", "model_name", "object_pk"]),
            models.Index(fields=["received_at"]),
        ]
        ordering = ["id"]

    def __str__(self):
        return f"#{self.id} {self.source_office_id} {self.operation} {self.app_label}.{self.model_name}:{self.object_pk}"

class CentralUpdateRelease(models.Model):
    """إصدار تحديث ينشره المطور من الخادم المركزي للمكاتب المحددة."""

    TYPE_INSTALLER = "installer"
    TYPE_PATCH = "patch"
    TYPE_CHOICES = [
        (TYPE_INSTALLER, "Installer كامل"),
        (TYPE_PATCH, "Patch ملفات معدلة"),
    ]

    CHANNEL_STABLE = "stable"
    CHANNEL_TEST = "test"
    CHANNEL_CHOICES = [
        (CHANNEL_STABLE, "مستقر"),
        (CHANNEL_TEST, ""),
    ]

    version = models.CharField("رقم النسخة", max_length=50, unique=True)
    title = models.CharField("عنوان التحديث", max_length=180, blank=True)
    channel = models.CharField("القناة", max_length=30, choices=CHANNEL_CHOICES, default=CHANNEL_STABLE)
    update_type = models.CharField("نوع التحديث", max_length=30, choices=TYPE_CHOICES, default=TYPE_PATCH)
    download_url = models.URLField("رابط التحميل الخارجي", blank=True)
    local_package_name = models.CharField("ملف التحديث المرفوع", max_length=255, blank=True)
    checksum_sha256 = models.CharField("SHA256", max_length=64, blank=True)
    file_size_bytes = models.BigIntegerField("حجم الملف بالبايت", null=True, blank=True)
    release_notes = models.TextField("ملاحظات الإصدار", blank=True)
    is_active = models.BooleanField("منشور", default=False)
    is_required = models.BooleanField("تحديث إجباري", default=False)
    rollout_all_offices = models.BooleanField("إرسال لكل المكاتب", default=True)
    allowed_office_ids = models.JSONField("المكاتب المسموحة", default=list, blank=True)
    blocked_office_ids = models.JSONField("المكاتب المحظورة", default=list, blank=True)
    min_current_version = models.CharField("أقل نسخة مسموح تحديثها", max_length=50, blank=True)
    published_at = models.DateTimeField("تاريخ النشر", null=True, blank=True)
    created_at = models.DateTimeField("تاريخ الإنشاء", auto_now_add=True)
    updated_at = models.DateTimeField("آخر تحديث", auto_now=True)

    class Meta:
        verbose_name = "إصدار تحديث مركزي"
        verbose_name_plural = "إصدارات التحديثات المركزية"
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return f"{self.version} - {self.title or self.get_update_type_display()}"

    def save(self, *args, **kwargs):
        if self.is_active and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def is_allowed_for_office(self, office_id: str) -> bool:
        office_id = str(office_id or "").strip()
        if not office_id:
            return False
        if office_id in (self.blocked_office_ids or []):
            return False
        if self.rollout_all_offices:
            return True
        return office_id in (self.allowed_office_ids or [])


class CentralUpdateCheckLog(models.Model):
    """سجل فحص التحديثات من المكاتب حتى يعرف المطور من فحص ومن لم يفحص."""

    office_ref = models.ForeignKey(
        CentralOffice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="update_checks",
        verbose_name="المكتب المركزي",
    )
    office_id = models.CharField("معرف المكتب", max_length=80)
    server_id = models.CharField("معرف الخادم", max_length=80, blank=True)
    current_version = models.CharField("النسخة الحالية", max_length=50, blank=True)
    channel = models.CharField("قناة التحديث", max_length=30, blank=True)
    offered_version = models.CharField("النسخة المعروضة", max_length=50, blank=True)
    has_update = models.BooleanField("يوجد تحديث", default=False)
    ip_address = models.GenericIPAddressField("عنوان IP", null=True, blank=True)
    user_agent = models.TextField("User Agent", blank=True)
    created_at = models.DateTimeField("وقت الفحص", auto_now_add=True)

    class Meta:
        verbose_name = "سجل فحص تحديث"
        verbose_name_plural = "سجل فحص التحديثات"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["office_id", "created_at"]),
            models.Index(fields=["has_update", "created_at"]),
        ]

    def __str__(self):
        return f"{self.office_id}: {self.current_version} -> {self.offered_version or '-'}"
