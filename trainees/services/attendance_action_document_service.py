from io import BytesIO
import re
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.http import content_disposition_header

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

try:
    import arabic_reshaper
except Exception:
    arabic_reshaper = None

try:
    from bidi.algorithm import get_display
except Exception:
    get_display = None


def register_pdf_font():
    candidates = [
        Path(settings.BASE_DIR) / "fonts" / "Amiri-Regular.ttf",
        Path(settings.BASE_DIR) / "fonts" / "NotoNaskhArabic-Regular.ttf",
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/tahoma.ttf"),
        Path("C:/Windows/Fonts/tradbdo.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ]
    for candidate in candidates:
        try:
            if not candidate.exists():
                continue
            if "ArabicUI" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("ArabicUI", str(candidate)))
            return "ArabicUI"
        except Exception:
            continue
    return "Helvetica"


def pdf_text(value):
    if value is None:
        return ""
    text = str(value)
    if not text:
        return ""
    try:
        if arabic_reshaper is not None and get_display is not None and any("؀" <= ch <= "ۿ" for ch in text):
            return get_display(arabic_reshaper.reshape(text))
    except Exception:
        pass
    return text


def action_date_display(value):
    if not value:
        return "..........................."
    try:
        return value.strftime("%Y-%m-%d")
    except Exception:
        return str(value)


def attendance_action_document_context(action, preview_query=""):
    return {
        "action_obj": action,
        "action_date_display": action_date_display,
        "document_title_display": action.document_heading,
        "preview_query": preview_query,
    }


def attendance_action_download_name(action, ext):
    kind = (action.get_action_type_display() or action.document_title or "وثيقة").strip()
    trainee_name = (action.trainee_name or "متكون").strip()
    raw = f"{trainee_name} - {kind}"
    safe = re.sub(r'[\\/:*?"<>|]+', '-', raw)
    safe = re.sub(r'\s+', ' ', safe).strip().strip('.') or 'document'
    return f"{safe}.{ext}"


def set_download_headers(response, action, ext):
    filename = attendance_action_download_name(action, ext)
    response["Content-Disposition"] = content_disposition_header(True, filename)
    return response


def build_attendance_action_word_response(action):
    context = attendance_action_document_context(action)
    html = render_to_string("trainees/attendance_action_word.html", context)
    response = HttpResponse(html, content_type="application/msword; charset=utf-8")
    return set_download_headers(response, action, "doc")


def draw_attendance_action_pdf_copy(c, action, x, y, width, height, copy_label=""):
    font_name = register_pdf_font()
    right_x = x + width - 16
    left_x = x + 16
    center_x = x + (width / 2)
    cursor_y = y + height - 22

    def draw_right(text, size=11, leading=15):
        nonlocal cursor_y
        c.setFont(font_name, size)
        c.drawRightString(right_x, cursor_y, pdf_text(text))
        cursor_y -= leading

    def draw_center(text, size=11, leading=15):
        nonlocal cursor_y
        c.setFont(font_name, size)
        c.drawCentredString(center_x, cursor_y, pdf_text(text))
        cursor_y -= leading

    c.setStrokeColor(colors.grey)
    c.setLineWidth(0.6)

    draw_center("الجمهورية الجزائرية الديمقراطية الشعبية", size=10.5, leading=13)
    draw_center("وزارة التكوين و التعليم المهنيين", size=10.5, leading=13)
    draw_right("المعهد الوطني المتخصص في التكوين المهني", size=10.5, leading=13)
    draw_right("المديرية الفرعية للإعلام والتوجيه والرقمنة والمساعدة على الإدماج المهني", size=10.5, leading=13)
    draw_right("مصلحة المراقبة العامة", size=10.5, leading=13)
    draw_right(f"الرقم: {action.document_number or '........................'} /م.ف.إ.ت.ر.م.إ.م/م.و.م.ت.م/{action.year}", size=10.5, leading=16)
    draw_center(action.document_heading, size=18, leading=24)

    draw_right(f"اللقب والإسم: {action.trainee_name or '.........................'}", size=11.5, leading=16)
    draw_right(f"التخصص: {action.trainee_specialty or '.........................'}", size=11.5, leading=16)
    draw_right(f"العنوان: {action.trainee_address or '.........................'}", size=11.5, leading=18)

    if action.action_type == "summon":
        paragraph = (
            f"لقد لفت انتباهنا غيابكم المستمر والغير المبرر منذ تاريخ {action_date_display(action.absence_start_date)} إلى يومنا هذا، وبعد استنفاد الأعذارات الإدارية المسجلة، فإننا نستدعيكم للحضور فورًا إلى إدارة المعهد وتسوية وضعيتكم البيداغوجية، وفي حالة عدم الالتحاق في مدة أقصاها (3) ثلاثة أيام عند استلامكم لهذا الاستدعاء سوف تتخذ الإجراءات الإدارية الصارمة طبقًا للقانون الخاص بالمعهد الوطني المتخصص في التكوين المهني لا سيما المادة رقم 27."
        )
    else:
        paragraph = (
            f"لقد لفت انتباهنا غيابكم المستمر والغير المبرر منذ تاريخ {action_date_display(action.absence_start_date)} إلى يومنا هذا، لذا نطلب منكم الإلتحاق في أقرب الأجال لإستئناف تكوينكم، وفي حالة عدم الالتحاق في مدة أقصاها (3) ثلاثة أيام عند استلامكم لهذا الإعذار سوف تتخذ الإجراءات الإدارية الصارمة طبقًا للقانون الخاص بالمعهد الوطني المتخصص في التكوين المهني لا سيما المادة رقم 27."
        )

    wrapped = simpleSplit(pdf_text(paragraph), font_name, 11.5, width - 36)
    c.setFont(font_name, 11.5)
    for line in wrapped:
        c.drawRightString(right_x, cursor_y, line)
        cursor_y -= 15

    c.setFont(font_name, 11.5)
    c.drawString(left_x, y + 42, pdf_text(f"حرر يوم: {action_date_display(action.send_date)}"))
    c.drawRightString(right_x, y + 42, pdf_text("ختم المراقب العام"))
    c.setFont(font_name, 9)
    c.setFillColor(colors.grey)
    c.drawString(left_x, y + 11, pdf_text(copy_label))
    c.setFillColor(colors.black)


def build_attendance_action_pdf_response(action):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    top_copy_h = (height / 2) - 18
    bottom_copy_h = top_copy_h
    draw_attendance_action_pdf_copy(c, action, 12, height / 2 + 6, width - 24, top_copy_h, "نسخة للإرسال")
    c.setDash(3, 2)
    c.line(12, height / 2, width - 12, height / 2)
    c.setDash()
    draw_attendance_action_pdf_copy(c, action, 12, 14, width - 24, bottom_copy_h, "نسخة للأرشفة")
    c.showPage()
    c.save()
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    return set_download_headers(response, action, "pdf")
