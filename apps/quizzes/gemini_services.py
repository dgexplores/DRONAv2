import os
import json
import logging
from google import genai
from google.genai import types
from apps.quizzes.models import Quiz, Question, Choice

logger = logging.getLogger(__name__)

# Current stable models (newest first). gemini-2.5-flash is deprecated for new users.
GEMINI_MODELS = [
    'gemini-3.5-flash',
    'gemini-3.1-flash-lite',
    'gemini-3-flash-preview',
    'gemini-2.5-flash',
]

def generate_quiz_from_text(module, text_content, num_questions=5):
    """
    Generates a Quiz with Questions and Choices using Gemini API or smart fallback.
    """
    quiz, _ = Quiz.objects.get_or_create(
        module=module,
        defaults={
            'title': f"Assessment: {module.title}",
            'title_hi': f"मूल्यांकन: {module.title_hi or module.title}",
            'passing_score': 70
        }
    )
    
    # Clear existing questions for re-generation
    quiz.questions.all().delete()

    api_key = os.environ.get("GEMINI_API_KEY")
    quiz_data = None

    if api_key:
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"""
You are an expert trainer for non-teaching staff at Shri Ram Murti Smarak (SRMS) Group of Institutions.
Based on the following Standard Operating Procedure (SOP) text, generate {num_questions} multiple-choice assessment questions.

SOP Content:
\"\"\"
{text_content[:4000]}
\"\"\"

Requirements:
Return ONLY a JSON array of objects with this exact format:
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
            response = None
            for model in GEMINI_MODELS:
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json"
                        )
                    )
                    break
                except Exception as model_err:
                    logger.warning(f"Model {model} failed: {model_err}")
                    continue

            if response is None:
                raise RuntimeError("All Gemini models failed.")

            quiz_data = json.loads(response.text)
        except Exception as e:
            logger.error(f"Gemini API error: {e}. Falling back to rule-based quiz generation.")

    if not quiz_data:
        # Smart rule-based contextual generator fallback
        quiz_data = _generate_fallback_questions(module.title, text_content, num_questions)

    # Save to Database
    for q_idx, item in enumerate(quiz_data, 1):
        question = Question.objects.create(
            quiz=quiz,
            text=item.get("question", f"Question {q_idx} regarding {module.title}"),
            text_hi=item.get("question_hi", f"प्रश्न {q_idx} ({module.title})"),
            explanation=item.get("explanation", "Correct according to SRMS SOP standard."),
            explanation_hi=item.get("explanation_hi", "एसआरएमएस एसओपी मानक के अनुसार सही।"),
            points=1
        )
        for opt in item.get("options", []):
            Choice.objects.create(
                question=question,
                text=opt.get("text", "Option"),
                text_hi=opt.get("text_hi", "विकल्प"),
                is_correct=opt.get("is_correct", False)
            )

    return quiz

def _generate_fallback_questions(module_title, text_content, num_questions):
    """
    Generates structured fallback questions based on module subject matter.
    """
    questions = []
    
    # Generic templates tailored to campus non-teaching staff SOPs
    sample_templates = [
        {
            "q": f"What is the primary objective of the {module_title} protocol at SRMS campus?",
            "q_hi": f"एसआरएमएस परिसर में {module_title} प्रोटोकॉल का मुख्य उद्देश्य क्या है?",
            "opts": [
                ("To ensure safety, compliance, and standard operational accuracy", "सुरक्षा, अनुपालन और मानक संचालन सटीकता सुनिश्चित करना", True),
                ("To reduce daily documentation procedures", "दैनिक दस्तावेज़ीकरण प्रक्रियाओं को कम करना", False),
                ("To bypass mandatory institutional reporting", "अनिवार्य संस्थागत रिपोर्टिंग को बायपास करना", False),
                ("None of the above", "उपरोक्त में से कोई नहीं", False)
            ],
            "exp": "SOPs are designed to ensure safety and standard operating compliance across all departments.",
            "exp_hi": "SOPs सभी विभागों में सुरक्षा और मानक संचालन अनुपालन सुनिश्चित करने के लिए डिज़ाइन किए गए हैं।"
        },
        {
            "q": f"In case of an operational anomaly during {module_title}, what is the first action staff should take?",
            "q_hi": f"{module_title} के दौरान परिचालन विसंगति के मामले में, कर्मचारियों को पहला क्या कदम उठाना चाहिए?",
            "opts": [
                ("Ignore the anomaly if minor", "यदि मामूली हो तो विसंगति को नज़रअंदाज़ करें", False),
                ("Immediately notify the Departmental HOD / Trainer and record in maintenance log", "तुरंत विभागाध्यक्ष/ट्रेनर को सूचित करें और रजिस्टर में दर्ज करें", True),
                ("Attempt unauthorized equipment modification", "अनधिकृत उपकरण संशोधन का प्रयास करें", False),
                ("Leave the workspace unattended", "कार्यस्थल को लावारिस छोड़ दें", False)
            ],
            "exp": "Immediate escalation and logging prevents equipment damage and ensures safety.",
            "exp_hi": "तत्काल रिपोर्टिंग और लॉगिंग से नुकसान से बचा जा सकता है।"
        },
        {
            "q": f"How frequently must compliance and maintenance checklists be reviewed for {module_title}?",
            "q_hi": f"{module_title} के लिए अनुपालन और रखरखाव जाँच सूचियों की समीक्षा कितनी बार की जानी चाहिए?",
            "opts": [
                ("Daily / per-shift basis prior to operations", "संचालन से पहले दैनिक / प्रति शिफ्ट के आधार पर", True),
                ("Once every academic year", "प्रत्येक शैक्षणिक वर्ष में एक बार", False),
                ("Only when requested by external auditors", "केवल बाहरी लेखा परीक्षकों द्वारा अनुरोध किए जाने पर", False),
                ("Never", "कभी नहीं", False)
            ],
            "exp": "Shift-wise inspection ensures operational readiness.",
            "exp_hi": "शिफ्ट-वार निरीक्षण परिचालन तत्परता सुनिश्चित करता है।"
        },
        {
            "q": f"What documentation is required after completing tasks under {module_title}?",
            "q_hi": f"{module_title} के तहत कार्यों को पूरा करने के बाद किस दस्तावेज़ीकरण की आवश्यकता होती है?",
            "opts": [
                ("No log is required", "किसी लॉग की आवश्यकता नहीं है", False),
                ("Updating the digital / physical departmental register with timestamp and Employee ID", "समय और कर्मचारी आईडी के साथ रजिस्टर को अपडेट करना", True),
                ("Informal verbal communication only", "केवल अनौपचारिक मौखिक संचार", False),
                ("Deleting session logs", "सत्र लॉग मिटाना", False)
            ],
            "exp": "Proper logging maintains institutional audit trails and accountability.",
            "exp_hi": "उचित लॉगिंग संस्थागत जवाबदेही बनाए रखती है।"
        },
        {
            "q": f"Which emergency safety protocol applies to {module_title} at SRMS campus?",
            "q_hi": f"एसआरएमएस परिसर में {module_title} पर कौन सा आपातकालीन सुरक्षा प्रोटोकॉल लागू होता है?",
            "opts": [
                ("Press emergency stop/isolation, evacuate area, and contact Security/HOD", "इमरजेंसी स्टॉप दबाएं, क्षेत्र खाली करें, और सुरक्षा/विभागाध्यक्ष से संपर्क करें", True),
                ("Continue working until shift ends", "शिफ्ट खत्म होने तक काम जारी रखें", False),
                ("Try to repair high-voltage or chemical hazards without PPE", "बिना पीपीई के उच्च वोल्टेज या रासायनिक खतरों को ठीक करने का प्रयास करें", False),
                ("Lock the facility doors from inside", "अंदर से परिसर के दरवाजे लॉक करें", False)
            ],
            "exp": "Standard emergency protocol prioritizes staff safety and swift evacuation.",
            "exp_hi": "मानक आपातकालीन प्रोटोकॉल कर्मचारी सुरक्षा को प्राथमिकता देता है।"
        }
    ]

    for t in sample_templates[:num_questions]:
        options = []
        for opt_en, opt_hi, is_corr in t["opts"]:
            options.append({"text": opt_en, "text_hi": opt_hi, "is_correct": is_corr})
        questions.append({
            "question": t["q"],
            "question_hi": t["q_hi"],
            "explanation": t["exp"],
            "explanation_hi": t["exp_hi"],
            "options": options
        })

    return questions
