#!/usr/bin/env python3
from flask import Flask, render_template_string, request
import json
import os

app = Flask(__name__)
DATA_FILE = os.environ.get("DATA_FILE", "/app/data.json")

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DailyDex</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <script type="module">
      import { prepare, layout } from 'https://cdn.jsdelivr.net/npm/@chenglou/pretext@0.0.3/+esm';
      window.pretext = { prepare, layout };
    </script>
    <style>
        :root { --bg: #0d0d0d; --surface: #161616; --border: #2a2a2a; --text: #fafafa; --text-dim: #888; --accent: #22c55e; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html { font-size: 15px; }
        body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; min-height: 100vh; }
        a { color: inherit; text-decoration: none; }
        header { padding: 1.5rem 1.25rem; border-bottom: 1px solid var(--border); background: var(--surface); }
        .logo { font-size: 1.1rem; font-weight: 600; }
        .logo span { color: var(--accent); }
        .tagline { color: var(--text-dim); font-size: 0.85rem; margin-top: 0.25rem; }
        .meta { display: inline-flex; gap: 0.5rem; margin-top: 0.75rem; padding: 0.35rem 0.75rem; background: var(--bg); border-radius: 100px; font-size: 0.75rem; color: var(--text-dim); }
        .stats { display: flex; gap: 0.5rem; padding: 1rem 1.25rem; overflow-x: auto; border-bottom: 1px solid var(--border); }
        .stat { display: flex; align-items: center; gap: 0.4rem; padding: 0.5rem 0.75rem; background: var(--surface); border-radius: 8px; white-space: nowrap; }
        .stat-value { font-weight: 600; font-family: 'JetBrains Mono', monospace; }
        .stat-label { color: var(--text-dim); font-size: 0.7rem; }
        nav { display: flex; gap: 0.25rem; padding: 0.75rem 1.25rem; overflow-x: auto; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--bg); z-index: 100; }
        nav::-webkit-scrollbar { display: none; }
        .nav-btn { padding: 0.5rem 1rem; background: transparent; border: none; border-radius: 6px; color: var(--text-dim); font-size: 0.8rem; font-weight: 500; cursor: pointer; white-space: nowrap; }
        .nav-btn:hover { color: var(--text); }
        .nav-btn.active { background: var(--accent); color: var(--bg); }
        main { padding: 1.25rem; }
        .section { display: none; }
        .section.active { display: block; }
        .section-header { font-size: 0.7rem; font-weight: 600; letter-spacing: 0.1em; color: var(--accent); text-transform: uppercase; margin-bottom: 1rem; }
        .card-grid { display: grid; grid-template-columns: 1fr; gap: 0.75rem; }
        .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1rem; position: relative; overflow: hidden; }
        .card:hover { background: #1f1f1f; transform: translateY(-2px); transition: all 0.2s ease; box-shadow: 0 4px 20px rgba(34, 197, 94, 0.15); }
        .card:active { background: #1f1f1f; transform: scale(0.98); transition: transform 0.1s; }
        .card::after { content: ''; position: absolute; inset: 0; border-radius: 12px; pointer-events: none; background: linear-gradient(135deg, transparent 40%, rgba(34, 197, 94, 0.05) 100%); opacity: 0; transition: opacity 0.2s; }
        .card:hover::after { opacity: 1; }
        .card-tag { display: inline-block; padding: 0.2rem 0.5rem; background: var(--bg); border-radius: 4px; font-size: 0.65rem; font-weight: 600; text-transform: uppercase; margin-bottom: 0.5rem; }
        .card-tag.github { color: #7dd3fc; background: rgba(125, 211, 252, 0.15); box-shadow: 0 0 10px rgba(125, 211, 252, 0.3); }
        .card-tag.youtube { color: #f87171; background: rgba(248, 113, 113, 0.15); box-shadow: 0 0 10px rgba(248, 113, 113, 0.3); }
        .card-tag.huggingface { color: #fbbf24; background: rgba(251, 191, 36, 0.15); box-shadow: 0 0 10px rgba(251, 191, 36, 0.3); }
        .card-tag.arxiv { color: #c084fc; background: rgba(192, 132, 252, 0.15); box-shadow: 0 0 10px rgba(192, 132, 252, 0.3); }
        
        /* Mobile touch feedback */
        @media (hover: none) {
            .card:active { background: #1f1f1f; }
            .nav-btn:active { background: var(--accent); color: var(--bg); }
            .stat:active { background: #252525; }
            button:active { opacity: 0.8; transform: scale(0.96); }
        }
        
        /* Better mobile defaults */
        @media (max-width: 640px) {
            .card { padding: 1rem; }
            .featured-main { padding: 1rem; }
            .featured-item { padding: 0.75rem; }
            .logo { font-size: 1rem; }
        }
        .card-title { font-weight: 500; font-size: 0.95rem; line-height: 1.4; margin-bottom: 0.35rem; }
        .card-desc { font-size: 0.8rem; color: var(--text-dim); line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
        .card-meta { display: flex; gap: 1rem; margin-top: 0.6rem; padding-top: 0.6rem; border-top: 1px solid var(--border); font-size: 0.75rem; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; }
        .featured-grid { display: grid; gap: 0.75rem; margin-bottom: 1.5rem; }
        .featured-main { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; border-left: 3px solid var(--accent); }
        .featured-list { display: flex; flex-direction: column; gap: 0.5rem; }
        .featured-item { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 0.85rem; }
        .featured-item-title { font-size: 0.9rem; font-weight: 500; line-height: 1.35; }
        .featured-item-meta { font-size: 0.7rem; color: var(--text-dim); margin-top: 0.25rem; }
        footer { text-align: center; padding: 2rem 1rem; border-top: 1px solid var(--border); color: var(--text-dim); font-size: 0.75rem; }
        @media (min-width: 640px) { .card-grid { grid-template-columns: repeat(2, 1fr); } .featured-grid { grid-template-columns: 2fr 1fr; } }
        @media (min-width: 1024px) { .card-grid { grid-template-columns: repeat(3, 1fr); } main { padding: 1.5rem 2rem; } nav, .stats { padding: 0.75rem 2rem; } header { padding: 1.5rem 2rem; } }
    </style>
</head>
<body>
    <header>
        <div class="logo">DailyDex</div>
        <div class="tagline">Daily briefing on artificial intelligence</div>
        <div class="meta"><span>Updated {{ last_updated }}</span></div>
    </header>
    <div class="stats">
        <div class="stat"><span class="stat-value">{{ github|length }}</span><span class="stat-label">GitHub</span></div>
        <div class="stat"><span class="stat-value">{{ huggingface|length }}</span><span class="stat-label">Models</span></div>
        <div class="stat"><span class="stat-value">{{ youtube|length }}</span><span class="stat-label">Videos</span></div>
        <div class="stat"><span class="stat-value">{{ blogs|length }}</span><span class="stat-label">News</span></div>
        <div class="stat"><span class="stat-value">{{ papers|length }}</span><span class="stat-label">Papers</span></div>
    </div>
    <nav>
        <button class="nav-btn active" onclick="show('all',this)">Feed</button>
        <button class="nav-btn" onclick="show('github',this)">GitHub</button>
        <button class="nav-btn" onclick="show('huggingface',this)">Models</button>
        <button class="nav-btn" onclick="show('youtube',this)">Videos</button>
        <button class="nav-btn" onclick="show('blogs',this)">News</button>
        <button class="nav-btn" onclick="show('papers',this)">Research</button>
    </nav>
    <main>
        <div id="all" class="section active">
            {% if github %}
            <div class="section-header">GitHub Trending</div>
            <div class="featured-grid">
                <a href="{{ github[0].url }}" class="featured-main" target="_blank">
                    <div class="card-tag github">Featured</div>
                    <div class="card-title">{{ github[0].title }}</div>
                    <div class="card-desc">{{ github[0].description }}</div>
                    <div class="card-meta"><span>* {{ github[0].stars }}</span><span>{{ github[0].language }}</span></div>
                </a>
                <div class="featured-list">
                    {% for item in github[1:5] %}
                    <a href="{{ item.url }}" class="featured-item" target="_blank">
                        <div class="featured-item-title">{{ item.title }}</div>
                        <div class="featured-item-meta">* {{ item.stars }}</div>
                    </a>
                    {% endfor %}
                </div>
            </div>
            {% endif %}
            {% if youtube %}
            <div class="section-header">Videos</div>
            <div class="card-grid">
                {% for item in youtube[:4] %}
                <div class="card">
                    <div class="card-tag youtube">YouTube</div>
                    <div class="card-title"><a href="{{ item.url }}" target="_blank">{{ item.title }}</a></div>
                    <div class="card-desc">{{ item.description }}</div>
                </div>
                {% endfor %}
            </div>
            {% endif %}
            {% if blogs %}
            <div class="section-header">News</div>
            <div class="card-grid">
                {% for item in blogs[:4] %}
                <div class="card">
                    <div class="card-tag">{{ item.source }}</div>
                    <div class="card-title"><a href="{{ item.url }}" target="_blank">{{ item.title }}</a></div>
                </div>
                {% endfor %}
            </div>
            {% endif %}
        </div>
        <div id="github" class="section">
            <div class="card-grid">
                {% for item in github %}
                <div class="card">
                    <div class="card-tag github">GitHub</div>
                    <div class="card-title"><a href="{{ item.url }}" target="_blank">{{ item.title }}</a></div>
                    <p class="card-desc">{{ item.description }}</p>
                    <div class="card-meta"><span>* {{ item.stars }}</span><span>{{ item.language }}</span></div>
                </div>
                {% endfor %}
            </div>
        </div>
        <div id="huggingface" class="section">
            <div class="card-grid">
                {% for item in huggingface %}
                <div class="card">
                    <div class="card-tag huggingface">HF</div>
                    <div class="card-title"><a href="{{ item.url }}" target="_blank">{{ item.title }}</a></div>
                    <div class="card-meta"><span>↓ {{ item.downloads }}</span><span>{{ item.likes }}</span></div>
                </div>
                {% endfor %}
            </div>
        </div>
        <div id="youtube" class="section">
            <div class="card-grid">
                {% for item in youtube %}
                <div class="card">
                    <div class="card-tag youtube">YouTube</div>
                    <div class="card-title"><a href="{{ item.url }}" target="_blank">{{ item.title }}</a></div>
                    <p class="card-desc">{{ item.description }}</p>
                </div>
                {% endfor %}
            </div>
        </div>
        <div id="blogs" class="section">
            <div class="card-grid">
                {% for item in blogs %}
                <div class="card">
                    <div class="card-tag">{{ item.source }}</div>
                    <div class="card-title"><a href="{{ item.url }}" target="_blank">{{ item.title }}</a></div>
                </div>
                {% endfor %}
            </div>
        </div>
        <div id="papers" class="section">
            <div class="card-grid">
                {% for item in papers %}
                <div class="card">
                    <div class="card-tag arxiv">ArXiv</div>
                    <div class="card-title"><a href="{{ item.url }}" target="_blank">{{ item.title }}</a></div>
                </div>
                {% endfor %}
            </div>
        </div>
    </main>
    <footer>
        <p>DailyDex - <a href="/admin">Admin</a> - Updated {{ last_updated }}</p>
    </footer>
    <script type="module">
    import { prepare, layout } from 'https://cdn.jsdelivr.net/npm/@chenglou/pretext@0.0.3/+esm';
    
    // Pretext-powered dynamic card heights
    async function measureCards() {
        const cards = document.querySelectorAll('.card');
        const font = '15px Inter';
        const prepared = {};
        
        for (const card of cards) {
            const titleEl = card.querySelector('.card-title, .featured-item-title');
            const descEl = card.querySelector('.card-desc');
            if (!titleEl) continue;
            
            const title = titleEl.textContent;
            const desc = descEl ? descEl.textContent : '';
            const combined = title + (desc ? ' ' + desc : '');
            
            if (!prepared[font]) {
                prepared[font] = prepare(combined.substring(0, 500), font);
            }
            
            // Measure with different widths for responsive layout
            const rect = card.getBoundingClientRect();
            const width = rect.width || 300;
            const lineHeight = 22;
            
            const { height } = layout(prepared[font], width - 32, lineHeight);
            
            // Apply dynamic height
            card.style.setProperty('--measured-height', height + 'px');
        }
    }
    
    // Run on load and resize
    window.addEventListener('load', () => {
        setTimeout(measureCards, 100);
    });
    window.addEventListener('resize', measureCards);
    
    // Expose for console debugging
    window.pretext = { prepare, layout, measureCards };
    </script>
    <script>
    function show(id, btn) {
        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
        document.querySelectorAll('.nav-btn').forEach(t => t.classList.remove('active'));
        document.getElementById(id).classList.add('active');
        btn.classList.add('active');
        window.scrollTo(0, 0);
        
        // Re-measure after section change
        if (window.pretext && window.pretext.measureCards) {
            setTimeout(window.pretext.measureCards, 50);
        }
    }
    </script>
</body>
</html>
"""

ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Dashboard - Settings</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #0d0d0d; --surface: #161616; --border: #2a2a2a; --text: #fafafa; --text-dim: #888; --accent: #22c55e; --danger: #ef4444; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; padding: 1rem; max-width: 800px; margin: 0 auto; }
        h1 { font-size: 1.25rem; margin-bottom: 1rem; display: flex; justify-content: space-between; }
        h2 { font-size: 0.75rem; color: var(--text-dim); margin: 1.25rem 0 0.5rem; text-transform: uppercase; letter-spacing: 0.1em; }
        .back { color: var(--text-dim); font-size: 0.85rem; }
        .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1rem; margin-bottom: 0.75rem; }
        .row { display: flex; gap: 0.5rem; flex-wrap: wrap; }
        input, select { flex: 1; min-width: 120px; padding: 0.6rem 0.75rem; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-size: 0.9rem; }
        input:focus { outline: none; border-color: var(--accent); }
        button { padding: 0.6rem 1rem; background: var(--accent); color: var(--bg); border: none; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 0.85rem; }
        button:hover { opacity: 0.9; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        .item { display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0; border-bottom: 1px solid var(--border); flex-wrap: wrap; gap: 0.5rem; }
        .item:last-child { border: none; }
        .item-name { font-weight: 500; font-size: 0.9rem; }
        .item-url { font-size: 0.7rem; color: var(--text-dim); font-family: 'JetBrains Mono', monospace; word-break: break-all; }
        .item-actions { display: flex; gap: 0.5rem; }
        .btn-danger { color: var(--danger); background: transparent; font-size: 0.8rem; padding: 0.3rem; }
        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin-bottom: 0.75rem; }
        .stat-box { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 0.75rem; text-align: center; }
        .stat-num { font-size: 1.25rem; font-weight: 700; }
        .stat-label { font-size: 0.65rem; color: var(--text-dim); text-transform: uppercase; }
        .status-box { padding: 0.75rem; background: var(--bg); border-radius: 8px; font-size: 0.85rem; display: none; }
        .status-box.success { display: block; border-left: 3px solid var(--accent); }
        .status-box.error { display: block; border-left: 3px solid var(--danger); }
        .status-box.loading { display: block; border-left: 3px solid #eab308; }
        .empty { color: var(--text-dim); font-size: 0.85rem; font-style: italic; }
        @media (max-width: 480px) { .stats-grid { grid-template-columns: repeat(3, 1fr); } }
    </style>
</head>
<body>
    <h1><span>Settings</span><a href="/" class="back">Dashboard</a></h1>
    <div id="status" class="status-box"></div>
    <div class="card">
        <h2 style="margin-top:0">Current Data</h2>
        <div class="stats-grid">
            <div class="stat-box"><div class="stat-num" id="yt-count">-</div><div class="stat-label">Videos</div></div>
            <div class="stat-box"><div class="stat-num" id="gh-count">-</div><div class="stat-label">GitHub</div></div>
            <div class="stat-box"><div class="stat-num" id="hf-count">-</div><div class="stat-label">Models</div></div>
            <div class="stat-box"><div class="stat-num" id="blog-count">-</div><div class="stat-label">News</div></div>
            <div class="stat-box"><div class="stat-num" id="paper-count">-</div><div class="stat-label">Papers</div></div>
            <div class="stat-box"><div class="stat-num" id="last-update">-</div><div class="stat-label">Updated</div></div>
        </div>
        <button onclick="refetch()" id="refresh-btn">Refresh All Data</button>
    </div>
    <div class="card">
        <h2 style="margin-top:0">YouTube Channels</h2>
        <div id="youtube-list"></div>
        <div class="row">
            <input id="yt-name" placeholder="Channel name">
            <input id="yt-url" placeholder="YouTube URL">
            <button onclick="addYouTube()">Add</button>
        </div>
    </div>
    <div class="card">
        <h2 style="margin-top:0">Blog RSS Feeds</h2>
        <div id="blogs-list"></div>
        <div class="row">
            <input id="blog-name" placeholder="Site name">
            <input id="blog-url" placeholder="RSS URL">
            <button onclick="addBlog()">Add</button>
        </div>
    </div>
    <div class="card">
        <h2 style="margin-top:0">Limits</h2>
        <div class="row">
            <select id="gh-limit">
                <option value="10">10 repos</option>
                <option value="15">15 repos</option>
                <option value="20">20 repos</option>
            </select>
            <select id="hf-limit">
                <option value="10">10 models</option>
                <option value="15">15 models</option>
            </select>
            <button onclick="saveLimits()">Save</button>
        </div>
    </div>
    <script>
    let config = {};
    let data = {};
    async function load() {
        config = await fetch('/api/config').then(r => r.json());
        data = await fetch('/api/data').then(r => r.json()).catch(() => ({}));
        render();
    }
    function render() {
        document.getElementById('yt-count').textContent = (data.youtube || []).length;
        document.getElementById('gh-count').textContent = (data.github || []).length;
        document.getElementById('hf-count').textContent = (data.huggingface || []).length;
        document.getElementById('blog-count').textContent = (data.blogs || []).length;
        document.getElementById('paper-count').textContent = (data.papers || []).length;
        document.getElementById('last-update').textContent = data.last_updated ? new Date(data.last_updated).toLocaleTimeString() : 'Never';
        const ytList = document.getElementById('youtube-list');
        const ytChannels = config.youtube ? config.youtube.channels : [];
        ytList.innerHTML = ytChannels.length ? ytChannels.map(function(c, i) { return '<div class="item"><div><div class="item-name">'+c.name+'</div><div class="item-url">'+c.url+'</div></div><div class="item-actions"><span class="btn-danger" onclick="removeYouTube('+i+')">[x]</span></div></div>'; }).join('') : '<div class="empty">No channels</div>';
        const blogList = document.getElementById('blogs-list');
        const blogs = config.blogs || [];
        blogList.innerHTML = blogs.length ? blogs.map(function(b, i) { return '<div class="item"><div><div class="item-name">'+b.name+'</div><div class="item-url">'+b.url+'</div></div><div class="item-actions"><span class="btn-danger" onclick="removeBlog('+i+')">[x]</span></div></div>'; }).join('') : '<div class="empty">No feeds</div>';
        document.getElementById('gh-limit').value = config.github ? config.github.limit : 15;
        document.getElementById('hf-limit').value = config.huggingface ? config.huggingface.limit : 15;
    }
    async function save() { await fetch('/api/config', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(config) }); }
    async function addYouTube() {
        var name = document.getElementById('yt-name').value.trim();
        var url = document.getElementById('yt-url').value.trim();
        if (!name || !url) return showStatus('Fill both fields', 'error');
        var fullUrl = url.indexOf('youtube.com') >= 0 ? url : 'https://www.youtube.com/@' + url.replace('@', '');
        if (!config.youtube) config.youtube = { channels: [] };
        config.youtube.channels.push({name: name, url: fullUrl});
        document.getElementById('yt-name').value = '';
        document.getElementById('yt-url').value = '';
        await save();
        render();
        showStatus('Channel added', 'success');
    }
    function removeYouTube(i) { config.youtube.channels.splice(i, 1); save().then(function() { render(); showStatus('Removed', 'success'); }); }
    async function addBlog() {
        var name = document.getElementById('blog-name').value.trim();
        var url = document.getElementById('blog-url').value.trim();
        if (!name || !url) return showStatus('Fill both fields', 'error');
        if (!config.blogs) config.blogs = [];
        config.blogs.push({name: name, url: url});
        document.getElementById('blog-name').value = '';
        document.getElementById('blog-url').value = '';
        await save();
        render();
        showStatus('Feed added', 'success');
    }
    function removeBlog(i) { config.blogs.splice(i, 1); save().then(function() { render(); showStatus('Removed', 'success'); }); }
    async function saveLimits() {
        if (!config.github) config.github = {};
        config.github.limit = parseInt(document.getElementById('gh-limit').value);
        if (!config.huggingface) config.huggingface = {};
        config.huggingface.limit = parseInt(document.getElementById('hf-limit').value);
        await save();
        showStatus('Limits saved', 'success');
    }
    function showStatus(msg, type) {
        var box = document.getElementById('status');
        box.textContent = msg;
        box.className = 'status-box ' + type;
        setTimeout(function() { box.style.display = 'none'; }, 3000);
    }
    async function refetch() {
        var btn = document.getElementById('refresh-btn');
        btn.disabled = true;
        btn.textContent = 'Refreshing...';
        showStatus('Refreshing...', 'loading');
        try { 
            await fetch('/api/refetch', { method: 'POST' }); 
            data = await fetch('/api/data').then(function(r) { return r.json(); }).catch(function() { return {}; }); 
            render(); 
            showStatus('Done', 'success'); 
        } catch(e) { showStatus('Error: ' + e.message, 'error'); }
        btn.disabled = false;
        btn.textContent = 'Refresh All Data';
    }
    load();
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        last_updated = data.get("last_updated", "Unknown")[:10]
        return render_template_string(
            HTML,
            last_updated=last_updated,
            youtube=data.get("youtube", []),
            github=data.get("github", []),
            huggingface=data.get("huggingface", []),
            blogs=data.get("blogs", []),
            papers=data.get("papers", []),
        )
    except:
        return "<h1>No data. Run fetch first.</h1>"


@app.route("/api/config", methods=["GET"])
def get_config():
    return json.load(open("/app/config.json"))


@app.route("/api/config", methods=["POST"])
def update_config():
    with open("/app/config.json", "w") as f:
        json.dump(request.json, f, indent=2)
    return {"status": "ok"}


@app.route("/api/data", methods=["GET"])
def get_data():
    return json.load(open(DATA_FILE))


@app.route("/api/refetch", methods=["POST"])
def refetch():
    import subprocess

    result = subprocess.run(
        ["python3", "/app/fetch_news.py"], capture_output=True, timeout=120
    )
    return {"output": result.stdout.decode(), "error": result.stderr.decode()}


@app.route("/admin")
def admin():
    return render_template_string(ADMIN_HTML)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8889)
