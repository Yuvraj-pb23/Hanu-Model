from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.contrib import messages
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.text import slugify
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Blog
import json
import os
import hashlib
import hmac
from datetime import datetime
from pathlib import Path
from django.core.mail import EmailMessage
from .models import Job, JobApplication
import requests
import subprocess
import re
import logging
import tempfile
from captcha.models import CaptchaStore
from captcha.helpers import captcha_image_url
import google.generativeai as genai
import PIL.Image
import pandas as pd
import time

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Whisper / Translation singletons — one instance shared across all requests.
# apps.py pre-warms these at startup so requests never pay the load penalty.
# ---------------------------------------------------------------------------
_transcription_engine = None
_translation_engine = None


def _get_transcription_engine():
    global _transcription_engine
    if _transcription_engine is None:
        from TranscriberBackend.transcription import TranscriptionEngine
        _transcription_engine = TranscriptionEngine("large-v3-turbo")
        _transcription_engine.load_model()  # explicit warm-up
    return _transcription_engine


def _get_translation_engine():
    global _translation_engine
    if _translation_engine is None:
        from TranscriberBackend.translation import TranslationEngine
        _translation_engine = TranslationEngine()
    return _translation_engine


# Views to serve JSON data files
# def serve_surveyors_data(request):
#     json_path = Path(settings.BASE_DIR) / "surveyors_data.json"
#     with open(json_path, 'r', encoding='utf-8') as f:
#         data = json.load(f)
#     return JsonResponse(data, safe=False)

# def serve_employees_data(request):
#     json_path = Path(settings.BASE_DIR) / "employees_data.json"
#     with open(json_path, 'r', encoding='utf-8') as f:
#         data = json.load(f)
#     return JsonResponse(data, safe=False)

def home(request):
    states = [
        ("Jammu & Kashmir", "blue"),
        ("Himachal Pradesh", "teal"),
        ("Punjab", "blue"),
        ("Haryana", "teal"),
        ("Delhi", "blue"),
        ("Uttar Pradesh", "teal"),
        ("Bihar", "blue"),
        ("Jharkhand", "teal"),
        ("West Bengal", "blue"),
        ("Assam", "teal"),
        ("Meghalaya", "blue"),
        ("Rajasthan", "teal"),
        ("Madhya Pradesh", "blue"),
        ("Chhattisgarh", "teal"),
        ("Odisha", "blue"),
        ("Gujarat", "teal"),
        ("Maharashtra", "blue"),
        ("Telangana", "teal"),
        ("Andhra Pradesh", "blue"),
        ("Karnataka", "teal"),
        ("Kerala", "blue"),
        ("Tamil Nadu", "teal"),
    ]
    return render(request, "home.html", {"states": states})


def services(request):
    return render(request, "services.html")


def webDev(request):
    return render(request, "Services/web.html")


def compVision(request):
    return render(request, "Services/comp.html")


def aiChat(request):
    return render(request, "Services/ai-chat.html")


def gis(request):
    return render(request, "Services/gis.html")


def blogs(request):
    blogs_list = Blog.objects.all().order_by("-published_date")
    
    # Detect mobile device from user agent
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    is_mobile = any(device in user_agent for device in ['mobile', 'android', 'iphone', 'ipad', 'ipod', 'blackberry', 'windows phone'])
    
    # Use 8 blogs per page for mobile (4 rows × 2), 9 for desktop (3 rows × 3)
    items_per_page = 8 if is_mobile else 9
    paginator = Paginator(blogs_list, items_per_page)
    
    page = request.GET.get('page')
    try:
        blogs = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        blogs = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page of results
        blogs = paginator.page(paginator.num_pages)
    
    return render(request, "blogs.html", {"blogs": blogs})

def about(request):
    return render(request, "about.html")


def gallery(request):
    # Get the path to the Gallery/Images folder
    gallery_path = os.path.join(
        settings.BASE_DIR, "Website", "Static", "Media", "Gallery", "Images"
    )

    # Get all image files from the folder
    images = []
    if os.path.exists(gallery_path):
        for filename in os.listdir(gallery_path):
            if filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                # Create the URL path for the image
                image_url = f"Media/Gallery/Images/{filename}"
                images.append(
                    {
                        "url": image_url,
                        "name": os.path.splitext(filename)[
                            0
                        ],  # filename without extension
                    }
                )

    return render(request, "gallery.html", {"images": images})


def careers(request):
    return render(request, "careers.html")

def generate_attendance_link(request):
    """
    Executes generate_gated_token.py and redirects the user to the generated URL.
    """
    try:
        # Run the script and capture output
        script_path = os.path.join(settings.BASE_DIR, 'generate_gated_token.py')
        result = subprocess.run(['python3', script_path], capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Script execution failed: {result.stderr}")
            messages.error(request, "Failed to generate attendance link.")
            return redirect('employee')

        # Find the URL in the output
        # Look for a line starting with http
        match = re.search(r'http[s]?://[^\s]+', result.stdout)
        if match:
            target_url = match.group(0)
            return redirect(target_url)
        else:
            logger.error(f"Could not find URL in script output: {result.stdout}")
            messages.error(request, "Attendance link not found in output.")
            return redirect('employee')
            
    except Exception as e:
        logger.error(f"Error generating attendance link: {e}")
        messages.error(request, "An unexpected error occurred.")
        return redirect('employee_dashboard')



def employee(request):
    """
    Renders the employee entry page.
    If already verified, redirects to the dashboard.
    """
    return render(request, "employee.html")


def employee_dashboard(request):
    """
    Renders the employee dashboard.
    """
    is_verified = request.session.get('is_verified_employee', False)
    return render(request, "dashboard.html", {"is_verified": is_verified})


def rsa_model(request):
    """
    Renders the RSA Model tool.
    """
    return render(request, "rsa_model.html")


STATIC_USER = {
    "email": "hanuai@blog.com",
    "password": "!@#$%^&*()",  # keep it safe; for prod use env vars
    "role": "blogger",
}
# Superuser credentials for testing:
# cpm50 - name
# cpm50 - password

def blog_detail(request, slug):
    blog = get_object_or_404(Blog, slug=slug)
    return render(request, "blog_page.html", {"blog": blog})


def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()

        if email == STATIC_USER["email"] and password == STATIC_USER["password"]:
            # Successful login -> set session
            request.session["is_authenticated_simple"] = True
            request.session["user_email_simple"] = STATIC_USER["email"]
            request.session["user_role_simple"] = STATIC_USER["role"]

            # redirect to 'next' if exists, else to admin_hub URL
            next_url = request.GET.get("next") or reverse("admin_hub")
            return redirect(next_url)
        else:
            messages.error(request, "Invalid email or password.")

    # If already logged in, forward to admin_hub
    if request.session.get("is_authenticated_simple"):
        return redirect(reverse("admin_hub"))

    return render(request, "login.html")


def logout_view(request):
    """
    Clear all session login data and redirect to employee entry page.
    """
    request.session.pop("is_authenticated_simple", None)
    request.session.pop("user_email_simple", None)
    request.session.pop("user_role_simple", None)
    request.session.pop("is_verified_employee", None)
    request.session.pop("verified_mobile", None)
    return redirect("login")


def _require_blogger_session(request):
    """
    Helper: returns (ok: bool, redirect_response/or_None)
    """
    if not request.session.get("is_authenticated_simple"):
        # Not logged in -> redirect to login with next param
        return False, redirect(f"/login/?next=/admin-hub/")
    if request.session.get("user_role_simple") != "blogger":
        # Logged in but not blogger -> forbidden or redirect as you wish
        return False, HttpResponseForbidden("Access denied.")
    return True, None

# def contact(request):
#     if request.method == 'POST':
#         # Capture form data
#         name = request.POST.get('name')
#         email = request.POST.get('email')
#         subject = request.POST.get('subject')
#         message = request.POST.get('message')

#         # Construct the email content
#         email_content = f"Name: {name}\nEmail: {email}\nSubject: {subject}\n\nMessage:\n{message}"

#         # Send the mail to the mentioned address
#         email_to_send = EmailMessage(
#             subject=f"Contact Form: {subject}",
#             body=email_content,
#             from_email=settings.DEFAULT_FROM_EMAIL,
#             to=['info@hanuai.com'], 
#         )
#         email_to_send.send()

#         messages.success(request, "Thank you! Your message has been sent successfully. We will get back to you soon.")

#         return redirect('contact')

#     return render(request, 'contact.html')


def contact(request):
    if request.method == "POST":
        #  # 🔹 Get recaptcha token
        # token = request.POST.get("g-recaptcha-response")

        # secret_key = "6LeL6IAsAAAAAKZj6mZX-SI6fz87pdqJ_ZUJ5E6L"

        # data = {
        #     "secret": secret_key,
        #     "response": token
        # }

        # r = requests.post(
        #     "https://www.google.com/recaptcha/api/siteverify",
        #     data=data
        # )

        # result = r.json()

        # # 🔹 If captcha fails
        # if not result.get("success"):
        #     messages.error(request, "reCAPTCHA verification failed.", extra_tags="contact")
        #     return redirect("contact")
        
        user_captcha = request.POST.get("captcha", "").strip()
        captcha_key = request.POST.get("captcha_key")

        # Remove expired captchas first
        CaptchaStore.remove_expired()

        # Check if captcha is valid (case-insensitive)
        if not CaptchaStore.objects.filter(hashkey=captcha_key, response=user_captcha.lower()).exists():
            messages.error(request, "Invalid CAPTCHA. Please try again.", extra_tags="contact")
            return redirect("contact")
        
        # Delete used captcha to prevent reuse
        CaptchaStore.objects.filter(hashkey=captcha_key).delete()
        
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        subject = request.POST.get("subject", "").strip()
        message = request.POST.get("message", "").strip()
        voice_message_text = request.POST.get("voice_message_text", "").strip()
        
        # Determine which form was submitted
        is_voice_form = bool(voice_message_text)
        form_type = "voice" if is_voice_form else "contact"
        
        # Use voice message text if available, otherwise use regular message
        final_message = voice_message_text if is_voice_form else message

        # Extra safety check
        if not name or not email or not final_message:
            messages.error(request, "All required fields must be filled.", extra_tags="contact")
            return redirect("contact")

        email_content = (
            f"New Contact Form Submission\n\n"
            f"Name: {name}\n"
            f"Email: {email}\n"
            f"Subject: {subject if subject else 'Voice Message'}\n\n"
            f"Message:\n{final_message}"
        )

        try:
            email_message = EmailMessage(
                subject=f"Contact Form: {subject if subject else 'Voice Message'}",
                body=email_content,
                from_email=settings.EMAIL_HOST_USER,  # safer than DEFAULT_FROM_EMAIL
                to=["info@hanuai.com","mohneesh.hanuai@gmail.com","prerna@hanu.ai","Rahul@hanu.ai","manav@hanu.ai","mohneesh@hanu.ai"],
                

                reply_to=[email],
            )
            email_message.send(fail_silently=False)

        except Exception as e:
            logger.error(f"CONTACT EMAIL FAILED: {e}")
            messages.error(
                request,
                "Sorry, something went wrong while sending your message. Please try again later.",
                extra_tags="contact"
            )
            return redirect(f"/contact/?form={form_type}&status=error")

        messages.success(
            request,
            "Thank you! Your message has been sent successfully. We will get back to you soon.",
            extra_tags="contact"
        )
        return redirect(f"/contact/?form={form_type}&status=success")

    captcha = CaptchaStore.generate_key()
    captcha_url = captcha_image_url(captcha)

    return render(request, "contact.html", {
        "captcha_key": captcha,
        "captcha_image": captcha_url
        })


def verify_recaptcha(token):
    secret_key = "6LeL6IAsAAAAAKZj6mZX-SI6fz87pdqJ_ZUJ5E6L"

    url = "https://www.google.com/recaptcha/api/siteverify"

    data = {
        "secret": secret_key,
        "response": token
    }

    response = requests.post(url, data=data)
    result = response.json()

    return result.get("success", False)

@csrf_exempt
def contact_transcribe_audio(request):
    """
    Receives an audio file (WebM/WAV) from the contact form,
    processes it natively using TranscriberBackend,
    and returns the english translation.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)

    audio_file = request.FILES.get('audio')
    if not audio_file:
        return JsonResponse({'success': False, 'message': 'No audio file provided'}, status=400)

    try:
        from TranscriberBackend.utils import convert_to_wav

        # Reuse the module-level singletons — no model reload between requests
        transcriber = _get_transcription_engine()
        translation_engine = _get_translation_engine()

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, audio_file.name)
            with open(input_path, 'wb') as f:
                f.write(audio_file.read())

            wav_path = os.path.join(temp_dir, "audio.wav")
            if not convert_to_wav(input_path, wav_path, 16000):
                return JsonResponse({'success': False, 'message': "Audio conversion failed"}, status=500)

            # beam_size=1 is ~4x faster than beam_size=5 on CPU with minimal
            # accuracy loss — fine for short contact-form voice messages.
            result = transcriber.transcribe(
                wav_path,
                language=None,
                word_timestamps=False,
                beam_size=1,
                vad_filter=True,
            )

            transcript = result.get("text", "").strip()
            detected_lang = result.get("language", "auto")
            transcribed_text = ""

            if transcript:
                translation_result = translation_engine.translate_text(
                    transcript,
                    target_lang="en",
                    source_lang=detected_lang,
                )
                transcribed_text = translation_result.get("translated_text", transcript)

            return JsonResponse({'success': True, 'text': transcribed_text, 'language': detected_lang})

    except Exception as e:
        logger.error(f"Error during native audio transcription: {e}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


def apply_job(request, job_id):
    if request.method == "POST":
        job = get_object_or_404(Job, id=job_id)
        
        name = request.POST.get("name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")
        resume = request.FILES.get("resume")
        cover_letter = request.POST.get("cover_letter")

        # 1. Basic Validation
        if not all([name, email, phone, resume]):
            return JsonResponse({"success": False, "message": "Missing required fields."})

        # 2. File size validation (e.g., limit to 5MB)
        if resume.size > 5 * 1024 * 1024:
            return JsonResponse({"success": False, "message": "File too large. Max 5MB."})

        try:
            # 3. Save to DB first
            application = JobApplication.objects.create(
                job=job, name=name, email=email, 
                phone=phone, resume=resume, cover_letter=cover_letter
            )

            # 4. Prepare Email
            admin_email = EmailMessage(
                subject=f"New Application: {job.title}",
                body=f"Candidate: {name}\nEmail: {email}\nPhone: {phone}\nJob: {job.title}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.ADMIN_EMAIL],
            )

            if resume:
                # IMPORTANT: Reset file pointer to the beginning
                resume.seek(0) 
                admin_email.attach(resume.name, resume.read(), resume.content_type)
            
            admin_email.send()
            return JsonResponse({"success": True, "message": "Applied successfully!"})

        except Exception as e:
            # Log the error for debugging
            print(f"Error: {e}")
            return JsonResponse({"success": False, "message": "An error occurred during submission."})

    return JsonResponse({"success": False, "message": "Invalid request method."})

def create_blog(request):
    """
    Your existing create_blog logic, protected by session-based simple auth.
    """
    ok, resp = _require_blogger_session(request)
    if not ok:
        return resp

    message = None
    blog_to_edit = None

    if request.method == "POST":
        if "delete_id" in request.POST:
            Blog.objects.filter(id=request.POST.get("delete_id")).delete()
            message = "🗑️ Blog deleted successfully."
        elif "edit_id" in request.POST:
            blog_to_edit = get_object_or_404(Blog, id=request.POST.get("edit_id"))
        elif "update_id" in request.POST:
            blog = get_object_or_404(Blog, id=request.POST.get("update_id"))

            # Update normal fields
            text_fields = [
                "title",
                "category",
                "content",
                "sub_title1",
                "sub_content1",
                "sub_title2",
                "sub_content2",
                "sub_title3",
                "sub_content3",
                "sub_title4",
                "sub_content4",
            ]
            for field in text_fields:
                if field in request.POST:
                    setattr(blog, field, request.POST.get(field))
            # Handle short_description: set to empty string if not present
            if "short_description" in request.POST:
                blog.short_description = request.POST.get("short_description")
            else:
                blog.short_description = ""

            # Update images only if new file uploaded
            image_fields = ["cover_image", "image1", "image2", "image3"]
            for img in image_fields:
                if img in request.FILES:
                    setattr(blog, img, request.FILES[img])

            blog.save()
            message = "✅ Blog updated successfully."

        else:
            fields = [
                "title",
                "category",
                "content",
                "sub_title1",
                "sub_content1",
                "sub_title2",
                "sub_content2",
                "sub_title3",
                "sub_content3",
                "sub_title4",
                "sub_content4",
            ]
            blog = Blog()
            for f in fields:
                setattr(blog, f, request.POST.get(f))
            # Handle short_description: set to empty string since not in form
            blog.short_description = ""
            for img in ["cover_image", "image1", "image2", "image3"]:
                setattr(blog, img, request.FILES.get(img))
            if blog.title and blog.cover_image:
                blog.slug = slugify(blog.title)
                blog.save()
                message = "✅ Blog created successfully."
            else:
                message = "⚠️ Title and cover image are required."

    blogs = Blog.objects.all().order_by("-published_date")
    return render(
        request,
        "blog_create.html",
        {"message": message, "blogs": blogs, "blog_to_edit": blog_to_edit},
    )

def admin_hub(request):
    ok, resp = _require_blogger_session(request)
    if not ok:
        return resp
    return render(request, "admin_hub.html")

def upload_gallery(request):
    ok, resp = _require_blogger_session(request)
    if not ok:
        return resp
        
    gallery_path = os.path.join(settings.BASE_DIR, "Website", "Static", "Media", "Gallery", "Images")
    os.makedirs(gallery_path, exist_ok=True)
    message = None
    
    if request.method == "POST":
        if "delete_image" in request.POST:
            image_name = request.POST.get("delete_image")
            clean_name = os.path.basename(image_name)
            file_path = os.path.join(gallery_path, clean_name)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    message = f"🗑️ Deleted {clean_name}"
                except Exception as e:
                    message = f"❌ Error deleting file: {e}"
                    
        elif request.FILES.getlist("gallery_images"):
            images = request.FILES.getlist("gallery_images")
            uploaded_count = 0
            for image in images:
                clean_filename = os.path.basename(image.name)
                # Ensure no spaces or weird characters if necessary, but leaving as is for now
                file_path = os.path.join(gallery_path, clean_filename)
                with open(file_path, 'wb+') as destination:
                    for chunk in image.chunks():
                        destination.write(chunk)
                uploaded_count += 1
            if uploaded_count > 0:
                message = f"✅ Successfully uploaded {uploaded_count} image(s)."

    # Get existing images
    images = []
    if os.path.exists(gallery_path):
        for filename in os.listdir(gallery_path):
            if filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                images.append({
                    "url": f"Media/Gallery/Images/{filename}",
                    "name": filename
                })
                
    # Sort images newest modified first
    images.sort(key=lambda x: os.path.getmtime(os.path.join(gallery_path, x["name"])), reverse=True)

    return render(request, "upload_gallery.html", {"images": images, "message": message})



def resources(request):
    blogs = Blog.objects.all().order_by("-published_date")
    return render(request, "resource.html", {"blogs": blogs})


# --- IMPORTANT ---
# This code assumes you have a 'utils.py' file in the same Django app directory
# that contains BOTH the ImageChatbot and TextChatbot classes.
from .utils import ImageChatbot, TextChatbot

# --- GLOBAL VARIABLES & CONFIGURATION ---

RESET_KEYWORDS = ["bye", "clear", "clear all", "goodbye", "quit", "exit"]

image_chatbot = None
text_chatbot = None

# --- MODEL LOADING ---

# Load Image Chatbot Model
try:
    print("Attempting to load ImageChatbot model...")
    image_model_path = os.path.join(settings.BASE_DIR, "image_chatbot_model.pkl")
    if os.path.exists(image_model_path):
        image_chatbot = ImageChatbot(model_path=image_model_path)
        print("✅ ImageChatbot loaded")
    else:
        print("❌ ImageChatbot model file not found")
except Exception as e:
    print(f"❌ ImageChatbot init failed: {e}")


try:
    print("Attempting to load TextChatbot model...")
    model_path = os.path.join(settings.BASE_DIR, "chatbot_model.pkl")
    label_path = os.path.join(settings.BASE_DIR, "label_encoder.pkl")
    semantic_path = os.path.join(settings.BASE_DIR, "semantic_data.pkl")

    if all(os.path.exists(p) for p in [model_path, label_path, semantic_path]):
        text_chatbot = TextChatbot(
            model_path=model_path,
            label_encoder_path=label_path,
            semantic_data_path=semantic_path
        )
        print("✅ TextChatbot loaded")
    else:
        print("❌ TextChatbot files missing")
except Exception as e:
    print(f"❌ TextChatbot init failed: {e}")


def format_images_for_response(image_results):
    if not image_results:
        return []

    return [
        {
            "name": img.get("name", ""),
            "fig_number": img.get("fig_number", ""),
            "image_url": img.get("image_url", ""),
            "definition": img.get("definition", ""),
            "similarity": float(img.get("similarity", 1.0)),
        }
        for img in image_results
    ]


@csrf_exempt
def chatbot_response(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        data = json.loads(request.body)
        user_question = data.get("message", "").strip()
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not user_question:
        return JsonResponse({"error": "Empty message"}, status=400)

    question_lower = user_question.lower()

    # -----------------------------
    # Reset Logic
    # -----------------------------
    if any(k in question_lower for k in RESET_KEYWORDS):
        return JsonResponse({
            "response": "Goodbye! Feel free to ask me another question anytime.",
            "reset": True
        })

    # -----------------------------
    # Concession Agreement (SEQUENTIAL VIDEO LOGIC)
    # -----------------------------
    if question_lower == "concession agreement":
        # 1. Single video file
        video_filenames = [
            "new2.mp4",
        ]

        text_name = "concession_agreement.txt"
        text_path = os.path.join(settings.MEDIA_ROOT, "IRC", text_name)
        
        paragraphs = []

        # 2. Read full text content as one paragraph
        if os.path.exists(text_path):
            try:
                with open(text_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    paragraphs = [content] if content else ["Document content not found."]
            except Exception as e:
                paragraphs = [f"Error reading document: {e}"]
        else:
            paragraphs = ["Document content not found."]

        # 3. Build sequence with single video
        sequence_data = []
        
        for video_file, paragraph_text in zip(video_filenames, paragraphs):
            video_url = f"/media/IRC/{video_file}"
            
            sequence_data.append({
                "video_url": video_url,
                "text_content": paragraph_text 
            })

        if sequence_data:
            return JsonResponse({
                "response": {
                    "display_type": "video_sequence", # Signal for frontend
                    "title": "About Us",
                    "sequence": sequence_data,        # The ordered list
                    "message": "Loading About Us presentation...",
                    "options": []
                }
            })
        else:
            return JsonResponse({
                "response": {
                    "message": "Concession Agreement content is unavailable.",
                    "options": []
                }
            })

    # -----------------------------
    # IRC Buttons
    # -----------------------------
    irc_map = {
        "irc 67": "irc67", "irc67": "irc67",
        "irc 35": "irc35", "irc35": "irc35",
        "irc 82": "irc82", "irc82": "irc82",
    }

    if question_lower in irc_map:
        irc_type = irc_map[question_lower]
        irc_name = irc_type.replace("irc", "IRC ")

        images = []
        questions = []

        if image_chatbot:
            images = format_images_for_response(
                image_chatbot.get_images_by_irc(irc_type, limit=4)
            )

        if text_chatbot:
            questions = text_chatbot.get_questions_by_type(irc_type) or []

        return JsonResponse({
            "response": {
                "message": f"According to {irc_name}, I found the perfect guidelines for you:",
                "images": images,
                "options": questions
            }
        })

    # -----------------------------
    # Image Search
    # -----------------------------
    if image_chatbot:
        image_results = image_chatbot.find_best_match(user_question)
        if image_results:
            return JsonResponse({
                "response": {
                    "message": "According to IRC I found the perfect guidelines for you:",
                    "images": format_images_for_response(image_results)
                }
            })

    # -----------------------------
    # Text Fallback
    # -----------------------------
    if text_chatbot:
        return JsonResponse({
            "response": text_chatbot.predict_answer(user_question)
        })

    # -----------------------------
    # Final Fallback
    # -----------------------------
    return JsonResponse({
        "response": "Chatbot service is currently unavailable."
    }, status=500)


@csrf_exempt
def validate_employee_api(request):
    """
    Validates user phone number against an external API.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            mobile = data.get("mobile", "").strip()
            name = data.get("name", "").strip().lower()

            if not mobile or not name:
                return JsonResponse({"success": False, "message": "Both Name and Mobile number are required."})

            # Example external API Endpoint
            # Replace 'https://example.com/api/users' with your actual API endpoint URL
            api_url = "http://attendance.hanuai.com/api/employee-list-summary" 

            try:
                # Call the external API (setting a timeout is good practice)
                response = requests.get(api_url, timeout=10)
                
                # Check if the API request was successful
                if response.status_code == 200:
                    api_data = response.json()
                    
                    # The API returns a dictionary with 'success' and 'employees' keys
                    # e.g., {"success": true, "employees": [{"name": "...", "phone": "..."}, ...]}
                    if isinstance(api_data, dict) and 'employees' in api_data:
                        employee_list = api_data['employees']
                        
                        if isinstance(employee_list, list):
                            # Verify if BOTH mobile number and name match the API records
                            user_match = any(
                                str(user.get("phone", "")) == mobile and 
                                str(user.get("name", "")).strip().lower() == name 
                                for user in employee_list
                            )
                            
                            if user_match:
                                request.session['is_verified_employee'] = True
                                request.session['verified_mobile'] = mobile
                                return JsonResponse({"success": True, "message": "Verification successful."})
                            else:
                                return JsonResponse({
                                    "success": False, 
                                    "message": "✗ Identity not recognized. Please ensure Name and Mobile match official records."
                                })
                        else:
                            return JsonResponse({"success": False, "message": "Unexpected format: 'employees' is not a list."})
                    else:
                        return JsonResponse({"success": False, "message": "Unexpected format from external API."})
                else:
                    return JsonResponse({
                        "success": False, 
                        "message": f"External API error: Returned status code {response.status_code}."
                    })
                    
            except requests.RequestException as e:
                # Handle network-related errors (timeout, connection error, invalid URL, etc.)
                return JsonResponse({"success": False, "message": "Failed to connect to the external API."})

        except json.JSONDecodeError:
            return JsonResponse({"success": False, "message": "Invalid JSON data received."}, status=400)
            
    return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)



@csrf_exempt
def process_rsa_upload(request):
    if request.method == 'POST':
        files = request.FILES.getlist('files[]')
        if not files:
            return JsonResponse({'success': False, 'message': 'No files uploaded.'})

        image_paths = []
        temp_dir = tempfile.mkdtemp()
        
        try:
            for f in files:
                file_path = os.path.join(temp_dir, f.name)
                with open(file_path, 'wb+') as destination:
                    for chunk in f.chunks():
                        destination.write(chunk)
                image_paths.append(file_path)

            from .test3 import process_uploaded_images
            results = process_uploaded_images(image_paths)
            return JsonResponse({'success': True, 'data': results})
        except Exception as e:
            logger.error(f"Error processing RSA: {str(e)}")
            return JsonResponse({'success': False, 'message': str(e)})
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    return JsonResponse({'success': False, 'message': 'Invalid request.'})


# Custom Error Handlers
def custom_400(request, exception):
    return render(request, '404.html', status=400)

def custom_403(request, exception):
    return render(request, '404.html', status=403)

def custom_404(request, exception):
    return render(request, '404.html', status=404)

def custom_500(request):
    return render(request, '404.html', status=500)