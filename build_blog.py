#!/usr/bin/env python3
# build_blog.py - Bilingual Static SEO Blog & Sitemap Generator (zh-Hant & en)
# Reads Markdown posts from `blog/posts/*.md` (zh-Hant) and `blog/posts_en/*.md` (en),
# compiles static HTML pages in `blog/<slug>.html` and `blog/en/<slug>.html`,
# generates `blog/index.html`, `blog/en/index.html`, `blog/rss.xml`, `blog/en/rss.xml`,
# and updates `sitemap.xml` with full bilingual URLs and hreflang support.
import os
import re
import json
import html
from datetime import datetime
from pathlib import Path

SITE_CONFIG = {
    "site_name": "KyteShelf",
    "base_url": "https://kyteshelf.aisming.com",
    "logo_path": "icon.ico",
    "og_image": "icon.ico",
    "blog_desc": "深入探討 Windows 10/11 桌面檔案暫存、跨視窗拖曳中繼、Dropover 替代方案與高效檔案整理工作流。",
    "blog_desc_en": "In-depth guides on Windows 10/11 file stashing, multi-window drag-and-drop workflows, Dropover alternatives, and desktop productivity.",
    "cta_url": "https://github.com/ais7896-hue/KyteShelf/releases/download/v1.4.5/KyteShelf_Setup_v1.4.5.exe",
    "cta_desc": "專為 Windows 10/11 打造的桌面懸浮拖曳暫存置物架，抓住檔案輕晃滑鼠即刻召喚，支援 ZIP 一鍵打包與 Outlook 附件直串。",
    "cta_desc_en": "The floating drag-and-drop staging shelf built for Windows 10/11. Shake your mouse cursor to summon, bundle ZIP archives in one click, and attach straight to Outlook."
}

ROOT_DIR = Path(__file__).resolve().parent
BLOG_DIR = ROOT_DIR / "blog"
BLOG_EN_DIR = BLOG_DIR / "en"
POSTS_DIR = BLOG_DIR / "posts"
POSTS_EN_DIR = BLOG_DIR / "posts_en"

def parse_frontmatter(md_text: str):
    meta = {}
    body = md_text
    if md_text.startswith("---"):
        parts = md_text.split("---", 2)
        if len(parts) >= 3:
            raw_meta = parts[1].strip()
            body = parts[2].strip()
            for line in raw_meta.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if v.startswith("[") and v.endswith("]"):
                        v = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
                    meta[k] = v
    return meta, body

def md_to_html(md: str) -> str:
    lines = md.splitlines()
    out = []
    in_list = False
    in_code = False
    code_buf = []

    def inline_fmt(text: str) -> str:
        text = re.sub(r'`([^`]+)`', r'<code class="px-1.5 py-0.5 rounded bg-slate-800 text-sky-300 font-mono text-xs">\1</code>', text)
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong class="text-white font-bold">\1</strong>', text)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" class="text-sky-400 hover:text-sky-300 underline underline-offset-4 transition">\1</a>', text)
        return text

    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                out.append('<pre class="p-4 rounded-2xl bg-slate-900 border border-white/10 overflow-x-auto text-xs font-mono text-slate-200 my-5"><code>' + html.escape("\n".join(code_buf)) + '</code></pre>')
                code_buf = []
                in_code = False
            else:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                in_code = True
            continue
        if in_code:
            code_buf.append(line)
            continue

        s = line.strip()
        if not s:
            if in_list:
                out.append("</ul>")
                in_list = False
            continue

        if s.startswith("## "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f'<h2 class="text-2xl font-extrabold text-white mt-10 mb-4 tracking-tight">{inline_fmt(s[3:])}</h2>')
        elif s.startswith("### "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f'<h3 class="text-xl font-bold text-slate-100 mt-7 mb-3">{inline_fmt(s[4:])}</h3>')
        elif s.startswith("- ") or s.startswith("* "):
            if not in_list:
                out.append('<ul class="list-disc list-inside space-y-2.5 text-slate-300 my-4 leading-relaxed">')
                in_list = True
            out.append(f'<li>{inline_fmt(s[2:])}</li>')
        elif s.startswith("> "):
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f'<blockquote class="border-l-4 border-sky-500 pl-4 py-2 my-5 bg-slate-900/70 rounded-r-xl text-slate-300 italic">{inline_fmt(s[2:])}</blockquote>')
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f'<p class="text-slate-300 leading-relaxed my-4 text-base">{inline_fmt(s)}</p>')

    if in_list:
        out.append("</ul>")
    return "\n".join(out)

def render_post_html(post: dict, all_posts: list, lang: str = "zh") -> str:
    cfg = SITE_CONFIG
    is_en = (lang == "en")
    html_lang = "en" if is_en else "zh-Hant"
    zh_url = f"{cfg['base_url']}/blog/{post['slug']}.html"
    en_url = f"{cfg['base_url']}/blog/en/{post['slug']}.html"
    canonical_url = en_url if is_en else zh_url
    home_rel = "../../index.html" if is_en else "../index.html"
    lang_switch_href = f"../{post['slug']}.html" if is_en else f"en/{post['slug']}.html"
    lang_switch_label = "繁中" if is_en else "EN"
    rss_href = f"{cfg['base_url']}/blog/en/rss.xml" if is_en else f"{cfg['base_url']}/blog/rss.xml"

    tags = post.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    tags_html = "".join(f'<span class="px-2.5 py-1 rounded-full bg-slate-800 text-sky-300 text-xs font-semibold border border-white/10">#{html.escape(t)}</span>' for t in tags)

    ld_json = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "BlogPosting",
                "headline": post["title"],
                "description": post["description"],
                "datePublished": post["date"],
                "dateModified": post["date"],
                "inLanguage": html_lang,
                "author": {
                    "@type": "Organization",
                    "name": "Aisming / Kyte Suite",
                    "url": "https://kyteindex.aisming.com/"
                },
                "publisher": {
                    "@type": "Organization",
                    "name": cfg["site_name"],
                    "logo": {
                        "@type": "ImageObject",
                        "url": f"{cfg['base_url']}/{cfg['logo_path']}"
                    }
                },
                "mainEntityOfPage": {
                    "@type": "WebPage",
                    "@id": canonical_url
                },
                "keywords": ", ".join(tags)
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": cfg["site_name"], "item": f"{cfg['base_url']}/"},
                    {"@type": "ListItem", "position": 2, "name": "Blog", "item": f"{cfg['base_url']}/blog/en/" if is_en else f"{cfg['base_url']}/blog/"},
                    {"@type": "ListItem", "position": 3, "name": post["title"], "item": canonical_url}
                ]
            }
        ]
    }

    related_html = ""
    others = [p for p in all_posts if p["slug"] != post["slug"]][:2]
    if others:
        cards = []
        for o in others:
            cards.append(f'''
            <a href="{o['slug']}.html" class="block p-5 rounded-2xl bg-slate-900/90 border border-white/10 hover:border-sky-400/50 transition">
                <div class="text-xs text-sky-400 font-semibold mb-1">{html.escape(o['date'])} · {html.escape(o.get('category', 'Guide'))}</div>
                <div class="font-bold text-white text-base mb-1">{html.escape(o['title'])}</div>
                <div class="text-xs text-slate-400 line-clamp-2">{html.escape(o['description'])}</div>
            </a>''')
        rel_title = "Further Reading / More Articles" if is_en else "延伸閱讀 / More Articles"
        related_html = f'''
        <section class="mt-14 pt-10 border-t border-white/10">
            <h3 class="text-lg font-extrabold text-white mb-4">{rel_title}</h3>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">{"".join(cards)}</div>
        </section>'''

    nav_blog_label = "Blog" if is_en else "Blog 技術專欄"
    nav_all_posts = "All Articles" if is_en else "所有文章"
    nav_dl_btn = f"Free Download {cfg['site_name']}" if is_en else f"免費下載 {cfg['site_name']}"
    bc_home = "Home" if is_en else "首頁"
    cta_title = f"Experience {cfg['site_name']} on Windows Today" if is_en else f"立即體驗 {cfg['site_name']} 的極致效率"
    cta_desc = cfg["cta_desc_en"] if is_en else cfg["cta_desc"]
    cta_btn1 = "Free Download for Windows" if is_en else "免費下載 Windows 版"
    cta_btn2 = "Explore Full Features" if is_en else "了解完整功能"
    ft_home = "Official Website" if is_en else "官方首頁"
    ft_blog = "Blog Home" if is_en else "Blog 首頁"
    ft_suite = "Kyte Suite Blog" if is_en else "Kyte Suite 總站專欄"
    ft_suite_url = "https://kyteindex.aisming.com/blog/en/" if is_en else "https://kyteindex.aisming.com/blog/"

    return f'''<!DOCTYPE html>
<html lang="{html_lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(post['title'])} | {cfg['site_name']} Blog</title>
    <meta name="description" content="{html.escape(post['description'])}">
    <meta name="keywords" content="{html.escape(', '.join(tags))}">
    <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
    <link rel="canonical" href="{canonical_url}">
    <link rel="alternate" hreflang="zh-Hant" href="{zh_url}">
    <link rel="alternate" hreflang="en" href="{en_url}">
    <link rel="alternate" hreflang="x-default" href="{en_url}">
    <link rel="alternate" type="application/rss+xml" title="{cfg['site_name']} Blog RSS" href="{rss_href}">

    <!-- Open Graph / Social -->
    <meta property="og:type" content="article">
    <meta property="og:title" content="{html.escape(post['title'])}">
    <meta property="og:description" content="{html.escape(post['description'])}">
    <meta property="og:url" content="{canonical_url}">
    <meta property="og:site_name" content="{cfg['site_name']} Blog">
    <meta property="og:image" content="{cfg['base_url']}/{cfg['og_image']}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{html.escape(post['title'])}">
    <meta name="twitter:description" content="{html.escape(post['description'])}">

    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <script type="application/ld+json">
{json.dumps(ld_json, ensure_ascii=False, indent=2)}
    </script>
</head>
<body class="bg-slate-950 text-slate-100 antialiased selection:bg-sky-600 selection:text-white min-h-screen flex flex-col">
    <!-- Top Navbar -->
    <nav class="sticky top-0 z-50 backdrop-blur-xl bg-slate-950/85 border-b border-white/10">
        <div class="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <a href="{home_rel}" class="font-extrabold text-white text-lg hover:text-sky-400 transition">{cfg['site_name']}</a>
                <span class="text-slate-600">/</span>
                <a href="index.html" class="text-sm font-bold text-sky-400 hover:text-sky-300 transition">{nav_blog_label}</a>
            </div>
            <div class="flex items-center gap-3 sm:gap-4 text-xs font-bold">
                <a href="index.html" class="text-slate-300 hover:text-white transition"><i class="fa-solid fa-arrow-left mr-1"></i>{nav_all_posts}</a>
                <a href="{lang_switch_href}" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition flex items-center gap-1.5">
                    <i class="fa-solid fa-globe text-sky-400"></i>
                    <span>{lang_switch_label}</span>
                </a>
                <a href="{cfg['cta_url']}" class="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white shadow transition">{nav_dl_btn}</a>
            </div>
        </div>
    </nav>

    <!-- Article Main -->
    <main class="max-w-3xl mx-auto px-6 py-12 flex-1 w-full">
        <nav aria-label="Breadcrumb" class="text-xs text-slate-400 mb-6 flex items-center gap-2">
            <a href="{home_rel}" class="hover:text-white transition">{bc_home}</a>
            <span>/</span>
            <a href="index.html" class="hover:text-white transition">Blog</a>
            <span>/</span>
            <span class="text-slate-300 truncate">{html.escape(post['title'])}</span>
        </nav>

        <article>
            <header class="mb-8 pb-8 border-b border-white/10">
                <div class="flex flex-wrap items-center gap-3 text-xs text-sky-400 font-semibold mb-3">
                    <span class="px-2.5 py-0.5 rounded-full bg-sky-500/15 border border-sky-400/30">{html.escape(post.get('category', 'Guide'))}</span>
                    <time datetime="{html.escape(post['date'])}"><i class="fa-regular fa-calendar mr-1"></i>{html.escape(post['date'])}</time>
                    <span><i class="fa-regular fa-clock mr-1"></i>{html.escape(post.get('read_time', '5 min read'))}</span>
                </div>
                <h1 class="text-3xl sm:text-4xl font-black text-white leading-tight tracking-tight mb-4">{html.escape(post['title'])}</h1>
                <p class="text-slate-400 text-base leading-relaxed">{html.escape(post['description'])}</p>
                <div class="flex flex-wrap gap-2 mt-4">{tags_html}</div>
            </header>

            <div class="prose prose-invert max-w-none">
                {post['html_body']}
            </div>
        </article>

        <!-- Conversion CTA Box -->
        <div class="mt-12 p-8 rounded-3xl bg-gradient-to-br from-slate-900 via-slate-900 to-sky-950/60 border border-sky-500/30 shadow-xl text-center">
            <h3 class="text-2xl font-black text-white mb-2">{cta_title}</h3>
            <p class="text-sm text-slate-300 mb-6 max-w-xl mx-auto">{cta_desc}</p>
            <div class="flex flex-wrap items-center justify-center gap-3">
                <a href="{cfg['cta_url']}" class="px-6 py-3 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-sm shadow-lg transition flex items-center gap-2">
                    <i class="fa-brands fa-windows"></i>
                    <span>{cta_btn1}</span>
                </a>
                <a href="{home_rel}" class="px-5 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold text-sm border border-white/10 transition">
                    {cta_btn2}
                </a>
            </div>
        </div>

        {related_html}
    </main>

    <!-- Footer -->
    <footer class="border-t border-white/10 py-8 text-center text-xs text-slate-500">
        <div class="max-w-5xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div>© 2026 Aisming ({cfg['site_name']}). All rights reserved.</div>
            <div class="flex items-center gap-4">
                <a href="{home_rel}" class="hover:text-slate-300 transition">{ft_home}</a>
                <a href="index.html" class="hover:text-slate-300 transition">{ft_blog}</a>
                <a href="rss.xml" class="hover:text-slate-300 transition"><i class="fa-solid fa-rss mr-1"></i>RSS</a>
                <a href="{ft_suite_url}" class="hover:text-slate-300 transition">{ft_suite}</a>
            </div>
        </div>
    </footer>
</body>
</html>'''

def render_index_html(posts: list, lang: str = "zh") -> str:
    cfg = SITE_CONFIG
    is_en = (lang == "en")
    html_lang = "en" if is_en else "zh-Hant"
    zh_url = f"{cfg['base_url']}/blog/"
    en_url = f"{cfg['base_url']}/blog/en/"
    canonical_url = en_url if is_en else zh_url
    home_rel = "../../index.html" if is_en else "../index.html"
    sitemap_rel = "../../sitemap.xml" if is_en else "../sitemap.xml"
    lang_switch_href = "../index.html" if is_en else "en/index.html"
    lang_switch_label = "繁中" if is_en else "EN"
    rss_href = f"{cfg['base_url']}/blog/en/rss.xml" if is_en else f"{cfg['base_url']}/blog/rss.xml"
    blog_desc = cfg["blog_desc_en"] if is_en else cfg["blog_desc"]

    page_title = (
        f"{cfg['site_name']} Blog — Windows Desktop Productivity & File Management Insights"
        if is_en else
        f"{cfg['site_name']} Blog — Windows 桌面效率與檔案管理技術專欄"
    )
    h1_title = f"{cfg['site_name']} Productivity & Tech Blog" if is_en else f"{cfg['site_name']} 效率與技術專欄"
    read_more = "Read Article" if is_en else "閱讀全文"
    back_home = "Back to Official Site" if is_en else "返回官網首頁"
    dl_btn = "Free Download" if is_en else "免費下載"
    eco_heading = "Explore Other Kyte Suite Technical Blogs" if is_en else "探索 Kyte Suite 生態系其他技術專欄"
    eco_suffix = "/blog/en/" if is_en else "/blog/"
    eco_1 = "Kyte Suite Hub Blog" if is_en else "Kyte Suite 總站專欄"
    eco_2 = "KyteView Instant Preview Blog" if is_en else "KyteView 極速預覽專欄"
    eco_3 = "KyteShelf Staging Shelf Blog" if is_en else "KyteShelf 暫存置物架專欄"
    eco_4 = "KyteRename Batch Rename Blog" if is_en else "KyteRename 批次更名專欄"

    ld_json = {
        "@context": "https://schema.org",
        "@type": "Blog",
        "name": page_title,
        "description": blog_desc,
        "inLanguage": html_lang,
        "url": canonical_url,
        "publisher": {
            "@type": "Organization",
            "name": cfg["site_name"],
            "url": f"{cfg['base_url']}/"
        },
        "blogPost": [
            {
                "@type": "BlogPosting",
                "headline": p["title"],
                "description": p["description"],
                "datePublished": p["date"],
                "url": f"{canonical_url}{p['slug']}.html"
            }
            for p in posts
        ]
    }

    cards_html = []
    for p in posts:
        tags = p.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        t_badges = "".join(f'<span class="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[11px]">#{html.escape(t)}</span>' for t in tags[:4])
        cards_html.append(f'''
        <article class="p-6 sm:p-8 rounded-3xl bg-slate-900/90 border border-white/10 hover:border-sky-400/50 transition flex flex-col justify-between shadow-lg">
            <div>
                <div class="flex items-center gap-3 text-xs text-sky-400 font-semibold mb-3">
                    <span class="px-2.5 py-0.5 rounded-full bg-sky-500/15 border border-sky-400/30">{html.escape(p.get('category', 'Guide'))}</span>
                    <time datetime="{html.escape(p['date'])}">{html.escape(p['date'])}</time>
                    <span class="text-slate-500">· {html.escape(p.get('read_time', '5 min read'))}</span>
                </div>
                <h2 class="text-xl sm:text-2xl font-extrabold text-white mb-3 leading-snug">
                    <a href="{p['slug']}.html" class="hover:text-sky-400 transition">{html.escape(p['title'])}</a>
                </h2>
                <p class="text-slate-400 text-sm leading-relaxed mb-5">{html.escape(p['description'])}</p>
            </div>
            <div class="flex items-center justify-between pt-4 border-t border-white/5">
                <div class="flex flex-wrap gap-1.5">{t_badges}</div>
                <a href="{p['slug']}.html" class="text-xs font-bold text-sky-400 hover:text-sky-300 flex items-center gap-1 shrink-0">
                    <span>{read_more}</span>
                    <i class="fa-solid fa-arrow-right"></i>
                </a>
            </div>
        </article>''')

    return f'''<!DOCTYPE html>
<html lang="{html_lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(page_title)}</title>
    <meta name="description" content="{html.escape(blog_desc)}">
    <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
    <link rel="canonical" href="{canonical_url}">
    <link rel="alternate" hreflang="zh-Hant" href="{zh_url}">
    <link rel="alternate" hreflang="en" href="{en_url}">
    <link rel="alternate" hreflang="x-default" href="{en_url}">
    <link rel="alternate" type="application/rss+xml" title="{cfg['site_name']} Blog RSS" href="{rss_href}">

    <!-- Open Graph -->
    <meta property="og:type" content="website">
    <meta property="og:title" content="{html.escape(page_title)}">
    <meta property="og:description" content="{html.escape(blog_desc)}">
    <meta property="og:url" content="{canonical_url}">
    <meta property="og:image" content="{cfg['base_url']}/{cfg['og_image']}">
    <meta name="twitter:card" content="summary_large_image">

    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <script type="application/ld+json">
{json.dumps(ld_json, ensure_ascii=False, indent=2)}
    </script>
</head>
<body class="bg-slate-950 text-slate-100 antialiased selection:bg-sky-600 selection:text-white min-h-screen flex flex-col">
    <!-- Navbar -->
    <nav class="sticky top-0 z-50 backdrop-blur-xl bg-slate-950/85 border-b border-white/10">
        <div class="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <a href="{home_rel}" class="font-extrabold text-white text-xl hover:text-sky-400 transition">{cfg['site_name']}</a>
                <span class="text-xs px-2 py-0.5 rounded-full bg-sky-500/20 text-sky-300 border border-sky-400/30 font-bold">BLOG</span>
            </div>
            <div class="flex items-center gap-4 text-xs sm:text-sm font-semibold">
                <a href="{home_rel}" class="text-slate-300 hover:text-white transition">{back_home}</a>
                <a href="rss.xml" class="text-slate-400 hover:text-amber-400 transition" title="RSS Feed"><i class="fa-solid fa-rss"></i></a>
                <a href="{lang_switch_href}" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition flex items-center gap-1.5 text-xs font-bold">
                    <i class="fa-solid fa-globe text-sky-400"></i>
                    <span>{lang_switch_label}</span>
                </a>
                <a href="{cfg['cta_url']}" class="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs shadow transition">{dl_btn}</a>
            </div>
        </div>
    </nav>

    <!-- Header -->
    <header class="py-16 px-6 text-center border-b border-white/10 bg-gradient-to-b from-slate-900/80 to-slate-950">
        <div class="max-w-3xl mx-auto">
            <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-sky-500/10 border border-sky-400/30 text-sky-400 text-xs font-bold mb-4">
                <i class="fa-solid fa-pen-nib"></i> WINDOWS PRODUCTIVITY INSIGHTS
            </span>
            <h1 class="text-3xl sm:text-5xl font-black text-white tracking-tight mb-4">{h1_title}</h1>
            <p class="text-slate-400 text-base sm:text-lg leading-relaxed">{html.escape(blog_desc)}</p>
        </div>
    </header>

    <!-- Posts Grid -->
    <main class="max-w-5xl mx-auto px-6 py-14 flex-1 w-full">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            {"".join(cards_html)}
        </div>

        <!-- Ecosystem Blog Links -->
        <section class="mt-16 p-6 rounded-2xl bg-slate-900/60 border border-white/10 text-center">
            <h2 class="text-sm font-bold text-slate-300 mb-3">{eco_heading}</h2>
            <div class="flex flex-wrap items-center justify-center gap-4 text-xs font-semibold">
                <a href="https://kyteindex.aisming.com{eco_suffix}" class="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-indigo-300 transition">{eco_1}</a>
                <a href="https://kyteview.aisming.com{eco_suffix}" class="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-sky-300 transition">{eco_2}</a>
                <a href="https://kyteshelf.aisming.com{eco_suffix}" class="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-blue-300 transition">{eco_3}</a>
                <a href="https://kyterename.aisming.com{eco_suffix}" class="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-emerald-300 transition">{eco_4}</a>
            </div>
        </section>
    </main>

    <!-- Footer -->
    <footer class="border-t border-white/10 py-8 text-center text-xs text-slate-500">
        <div class="max-w-5xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div>© 2026 Aisming ({cfg['site_name']}). All rights reserved.</div>
            <div class="flex items-center gap-4">
                <a href="{home_rel}" class="hover:text-slate-300 transition">{back_home}</a>
                <a href="{sitemap_rel}" class="hover:text-slate-300 transition">Sitemap</a>
                <a href="rss.xml" class="hover:text-slate-300 transition">RSS Feed</a>
            </div>
        </div>
    </footer>
</body>
</html>'''

def render_rss_xml(posts: list, lang: str = "zh") -> str:
    cfg = SITE_CONFIG
    is_en = (lang == "en")
    base_blog_url = f"{cfg['base_url']}/blog/en/" if is_en else f"{cfg['base_url']}/blog/"
    desc = cfg["blog_desc_en"] if is_en else cfg["blog_desc"]
    lang_code = "en-us" if is_en else "zh-tw"
    items = []
    for p in posts:
        url = f"{base_blog_url}{p['slug']}.html"
        items.append(f'''    <item>
      <title>{html.escape(p['title'])}</title>
      <link>{url}</link>
      <guid>{url}</guid>
      <pubDate>{html.escape(p['date'])}</pubDate>
      <description>{html.escape(p['description'])}</description>
    </item>''')
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{cfg['site_name']} Blog ({lang.upper()})</title>
    <link>{base_blog_url}</link>
    <description>{html.escape(desc)}</description>
    <language>{lang_code}</language>
{chr(10).join(items)}
  </channel>
</rss>
'''

def update_sitemap(posts_zh: list, posts_en: list):
    cfg = SITE_CONFIG
    sitemap_path = ROOT_DIR / "sitemap.xml"
    today = datetime.now().strftime("%Y-%m-%d")

    base_urls = [
        (f"{cfg['base_url']}/", today, "weekly", "1.0"),
        (f"{cfg['base_url']}/blog/", today, "daily", "0.9"),
        (f"{cfg['base_url']}/blog/en/", today, "daily", "0.9"),
    ]
    if (ROOT_DIR / "guide.html").exists():
        base_urls.append((f"{cfg['base_url']}/guide.html", today, "monthly", "0.8"))
    if (ROOT_DIR / "guide_en.html").exists():
        base_urls.append((f"{cfg['base_url']}/guide_en.html", today, "monthly", "0.8"))
    if (ROOT_DIR / "privacy.html").exists():
        base_urls.append((f"{cfg['base_url']}/privacy.html", today, "monthly", "0.5"))
    if (ROOT_DIR / "terms.html").exists():
        base_urls.append((f"{cfg['base_url']}/terms.html", today, "monthly", "0.5"))

    for p in posts_zh:
        base_urls.append((f"{cfg['base_url']}/blog/{p['slug']}.html", p["date"], "monthly", "0.8"))
    for p in posts_en:
        base_urls.append((f"{cfg['base_url']}/blog/en/{p['slug']}.html", p["date"], "monthly", "0.8"))

    entries = []
    for loc, lastmod, freq, prio in base_urls:
        entries.append(f'''  <url>
    <loc>{loc}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>{freq}</changefreq>
    <priority>{prio}</priority>
  </url>''')

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(entries) + '\n</urlset>\n'
    sitemap_path.write_text(xml, encoding="utf-8")
    print(f"[OK] Updated {sitemap_path} ({len(base_urls)} URLs)")

def load_posts_from_dir(directory: Path) -> list:
    posts = []
    if not directory.exists():
        return posts
    for md_file in sorted(directory.glob("*.md"), reverse=True):
        raw = md_file.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(raw)
        slug = meta.get("slug", md_file.stem)
        post = {
            "slug": slug,
            "title": meta.get("title", slug),
            "description": meta.get("description", ""),
            "date": meta.get("date", datetime.now().strftime("%Y-%m-%d")),
            "category": meta.get("category", "Guide"),
            "read_time": meta.get("read_time", "5 min read"),
            "tags": meta.get("tags", []),
            "html_body": md_to_html(body),
        }
        posts.append(post)
    posts.sort(key=lambda x: x["date"], reverse=True)
    return posts

def main():
    BLOG_DIR.mkdir(parents=True, exist_ok=True)
    BLOG_EN_DIR.mkdir(parents=True, exist_ok=True)
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    POSTS_EN_DIR.mkdir(parents=True, exist_ok=True)

    posts_zh = load_posts_from_dir(POSTS_DIR)
    posts_en = load_posts_from_dir(POSTS_EN_DIR)

    for p in posts_zh:
        out_file = BLOG_DIR / f"{p['slug']}.html"
        out_file.write_text(render_post_html(p, posts_zh, lang="zh"), encoding="utf-8")
    (BLOG_DIR / "index.html").write_text(render_index_html(posts_zh, lang="zh"), encoding="utf-8")
    (BLOG_DIR / "rss.xml").write_text(render_rss_xml(posts_zh, lang="zh"), encoding="utf-8")

    for p in posts_en:
        out_file = BLOG_EN_DIR / f"{p['slug']}.html"
        out_file.write_text(render_post_html(p, posts_en, lang="en"), encoding="utf-8")
    (BLOG_EN_DIR / "index.html").write_text(render_index_html(posts_en, lang="en"), encoding="utf-8")
    (BLOG_EN_DIR / "rss.xml").write_text(render_rss_xml(posts_en, lang="en"), encoding="utf-8")

    update_sitemap(posts_zh, posts_en)

if __name__ == "__main__":
    main()
