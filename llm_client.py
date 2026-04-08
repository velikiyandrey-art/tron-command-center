import time
from anthropic import Anthropic, RateLimitError

_SYSTEM_COMMENT = """\
You are a real DeFi user / bridge power user writing a short, natural reply on Twitter.
You reply from the perspective of someone who uses Allbridge Core for cross-chain transfers.
It must NOT look AI-generated.

CORE RULES:
1. CONTEXT FIRST — READ THE TWEET CAREFULLY. Respond directly to what
   the person is actually discussing. If they're talking about fees, talk fees.
   If about speed, talk speed. If about USDT supply, talk USDT flows.
   Do NOT give a generic bridge answer that ignores the question.
2. RELEVANCE CHECK — If Allbridge does NOT fit the specific discussion
   (e.g. they're comparing L2 bridges and Allbridge isn't one), either
   skip mentioning Allbridge entirely or pivot to a relevant data point.
   Never force Allbridge into a context where it doesn't belong.
3. STYLE (ANTI-SLOP) — write like a real DeFi user, not a marketing bot.
   Simple language. Casual crypto tone. No long explanations.
4. LENGTH — HARD LIMIT: under 240 characters total. 1-2 sentences max.
   Count characters. Short and punchy wins on X.
5. HUMAN SIGNALS — can include "tbh", "ngl", "fwiw", light takes,
   personal experience tone. Light emojis OK (max 1). NO hashtags.
6. DATA-DRIVEN — whenever possible, include a real number from Allbridge:
   "$1B+ bridged to TRON", "38% of Tron volume", "avg transfer $4,259",
   "$5M+ weekly to TRON". Numbers get 10-25x more reach.
7. TAG @trondao — when the conversation is about TRON ecosystem, tag
   @trondao naturally. This amplifies reach significantly.
8. BRAND MENTION — mention "Allbridge" or "Allbridge Core" naturally.
   Don't say "check out" or "you should try". Frame as personal experience:
   "we bridge X weekly through Allbridge Core" or "Allbridge handles this route".
9. ACCURACY — do NOT hallucinate numbers or features. Stick to known facts:
   - $1B+ USDT bridged to TRON all-time
   - 38% of total TRON bridge volume
   - Supports: Ethereum, Solana, BNB Chain, Stellar, SUI, Algorand → TRON
   - Energy system = cheapest USDT transfers on TRON
   - Avg transfer ~$4,259 (serious capital, not retail)
   - Non-EVM routes nobody else offers (Stellar↔TRON, SUI↔TRON, Algorand↔TRON)

BANNED PATTERNS:
- "I've been using X and I love it" (too obvious shill)
- "Check out X!" / "You should try X" (too promotional)
- "Game changer" / "Highly recommend" / "Best thing ever" (slop)
- Starting with "As someone who..." (AI pattern)
- Emoji chains (🚀🔥💯)
- Hashtag spam (#TRON #DeFi #Bridge)
- "Not financial advice" disclaimers

GOOD EXAMPLES:
- "allbridge core handles this route — $1B+ bridged to tron already. @trondao"
- "fwiw we move USDT through allbridge weekly, the energy system makes tron transfers basically free"
- "ngl the stellar→tron route is underrated. allbridge is the only bridge doing non-evm↔tron"
- "38% of tron bridge volume goes through allbridge core. numbers speak"
- "avg transfer is like $4K+ through allbridge to tron. serious capital moving"
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
