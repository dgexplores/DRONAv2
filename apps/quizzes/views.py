from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.courses.models import Course, Module, Enrollment
from apps.quizzes.models import Quiz, Question, Choice, QuizAttempt
from apps.certificates.pdf_builder import generate_certificate_pdf
from apps.quizzes.gemini_services import generate_quiz_from_text

@login_required
def take_quiz_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    quiz = Quiz.objects.filter(course=course).first()
    
    if not quiz:
        # Check if any module has a quiz
        module_quiz = Quiz.objects.filter(module__course=course).first()
        quiz = module_quiz

    if not quiz:
        messages.warning(request, "No quiz found for this course yet.")
        return redirect('course_detail', course_id=course.id)

    questions = quiz.questions.prefetch_related('choices').all()

    context = {
        'course': course,
        'quiz': quiz,
        'questions': questions,
    }
    return render(request, 'quizzes/take_quiz.html', context)

@login_required
def submit_quiz_view(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    course = quiz.course or (quiz.module.course if quiz.module else None)

    if request.method == 'POST':
        questions = quiz.questions.prefetch_related('choices').all()
        total_q = questions.count()
        correct_count = 0

        for q in questions:
            selected_choice_id = request.POST.get(f"question_{q.id}")
            if selected_choice_id:
                try:
                    choice = Choice.objects.get(id=selected_choice_id, question=q)
                    if choice.is_correct:
                        correct_count += 1
                except Choice.DoesNotExist:
                    pass

        score_percent = round((correct_count / total_q) * 100, 1) if total_q > 0 else 0
        passed = score_percent >= quiz.passing_score

        attempt = QuizAttempt.objects.create(
            staff_user=request.user,
            quiz=quiz,
            score=score_percent,
            total_questions=total_q,
            passed=passed
        )

        # Check if course completed and certificate can be issued!
        if course:
            enrollment, _ = Enrollment.objects.get_or_create(staff_user=request.user, course=course)
            if passed and enrollment.progress_percent >= 100:
                host = request.get_host()
                generate_certificate_pdf(request.user, course, request_host=host)
                messages.success(request, f"Congratulations! You passed with {score_percent}% and earned your official SRMS Verified Certificate!")
            elif passed:
                messages.success(request, f"You passed the quiz with {score_percent}%! Complete remaining video/PDF lessons to receive your certificate.")
            else:
                messages.error(request, f"You scored {score_percent}%. Passing threshold is {quiz.passing_score}%. Please review course SOPs and retry.")

        context = {
            'quiz': quiz,
            'attempt': attempt,
            'score_percent': score_percent,
            'passed': passed,
            'correct_count': correct_count,
            'total_q': total_q,
            'course': course,
        }
        return render(request, 'quizzes/quiz_result.html', context)

    return redirect('dashboard')

@login_required
def generate_ai_quiz(request):
    """
    Admin / Trainer view to trigger Gemini AI Quiz generation from text/PDF SOP.
    """
    if request.user.role not in ['trainer', 'admin'] and not request.user.is_staff:
        messages.error(request, "Permission denied. Only Trainers and HODs can generate AI quizzes.")
        return redirect('dashboard')

    modules = Module.objects.select_related('course').all()

    if request.method == 'POST':
        module_id = request.POST.get('module_id')
        sop_text = request.POST.get('sop_text', '').strip()
        num_questions = int(request.POST.get('num_questions', 5))

        module = get_object_or_404(Module, id=module_id)

        # If PDF uploaded, extract text with pypdf
        if 'pdf_file' in request.FILES:
            pdf_file = request.FILES['pdf_file']
            try:
                import pypdf
                reader = pypdf.PdfReader(pdf_file)
                extracted_text = ""
                for page in reader.pages:
                    extracted_text += page.extract_text() or ""
                if extracted_text:
                    sop_text = extracted_text
            except Exception as e:
                messages.error(request, f"Failed to extract text from PDF: {e}")

        if not sop_text:
            sop_text = f"Standard Operating Procedure for {module.title} at SRMS Campus."

        quiz = generate_quiz_from_text(module, sop_text, num_questions=num_questions)
        messages.success(request, f"Gemini AI Quiz generated with {quiz.questions.count()} MCQs for '{module.title}'!")
        return redirect('admin:quizzes_quiz_change', quiz.id)

    return render(request, 'quizzes/ai_quiz_generator.html', {'modules': modules})
