import html
import re
import ssl
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import certifi
import feedparser

from config import (
    MAIL_ITEMS_IN_PROMPT,
    PERSONAS,
    RSS_ITEMS_IN_PROMPT,
    RSS_ITEMS_PER_FEED,
    RSS_SUMMARY_CHARS,
    RSS_TIMEOUT,
    RSS_USER_AGENT,
    VEILLE_INSTRUCTION,
)
from db import get_user_persona, list_feeds, mark_feed, recent_articles, upsert_article
#flux_rss_email
from mail_watcher import matches_theme, refresh_mailbox

_TAGS = re.compile(r"<[^>]+>")


#flux RSS
class RssError(Exception):
    pass


#flux RSS
def _plain(value):
    text = html.unescape(_TAGS.sub(" ", value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:RSS_SUMMARY_CHARS]


#flux RSS
def _published(entry):
    stamp = entry.get("published_parsed") or entry.get("updated_parsed")
    if not stamp:
        return ""
    return time.strftime("%Y-%m-%d %H:%M", stamp)


#flux RSS
def _download(url):
    # Python.org sur macOS n'a pas les certificats du système. certifi les fournit.
    context = ssl.create_default_context(cafile=certifi.where())
    request = urllib.request.Request(url, headers={"User-Agent": RSS_USER_AGENT})
    with urllib.request.urlopen(request, timeout=RSS_TIMEOUT, context=context) as response:
        return response.read()


#flux RSS
def fetch_entries(url):
    # Le corps est parsé tel quel : EasyBourse annonce text/html alors que c'est du RSS.
    parsed = feedparser.parse(_download(url))
    if parsed.bozo and not parsed.entries:
        raise RssError(str(parsed.bozo_exception))
    entries = []
    for entry in parsed.entries[:RSS_ITEMS_PER_FEED]:
        link = (entry.get("link") or "").strip()
        title = _plain(entry.get("title")) or "(sans titre)"
        guid = (entry.get("id") or link or title).strip()
        entries.append({
            "guid": guid,
            "title": title,
            "link": link,
            "summary": _plain(entry.get("summary") or entry.get("description")),
            "published_at": _published(entry),
        })
    return entries


#flux RSS
def refresh_user(user_id):
    feeds = [
        feed for feed in list_feeds(user_id)
        if feed["active"] and feed["kind"] == "rss"
    ]
    errors = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(fetch_entries, feed["url"]): feed
            for feed in feeds
        }
        for future in as_completed(futures):
            feed = futures[future]
            try:
                entries = future.result()
            except Exception as error:
                mark_feed(feed["id"], str(error))
                errors.append(f"{feed['name']} : {error}")
                continue
            for entry in entries:
                upsert_article(user_id, feed["id"], **entry)
            mark_feed(feed["id"], None)
    #flux_rss_email
    errors.extend(refresh_mailbox(user_id))
    return errors


#flux_rss_email
def _digest_lines(rows):
    lines = []
    for row in rows:
        when = row["published_at"] or "date inconnue"
        lines.append(f"- {row['source']} — {row['title']} ({when})")
        if row["link"]:
            lines.append(f"  {row['link']}")
        if row["summary"]:
            lines.append(f"  {row['summary']}")
    return lines


#flux RSS
#flux_rss_email
def digest_for(user_id):
    rss_rows = recent_articles(user_id, RSS_ITEMS_IN_PROMPT, kind="rss")
    #flux_rss_email
    # Les newsletters de septembre ne doivent pas être chassées par les flux du jour.
    persona = get_user_persona(user_id)
    mail_rows = [
        row for row in recent_articles(user_id, MAIL_ITEMS_IN_PROMPT, kind="email")
        if matches_theme(persona, row["title"], row["summary"])
    ]
    if not rss_rows and not mail_rows:
        return ""
    lines = [VEILLE_INSTRUCTION, ""]
    if rss_rows:
        lines.append("Veille récente :")
        lines.extend(_digest_lines(rss_rows))
    if mail_rows:
        label = PERSONAS.get(persona, {}).get("label", "veille du compte")
        lines.append("")
        lines.append(
            f"Newsletters Gmail du mois dernier retenues pour la {label}. "
            "L'objet contient « newsletter » et le texte parle de ce thème. "
            "Elles peuvent servir de source pour un post sur ce thème. "
            "N'utilise pas une newsletter qui n'est pas dans cette liste."
        )
        lines.extend(_digest_lines(mail_rows))
    return "\n".join(lines)


if __name__ == "__main__":
    sample = "https://www.frandroid.com/feed"
    for entry in fetch_entries(sample)[:3]:
        print(entry["published_at"], entry["title"])
        print(entry["link"])
        print()
