from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("services/", views.services, name="services"),
    path("service/development/", views.webDev, name="webDev"),
    path("service/vision-ai/", views.compVision, name="compVision"),
    path("service/ai-services/", views.aiChat, name="aiChat"),
    path("service/nlpa/", views.gis, name="gis"),
    path("contact/", views.contact, name="contact"),
    path("blogs/", views.blogs, name="blogs"),
    path("about/", views.about, name="about"),
    path("gallery/", views.gallery, name="gallery"),
    path("careers/", views.careers, name="careers"),
    path('apply-job/<int:job_id>/', views.apply_job, name='apply_job'),
    path('api/contact-transcribe/', views.contact_transcribe_audio, name='contact_transcribe_audio'),
    
    path("chat/", views.chatbot_response, name="chatbot_response"),
    
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('employee/', views.employee, name='employee'),
    path('employee/dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('employee/rsa-model/', views.rsa_model, name='rsa_model'),
    path('api/validate-employee/', views.validate_employee_api, name='validate_employee_api'),
    path('attendance/generate/', views.generate_attendance_link, name='generate_attendance_link'),    
    
    path('create/', views.create_blog, name='create_blog'),
    path('resource/', views.resources, name='resources'),
    path('blogs/<slug:slug>/', views.blog_detail, name='blog_detail'),
]
