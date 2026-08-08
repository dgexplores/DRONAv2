from django.conf import settings


def language_context(request):
    """
    Provides UI language (English/Hindi) dictionary to all templates.
    Priority: session override, then user preference (if authenticated), then en.
    """
    lang = request.session.get('django_language')
    if lang is None:
        lang = getattr(request.user, 'preferred_language', None)
    lang = 'hi' if lang == 'hi' else 'en'
    return {
        'UI_LANG': lang,
        'is_hindi': lang == 'hi',
        'is_debug': settings.DEBUG,
    }
