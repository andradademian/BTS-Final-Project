let articles = [];

window.addEventListener('DOMContentLoaded', () => {
    loadArticles();
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('refreshBtn').addEventListener('click', loadArticles);
    document.getElementById('categorySelect').addEventListener('change', loadArticles);
    document.querySelector('.modal-close').addEventListener('click', closeModal);

    // Close modal when clicking outside
    document.getElementById('analysisModal').addEventListener('click', (e) => {
        if (e.target.id === 'analysisModal') {
            closeModal();
        }
    });
}

async function loadArticles() {
    const category = document.getElementById('categorySelect').value;
    const loading = document.getElementById('loading');
    const container = document.getElementById('articlesContainer');
    const noArticles = document.getElementById('noArticles');
    const refreshBtn = document.getElementById('refreshBtn');

    loading.style.display = 'block';
    container.innerHTML = '';
    noArticles.style.display = 'none';
    refreshBtn.disabled = true;

    try {
        const params = new URLSearchParams({
            country: 'us',
            language: 'en'
        });

        if (category) {
            params.append('category', category);
        }

        const response = await fetch(`/api/articles?${params}`);
        const data = await response.json();

        if (data.status === 'success' && data.articles.length > 0) {
            articles = data.articles;
            displayArticles(articles);
            document.getElementById('articleCount').textContent =
                `${articles.length} article${articles.length !== 1 ? 's' : ''} loaded`;
        } else {
            noArticles.style.display = 'block';
        }
    } catch (error) {
        console.error('Error loading articles:', error);
        container.innerHTML = '<div class="no-articles">Error loading articles. Please try again.</div>';
    } finally {
        loading.style.display = 'none';
        refreshBtn.disabled = false;
    }
}

function displayArticles(articles) {
    const container = document.getElementById('articlesContainer');
    container.innerHTML = '';

    articles.forEach((article, index) => {
        const card = document.createElement('div');
        card.className = 'article-card';

        const categories = Array.isArray(article.category) ? article.category : [];
        const categoryBadges = categories.map(cat =>
            `<span class="category-badge">${cat}</span>`
        ).join('');

        card.innerHTML = `
            <div class="article-meta">
                <span class="article-source">${article.source_name || article.source}</span>
                <span>•</span>
                <span>${new Date(article.published_at).toLocaleDateString()}</span>
            </div>
            ${categoryBadges}
            <h2 class="article-title">${article.title}</h2>
            <p class="article-description">${article.description}</p>
            <div class="article-actions">
                <button class="btn-analyze" onclick="analyzeArticle(${index})">
                    Analyze Article
                </button>
                <a href="${article.url}" target="_blank" class="btn-read">
                    Read Full Article
                </a>
            </div>
        `;

        container.appendChild(card);
    });
}

async function analyzeArticle(index) {
    const article = articles[index];
    const modal = document.getElementById('analysisModal');

    // Show modal with loading state
    showModal();
    document.getElementById('analysisContent').innerHTML = '<div class="loading">Analyzing article...</div>';

    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: article.title,
                text: article.content,
                article_id: article.id
            })
        });

        const data = await response.json();

        if (data.status === 'success') {
            displayAnalysis(data.analysis);
        } else {
            document.getElementById('analysisContent').innerHTML =
                `<div class="no-articles">Error: ${data.message}</div>`;
        }
    } catch (error) {
        console.error('Error analyzing article:', error);
        document.getElementById('analysisContent').innerHTML =
            '<div class="no-articles">Error analyzing article. Please try again.</div>';
    }
}

function displayAnalysis(analysis) {
    const probReal = Math.round(analysis.prob_real * 100);
    const probFake = Math.round(analysis.prob_fake * 100);

    let credibilityClass = 'high';
    if (probReal < 40) credibilityClass = 'low';
    else if (probReal < 70) credibilityClass = 'medium';

    const crisisCategories = analysis.crisis_categories && analysis.crisis_categories.length > 0
        ? analysis.crisis_categories.join(', ')
        : 'None detected';

    document.getElementById('analysisContent').innerHTML = `
        <h2>Analysis Results</h2>
        
        <div class="analysis-section">
            <h3>Credibility Score</h3>
            <div class="credibility-bar">
                <div class="credibility-fill ${credibilityClass}" style="width: ${probReal}%">
                    ${probReal}%
                </div>
            </div>
            <p><strong>Real:</strong> ${probReal}%</p>
            <p><strong>Fake:</strong> ${probFake}%</p>
            <p><strong>Classification:</strong> ${analysis.classification}</p>
            <p><strong>Threshold Used:</strong> ${analysis.threshold_used}</p>
        </div>

        <div class="analysis-section">
            <h3>Crisis Detection</h3>
            <p><strong>Crisis-Related:</strong> ${analysis.crisis_detected ? 'Yes' : 'No'}</p>
            <p><strong>Categories:</strong> ${crisisCategories}</p>
            <p><strong>Crisis Intensity:</strong> ${analysis.crisis_intensity || 0} keywords</p>
        </div>
    `;
}

function showModal() {
    document.getElementById('analysisModal').classList.add('active');
}

function closeModal() {
    document.getElementById('analysisModal').classList.remove('active');
}