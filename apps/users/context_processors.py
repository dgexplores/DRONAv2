from django.conf import settings


def language_context(request):
    """
    Provides UI language (English/Hindi) dictionary to all templates.
    """
    lang = 'hi' if getattr(request.user, 'preferred_language', 'en') == 'hi' else 'en'
    return {
        'UI_LANG': lang,
        'is_hindi': lang == 'hi',
        'is_debug': settings.DEBUG,
    }
