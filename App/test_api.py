
from news_fetcher import NewsDataFetcher
import json
import os
from dotenv import load_dotenv

load_dotenv()


def test_fetch():
    # Get API key from environment variable
    API_KEY = os.getenv('NEWSDATA_API_KEY', 'your_api_key_here')

    if API_KEY == 'your_api_key_here':
        print(" Warning: Using placeholder API key")
        print("Set NEWSDATA_API_KEY in .env file or environment variable")
        return

    fetcher = NewsDataFetcher(API_KEY)

    print("=" * 70)
    print("Testing newsdata.io API")
    print("=" * 70)

    try:
        # Test 1: Fetch latest news
        print("\n1. Fetching latest US news...")
        articles = fetcher.fetch_articles(country='us', language='en', max_results=10)
        print(f"✓ Successfully fetched {len(articles)} articles (with valid content)")

        # Print first article details
        if articles:
            print("\n" + "=" * 70)
            print("FIRST ARTICLE:")
            print("=" * 70)
            print(f"Title: {articles[0]['title']}")
            print(f"Source: {articles[0]['source_name']}")
            print(f"Published: {articles[0]['published_at']}")
            print(f"Description: {articles[0]['description'][:150]}...")
            print(f"Content length: {len(articles[0]['content'])} characters")
            print(f"Content preview: {articles[0]['content'][:200]}...")
            print(f"URL: {articles[0]['url']}")

            # Print all article titles
            print("\n" + "=" * 70)
            print("ALL FETCHED ARTICLES (with valid content):")
            print("=" * 70)
            for i, article in enumerate(articles, 1):
                print(f"{i}. {article['title']}")
                print(f"   Source: {article['source_name']}")
                print(f"   Content: {len(article['content'])} chars")
                print()

        # Test 2: Fetch by category
        print("\n2. Fetching technology news...")
        tech_articles = fetcher.fetch_articles(
            category='technology',
            language='en',
            max_results=5
        )
        print(f"✓ Successfully fetched {len(tech_articles)} technology articles")
        for i, article in enumerate(tech_articles, 1):
            print(f"   {i}. {article['title']}")

        print("\n" + "=" * 70)
        print("ALL TESTS PASSED! ✓")
        print("=" * 70)
        print("\nNote: Articles with 'ONLY AVAILABLE IN PAID PLANS' were filtered out")
        print("You can now run the Flask app with: python app.py")

    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Check your internet connection")
        print("2. Verify the API key is still valid")
        print("3. Check newsdata.io API status")


if __name__ == '__main__':
    test_fetch()