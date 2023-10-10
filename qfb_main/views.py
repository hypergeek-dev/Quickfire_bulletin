from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.http import JsonResponse
import os
import requests
import json
import logging  # Import the logging module
import traceback
from datetime import datetime
from django.utils import timezone
from django.utils.text import slugify
import uuid
from qfb_main.models import NewsArticle
from .forms import CommentForm
import spacy

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# Define a logger
logger = logging.getLogger(__name__)

# Function to fetch news
def fetch_news():
    api_key = os.getenv('NEWS_API_KEY')
    url = f"https://newsdata.io/api/1/news?apikey={api_key}&country=us&language=en"
    response = requests.get(url)
    if response.status_code == 200:
        try:
            data = json.loads(response.text)
            articles = data['results']
            for article in articles:
                try:
                    pub_date_str = article.get('pubDate', None)
                    if pub_date_str:
                        pub_date = datetime.strptime(pub_date_str, '%Y-%m-%d %H:%M:%S')
                        pub_date = timezone.make_aware(pub_date)
                    slug = slugify(article['title']) + '-' + str(uuid.uuid4())[:8]
                    doc = nlp(article.get('content', ''))
                    sentences = [sent.text for sent in doc.sents]
                    def group_into_paragraphs(sentences, n):
                        paragraphs = []
                        for i in range(0, len(sentences), n):
                            paragraph = " ".join(sentences[i:i+n])
                            paragraphs.append(paragraph)
                        return paragraphs
                    paragraphs = group_into_paragraphs(sentences, 5)
                    formatted_content = "\n\n".join(paragraphs)
                    news_article, created = NewsArticle.objects.update_or_create(
                        title=article['title'],
                        defaults={
                            'slug': slug,
                            'content': formatted_content,
                            'author_id': 1,
                            'source_id': article['source_id'],
                            'source_priority': article['source_priority'],
                            'category': ','.join(article['category']),
                            'language': article['language'],
                            'pub_date': pub_date if pub_date_str else None,
                            'image_url': article.get('image_url', ''),
                            'status': 1
                        }
                    )
                    # Log a message when an article is saved
                    logger.debug(f"Saved article with ID: {news_article.id}")
                except Exception as e:
                    tb_str = traceback.format_exception(type(e), e, e.__traceback__)
                    tb_str = "".join(tb_str)
                    # Log an error message when an error occurs
                    logger.error(f"Failed to save article: {e}\n{tb_str}")
        except KeyError:
            logger.error(f"API response missing 'articles' key: {response.text}")
        except Exception as e:
            tb_str = traceback.format_exception(type(e), e, e.__traceback__)
            tb_str = "".join(tb_str)
            # Log an error message when an error occurs
            logger.error(f"An error occurred while processing the API response: {e}\n{tb_str}")
    else:
        logger.error(f"API call failed with status code {response.status_code}: {response.text}")

# Function to render news articles
def news_article_list(request):
    from django.db.models import Q

    articles = NewsArticle.objects.filter(Q(status=1))
    return render(request, 'index.html', {'news_article_list': articles})

# Function to render individual news article details
def news_article_detail(request, id):
    article = get_object_or_404(NewsArticle, id=id)
    return render(request, 'news_article_detail.html', {'article': article})

# Function to add a comment to an article
def add_comment_to_article(request, article_id):
    article = get_object_or_404(NewsArticle, id=article_id)
    response_data = {}

    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            new_comment = form.save(commit=False)
            new_comment.news_article = article  
            new_comment.save()

            # Log a message when a new comment is saved
            logger.info(f"New comment saved: {new_comment}")

            if request.is_ajax():
                response_data['result'] = 'Comment added successfully'
                response_data['comment_id'] = new_comment.id 
                return JsonResponse(response_data)
            else:
                return redirect('article_detail', article_id=article.id)
        else:
            if request.is_ajax():
                return HttpResponseBadRequest('Invalid form')

    else:
        form = CommentForm()

    return render(request, 'forms.html', {
        'article': article,
        'form': form,
    })

# Signup view
def account_signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'account/signup.html', {'form': form})

# Login view
def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'account/login.html', {'form': form})

# Logout view
def user_logout(request):
    logout(request)
    return redirect('home')
