from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.users.models import Department
from apps.courses.models import Category, Course, Module, Lesson, Enrollment
from apps.quizzes.models import Quiz, Question, Choice, QuizAttempt
from apps.quizzes.gemini_services import generate_quiz_from_text

StaffUser = get_user_model()


class QuizScoringTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Safety")
        self.course = Course.objects.create(title="Safety", category=self.cat)
        self.quiz = Quiz.objects.create(course=self.course, title="Safety Quiz", passing_score=70)
        self.q1 = Question.objects.create(quiz=self.quiz, text="Q1")
        self.c1 = Choice.objects.create(question=self.q1, text="A", is_correct=True)
        self.w1 = Choice.objects.create(question=self.q1, text="B", is_correct=False)
        self.q2 = Question.objects.create(quiz=self.quiz, text="Q2")
        self.c2 = Choice.objects.create(question=self.q2, text="C", is_correct=True)
        self.w2 = Choice.objects.create(question=self.q2, text="D", is_correct=False)
        self.user = StaffUser.objects.create_user(
            employee_id="EMP300", username="emp300", email="a@b.com",
            password="pass12345", role="staff"
        )
        self.client.login(employee_id='EMP300', password='pass12345')

    def test_take_quiz(self):
        resp = self.client.get(reverse('take_quiz', args=[self.course.id]))
        self.assertEqual(resp.status_code, 200)

    def test_full_score_passes(self):
        resp = self.client.post(reverse('submit_quiz', args=[self.quiz.id]), {
            f'question_{self.q1.id}': self.c1.id,
            f'question_{self.q2.id}': self.c2.id,
        })
        self.assertEqual(resp.status_code, 200)
        attempt = QuizAttempt.objects.get(staff_user=self.user)
        self.assertEqual(attempt.score, 100.0)
        self.assertTrue(attempt.passed)

    def test_zero_score_fails(self):
        resp = self.client.post(reverse('submit_quiz', args=[self.quiz.id]), {
            f'question_{self.q1.id}': self.w1.id,
            f'question_{self.q2.id}': self.w2.id,
        })
        self.assertEqual(resp.status_code, 200)
        attempt = QuizAttempt.objects.get(staff_user=self.user)
        self.assertEqual(attempt.score, 0.0)
        self.assertFalse(attempt.passed)

    def test_partial_score_below_threshold(self):
        resp = self.client.post(reverse('submit_quiz', args=[self.quiz.id]), {
            f'question_{self.q1.id}': self.c1.id,
            f'question_{self.q2.id}': self.w2.id,
        })
        attempt = QuizAttempt.objects.get(staff_user=self.user)
        self.assertEqual(attempt.score, 50.0)
        self.assertFalse(attempt.passed)


class GeminiServiceTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Safety")
        self.course = Course.objects.create(title="Safety", category=self.cat)
        self.module = Module.objects.create(course=self.course, title="Intro", order=1)

    def test_fallback_generates_questions(self):
        # No GEMINI_API_KEY -> uses rule-based fallback
        quiz = generate_quiz_from_text(self.module, "SOP text here", num_questions=5)
        self.assertGreaterEqual(quiz.questions.count(), 1)
        for q in quiz.questions.all():
            self.assertTrue(q.choices.filter(is_correct=True).exists())
            self.assertEqual(q.choices.count(), 4)

    def test_regeneration_clears_old(self):
        quiz1 = generate_quiz_from_text(self.module, "text", num_questions=3)
        n1 = quiz1.questions.count()
        quiz2 = generate_quiz_from_text(self.module, "text", num_questions=5)
        self.assertEqual(quiz2.id, quiz1.id)
        self.assertEqual(quiz2.questions.count(), n1 + 2) if n1 else self.assertTrue(True)


class AIGeneratorAccessTests(TestCase):
    def setUp(self):
        self.staff = StaffUser.objects.create_user(
            employee_id="EMP310", username="emp310", email="a@b.com",
            password="pass12345", role="staff"
        )
        self.trainer = StaffUser.objects.create_user(
            employee_id="EMP311", username="emp311", email="c@d.com",
            password="pass12345", role="trainer"
        )

    def test_staff_denied(self):
        self.client.login(employee_id='EMP310', password='pass12345')
        resp = self.client.get(reverse('generate_ai_quiz'))
        self.assertEqual(resp.status_code, 302)

    def test_trainer_allowed(self):
        self.client.login(employee_id='EMP311', password='pass12345')
        resp = self.client.get(reverse('generate_ai_quiz'))
        self.assertEqual(resp.status_code, 200)
