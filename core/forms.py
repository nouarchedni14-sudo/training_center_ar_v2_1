from django import forms

from core.models import LicenseInfo


class LocalUpdateUploadForm(forms.Form):
    update_file = forms.FileField(
        label="ملف التحديث المحلي",
        help_text="ارفع ملف ZIP يحتوي على manifest.json ومجلد app/ للملفات الجديدة.",
    )

    def clean_update_file(self):
        uploaded = self.cleaned_data["update_file"]
        name = (uploaded.name or "").lower()
        if not name.endswith('.zip'):
            raise forms.ValidationError("يجب أن يكون ملف التحديث بصيغة ZIP.")
        return uploaded


class LicenseInfoForm(forms.ModelForm):
    class Meta:
        model = LicenseInfo
        fields = [
            "customer_name",
            "license_code",
            "license_status",
            "support_expires_at",
            "max_devices",
            "notes",
        ]
        widgets = {
            "support_expires_at": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }
        labels = {
            "customer_name": "اسم العميل أو المؤسسة",
            "license_code": "رمز الترخيص",
            "license_status": "حالة الترخيص",
            "support_expires_at": "تاريخ انتهاء الدعم الفني",
            "max_devices": "الحد الأقصى للأجهزة",
            "notes": "ملاحظات",
        }
