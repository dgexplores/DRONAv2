import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'srms_drona.settings')
django.setup()

SEED_ADMIN_PASSWORD = os.environ.get('SEED_ADMIN_PASSWORD', 'Admin12345')

from apps.users.models import StaffUser, Department
from apps.courses.models import Category, Course, Module, Lesson, Enrollment, LessonProgress
from apps.quizzes.models import Quiz, Question, Choice, QuizAttempt
from apps.certificates.models import Certificate

def create_departments():
    depts = [
        ('Library & Resource Center', 'LIB', 'Manages library cataloging, circulation, and digital resources.'),
        ('Computer & IT Lab', 'IT', 'Maintains computer labs, network equipment, and software.'),
        ('Mechanical Workshop', 'MEC', 'Oversees mechanical workshop equipment and machinery.'),
        ('Administration Office', 'ADM', 'Handles administrative records, filing, and office ERP.'),
        ('Facility & Maintenance', 'FAC', 'Manages campus facilities, electrical, and maintenance.'),
        ('Healthcare & Support', 'HCS', 'Provides healthcare support and first-aid services.'),
    ]
    created = []
    for name, code, desc in depts:
        dept, _ = Department.objects.get_or_create(code=code, defaults={'name': name, 'description': desc})
        created.append(dept)
    return created

def create_super_admin():
    if not StaffUser.objects.filter(employee_id='ADMIN001').exists():
        admin = StaffUser.objects.create_superuser(
            employee_id='ADMIN001',
            username='admin',
            email='admin@srms.ac.in',
            first_name='Super',
            last_name='Admin',
            password=SEED_ADMIN_PASSWORD,
            role='admin',
            designation='System Administrator'
        )
        print(f"Super Admin created: ADMIN001 / {SEED_ADMIN_PASSWORD}")
    return StaffUser.objects.get(employee_id='ADMIN001')

def create_staff(dept):
    staff_data = [
        ('EMP001', 'Amit', 'Sharma', 'Lab Assistant', 'staff'),
        ('EMP002', 'Priya', 'Verma', 'Library Assistant', 'staff'),
        ('EMP003', 'Rahul', 'Kumar', 'Lab Technician', 'staff'),
        ('EMP004', 'Sunita', 'Gupta', 'Admin Assistant', 'staff'),
        ('EMP005', 'Vikram', 'Singh', 'Maintenance Staff', 'staff'),
        ('EMP006', 'Neha', 'Tiwari', 'Healthcare Assistant', 'staff'),
    ]
    for emp_id, first, last, designation, role in staff_data:
        if not StaffUser.objects.filter(employee_id=emp_id).exists():
            StaffUser.objects.create_user(
                employee_id=emp_id,
                username=emp_id.lower(),
                email=f"{emp_id.lower()}@srms.ac.in",
                first_name=first,
                last_name=last,
                password='drona123',
                department=dept,
                role=role,
                designation=designation,
            )
    # HOD / Trainer
    if not StaffUser.objects.filter(employee_id='EMP010').exists():
        StaffUser.objects.create_user(
            employee_id='EMP010',
            username='hod',
            email='hod.it@srms.ac.in',
            first_name='Rajesh',
            last_name='Yadav',
            password='drona123',
            department=dept,
            role='trainer',
            designation='HOD, Computer & IT Lab',
        )
    print("Staff created. Credentials: EMP001-EMP006, EMP010 / drona123")

def create_courses(departments):
    dept_map = {d.code: d for d in departments}

    categories_data = [
        ('Computer & IT', 'कंप्यूटर और आईटी', 'laptop', 'Computer lab handling and software skills.'),
        ('Safety & Compliance', 'सुरक्षा और अनुपालन', 'shield', 'Mandatory safety training and compliance.'),
        ('Library & Administration', 'पुस्तकालय और प्रशासन', 'book', 'Library cataloging and office administration.'),
        ('Maintenance & Facility', 'रखरखाव और सुविधा', 'wrench', 'Facility maintenance and operations.'),
        ('Healthcare & Support', 'स्वास्थ्य सेवा और समर्थन', 'heart', 'Healthcare support and first aid.'),
    ]
    cat_map = {}
    for name, name_hi, icon, desc in categories_data:
        cat, _ = Category.objects.get_or_create(name=name, defaults={'name_hi': name_hi, 'icon': icon, 'description': desc})
        cat_map[name] = cat

    courses_data = [
        {
            'title': 'Computer Lab Equipment Handling',
            'title_hi': 'कंप्यूटर लैब उपकरण प्रबंधन',
            'desc': 'Learn safe handling, maintenance, and troubleshooting of computer lab equipment.',
            'desc_hi': 'कंप्यूटर लैब उपकरणों का सुरक्षित संचालन, रखरखाव और समस्या निवारण सीखें।',
            'category': 'Computer & IT',
            'mandatory': False,
            'depts': ['IT'],
        },
        {
            'title': 'Fire & Chemical Safety Training',
            'title_hi': 'अग्नि और रासायनिक सुरक्षा प्रशिक्षण',
            'desc': 'Mandatory safety protocol for fire prevention and chemical handling.',
            'desc_hi': 'अग्नि रोकथाम और रासायनिक प्रबंधन के लिए अनिवार्य सुरक्षा प्रोटोकॉल।',
            'category': 'Safety & Compliance',
            'mandatory': True,
            'depts': ['MEC', 'FAC', 'IT', 'LIB', 'ADM', 'HCS'],
        },
        {
            'title': 'Library Cataloging & Digital Resources',
            'title_hi': 'पुस्तकालय कैटलॉगिंग और डिजिटल संसाधन',
            'desc': 'Learn modern library cataloging systems and digital resource management.',
            'desc_hi': 'आधुनिक पुस्तकालय कैटलॉगिंग सिस्टम और डिजिटल संसाधन प्रबंधन सीखें।',
            'category': 'Library & Administration',
            'mandatory': False,
            'depts': ['LIB'],
        },
        {
            'title': 'Office ERP Automation',
            'title_hi': 'कार्यालय ईआरपी स्वचालन',
            'desc': 'Master office ERP systems for administration, filing, and record keeping.',
            'desc_hi': 'प्रशासन, फाइलिंग और रिकॉर्ड रखने के लिए कार्यालय ईआरपी सिस्टम में महारत हासिल करें।',
            'category': 'Library & Administration',
            'mandatory': False,
            'depts': ['ADM'],
        },
        {
            'title': 'Facility & Electrical Safety',
            'title_hi': 'सुविधा और विद्युत सुरक्षा',
            'desc': 'Safety and maintenance procedures for campus facilities and electrical systems.',
            'desc_hi': 'परिसर सुविधाओं और विद्युत प्रणालियों के लिए सुरक्षा और रखरखाव प्रक्रियाएं।',
            'category': 'Maintenance & Facility',
            'mandatory': True,
            'depts': ['FAC', 'MEC'],
        },
        {
            'title': 'Healthcare & First Aid Basics',
            'title_hi': 'स्वास्थ्य सेवा और प्राथमिक चिकित्सा',
            'desc': 'Basic healthcare support and first aid procedures for campus staff.',
            'desc_hi': 'परिसर कर्मचारियों के लिए बुनियादी स्वास्थ्य सेवा और प्राथमिक चिकित्सा प्रक्रियाएं।',
            'category': 'Healthcare & Support',
            'mandatory': False,
            'depts': ['HCS'],
        },
    ]

    course_map = {}
    for c in courses_data:
        cat = cat_map[c['category']]
        course, created = Course.objects.get_or_create(
            title=c['title'],
            defaults={
                'title_hi': c['title_hi'],
                'description': c['desc'],
                'description_hi': c['desc_hi'],
                'category': cat,
                'is_mandatory': c['mandatory'],
            }
        )
        for code in c['depts']:
            course.target_departments.add(dept_map[code])
        course_map[c['title']] = course

        # Create modules and lessons
        if created or course.modules.count() == 0:
            create_modules_and_lessons(course)

    print(f"Created {len(courses_data)} courses with modules & lessons.")
    return course_map

def create_modules_and_lessons(course):
    base_title = course.title
    module_specs = [
        {
            'title': f'Introduction to {base_title}',
            'title_hi': f'{course.title_hi} का परिचय',
            'lessons': [
                {'title': 'Welcome & Overview', 'title_hi': 'स्वागत और अवलोकन', 'type': 'video', 'dur': 12},
                {'title': 'Key Concepts & Terminology', 'title_hi': 'प्रमुख अवधारणाएं और शब्दावली', 'type': 'pdf', 'dur': 15},
            ],
        },
        {
            'title': f'Core Procedures in {base_title}',
            'title_hi': f'{course.title_hi} में मुख्य प्रक्रियाएं',
            'lessons': [
                {'title': 'Standard Operating Procedure', 'title_hi': 'मानक संचालन प्रक्रिया', 'type': 'pdf', 'dur': 20},
                {'title': 'Hands-On Demonstration', 'title_hi': 'व्यावहारिक प्रदर्शन', 'type': 'video', 'dur': 25},
            ],
        },
        {
            'title': f'Safety & Compliance for {base_title}',
            'title_hi': f'{course.title_hi} के लिए सुरक्षा और अनुपालन',
            'lessons': [
                {'title': 'Safety Guidelines', 'title_hi': 'सुरक्षा दिशानिर्देश', 'type': 'video', 'dur': 18},
                {'title': 'Compliance Checklist', 'title_hi': 'अनुपालन जांच सूची', 'type': 'pdf', 'dur': 10},
            ],
        },
    ]

    for m_idx, m in enumerate(module_specs, start=1):
        module, _ = Module.objects.get_or_create(
            course=course,
            order=m_idx,
            defaults={'title': m['title'], 'title_hi': m['title_hi']}
        )
        for l_idx, l in enumerate(m['lessons'], start=1):
            if not Lesson.objects.filter(module=module, order=l_idx).exists():
                lesson = Lesson.objects.create(
                    module=module,
                    title=l['title'],
                    title_hi=l['title_hi'],
                    lesson_type=l['type'],
                    duration_minutes=l['dur'],
                    order=l_idx,
                )
                if l['type'] == 'pdf':
                    lesson.sop_text = _generate_sop_text(base_title, module.title, lesson.title)
                    lesson.save()

def _generate_sop_text(course_title, module_title, lesson_title):
    return f"""
STANDARD OPERATING PROCEDURE (SOP)
{module_title}

PURPOSE:
This document establishes the standard operating procedure for {lesson_title} at SRMS Group of Institutions.

SCOPE:
This procedure applies to all non-teaching staff members responsible for {course_title}.

RESPONSIBILITIES:
1. All staff must complete mandatory safety and compliance training annually.
2. Staff must maintain a digital or physical log of all operational activities.
3. Any operational anomaly must be immediately reported to the Departmental HOD.

GENERAL GUIDELINES:
1. Before starting operations, review the daily checklist.
2. Ensure proper use of personal protective equipment (PPE) where required.
3. Maintain a clean and organized workspace.
4. Do not modify equipment settings without authorization.
5. Report all incidents immediately using the institutional incident form.

COMPLIANCE:
Staff must achieve 100% completion of this SOP training and pass the final assessment with a score of 70% or higher to receive their verified certificate.

REVIEW:
This SOP is reviewed annually or whenever operational procedures change.
"""

def create_quizzes(course_map):
    quiz_titles = {
        'Computer Lab Equipment Handling': 'Computer Lab Equipment Quiz',
        'Fire & Chemical Safety Training': 'Fire & Chemical Safety Quiz',
        'Library Cataloging & Digital Resources': 'Library Cataloging Quiz',
        'Office ERP Automation': 'Office ERP Automation Quiz',
        'Facility & Electrical Safety': 'Facility & Electrical Safety Quiz',
        'Healthcare & First Aid Basics': 'Healthcare & First Aid Quiz',
    }
    for course_title, quiz_title in quiz_titles.items():
        course = course_map.get(course_title)
        if not course:
            continue
        quiz, created = Quiz.objects.get_or_create(
            course=course,
            defaults={'title': quiz_title, 'passing_score': 70}
        )
        if created or quiz.questions.count() == 0:
            _create_quiz_questions(quiz, course.title)
    print(f"Created {len(quiz_titles)} quizzes.")

def _create_quiz_questions(quiz, course_title):
    # Simple MCQ generator based on course topic
    topic_keywords = {
        'Computer Lab Equipment Handling': 'equipment',
        'Fire & Chemical Safety Training': 'safety',
        'Library Cataloging & Digital Resources': 'library',
        'Office ERP Automation': 'ERP',
        'Facility & Electrical Safety': 'electrical',
        'Healthcare & First Aid Basics': 'first aid',
    }
    keyword = topic_keywords.get(course_title, 'campus')

    question_bank = [
        {
            'q': f'What is the primary objective of the {course_title} protocol at SRMS campus?',
            'q_hi': f'एसआरएमएस परिसर में {course_title} प्रोटोकॉल का मुख्य उद्देश्य क्या है?',
            'opts': [
                ('To ensure safety, compliance, and standard operational accuracy', 'सुरक्षा, अनुपालन और मानक संचालन सटीकता सुनिश्चित करना', True),
                ('To reduce daily documentation procedures', 'दैनिक दस्तावेज़ीकरण प्रक्रियाओं को कम करना', False),
                ('To bypass mandatory institutional reporting', 'अनिवार्य संस्थागत रिपोर्टिंग को बायपास करना', False),
                ('None of the above', 'उपरोक्त में से कोई नहीं', False),
            ],
            'exp': f'The {keyword} protocol is designed to ensure safety and standard operating compliance.',
        },
        {
            'q': f'In case of an operational anomaly during {course_title}, what is the first action staff should take?',
            'q_hi': f'{course_title} के दौरान परिचालन विसंगति के मामले में, कर्मचारियों को पहला क्या कदम उठाना चाहिए?',
            'opts': [
                ('Ignore the anomaly if minor', 'यदि मामूली हो तो विसंगति को नज़रअंदाज़ करें', False),
                ('Immediately notify the Departmental HOD and record in maintenance log', 'तुरंत विभागाध्यक्ष को सूचित करें और रजिस्टर में दर्ज करें', True),
                ('Attempt unauthorized modification', 'अनधिकृत संशोधन का प्रयास करें', False),
                ('Leave the workspace unattended', 'कार्यस्थल को लावारिस छोड़ दें', False),
            ],
            'exp': 'Immediate escalation and logging prevents equipment damage and ensures safety.',
        },
        {
            'q': f'How frequently must compliance checklists be reviewed for {course_title}?',
            'q_hi': f'{course_title} के लिए अनुपालन जाँच सूचियों की समीक्षा कितनी बार की जानी चाहिए?',
            'opts': [
                ('Daily / per-shift basis prior to operations', 'संचालन से पहले दैनिक / प्रति शिफ्ट के आधार पर', True),
                ('Once every academic year', 'प्रत्येक शैक्षणिक वर्ष में एक बार', False),
                ('Only when requested by external auditors', 'केवल बाहरी लेखा परीक्षकों द्वारा अनुरोध किए जाने पर', False),
                ('Never', 'कभी नहीं', False),
            ],
            'exp': 'Shift-wise inspection ensures operational readiness.',
        },
        {
            'q': f'What documentation is required after completing tasks under {course_title}?',
            'q_hi': f'{course_title} के तहत कार्यों को पूरा करने के बाद किस दस्तावेज़ीकरण की आवश्यकता होती है?',
            'opts': [
                ('No log is required', 'किसी लॉग की आवश्यकता नहीं है', False),
                ('Update the digital/physical register with timestamp and Employee ID', 'समय और कर्मचारी आईडी के साथ रजिस्टर को अपडेट करें', True),
                ('Informal verbal communication only', 'केवल अनौपचारिक मौखिक संचार', False),
                ('Deleting session logs', 'सत्र लॉग मिटाना', False),
            ],
            'exp': 'Proper logging maintains institutional audit trails and accountability.',
        },
        {
            'q': f'Which emergency safety protocol applies to {course_title} at SRMS campus?',
            'q_hi': f'एसआरएमएस परिसर में {course_title} पर कौन सा आपातकालीन सुरक्षा प्रोटोकॉल लागू होता है?',
            'opts': [
                ('Press emergency stop, evacuate area, and contact Security/HOD', 'इमरजेंसी स्टॉप दबाएं, क्षेत्र खाली करें, और सुरक्षा/विभागाध्यक्ष से संपर्क करें', True),
                ('Continue working until shift ends', 'शिफ्ट खत्म होने तक काम जारी रखें', False),
                ('Attempt repairs without PPE', 'बिना पीपीई के मरम्मत का प्रयास करें', False),
                ('Lock the facility doors from inside', 'अंदर से परिसर के दरवाजे लॉक करें', False),
            ],
            'exp': 'Standard emergency protocol prioritizes staff safety and swift evacuation.',
        },
    ]

    for idx, item in enumerate(question_bank[:5], start=1):
        q = Question.objects.create(
            quiz=quiz,
            text=item['q'],
            text_hi=item['q_hi'],
            explanation=item['exp'],
            points=1,
        )
        for opt_en, opt_hi, is_corr in item['opts']:
            Choice.objects.create(question=q, text=opt_en, text_hi=opt_hi, is_correct=is_corr)

def create_enrollments_and_progress(staff):
    dept_courses = Course.objects.filter(is_mandatory=True, target_departments=staff.department)
    for course in dept_courses:
        enrollment, created = Enrollment.objects.get_or_create(staff_user=staff, course=course)
        if created:
            # Auto-complete all lessons and progress
            lessons = list(Lesson.objects.filter(module__course=course).order_by('module__order', 'order'))
            for lesson in lessons:
                LessonProgress.objects.get_or_create(
                    enrollment=enrollment, lesson=lesson,
                    defaults={'is_completed': True}
                )
            enrollment.update_progress()

            # Create a passing quiz attempt and certificate
            quiz = Quiz.objects.filter(course=course).first()
            if quiz:
                QuizAttempt.objects.create(
                    staff_user=staff, quiz=quiz, score=90.0,
                    total_questions=5, passed=True
                )
            if enrollment.progress_percent >= 100:
                Certificate.objects.get_or_create(staff_user=staff, course=course)
    print(f"Enrolled {staff.employee_id} in mandatory courses and issued certificates.")

def run():
    print("=== SRMS Drona Seed Script ===")
    departments = create_departments()
    create_super_admin()
    create_staff(departments[1])  # IT dept
    course_map = create_courses(departments)
    create_quizzes(course_map)

    for staff in StaffUser.objects.filter(role='staff'):
        create_enrollments_and_progress(staff)

    print("=== Seed complete ===")
    print("Login credentials:")
    print("  Admin:     ADMIN001 / " + SEED_ADMIN_PASSWORD)
    print("  HOD/Train: EMP010   / drona123")
    print("  Staff:     EMP001-EMP006 / drona123")

if __name__ == '__main__':
    run()
