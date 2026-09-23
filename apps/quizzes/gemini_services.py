"""MCQ generation from SOP text.

Primary path is Google Gemini. When no API key is configured, or every model
fails, a rule-based generator keeps the feature usable.

The fallback is deliberately *not* silent: ``generate_quiz_from_text`` returns a
:class:`GenerationReport` alongside the quiz so callers can tell AI output from
canned text. Presenting generic template questions to staff as AI-generated
assessment is worse than failing loudly.
"""
import json
import logging
import os
import re
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from apps.quizzes.models import Choice, Question, Quiz

logger = logging.getLogger(__name__)

# Tried in order. Pin one with the GEMINI_MODEL env var -- a hardcoded list rots
# silently as Google retires model versions, and each retirement would quietly
# degrade the feature to the fallback with no signal to anyone. Stable models
# first; the preview entry goes last because previews get retired with little
# notice.
DEFAULT_GEMINI_MODELS = (
    'gemini-3.5-flash',
    'gemini-3.1-flash-lite',
    'gemini-2.5-flash',
    'gemini-3-flash-preview',
)

MIN_QUESTIONS = 1
MAX_QUESTIONS = 10
# The rule-based pool is fixed; it cannot honour a larger request.
FALLBACK_POOL_SIZE = 10


def _model_candidates():
    pinned = (os.environ.get('GEMINI_MODEL') or '').strip()
    return [pinned] if pinned else list(DEFAULT_GEMINI_MODELS)


@dataclass
class GenerationReport:
    """What actually happened during generation."""

    source: str = 'fallback'  # 'gemini' | 'fallback'
    model: str = ''
    requested: int = 0
    created: int = 0
    notes: list = field(default_factory=list)

    @property
    def used_fallback(self):
        return self.source != 'gemini'

    @property
    def is_short(self):
        return self.created < self.requested

    def summary(self):
        """One-line description for an admin-facing message."""
        if self.used_fallback:
            detail = (
                f"AI unavailable - generated {self.created} template question(s) "
                "with the offline generator. Review before publishing."
            )
            if self.notes:
                detail += f" Reason: {self.notes[-1]}."
            return detail
        return f"Generated {self.created} question(s) with {self.model}."


def _parse_json_array(raw):
    """Parse a JSON array, tolerating the markdown fences models add anyway."""
    if not raw or not raw.strip():
        raise ValueError("empty response")
    text = raw.strip()
    fence = re.match(r'^```(?:json)?\s*(.*?)\s*```$', text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    if not text.startswith('['):
        start, end = text.find('['), text.rfind(']')
        if start == -1 or end == -1:
            raise ValueError("no JSON array in response")
        text = text[start:end + 1]
    data = json.loads(text)
    if not isinstance(data, list) or not data:
        raise ValueError("response was not a non-empty JSON array")
    return data


def _normalise_questions(items, limit):
    """Keep only well-formed questions; drop anything unusable.

    A malformed model response must not reach the database as a broken quiz, and
    must not silently reduce the count without the caller knowing.
    """
    cleaned = []
    for item in items:
        if not isinstance(item, dict):
            continue
        question = str(item.get('question') or '').strip()
        raw_options = item.get('options')
        if not isinstance(raw_options, list):
            continue
        options = []
        for opt in raw_options:
            if not isinstance(opt, dict):
                continue
            text = str(opt.get('text') or '').strip()
            if not text:
                continue
            options.append({
                'text': text,
                'text_hi': str(opt.get('text_hi') or '').strip(),
                'is_correct': bool(opt.get('is_correct')),
            })
        # Need a stem, at least two choices, and exactly one correct answer.
        if not question or len(options) < 2:
            continue
        if sum(1 for o in options if o['is_correct']) != 1:
            continue
        cleaned.append({
            'question': question,
            'question_hi': str(item.get('question_hi') or '').strip(),
            'explanation': str(item.get('explanation') or '').strip(),
            'explanation_hi': str(item.get('explanation_hi') or '').strip(),
            'options': options,
        })
        if len(cleaned) >= limit:
            break
    return cleaned


def _build_prompt(module, text_content, num_questions):
    return f"""
You are an expert trainer for non-teaching staff at Shri Ram Murti Smarak (SRMS) Group of Institutions.
Based on the following Standard Operating Procedure (SOP) text, generate {num_questions} multiple-choice assessment questions.

SOP Content:
\"\"\"
{text_content[:4000]}
\"\"\"

Requirements:
- Each question must have exactly four options with exactly one correct answer.
- Return ONLY a JSON array, with no surrounding prose or markdown fences.

Return a JSON array of objects with this exact format:
[
  {{
    "question": "Question text in English",
    "question_hi": "Question text in Hindi",
    "explanation": "Brief explanation why correct answer is right",
    "explanation_hi": "Explanation in Hindi",
    "options": [
      {{"text": "Option A", "text_hi": "Option A Hindi", "is_correct": false}},
      {{"text": "Option B", "text_hi": "Option B Hindi", "is_correct": true}},
      {{"text": "Option C", "text_hi": "Option C Hindi", "is_correct": false}},
      {{"text": "Option D", "text_hi": "Option D Hindi", "is_correct": false}}
    ]
  }}
]
"""


def _generate_with_gemini(api_key, module, text_content, num_questions, report):
    """Try each candidate model in order. Returns (questions, model_name)."""
    prompt = _build_prompt(module, text_content, num_questions)
    try:
        client = genai.Client(api_key=api_key)
    except Exception as exc:  # noqa: BLE001 - report and fall back
        logger.warning("Gemini client init failed: %s", exc)
        report.notes.append(f"client init failed ({type(exc).__name__})")
        return [], ''

    for model in _model_candidates():
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            questions = _normalise_questions(_parse_json_array(response.text), num_questions)
            if questions:
                return questions, model
            logger.warning("Gemini model %s returned no usable questions", model)
            report.notes.append(f"{model}: no usable questions in response")
        except Exception as exc:  # noqa: BLE001 - try the next model
            logger.warning("Gemini model %s failed: %s", model, exc)
            report.notes.append(f"{model}: {type(exc).__name__}")
    return [], ''


def generate_quiz_from_text(module, text_content, num_questions=5):
    """Generate (or regenerate) a quiz for ``module``.

    Returns ``(quiz, GenerationReport)``. Never raises for a generation failure:
    the rule-based fallback keeps the feature usable, and the report lets the
    caller say so instead of mislabelling template output as AI-generated.
    """
    try:
        requested = int(num_questions)
    except (TypeError, ValueError):
        requested = 5
    requested = max(MIN_QUESTIONS, min(requested, MAX_QUESTIONS))
    report = GenerationReport(requested=requested)

    quiz, _ = Quiz.objects.get_or_create(
        module=module,
        defaults={
            'title': f"Assessment: {module.title}",
            'title_hi': f"मूल्यांकन: {module.title_hi or module.title}",
            'passing_score': 70,
        }
    )
    # Clear existing questions for re-generation.
    quiz.questions.all().delete()

    questions = []
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # Without this line an unset key degrades every quiz to the rule-based
        # fallback with no trace in the logs -- operators cannot tell a healthy
        # deployment from a misconfigured one. See ENGINEERING.md, silent fallback.
        logger.warning(
            "GEMINI_API_KEY is not set; quiz %s will use the rule-based fallback.", quiz.pk
        )
    else:
        questions, report.model = _generate_with_gemini(
            api_key, module, text_content, requested, report
        )
        if questions:
            report.source = 'gemini'

    if not questions:
        questions = _generate_fallback_questions(module.title, text_content, requested)
        report.source = 'fallback'
        logger.warning(
            "Quiz %s fell back to rule-based questions (%s created, %s requested).",
            quiz.pk, len(questions), requested,
        )

    for item in questions:
        question = Question.objects.create(
            quiz=quiz,
            text=item['question'],
            text_hi=item['question_hi'],
            explanation=item['explanation'],
            explanation_hi=item['explanation_hi'],
            points=1,
        )
        for opt in item['options']:
            Choice.objects.create(
                question=question,
                text=opt['text'],
                text_hi=opt['text_hi'] or opt['text'],
                is_correct=opt['is_correct'],
            )

    report.created = len(questions)
    if report.is_short:
        report.notes.append(
            f"generated {report.created} of {report.requested} requested questions"
        )
    return quiz, report


def _generate_fallback_questions(module_title, text_content, num_questions):
    """Rule-based questions used when Gemini is unavailable.

    The pool is fixed at FALLBACK_POOL_SIZE entries; callers asking for more get
    FALLBACK_POOL_SIZE and are told so through the report.
    """
    templates = [
        {
            "q": f"What is the primary objective of the {module_title} protocol at SRMS campus?",
            "q_hi": f"एसआरएमएस परिसर में {module_title} प्रोटोकॉल का मुख्य उद्देश्य क्या है?",
            "opts": [
                ("To ensure safety, compliance, and standard operational accuracy", "सुरक्षा, अनुपालन और मानक संचालन सटीकता सुनिश्चित करना", True),
                ("To reduce daily documentation procedures", "दैनिक दस्तावेज़ीकरण प्रक्रियाओं को कम करना", False),
                ("To bypass mandatory institutional reporting", "अनिवार्य संस्थागत रिपोर्टिंग को बायपास करना", False),
                ("None of the above", "उपरोक्त में से कोई नहीं", False),
            ],
            "exp": "SOPs are designed to ensure safety and standard operating compliance across all departments.",
            "exp_hi": "SOPs सभी विभागों में सुरक्षा और मानक संचालन अनुपालन सुनिश्चित करने के लिए डिज़ाइन किए गए हैं।",
        },
        {
            "q": f"In case of an operational anomaly during {module_title}, what is the first action staff should take?",
            "q_hi": f"{module_title} के दौरान परिचालन विसंगति के मामले में, कर्मचारियों को पहला क्या कदम उठाना चाहिए?",
            "opts": [
                ("Ignore the anomaly if minor", "यदि मामूली हो तो विसंगति को नज़रअंदाज़ करें", False),
                ("Immediately notify the Departmental HOD / Trainer and record in maintenance log", "तुरंत विभागाध्यक्ष/ट्रेनर को सूचित करें और रजिस्टर में दर्ज करें", True),
                ("Attempt unauthorized equipment modification", "अनधिकृत उपकरण संशोधन का प्रयास करें", False),
                ("Leave the workspace unattended", "कार्यस्थल को लावारिस छोड़ दें", False),
            ],
            "exp": "Immediate escalation and logging prevents equipment damage and ensures safety.",
            "exp_hi": "तत्काल रिपोर्टिंग और लॉगिंग से नुकसान से बचा जा सकता है।",
        },
        {
            "q": f"How frequently must compliance and maintenance checklists be reviewed for {module_title}?",
            "q_hi": f"{module_title} के लिए अनुपालन और रखरखाव जाँच सूचियों की समीक्षा कितनी बार की जानी चाहिए?",
            "opts": [
                ("Daily / per-shift basis prior to operations", "संचालन से पहले दैनिक / प्रति शिफ्ट के आधार पर", True),
                ("Once every academic year", "प्रत्येक शैक्षणिक वर्ष में एक बार", False),
                ("Only when requested by external auditors", "केवल बाहरी लेखा परीक्षकों द्वारा अनुरोध किए जाने पर", False),
                ("Never", "कभी नहीं", False),
            ],
            "exp": "Shift-wise inspection ensures operational readiness.",
            "exp_hi": "शिफ्ट-वार निरीक्षण परिचालन तत्परता सुनिश्चित करता है।",
        },
        {
            "q": f"What documentation is required after completing tasks under {module_title}?",
            "q_hi": f"{module_title} के तहत कार्यों को पूरा करने के बाद किस दस्तावेज़ीकरण की आवश्यकता होती है?",
            "opts": [
                ("No log is required", "किसी लॉग की आवश्यकता नहीं है", False),
                ("Updating the digital / physical departmental register with timestamp and Employee ID", "समय और कर्मचारी आईडी के साथ रजिस्टर को अपडेट करना", True),
                ("Informal verbal communication only", "केवल अनौपचारिक मौखिक संचार", False),
                ("Deleting session logs", "सत्र लॉग मिटाना", False),
            ],
            "exp": "Proper logging maintains institutional audit trails and accountability.",
            "exp_hi": "उचित लॉगिंग संस्थागत जवाबदेही बनाए रखती है।",
        },
        {
            "q": f"Which emergency safety protocol applies to {module_title} at SRMS campus?",
            "q_hi": f"एसआरएमएस परिसर में {module_title} पर कौन सा आपातकालीन सुरक्षा प्रोटोकॉल लागू होता है?",
            "opts": [
                ("Press emergency stop/isolation, evacuate area, and contact Security/HOD", "इमरजेंसी स्टॉप दबाएं, क्षेत्र खाली करें, और सुरक्षा/विभागाध्यक्ष से संपर्क करें", True),
                ("Continue working until shift ends", "शिफ्ट खत्म होने तक काम जारी रखें", False),
                ("Try to repair high-voltage or chemical hazards without PPE", "बिना पीपीई के उच्च वोल्टेज या रासायनिक खतरों को ठीक करने का प्रयास करें", False),
                ("Lock the facility doors from inside", "अंदर से परिसर के दरवाजे लॉक करें", False),
            ],
            "exp": "Standard emergency protocol prioritizes staff safety and swift evacuation.",
            "exp_hi": "मानक आपातकालीन प्रोटोकॉल कर्मचारी सुरक्षा को प्राथमिकता देता है।",
        },
        {
            "q": f"Which personal protective equipment is mandatory while performing {module_title} duties?",
            "q_hi": f"{module_title} कर्तव्यों को करते समय कौन सा व्यक्तिगत सुरक्षा उपकरण अनिवार्य है?",
            "opts": [
                ("The PPE specified in the departmental SOP for that task", "उस कार्य के लिए विभागीय SOP में निर्दिष्ट पीपीई", True),
                ("No PPE is required for non-teaching staff", "गैर-शिक्षण कर्मचारियों के लिए कोई पीपीई आवश्यक नहीं है", False),
                ("PPE is optional if the task takes under five minutes", "यदि कार्य पाँच मिनट से कम का हो तो पीपीई वैकल्पिक है", False),
                ("Only a uniform is required", "केवल वर्दी आवश्यक है", False),
            ],
            "exp": "PPE requirements are defined per task in the departmental SOP and are not optional.",
            "exp_hi": "पीपीई की आवश्यकताएँ विभागीय SOP में प्रति कार्य परिभाषित हैं और वैकल्पिक नहीं हैं।",
        },
        {
            "q": f"How should a shift handover be recorded for {module_title}?",
            "q_hi": f"{module_title} के लिए शिफ्ट हैंडओवर कैसे दर्ज किया जाना चाहिए?",
            "opts": [
                ("Verbally, with no written record", "मौखिक रूप से, बिना किसी लिखित रिकॉर्ड के", False),
                ("In the handover register, noting pending items, anomalies, and the outgoing Employee ID", "हैंडओवर रजिस्टर में, लंबित कार्य, विसंगतियाँ और जावक कर्मचारी आईडी दर्ज करके", True),
                ("By leaving a note on any available surface", "किसी भी उपलब्ध सतह पर नोट छोड़कर", False),
                ("Handover is not required between shifts", "शिफ्टों के बीच हैंडओवर आवश्यक नहीं है", False),
            ],
            "exp": "A written handover preserves continuity and accountability across shifts.",
            "exp_hi": "लिखित हैंडओवर शिफ्टों के बीच निरंतरता और जवाबदेही बनाए रखता है।",
        },
        {
            "q": f"What should staff do if they have not been trained on a {module_title} task?",
            "q_hi": f"यदि कर्मचारी {module_title} कार्य में प्रशिक्षित नहीं हैं तो उन्हें क्या करना चाहिए?",
            "opts": [
                ("Attempt the task and learn while doing it", "कार्य करने का प्रयास करें और करते-करते सीखें", False),
                ("Ask a colleague to sign off on their behalf", "किसी सहकर्मी से उनकी ओर से हस्ताक्षर करने के लिए कहें", False),
                ("Decline the task and request training or authorisation from the HOD", "कार्य से मना करें और विभागाध्यक्ष से प्रशिक्षण या प्राधिकरण का अनुरोध करें", True),
                ("Proceed if a supervisor is not present", "यदि पर्यवेक्षक उपस्थित न हो तो आगे बढ़ें", False),
            ],
            "exp": "Only trained and authorised staff may perform the task; escalate instead of improvising.",
            "exp_hi": "केवल प्रशिक्षित और अधिकृत कर्मचारी ही कार्य कर सकते हैं; अनुमान लगाने के बजाय रिपोर्ट करें।",
        },
        {
            "q": f"Where should completed {module_title} records be retained, and for how long?",
            "q_hi": f"पूर्ण किए गए {module_title} रिकॉर्ड कहाँ और कितने समय तक रखे जाने चाहिए?",
            "opts": [
                ("In the departmental file or system of record, per the retention period in the SOP", "विभागीय फ़ाइल या रिकॉर्ड प्रणाली में, SOP में दी गई अवधि के अनुसार", True),
                ("Discarded once the shift ends", "शिफ्ट समाप्त होने पर नष्ट कर दें", False),
                ("Kept only by the individual staff member", "केवल संबंधित कर्मचारी अपने पास रखे", False),
                ("Emailed to an external address", "बाहरी ईमेल पते पर भेजें", False),
            ],
            "exp": "Retention supports institutional audits and compliance verification.",
            "exp_hi": "रिकॉर्ड रखरखाव संस्थागत ऑडिट और अनुपालन सत्यापन में सहायक है।",
        },
        {
            "q": f"Which action best reflects correct escalation for an unresolved {module_title} issue?",
            "q_hi": f"अनसुलझे {module_title} मुद्दे के लिए सही एस्केलेशन कौन सा है?",
            "opts": [
                ("Wait for the next inspection cycle", "अगले निरीक्षण चक्र की प्रतीक्षा करें", False),
                ("Raise it with the HOD in writing, with the log reference, and track it to closure", "लॉग संदर्भ के साथ विभागाध्यक्ष को लिखित रूप में सूचित करें और समाधान तक ट्रैक करें", True),
                ("Post it in a staff group chat", "स्टाफ ग्रुप चैट में पोस्ट करें", False),
                ("Close it if it has not recurred within a week", "यदि एक सप्ताह में दोबारा न हो तो बंद कर दें", False),
            ],
            "exp": "Written escalation with a log reference keeps the issue auditable until it is closed.",
            "exp_hi": "लॉग संदर्भ के साथ लिखित एस्केलेशन मुद्दे को समाधान तक ऑडिट-योग्य रखता है।",
        },
    ]

    wanted = min(max(1, num_questions), FALLBACK_POOL_SIZE)
    questions = []
    for template in templates[:wanted]:
        questions.append({
            'question': template['q'],
            'question_hi': template['q_hi'],
            'explanation': template['exp'],
            'explanation_hi': template['exp_hi'],
            'options': [
                {'text': text, 'text_hi': text_hi, 'is_correct': is_correct}
                for text, text_hi, is_correct in template['opts']
            ],
        })
    return questions
