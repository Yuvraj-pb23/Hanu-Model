from django.db import models
from django.utils.text import slugify

class Blog(models.Model):
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=50, default="Insight")
    slug = models.SlugField(unique=True, blank=True)
    
    short_description = models.TextField()
    content = models.TextField()
    cover_image = models.ImageField(upload_to='blogs/')
    
    
    sub_title1 = models.CharField(max_length=200, blank=True, null=True)
    sub_content1 = models.TextField(blank=True, null=True)
    image1 = models.ImageField(upload_to='blogs/', blank=True, null=True)
    
    sub_title2 = models.CharField(max_length=200, blank=True, null=True)
    sub_content2 = models.TextField(blank=True, null=True)
    image2 = models.ImageField(upload_to='blogs/', blank=True, null=True)
    
    sub_title3 = models.CharField(max_length=200, blank=True, null=True)
    sub_content3 = models.TextField(blank=True, null=True)
    image3 = models.ImageField(upload_to='blogs/', blank=True, null=True)
    
    sub_title4 = models.CharField(max_length=200, blank=True, null=True)
    sub_content4 = models.TextField(blank=True, null=True)
        
    
    published_date = models.DateField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Job(models.Model):
    title = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    experience = models.CharField(max_length=100)
    description = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

class JobApplication(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    resume = models.FileField(upload_to='resumes/')
    cover_letter = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)