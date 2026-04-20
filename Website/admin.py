from django.contrib import admin
from .models import Blog, Job, JobApplication

@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'published_date')
    search_fields = ('title', 'category')

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'location', 'experience', 'is_active')
    search_fields = ('title', 'location')
    list_filter = ('is_active', 'location')

@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'job', 'email', 'phone', 'created_at')
    search_fields = ('name', 'email', 'job__title')
    list_filter = ('job', 'created_at')
