import os
import io
import qrcode
from django.conf import settings
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from apps.certificates.models import Certificate

def generate_certificate_pdf(staff_user, course, request_host="127.0.0.1:8000"):
    cert, created = Certificate.objects.get_or_create(
        staff_user=staff_user,
        course=course
    )

    pdf_filename = f"{cert.certificate_id}.pdf"
    pdf_dir = os.path.join(settings.MEDIA_ROOT, 'certificates')
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, pdf_filename)

    # 1. Generate QR Code
    verify_url = f"http://{request_host}/verify/{cert.certificate_id}/"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(verify_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#1E3A8A", back_color="white") # Navy Blue QR
    
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    # 2. Build PDF Document with ReportLab Canvas
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch
    )

    story = []
    styles = getSampleStyleSheet()

    # Custom Styles
    title_style = ParagraphStyle(
        'CertHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#1E3A8A"), # SRMS Blue
        alignment=1, # Center
        spaceAfter=6
    )

    sub_header_style = ParagraphStyle(
        'CertSubHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#B91C1C"), # Crimson Red
        alignment=1,
        spaceAfter=20
    )

    cert_title_style = ParagraphStyle(
        'CertTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#111827"),
        alignment=1,
        spaceAfter=15
    )

    body_style = ParagraphStyle(
        'CertBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=20,
        textColor=colors.HexColor("#374151"),
        alignment=1,
        spaceAfter=15
    )

    name_style = ParagraphStyle(
        'CertName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#1E3A8A"),
        alignment=1,
        spaceAfter=15
    )

    course_style = ParagraphStyle(
        'CertCourse',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#065F46"), # Emerald Green
        alignment=1,
        spaceAfter=20
    )

    # Building Flow
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("SHRI RAM MURTI SMARAK GROUP OF INSTITUTIONS", title_style))
    story.append(Paragraph("SRMS DRONA SKILL LEARNING & PERFORMANCE PLATFORM", sub_header_style))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("CERTIFICATE OF PROFICIENCY & COMPLIANCE", cert_title_style))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("This is proudly presented to", body_style))
    
    full_name = staff_user.get_full_name() or staff_user.employee_id
    story.append(Paragraph(full_name.upper(), name_style))
    
    dept_name = staff_user.department.name if staff_user.department else "General Administration"
    designation = staff_user.designation or "Staff Member"
    emp_details = f"Employee ID: <b>{staff_user.employee_id}</b> &nbsp;|&nbsp; Designation: <b>{designation}</b> &nbsp;|&nbsp; Department: <b>{dept_name}</b>"
    story.append(Paragraph(emp_details, body_style))
    
    story.append(Paragraph("for successfully completing mandatory course training and qualifying the final assessment in", body_style))
    story.append(Paragraph(course.title, course_style))

    issue_date = cert.issued_at.strftime("%d %B %Y")
    story.append(Paragraph(f"Issued on: <b>{issue_date}</b> &nbsp;|&nbsp; Verification ID: <b>{cert.certificate_id}</b>", body_style))
    story.append(Spacer(1, 0.2 * inch))

    # Bottom Table: Left QR Code, Right Signature
    qr_image = Image(qr_buffer, width=1.1*inch, height=1.1*inch)
    
    qr_cell = [
        qr_image,
        Paragraph(f"<font size=8 color='#4B5563'>Scan QR to Verify<br/>{cert.certificate_id}</font>", ParagraphStyle('QRSub', alignment=1))
    ]

    sig_cell = Paragraph(
        "<b>_______________________</b><br/>"
        "<b>Head of HR & Learning</b><br/>"
        "<font size=9 color='#6B7280'>SRMS Group of Institutions</font>",
        ParagraphStyle('Sig', alignment=1, fontSize=10, leading=14)
    )

    footer_table = Table([[qr_cell, "", sig_cell]], colWidths=[2.5*inch, 4.0*inch, 2.5*inch])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'CENTER'),
        ('ALIGN', (2,0), (2,0), 'CENTER'),
    ]))
    
    story.append(footer_table)

    # Draw Decorative Border on Canvas
    def draw_background_and_border(canvas_obj, doc_obj):
        canvas_obj.saveState()
        width, height = doc_obj.pagesize
        
        # Outer Gold Border
        canvas_obj.setStrokeColor(colors.HexColor("#D97706")) # Amber/Gold
        canvas_obj.setLineWidth(4)
        canvas_obj.rect(0.25 * inch, 0.25 * inch, width - 0.5 * inch, height - 0.5 * inch)

        # Inner Navy Border
        canvas_obj.setStrokeColor(colors.HexColor("#1E3A8A"))
        canvas_obj.setLineWidth(1.5)
        canvas_obj.rect(0.32 * inch, 0.32 * inch, width - 0.64 * inch, height - 0.64 * inch)
        
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=draw_background_and_border)

    # Save PDF to disk
    pdf_bytes = buffer.getvalue()
    with open(pdf_path, 'wb') as f:
        f.write(pdf_bytes)

    cert.pdf_file = f"certificates/{pdf_filename}"
    cert.save()

    return cert
