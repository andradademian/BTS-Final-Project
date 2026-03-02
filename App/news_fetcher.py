import requests
from typing import List, Dict, Optional

class NewsDataFetcher:

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://newsdata.io/api/1/latest"

    def fetch_articles(
            self,
            country: str = 'us',
            language: str = 'en',
            category: Optional[str] = None,
            query: Optional[str] = None,
            max_results: int = 10
    ) -> List[Dict]:

        params = {
            'apikey': self.api_key,
            'country': country,
            'language': language,
        }

        if category:
            params['category'] = category

        if query:
            params['q'] = query

        try:
            print(f"Fetching articles from {self.base_url}")
            print(f"Parameters: {params}")

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            print(f"API Status: {data.get('status')}")
            print(f"Total results: {data.get('totalResults', 0)}")

            if data.get('status') == 'success':
                articles = self._process_articles(data.get('results', []))
                # Filter out articles with paid-only content
                articles = [a for a in articles if a['content'] and a['content'] != "ONLY AVAILABLE IN PAID PLANS"]
                print(f"After filtering paid-only: {len(articles)} articles")
                return articles[:max_results]
            else:
                raise Exception(f"API returned error: {data.get('message', 'Unknown error')}")

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch articles: {str(e)}")

    def _process_articles(self, raw_articles: List[Dict]) -> List[Dict]:

        processed = []

        for article in raw_articles:
            # Get content, handle paid plans
            content = article.get('content', '')
            description = article.get('description', '')

            # If content is paid-only, use description
            if content == "ONLY AVAILABLE IN PAID PLANS":
                content = description

            # Skip if no usable content at all
            if not content or content == "ONLY AVAILABLE IN PAID PLANS":
                continue

            processed_article = {
                'id': article.get('article_id', ''),
                'title': article.get('title', 'No title'),
                'description': description if description else 'No description available',
                'content': content,
                'source': article.get('source_id', 'Unknown'),
                'source_name': article.get('source_name', 'Unknown Source'),
                'url': article.get('link', ''),
                'image_url': article.get('image_url', ''),
                'published_at': article.get('pubDate', ''),
                'category': article.get('category', []),
                'country': article.get('country', []),
                'language': article.get('language', 'en'),
            }
            processed.append(processed_article)

        return processed

    def search_articles(
            self,
            query: str,
            language: str = 'en',
            max_results: int = 10
    ) -> List[Dict]:

        return self.fetch_articles(
            query=query,
            language=language,
            max_results=max_results
        )


# Example usage
if __name__ == '__main__':
    API_KEY = "pub_3f56b4a359104924a9ac056fa6866e6c"
    fetcher = NewsDataFetcher(API_KEY)

    # Fetch top news
    print("Fetching latest news...")
    articles = fetcher.fetch_articles(country='us', language='en')

    print(f"\nFetched {len(articles)} articles (with valid content):")
    for i, article in enumerate(articles, 1):
        print(f"\n{i}. {article['title']}")
        print(f"   Source: {article['source_name']}")
        print(f"   Published: {article['published_at']}")
        print(f"   Content length: {len(article['content'])} characters")