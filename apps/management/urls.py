from django.urls import path
from apps.management import views

urlpatterns = [
    path('', views.console_home, name='mgmt_home'),
    path('courses/', views.course_list, name='mgmt_course_list'),
    path('courses/new/', views.course_create, name='mgmt_course_create'),
    path('courses/<int:course_id>/', views.course_detail, name='mgmt_course_detail'),
    path('courses/<int:course_id>/edit/', views.course_edit, name='mgmt_course_edit'),
    path('courses/<int:course_id>/delete/', views.course_delete, name='mgmt_course_delete'),
    path('modules/<int:module_id>/edit/', views.module_edit, name='mgmt_module_edit'),
    path('modules/<int:module_id>/delete/', views.module_delete, name='mgmt_module_delete'),
    path('modules/<int:module_id>/lessons/new/', views.lesson_create, name='mgmt_lesson_create'),
    path('lessons/<int:lesson_id>/edit/', views.lesson_edit, name='mgmt_lesson_edit'),
    path('lessons/<int:lesson_id>/delete/', views.lesson_delete, name='mgmt_lesson_delete'),
    path('enroll/', views.bulk_enroll, name='mgmt_bulk_enroll'),
    path('sessions/', views.session_list, name='mgmt_session_list'),
    path('sessions/new/', views.session_create, name='mgmt_session_create'),
    path('sessions/<int:session_id>/edit/', views.session_edit, name='mgmt_session_edit'),
    path('sessions/<int:session_id>/delete/', views.session_delete, name='mgmt_session_delete'),
    path('staff/import/', views.import_staff, name='mgmt_staff_import'),
]
