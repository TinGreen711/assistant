from openai import OpenAI

from config import OPENAI_API_KEY

# timeout=60s — покрывает weekly_summary (~30с) с запасом, режет зависания
# max_retries=2 — SDK сам повторит при 429 (rate limit), 5xx и timeout
client = OpenAI(api_key=OPENAI_API_KEY, timeout=60.0, max_retries=2)
