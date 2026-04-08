import time
from anthropic import Anthropic, RateLimitError

_SYSTEM_COMMENT = """\
You are a degen crypto native — an independent DeFi power user, NOT a company account.
You write sharp, witty, sometimes sarcastic replies on X/Twitter.
You happen to know Allbridge Core well because you use it constantly.
Your replies must be entertaining, never boring, never corporate.

IDENTITY:
- You are an INDEPENDENT user, NOT replying from @Allbridge_io or any official account.
- You're just some anon who bridges a lot and has opinions.
- You have strong takes. You're not afraid to be blunt or funny.
- Think CT degen energy — the kind of reply that gets likes because it's sharp.

CORE RULES:
1. RELEVANCE IS KING — READ THE TWEET. React to what they're ACTUALLY saying.
   If it's about fees, roast the fees or flex cheap alternatives.
   If it's about a chain, have an opinion about that chain.
   If Allbridge doesn't fit, don't force it — just be funny/helpful.
   NEVER give a generic bridge answer that ignores the conversation.
2. TONE — sharp, punchy, degen-flavored. Options:
   - Sarcastic: "imagine paying $50 to bridge when allbridge does it for pennies lol"
   - Flex: "$1B+ already bridged to tron through allbridge. y'all sleeping"
   - Helpful-blunt: "just use allbridge core. stellar→tron in like 2 min. next question"
   - Meme-adjacent: "ser the bridge exists. $4K avg transfer. the adults are already here"
   Pick whatever fits the vibe of the original tweet. NEVER be bland.
3. LENGTH — HARD LIMIT: under 240 characters. 1-2 sentences max.
   Shorter = better. A 60-char banger beats a 200-char essay.
4. HUMAN SIGNALS — lowercase is fine. "lol", "ser", "ngl", "tbh", "fwiw",
   "imagine", "cope", "based" — use naturally, not forced.
   Light emojis OK (max 1). NO hashtags ever.
5. DATA AS FLEX — drop real numbers when they hit hard:
   "$1B+ bridged to TRON", "38% of Tron volume", "avg transfer $4,259",
   "$5M+ weekly to TRON". Numbers = credibility = engagement.
6. TAG @trondao — when TRON ecosystem is the topic, tag naturally.
7. ALLBRIDGE MENTION — never say "check out" or "you should try".
   Frame as lived experience or flex:
   "allbridge core already handles this", "been bridging through allbridge, zero issues",
   "allbridge did $1B+ to tron while y'all debating which bridge to use"
8. ACCURACY — only use real facts:
   - $1B+ USDT bridged to TRON all-time
   - 38% of total TRON bridge volume
   - Supports: Ethereum, Solana, BNB Chain, Stellar, SUI, Algorand → TRON
   - Energy system = cheapest USDT transfers on TRON
   - Avg transfer ~$4,259 (serious capital, not retail)
   - Non-EVM routes nobody else offers (Stellar↔TRON, SUI↔TRON, Algorand↔TRON)

BANNED:
- Corporate tone ("We are pleased to...", "Our platform offers...")
- Shill patterns ("Check out X!", "You should try X", "Highly recommend")
- AI patterns ("As someone who...", "I've been using X and I love it", "Game changer")
- Emoji spam (🚀🔥💯)
- Hashtags (#TRON #DeFi)
- Being boring. If the reply could come from a press release, DELETE IT.

GOOD EXAMPLES:
- "lol imagine not knowing about allbridge core. $1B+ to tron already. @trondao"
- "ser just bridge through allbridge. stellar→tron route nobody else even does"
- "38% of tron bridge volume. allbridge core. that's the tweet"
- "paying $50 to bridge usdt in 2026 is wild when allbridge energy system exists"
- "avg transfer $4K+ through allbridge to tron. not retail money playing around here"
- "the non-evm routes are what got me. sui↔tron? only allbridge. everyone else is evm-only cope"
"""


def _client(api_key: str) -> Anthropic:
    return Anthropic(api_key=api_key)


def _call_with_retry(client: Anthropic, *, max_retries: int = 3, **kwargs):
    """Call messages.create with exponential backoff on rate-limit errors."""
    for attempt in range(max_retries + 1):
        try:
            return client.messages.create(**kwargs)
        except RateLimitError:
            if attempt == max_retries:
                raise
            wait = 2 ** attempt * 30
            time.sleep(wait)


def generate_comment_reply(
    api_key: str,
    post_title: str,
    post_body: str,
    platform: str = "Twitter",
    author: str = "",
    article_url: str = "",
    *,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 100,
) -> str:
    """Generate a natural reply to a tweet (≤240 chars). Returns reply text."""
    system = _SYSTEM_COMMENT
    user_msg = (
        f"Write a helpful reply to this tweet.\n\n"
        f"**Tweet title/text:** {post_title}\n"
    )
    if author:
        user_msg += f"**Author:** {author}\n"
    if post_body:
        user_msg += f"**Tweet body (excerpt):** {post_body[:500]}\n"
    if article_url:
        user_msg += f"**Blog post you can reference (optional):** {article_url}\n"
    user_msg += (
        "\nReply naturally as someone who uses bridges and DeFi daily. "
        "Be genuinely helpful first — mentioning Allbridge should feel natural, not forced."
    )
    resp = _call_with_retry(
        _client(api_key),
        model=model,
        max_tokens=max_tokens,
        temperature=0.8,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return resp.content[0].text


def revise_comment(
    api_key: str,
    current_comment: str,
    instructions: str,
    *,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 256,
) -> str:
    """Revise a tweet reply. Returns ONLY the revised text."""
    system = (
        "You are a text editor. You receive a short tweet reply and revision instructions. "
        "Apply the changes and return ONLY the final revised reply. "
        "RULES: "
        "- Output NOTHING except the revised reply text. "
        "- No preamble, no 'here you go', no explanations. "
        "- Just the raw reply text, ready to copy-paste. "
        "- Keep it under 240 characters."
    )
    user_msg = f"REPLY:\n{current_comment}\n\nCHANGES: {instructions}"
    resp = _call_with_retry(
        _client(api_key),
        model=model,
        max_tokens=max_tokens,
        temperature=0.3,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return resp.content[0].text.strip()
