from django.conf import settings
from django.db import models


class AttendanceSlotSheet(models.Model):
    PROGRAM_CHOICES = [
        ("initial", "الحضوري الأولي"),
        ("apprentice", "التمهين"),
        ("evening", "الدروس المسائية"),
        ("crossing", "المعابر"),
    ]

    WEEKDAY_CHOICES = [
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
    الدفعة = models.ForeignKey("دفعة", verbose_name="الدفعة", on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_slot_sheets")
    الشهر = models.PositiveSmallIntegerField("الشهر")
    السنة = models.PositiveIntegerField("السنة")
    يوم_الدراسة_1 = models.PositiveSmallIntegerField("يوم الدراسة 1", choices=WEEKDAY_CHOICES, null=True, blank=True)
    يوم_الدراسة_2 = models.PositiveSmallIntegerField("يوم الدراسة 2", choices=WEEKDAY_CHOICES, null=True, blank=True)
    يوم_الدراسة_3 = models.PositiveSmallIntegerField("يوم الدراسة 3", choices=WEEKDAY_CHOICES, null=True, blank=True)
    يوم_الدراسة_4 = models.PositiveSmallIntegerField("يوم الدراسة 4", choices=WEEKDAY_CHOICES, null=True, blank=True)
    يوم_الدراسة_5 = models.PositiveSmallIntegerField("يوم الدراسة 5", choices=WEEKDAY_CHOICES, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="attendance_slot_sheets_created", verbose_name="أنشئ بواسطة")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "جدول غياب بالحصة"
        verbose_name_plural = "جداول الغياب بالحصة"
        ordering = ["-السنة", "-الشهر", "البرنامج", "التخصص"]
        indexes = [
            models.Index(fields=["البرنامج", "السنة", "الشهر"]),
            models.Index(fields=["البرنامج", "الدفعة", "التخصص", "السنة", "الشهر"]),
        ]

    def __str__(self):
        program_label = dict(self.PROGRAM_CHOICES).get(self.البرنامج, self.البرنامج)
        batch_label = str(self.الدفعة) if self.الدفعة_id else "كل الدفعات"
        specialty_label = self.التخصص or "كل التخصصات"
        return f"غياب بالحصة - {program_label} - {specialty_label} - {batch_label} - {self.الشهر:02d}/{self.السنة}"


class AttendanceSlotCell(models.Model):
    STATUS_CHOICES = [
        ("present", "حاضر"),
        ("absent", "غائب"),
    ]

    الكشف = models.ForeignKey(AttendanceSlotSheet, on_delete=models.CASCADE, related_name="entries", verbose_name="جدول الحصص")
    trainee_id = models.PositiveIntegerField("معرّف المتكوّن")
    التاريخ = models.DateField("التاريخ")
    رقم_الحصة = models.PositiveSmallIntegerField("رقم الحصة")
    الحالة = models.CharField("الحالة", max_length=20, choices=STATUS_CHOICES, default="present")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="attendance_slot_cells_recorded", verbose_name="سجل بواسطة")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "خلية غياب بالحصة"
        verbose_name_plural = "خلايا الغياب بالحصة"
        ordering = ["التاريخ", "trainee_id", "رقم_الحصة"]
        constraints = [
            models.UniqueConstraint(fields=["الكشف", "trainee_id", "التاريخ", "رقم_الحصة"], name="trainees_unique_attendance_slot_cell"),
        ]
        indexes = [
            models.Index(fields=["الكشف", "التاريخ", "رقم_الحصة"]),
            models.Index(fields=["الكشف", "trainee_id", "التاريخ", "رقم_الحصة"]),
        ]

    def __str__(self):
        return f"{self.الكشف} / {self.trainee_id} / {self.التاريخ} / الحصة {self.رقم_الحصة}"
