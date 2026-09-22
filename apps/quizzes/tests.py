import os
from unittest import mock

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
        # Learners must be enrolled to take or submit a quiz.
        Enrollment.objects.create(staff_user=self.user, course=self.course)
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
        quiz, report = generate_quiz_from_text(self.module, "SOP text here", num_questions=5)
        self.assertGreaterEqual(quiz.questions.count(), 1)
        for q in quiz.questions.all():
            self.assertTrue(q.choices.filter(is_correct=True).exists())
            self.assertEqual(q.choices.count(), 4)

    def test_fallback_is_reported_not_silent(self):
        """The caller must be able to tell canned output from AI output."""
        _, report = generate_quiz_from_text(self.module, "text", num_questions=3)
        self.assertTrue(report.used_fallback)
        self.assertEqual(report.source, 'fallback')
        self.assertIn('AI unavailable', report.summary())

    def test_missing_api_key_is_logged_not_silent(self):
        """Regression guard: an unset GEMINI_API_KEY used to degrade every quiz
        to the rule-based fallback with no trace in the logs, so an operator
        could not tell a healthy deployment from a misconfigured one."""
        without_key = {k: v for k, v in os.environ.items() if k != 'GEMINI_API_KEY'}
        with mock.patch.dict(os.environ, without_key, clear=True):
            with self.assertLogs('apps.quizzes.gemini_services', level='WARNING') as captured:
                generate_quiz_from_text(self.module, "text", num_questions=3)
        self.assertTrue(
            any('GEMINI_API_KEY is not set' in line for line in captured.output),
            f"expected a warning about the missing key; got: {captured.output}",
        )

    def test_fallback_honours_the_requested_count(self):
        """Regression guard: the pool used to be 5, so 6-10 silently yielded 5."""
        for count in (1, 5, 8, 10):
            _, report = generate_quiz_from_text(self.module, "text", num_questions=count)
            self.assertEqual(report.created, count, f"requested {count}")
            self.assertFalse(report.is_short)

    def test_requested_count_is_clamped_and_reported(self):
        _, report = generate_quiz_from_text(self.module, "text", num_questions=99)
        self.assertEqual(report.requested, 10)
        self.assertEqual(report.created, 10)

    def test_regeneration_clears_old(self):
        quiz1, _ = generate_quiz_from_text(self.module, "text", num_questions=3)
        quiz2, report = generate_quiz_from_text(self.module, "text", num_questions=5)
        self.assertEqual(quiz2.id, quiz1.id)
        self.assertEqual(quiz2.questions.count(), 5)
        self.assertEqual(report.created, 5)


class GenerationParsingTests(TestCase):
    """Unit tests for the response-parsing guards (internal helpers)."""

    def test_markdown_fenced_json_is_parsed(self):
        from apps.quizzes.gemini_services import _parse_json_array
        raw = '```json\n[{"question": "Q", "options": []}]\n```'
        self.assertEqual(len(_parse_json_array(raw)), 1)

    def test_json_embedded_in_prose_is_parsed(self):
        from apps.quizzes.gemini_services import _parse_json_array
        raw = 'Sure, here you go:\n[{"question": "Q", "options": []}]\nHope that helps!'
        self.assertEqual(len(_parse_json_array(raw)), 1)

    def test_empty_or_non_array_response_raises(self):
        from apps.quizzes.gemini_services import _parse_json_array
        for raw in ('', '   ', 'not json at all', '{"question": "Q"}'):
            with self.assertRaises(ValueError, msg=f"raw={raw!r}"):
                _parse_json_array(raw)

    def test_malformed_questions_are_dropped(self):
        from apps.quizzes.gemini_services import _normalise_questions
        items = [
            {"question": "Good", "options": [
                {"text": "A", "is_correct": True}, {"text": "B", "is_correct": False}]},
            {"question": "", "options": [
                {"text": "A", "is_correct": True}, {"text": "B", "is_correct": False}]},
            {"question": "No correct answer", "options": [
                {"text": "A", "is_correct": False}, {"text": "B", "is_correct": False}]},
            {"question": "Two correct", "options": [
                {"text": "A", "is_correct": True}, {"text": "B", "is_correct": True}]},
            {"question": "Only one option", "options": [{"text": "A", "is_correct": True}]},
            "not a dict",
        ]
        cleaned = _normalise_questions(items, 10)
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]['question'], "Good")

    def test_normalise_respects_the_limit(self):
        from apps.quizzes.gemini_services import _normalise_questions
        items = [
            {"question": f"Q{i}", "options": [
                {"text": "A", "is_correct": True}, {"text": "B", "is_correct": False}]}
            for i in range(10)
        ]
        self.assertEqual(len(_normalise_questions(items, 3)), 3)


class QuizEnrollmentGateTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Safety")
        self.course = Course.objects.create(title="Safety", category=self.cat)
        self.quiz = Quiz.objects.create(course=self.course, title="Q", passing_score=70)
        self.q1 = Question.objects.create(quiz=self.quiz, text="Q1")
        self.c1 = Choice.objects.create(question=self.q1, text="A", is_correct=True)
        self.enrolled = StaffUser.objects.create_user(
            employee_id="EMP320", username="emp320", email="e@b.com",
            password="pass12345", role="staff"
        )
        self.outsider = StaffUser.objects.create_user(
            employee_id="EMP321", username="emp321", email="o@b.com",
            password="pass12345", role="staff"
        )
        Enrollment.objects.create(staff_user=self.enrolled, course=self.course)

    def test_enrolled_user_can_take_quiz(self):
        self.client.login(employee_id='EMP320', password='pass12345')
        self.assertEqual(self.client.get(reverse('take_quiz', args=[self.course.id])).status_code, 200)

    def test_unenrolled_user_cannot_take_quiz(self):
        self.client.login(employee_id='EMP321', password='pass12345')
        resp = self.client.get(reverse('take_quiz', args=[self.course.id]))
        self.assertEqual(resp.status_code, 302)

    def test_unenrolled_user_cannot_submit_and_is_not_enrolled(self):
        """Submitting used to auto-enroll the caller as a side effect."""
        self.client.login(employee_id='EMP321', password='pass12345')
        resp = self.client.post(reverse('submit_quiz', args=[self.quiz.id]), {
            f'question_{self.q1.id}': self.c1.id,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Enrollment.objects.filter(staff_user=self.outsider).exists())
        self.assertFalse(QuizAttempt.objects.filter(staff_user=self.outsider).exists())

    def test_orphan_quiz_submit_renders_without_500(self):
        """A quiz with no course/module rendered course.id unguarded -> NoReverseMatch 500."""
        orphan = Quiz.objects.create(title="Orphan", passing_score=70, course=None, module=None)
        q = Question.objects.create(quiz=orphan, text="Q?")
        right = Choice.objects.create(question=q, text="A", is_correct=True)
        self.client.login(employee_id='EMP320', password='pass12345')
        resp = self.client.post(reverse('submit_quiz', args=[orphan.id]), {
            f'question_{q.id}': right.id,
        })
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(reverse('submit_quiz', args=[orphan.id]), {})
        self.assertEqual(resp.status_code, 200)


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
