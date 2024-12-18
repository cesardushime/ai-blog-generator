from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from yt_dlp import YoutubeDL
from django.conf import settings
import os
import re
import markdown2
import assemblyai as aai
import google.generativeai as genai
from .models import BlogPost

# Creating veiws and rendering templates.

@login_required
def index(request):
    return render(request, 'index.html')

## To be fixed as it can't generate a blog
@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']
        except(KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid request method'}, status=405) 
        
        # To be fixed as pytube doesn't seem to get the youtube title
        # get yt title
        title = yt_title(yt_link)
        # get transcript
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({'error': "Failed to get transcript"}, status=500)
        # use Gemini to generate the blog
        blog_content = generate_blog_from_transcription(transcription)
        if not blog_content:
            return JsonResponse({'error': "Failed to generate blog article"}, status=500)
        # Save blog article to database
        
        new_blog_article = BlogPost.objects.create(
            user = request.user,
            youtube_title = title,
            youtube_link = yt_link,
            generated_content = blog_content,
        )
        new_blog_article.save()
        # return blog article as a response
        return JsonResponse({'content': blog_content})
    else:
        return JsonResponse({'error': 'Invalid data sent'}, status=400)
def yt_title(link):
    with YoutubeDL() as myVideo:
            info_dict = myVideo.extract_info(link, download=False)
            title = clean_filename(info_dict.get("title", "No title found"))
    return title
        
# Remove or replace any unsupported characters
def clean_filename(title):
    return re.sub(r'''[<>':"/\\|?*]''', '', title)

# Downloading audio file and returning its filepath
def download_audio(link):
    # Cleaning title for valid os filename
    with YoutubeDL({'quiet': True}) as myDownload:
        info_dict = myDownload.extract_info(link, download=False)
        clean_title = clean_filename(info_dict.get('title', 'audio'))
    
    # Download options
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{settings.MEDIA_ROOT}/{clean_title}.%(ext)s',  
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'ffmpeg_location': "C:\\Users\\user\\OneDrive\\Documents\\ffmpeg-7.0.2-essentials_build\\bin"
    }
    
    # Download the file
    with YoutubeDL(ydl_opts) as myDownload:
        myDownload.download([link])
        
    # Cleaned file path
    file_path = os.path.join(settings.MEDIA_ROOT, f"{clean_title}.mp3")
    return file_path

# Transcribing text with assembly AI
def get_transcription(link):
    audio_file = download_audio(link)
    if not audio_file:
        return None
    
    aai.settings.api_key = "26a65cb798cb4519a6a7d217f4f4b7c8"

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)
    
    return transcript.text

def generate_blog_from_transcription(transcription):
    genai.configure(api_key = 'AIzaSyBBPETsDFIna-_Hf_aK9ktWhOHR6W1cYEQ')
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(f"Based on the following transcript from a YouTube video, write a comprehensive blog article, write it based on the transcript, but don't make it look like a youtube video, make it look like a proper blog article:\n\n{transcription}\n\n Article:")
    
    generated_content = response.text
    generated_content_html = markdown2.markdown(generated_content)

    return generated_content_html


# Matching blog posts generated by a specific user
@login_required
def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, 'all-blogs.html', {'blog_articles': blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('/')

## Login functionality
def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']  
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid password!"
            return render(request, 'login.html', {'error_message': error_message})
    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message': error_message})
        else:
            error_message = "Password do not match"
            return render(request, 'signup.html', {'error_message': error_message})
    return render(request, 'signup.html')
def user_logout(request):
    logout(request)
    return redirect('/')