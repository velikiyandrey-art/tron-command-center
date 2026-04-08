import streamlit as st
import json
import os
import re
import pandas as pd

st.set_page_config(page_title="Allbridge x TRON", page_icon="🔴", layout="wide", initial_sidebar_state="collapsed")

# ── Page: Static Dashboard ──
def page_dashboard():
    with open("tron-dashboard.html", "r") as f:
        html = f.read()
    # Inject the app's base URL for cross-iframe navigation links
    try:
        host = st.context.headers.get("Host", "")
        if host:
            proto = "https" if "streamlit" in host or "443" in host else "http"
            base_url = f"{proto}://{host}/"
        else:
            base_url = "http://localhost:8501/"
    except Exception:
        base_url = "http://localhost:8501/"
    html = html.replace("__APP_BASE_URL__", base_url)
    st.components.v1.html(html, height=4000, scrolling=True)


# ── X Distribution: State Persistence ──
_DIST_CACHE = "distribution_cache.json"

def _save_distribution_state():
    state = {
        "fetched_posts": st.session_state.get("fetched_posts", []),
        "comment_queue": st.session_state.get("comment_queue", []),
        "twitter_found": st.session_state.get("twitter_found", []),
    }
    with open(_DIST_CACHE, "w") as f:
        json.dump(state, f, default=str)

def _load_distribution_state():
    if os.path.exists(_DIST_CACHE):
        try:
            with open(_DIST_CACHE) as f:
                state = json.load(f)
            for key in ["fetched_posts", "comment_queue", "twitter_found"]:
                if key in state and key not in st.session_state:
                    st.session_state[key] = state[key]
        except Exception:
            pass


# ── X Distribution: Search Queries ──
TWITTER_QUERIES = [
    'site:twitter.com OR site:x.com "bridge to tron"',
    'site:twitter.com OR site:x.com "send USDT to tron"',
    'site:twitter.com OR site:x.com "USDT TRC-20" bridge OR transfer OR send',
    'site:twitter.com OR site:x.com "cheapest way" USDT tron',
    'site:twitter.com OR site:x.com "how to get USDT on tron"',
    'site:twitter.com OR site:x.com tron bridge -from:Allbridge_io',
    'site:twitter.com OR site:x.com "cross-chain" tron OR @trondao',
    'site:twitter.com OR site:x.com SunPump OR SunSwap "need USDT"',
    'site:twitter.com OR site:x.com "best tron bridge"',
    'site:twitter.com OR site:x.com "USDT bridge" cheapest fees',
    'site:twitter.com OR site:x.com allbridge tron',
    'site:twitter.com OR site:x.com "bridge USDT" ethereum tron',
]


# ── X Distribution: SerpAPI Search ──
def _serpapi_search_twitter(custom_q: str, num_q: int, serpapi_key: str) -> list[dict]:
    import requests

    queries = []
    site_prefix = "site:twitter.com OR site:x.com"
    if custom_q:
        queries.append(f"{site_prefix} {custom_q}")
    queries.extend(TWITTER_QUERIES[:num_q])

    all_posts = []
    seen = set()
    progress = st.progress(0)

    for i, q in enumerate(queries):
        try:
            resp = requests.get("https://serpapi.com/search.json", params={
                "api_key": serpapi_key,
                "engine": "google",
                "q": q,
                "num": 10,
                "tbs": "qdr:m3",
            }, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("organic_results", []):
                    link = item.get("link", "")
                    if link in seen:
                        continue
                    seen.add(link)
                    m = re.search(r'(?:twitter|x)\.com/(\w+)/status', link)
                    if not m:
                        continue
                    all_posts.append({
                        "title": item.get("title", "")[:120],
                        "author": f"@{m.group(1)}",
                        "snippet": item.get("snippet", "")[:200],
                        "url": link,
                        "platform": "Twitter",
                        "keyword": q.replace("site:twitter.com OR site:x.com ", ""),
                    })
        except Exception:
            pass
        progress.progress((i + 1) / len(queries))

    progress.empty()
    return all_posts[:30]


# ── X Distribution: Display Found Tweets ──
def _show_twitter_results():
    found = st.session_state.get("twitter_found", [])
    if not found:
        return

    st.success(f"Found {len(found)} tweets")

    col_sel, col_send = st.columns([3, 2])
    with col_sel:
        if st.button("Select All", key="select_all_tweets"):
            for i in range(len(found)):
                st.session_state[f"tsel_{i}"] = True
            st.rerun()
        if st.button("Deselect All", key="deselect_all_tweets"):
            for i in range(len(found)):
                st.session_state[f"tsel_{i}"] = False
            st.rerun()

    selected_urls = []
    for i, post in enumerate(found):
        with st.container(border=True):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"**{post['title'][:80]}** — {post['author']}")
                if post.get("snippet"):
                    st.caption(post["snippet"][:120] + "...")
            with col2:
                if st.checkbox("Select", key=f"tsel_{i}"):
                    selected_urls.append(post["url"])

    with col_send:
        if st.button(f"Send {len(selected_urls)} to Draft Replies", type="primary",
                     disabled=not selected_urls):
            existing = st.session_state.get("prefilled_urls", "")
            new_urls = "\n".join(selected_urls)
            st.session_state["prefilled_urls"] = (existing + "\n" + new_urls).strip()

            post_cache = st.session_state.get("post_metadata_cache", {})
            for p in found:
                if p["url"] in selected_urls:
                    post_cache[p["url"]] = {
                        "title": p.get("title", ""),
                        "snippet": p.get("snippet", ""),
                        "author": p.get("author", ""),
                        "keyword": p.get("keyword", ""),
                        "platform": "Twitter",
                    }
            st.session_state["post_metadata_cache"] = post_cache
            st.success(f"Added {len(selected_urls)} URLs! Switch to **Draft Replies** tab.")


# ── X Distribution: Fetch Tweet Context ──
def _fetch_tweet(url: str) -> dict:
    import requests

    post = {"url": url, "title": "", "body": "", "author": "", "platform": "Twitter", "keyword": ""}

    post_cache = st.session_state.get("post_metadata_cache", {})
    if url in post_cache:
        cached = post_cache[url]
        post["title"] = cached.get("title", "")
        post["body"] = cached.get("snippet", "")
        post["author"] = cached.get("author", "")
        post["keyword"] = cached.get("keyword", "")
        if post["title"] and post["body"]:
            return post

    m = re.search(r'(?:twitter|x)\.com/(\w+)/status', url)
    post["author"] = f"@{m.group(1)}" if m else ""
    post["title"] = f"Tweet by {post['author']}" if post["author"] else "Tweet"

    serpapi_key = st.session_state.get("serpapi_key", "")
    if serpapi_key and not post.get("body"):
        try:
            resp = requests.get("https://serpapi.com/search.json", params={
                "api_key": serpapi_key,
                "engine": "google",
                "q": url,
                "num": 1,
            }, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                organic = data.get("organic_results", [])
                if organic:
                    snippet = organic[0].get("snippet", "")
                    title = organic[0].get("title", "")
                    if snippet:
                        post["body"] = snippet[:500]
                        post["title"] = title[:120] if title else post["title"]
        except Exception:
            pass
    return post


# ── X Distribution: Generate Replies ──
def _generate_all_comments(fetched_posts, api_key, ref_url=""):
    from llm_client import generate_comment_reply

    queue = []  # Clear previous queue — fresh generation each time
    progress = st.progress(0)
    status = st.empty()

    for i, post in enumerate(fetched_posts):

        status.text(f"Generating reply for: {post['title'][:50]}...")
        try:
            comment = generate_comment_reply(
                api_key,
                post_title=post["title"],
                post_body=post.get("body", ""),
                platform="Twitter",
                author=post.get("author", ""),
                article_url=ref_url,
            )
            queue.append({
                "url": post["url"],
                "title": post["title"],
                "platform": "Twitter",
                "author": post.get("author", ""),
                "comment": comment,
                "status": "draft",
                "keyword": post.get("keyword", ""),
            })
        except Exception as e:
            queue.append({
                "url": post["url"],
                "title": post["title"],
                "platform": "Twitter",
                "author": post.get("author", ""),
                "comment": f"[Error: {e}]",
                "status": "error",
                "keyword": post.get("keyword", ""),
            })
        progress.progress((i + 1) / len(fetched_posts))

    st.session_state["comment_queue"] = queue
    _save_distribution_state()
    status.empty()
    progress.empty()
    return queue


# ── Page: X Distribution ──
def page_x_distribution():
    st.title("X Distribution")
    st.caption("Find relevant tweets → generate natural replies → track posting → push to Google Sheets")

    with st.container(border=True):
        st.markdown("**Rules:** 1. Never shill under negative/hack posts. "
                    "2. Add value first — data, then mention Allbridge. "
                    "3. Max 3-4 replies per account per week. "
                    "4. Tag @trondao when relevant. "
                    "5. Match the original post's tone.")

    _load_distribution_state()

    def _get_secret(key, default=""):
        try:
            return st.secrets.get(key, default)
        except Exception:
            return default

    api_key = st.session_state.get("anthropic_key") or _get_secret("ANTHROPIC_API_KEY")
    serpapi_key = st.session_state.get("serpapi_key") or _get_secret("SERPAPI_KEY")

    # API keys directly on the page
    if not api_key or not serpapi_key:
        with st.container(border=True):
            st.markdown("**API Keys**")
            col_a, col_s = st.columns(2)
            with col_s:
                if not serpapi_key:
                    serpapi_input = st.text_input("SerpAPI Key (for tweet search)", type="password",
                                                  key="serpapi_key_input",
                                                  placeholder="Paste your serpapi.com key")
                    if serpapi_input:
                        st.session_state["serpapi_key"] = serpapi_input
                        serpapi_key = serpapi_input
                else:
                    st.success("SerpAPI key set")
            with col_a:
                if not api_key:
                    api_input = st.text_input("Anthropic API Key (for reply generation)", type="password",
                                              key="anthropic_key_input",
                                              placeholder="sk-ant-...")
                    if api_input:
                        st.session_state["anthropic_key"] = api_input
                        api_key = api_input
                else:
                    st.success("Anthropic key set")

    ref_url = ""

    tab_search, tab_drafts, tab_tracker = st.tabs(["Find Tweets", "Draft Replies", "Queue"])

    # ── Tab 1: Find Tweets ──
    with tab_search:
        if not serpapi_key:
            st.warning("Add your **SerpAPI key** in the sidebar to search.")

        col1, col2 = st.columns([3, 1])
        with col1:
            twitter_q = st.text_input("Custom search", placeholder='e.g. "bridge USDT to tron"')
        with col2:
            twitter_n = st.number_input("Queries", value=4, min_value=1, max_value=12,
                                         help="1 SerpAPI credit per query")

        if st.button("Search X/Twitter", type="primary", disabled=not serpapi_key):
            results = _serpapi_search_twitter(twitter_q, twitter_n, serpapi_key)
            st.session_state["twitter_found"] = results[:30]
            _save_distribution_state()
            st.rerun()

        _show_twitter_results()

    # ── Tab 2: Draft Replies ──
    with tab_drafts:
        st.subheader("Draft Replies")

        prefilled = st.session_state.get("prefilled_urls", "")
        urls_text = st.text_area("Paste tweet URLs (one per line)", value=prefilled or "",
                                  height=200, placeholder="https://x.com/user/status/123456...")

        col_fetch, col_gen = st.columns(2)
        with col_fetch:
            if st.button("Fetch Tweets", type="primary", disabled=not urls_text.strip()):
                urls = [u.strip() for u in urls_text.strip().split("\n") if u.strip()]
                fetched = [_fetch_tweet(url) for url in urls]
                st.session_state["fetched_posts"] = fetched
                _save_distribution_state()
                st.rerun()

        with col_gen:
            fetched = st.session_state.get("fetched_posts", [])
            if not api_key and fetched:
                st.warning("Add Anthropic API key to generate replies.")
            if st.button("Generate All Replies", type="primary",
                         disabled=not api_key or not fetched):
                _generate_all_comments(fetched, api_key, ref_url)
                st.success("Replies generated! Go to **Queue** tab.")
                st.rerun()

        fetched = st.session_state.get("fetched_posts", [])
        if fetched:
            st.divider()
            st.markdown(f"### {len(fetched)} tweets fetched")
            for i, post in enumerate(fetched):
                st.markdown(f"{i+1}. **{post['title'][:80]}** — {post.get('author', '')}")

    # ── Tab 3: Queue ──
    with tab_tracker:
        st.subheader("Reply Queue")
        queue = st.session_state.get("comment_queue", [])

        if not queue:
            st.info("No replies yet. Find tweets → Draft replies first.")
        else:
            total = len(queue)
            posted = sum(1 for q in queue if q["status"] == "posted")
            drafts_count = sum(1 for q in queue if q["status"] == "draft")
            c1, c2, c3 = st.columns(3)
            c1.metric("Total", total)
            c2.metric("Drafts", drafts_count)
            c3.metric("Posted", posted)

            revise_all_text = st.text_input("Revise all drafts:", placeholder="e.g. shorter, add @trondao tag")
            if st.button("Revise All Drafts", disabled=not api_key or not revise_all_text):
                from llm_client import revise_comment
                drafts = [i for i, q in enumerate(queue) if q["status"] == "draft"]
                progress = st.progress(0)
                for j, idx in enumerate(drafts):
                    try:
                        queue[idx]["comment"] = revise_comment(api_key, queue[idx]["comment"], revise_all_text)
                        st.session_state[f"q_ver_{idx}"] = st.session_state.get(f"q_ver_{idx}", 0) + 1
                    except Exception:
                        pass
                    progress.progress((j + 1) / len(drafts))
                st.session_state["comment_queue"] = queue
                _save_distribution_state()
                progress.empty()
                st.rerun()

            st.divider()

            for i, item in enumerate(queue):
                with st.container(border=True):
                    icon = {"draft": "📝", "posted": "✅", "error": "❌"}.get(item["status"], "📝")
                    st.markdown(f"{icon} **[{item['title'][:70]}]({item['url']})** — {item.get('author', '')}")

                    ver = st.session_state.get(f"q_ver_{i}", 0)
                    edited = st.text_area("Reply", value=item["comment"], height=100,
                                          key=f"q_comment_{i}_{ver}", label_visibility="collapsed")
                    queue[i]["comment"] = edited

                    char_count = len(edited)
                    if char_count > 280:
                        st.error(f"{char_count}/280 characters — too long!")
                    else:
                        st.caption(f"{char_count}/280 characters")

                    rev_text = st.text_input("Revision instructions:", placeholder="make it shorter and funnier",
                                             key=f"q_rev_{i}")

                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.markdown(f"[Open tweet]({item['url']})")
                    with col2:
                        if st.button("Revise", key=f"q_rev_btn_{i}", disabled=not api_key or not rev_text):
                            from llm_client import revise_comment
                            try:
                                queue[i]["comment"] = revise_comment(api_key, edited, rev_text)
                                st.session_state[f"q_ver_{i}"] = ver + 1
                                st.session_state["comment_queue"] = queue
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")
                    with col3:
                        if item["status"] != "posted":
                            if st.button("Mark Posted", key=f"q_posted_{i}"):
                                queue[i]["status"] = "posted"
                                st.session_state["comment_queue"] = queue
                                _save_distribution_state()
                                st.rerun()
                    with col4:
                        st.download_button("Copy", data=edited, file_name=f"reply_{i}.txt",
                                           mime="text/plain", key=f"q_dl_{i}")

            st.session_state["comment_queue"] = queue
            _save_distribution_state()

            # ── Export section ──
            st.divider()
            export_rows = []
            for item in queue:
                export_rows.append({
                    "Tweet URL": item["url"],
                    "Tweet Text": item["title"],
                    "Author": item.get("author", ""),
                    "Our Reply": item["comment"],
                    "Status": item["status"],
                    "Keyword": item.get("keyword", ""),
                    "Date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                })
            export_df = pd.DataFrame(export_rows)
            csv_data = export_df.to_csv(index=False)

            col_exp1, col_exp2, col_exp3 = st.columns(3)
            with col_exp1:
                st.download_button("Export All CSV", data=csv_data,
                                   file_name=f"x_replies_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                                   mime="text/csv")
            with col_exp2:
                draft_rows = [r for r in export_rows if r["Status"] == "draft"]
                if draft_rows:
                    st.download_button(f"Export {len(draft_rows)} Drafts",
                                       data=pd.DataFrame(draft_rows).to_csv(index=False),
                                       file_name=f"x_drafts_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                                       mime="text/csv")
            with col_exp3:
                gsheets_creds = st.session_state.get("gsheets_json") or _get_secret("gsheets")
                if st.button("Push to Google Sheets", type="primary", disabled=not gsheets_creds):
                    from sheets_client import push_comments
                    try:
                        n = push_comments(gsheets_creds, queue)
                        if n:
                            st.success(f"Pushed {n} new replies to Google Sheets")
                        else:
                            st.info("All replies already in sheet.")
                    except Exception as e:
                        st.error(f"Failed: {e}")


# ── Routing via query params ──
page = st.query_params.get("page", "dashboard")

if page == "x_distribution":
    # Hide Streamlit sidebar and header chrome
    st.markdown("""<style>
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        header[data-testid="stHeader"] { display: none !important; }
    </style>""", unsafe_allow_html=True)
    if st.button("← Back to Command Center"):
        st.query_params.clear()
        st.rerun()
    page_x_distribution()
else:
    # Hide Streamlit sidebar on dashboard — HTML has its own
    st.markdown("""<style>
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        header[data-testid="stHeader"] { display: none !important; }
        .stMainBlockContainer { padding: 0 !important; max-width: 100vw !important; width: 100vw !important; }
        .stMain { padding: 0 !important; }
        [data-testid="stAppViewBlockContainer"] { padding: 0 !important; max-width: 100vw !important; }
        [data-testid="stVerticalBlockBorderWrapper"] { width: 100vw !important; max-width: 100vw !important; }
        [data-testid="element-container"] { width: 100vw !important; max-width: 100vw !important; }
        iframe[title="st.iframe"] { width: 100vw !important; min-width: 100vw !important; overflow: visible !important; }
    </style>""", unsafe_allow_html=True)
    page_dashboard()
