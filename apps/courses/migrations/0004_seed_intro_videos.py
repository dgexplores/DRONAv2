from django.db import migrations


def seed_intro_course(apps, schema_editor):
    Category = apps.get_model('courses', 'Category')
    Course = apps.get_model('courses', 'Course')
    Module = apps.get_model('courses', 'Module')
    Lesson = apps.get_model('courses', 'Lesson')

    category, _ = Category.objects.get_or_create(
        name='Introduction',
        defaults={
            'name_hi': 'परिचय',
            'icon': 'play-circle',
            'description': 'Welcome videos for the Drona learning platform.',
        },
    )

    course, created = Course.objects.get_or_create(
        title='Platform Introduction',
        defaults={
            'title_hi': 'प्लेटफ़ॉर्म परिचय',
            'description': 'Watch these short videos to get familiar with the Drona learning platform and how it works.',
            'description_hi': 'ड्रोना लर्निंग प्लेटफ़ॉर्म से परिचित होने के लिए ये छोटे वीडियो देखें।',
            'category': category,
            'is_mandatory': False,
        },
    )

    module, _ = Module.objects.get_or_create(
        course=course,
        order=1,
        defaults={'title': 'Getting Started', 'title_hi': 'शुरुआत'},
    )

    Lesson.objects.get_or_create(
        module=module,
        title='Welcome Overview',
        defaults={
            'title_hi': 'स्वागत अवलोकन',
            'lesson_type': 'video',
            'video_url': '/media/intro/intro_overview.mp4',
            'duration_minutes': 2,
            'order': 1,
        },
    )

    Lesson.objects.get_or_create(
        module=module,
        title='Platform Tour',
        defaults={
            'title_hi': 'प्लेटफ़ॉर्म टूर',
            'lesson_type': 'video',
            'video_url': '/media/intro/intro_tour.mp4',
            'duration_minutes': 3,
            'order': 2,
        },
    )


def unseed_intro_course(apps, schema_editor):
    Lesson = apps.get_model('courses', 'Lesson')
    Module = apps.get_model('courses', 'Module')
    Course = apps.get_model('courses', 'Course')
    Category = apps.get_model('courses', 'Category')

    for course in Course.objects.filter(title='Platform Introduction'):
        for module in course.modules.all():
            module.lessons.all().delete()
        course.delete()
    Category.objects.filter(name='Introduction').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0003_enrollment_watch_seconds_trainingsession'),
    ]

    operations = [
        migrations.RunPython(seed_intro_course, unseed_intro_course),
    ]
