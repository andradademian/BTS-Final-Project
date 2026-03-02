from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import requests
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests

# Configuration - Load from environment
NEWSDATA_API_KEY = os.getenv('NEWSDATA_API_KEY')
NEWSDATA_API_URL = "https://newsdata.io/api/1/latest"

# Validate API key exists
if not NEWSDATA_API_KEY:
    raise ValueError("NEWSDATA_API_KEY not found in environment variables. Please set it in .env file")

# Store fetched articles in memory (use database in production)
articles_cache = []


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/articles', methods=['GET'])
def get_articles():

    try:
        # Get query parameters
        country = request.args.get('country', 'us')
        language = request.args.get('language', 'en')
        category = request.args.get('category', '')
        query = request.args.get('q', '')

        # Build API request parameters
        params = {
            'apikey': NEWSDATA_API_KEY,
            'country': country,
            'language': language,
        }

        if category:
            params['category'] = category

        if query:
            params['q'] = query

        print(f"Fetching articles with params (country={country}, lang={language}, category={category})")

        # Make request to newsdata.io
        response = requests.get(NEWSDATA_API_URL, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        print(f"API Response status: {data.get('status')}")

        if data['status'] == 'success':
            # Process and clean articles
            articles = []
            for article in data.get('results', []):
                # Get content, check if it's paid-only
                content = article.get('content', '')

                # Skip or replace paid content
                if content == "ONLY AVAILABLE IN PAID PLANS":
                    content = article.get('description', '')

                # Skip articles with no usable content
                if not content or content == "ONLY AVAILABLE IN PAID PLANS":
                    print(f"Skipping article with no content: {article.get('title', 'Unknown')}")
                    continue

                processed_article = {
                    'id': article.get('article_id', ''),
                    'title': article.get('title', 'No title'),
                    'description': article.get('description', 'No description available'),
                    'content': content,
                    'source': article.get('source_id', 'Unknown'),
                    'source_name': article.get('source_name', 'Unknown Source'),
                    'url': article.get('link', ''),
                    'image_url': article.get('image_url', ''),
                    'published_at': article.get('pubDate', ''),
                    'category': article.get('category', []),
                    'country': article.get('country', []),
                }
                articles.append(processed_article)

            # Cache articles
            global articles_cache
            articles_cache = articles

            print(f"Successfully fetched {len(articles)} articles (filtered out paid-only)")

            return jsonify({
                'status': 'success',
                'total_results': len(articles),
                'articles': articles
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to fetch articles from newsdata.io'
            }), 500

    except requests.exceptions.RequestException as e:
        print(f"Request error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'API request failed: {str(e)}'
        }), 500
    except Exception as e:
        print(f"Server error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Server error: {str(e)}'
        }), 500


@app.route('/api/article/<article_id>', methods=['GET'])
def get_article(article_id):
    article = next((a for a in articles_cache if a['id'] == article_id), None)

    if article:
        return jsonify({
            'status': 'success',
            'article': article
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Article not found'
        }), 404


@app.route('/api/analyze', methods=['POST'])
def analyze_article():
    #here connect with the ml model
    try:
        data = request.get_json()

        title = data.get('title', '')
        text = data.get('text', '')
        article_id = data.get('article_id', '')

        if not title or not text:
            return jsonify({
                'status': 'error',
                'message': 'Title and text are required'
            }), 400

        #for now, return mock data
        result = {
            'status': 'success',
            'article_id': article_id,
            'analysis': {
                'classification': 'Most likely real',
                'prob_real': 0.78,
                'prob_fake': 0.22,
                'threshold_used': 0.5,
                'crisis_detected': False,
                'crisis_categories': [],
                'crisis_keywords': {},
                'crisis_intensity': 0
            }
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Analysis failed: {str(e)}'
        }), 500


if __name__ == '__main__':
    print("Starting Flask server...")
    print("API endpoint: http://localhost:5000")
    print("Test articles: http://localhost:5000/api/articles")
    app.run(debug=True, host='0.0.0.0', port=5000)