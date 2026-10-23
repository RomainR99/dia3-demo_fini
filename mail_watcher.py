import html
import imaplib
import re
import ssl
import unicodedata
from datetime import datetime, timezone
from email import message_from_bytes
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import certifi

from config import (
    GMAIL_IMAP_HOST,
    GMAIL_IMAP_PORT,
    MAIL_MAX,
    MAIL_SUBJECT,
    MAIL_TIMEOUT,
    PERSONA_MAIL_KEYWORDS,
    RSS_SUMMARY_CHARS,
)
from db import (
    delete_mail_articles,
    get_mailbox_credentials,
    get_user_persona,
    mail_feed,
    mark_feed,
    save_mailbox,
    upsert_article,
)

_TAGS = re.compile(r"<[^>]+>")
_MONTHS = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


#flux_rss_email
class MailError(Exception):
    """Message déjà rédigé pour la barre latérale."""


#flux_rss_email
def _fold(text):
    decomposed = unicodedata.normalize("NFD", text or "")
    stripped = "".join(
        char for char in decomposed
        if unicodedata.category(char) != "Mn"
    )
    return stripped.lower()


#flux_rss_email
def matches_theme(persona, title, summary):
    # Un mot du thème doit être un mot entier. « ia » ne doit pas sortir de « via ».
    keywords = PERSONA_MAIL_KEYWORDS.get(persona) or ()
    folded = _fold(f"{title} {summary}")
    for keyword in keywords:
        pattern = (
            r"(?<![a-z0-9])"
            + re.escape(_fold(keyword))
            + r"(?![a-z0-9])"
        )
        if re.search(pattern, folded):
            return True
    return False


#flux_rss_email
def last_month_bounds(today=None):
    # Mois calendaire précédent : en octobre, du 1er septembre au 1er octobre exclu.
    today = today or datetime.now(timezone.utc).date()
    first_this = today.replace(day=1)
    if first_this.month == 1:
        first_last = first_this.replace(year=first_this.year - 1, month=12)
    else:
        first_last = first_this.replace(month=first_this.month - 1)
    return first_last, first_this


#flux_rss_email
def imap_date(day):
    # Les noms de mois IMAP sont en anglais, même si le Mac est en français.
    return f"{day.day:02d}-{_MONTHS[day.month - 1]}-{day.year}"


#flux_rss_email
def _decode_header(value):
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


#flux_rss_email
def _plain(value):
    text = html.unescape(_TAGS.sub(" ", value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:RSS_SUMMARY_CHARS]


#flux_rss_email
def _part_text(part):
    payload = part.get_payload(decode=True) or b""
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


#flux_rss_email
def _body_text(message):
    plain = []
    html_parts = []
    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        if part.get_content_disposition() == "attachment":
            continue
        kind = part.get_content_type()
        if kind == "text/plain":
            plain.append(_part_text(part))
        elif kind == "text/html":
            html_parts.append(_part_text(part))
    # Les newsletters sont souvent uniquement en HTML.
    return "\n".join(plain) if plain else "\n".join(html_parts)


#flux_rss_email
def parse_message(raw):
    message = message_from_bytes(raw)
    subject = _decode_header(message.get("Subject")) or "(sans objet)"
    sender = _decode_header(message.get("From"))
    message_id = (message.get("Message-ID") or "").strip()
    guid = f"email:{message_id or subject}"
    link = ""
    if message_id:
        clean = message_id.strip("<>")
        link = "https://mail.google.com/mail/u/0/#search/rfc822msgid:" + quote(clean)
    published = ""
    if message.get("Date"):
        try:
            when = parsedate_to_datetime(message.get("Date"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            published = when.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError, OverflowError):
            published = ""
    summary = _plain(f"De {sender}. {_body_text(message)}")
    return {
        "guid": guid,
        "title": _plain(subject) or "(sans objet)",
        "link": link,
        "summary": summary,
        "published_at": published,
    }


#flux_rss_email
def _clean_login(address, app_password):
    address = (address or "").strip().lower()
    # Google affiche le mot de passe d'application par groupes de 4 lettres.
    app_password = (app_password or "").replace(" ", "").strip()
    if "@" not in address or not app_password:
        raise MailError("Indique l'adresse Gmail et le mot de passe d'application.")
    return address, app_password


#flux_rss_email
def _hide_secret(text, secret):
    if secret and secret in text:
        return text.replace(secret, "••••")
    return text


#flux_rss_email
def _open_inbox(address, app_password):
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        imap = imaplib.IMAP4_SSL(
            GMAIL_IMAP_HOST,
            GMAIL_IMAP_PORT,
            ssl_context=context,
            timeout=MAIL_TIMEOUT,
        )
    except (TimeoutError, OSError) as error:
        raise MailError("Impossible de joindre imap.gmail.com.") from error
    try:
        imap.login(address, app_password)
    except imaplib.IMAP4.error as error:
        try:
            imap.logout()
        except Exception:
            pass
        detail = _hide_secret(str(error), app_password)
        if "AUTHENTICATIONFAILED" in detail or "Invalid credentials" in detail:
            raise MailError(
                "Gmail a refusé la connexion. "
                "Active IMAP dans les réglages Gmail, "
                "et utilise un mot de passe d'application, pas le mot de passe du compte."
            ) from error
        raise MailError(f"Gmail a répondu : {detail}") from error
    status, _payload = imap.select("INBOX", readonly=True)
    if status != "OK":
        try:
            imap.logout()
        except Exception:
            pass
        raise MailError("La boîte de réception Gmail est inaccessible.")
    return imap


#flux_rss_email
def _raw_message(fetched):
    for item in fetched or []:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray)):
            return bytes(item[1])
    return None


#flux_rss_email
def fetch_newsletters(address, app_password):
    start, end = last_month_bounds()
    since = imap_date(start)
    before = imap_date(end)
    imap = _open_inbox(address, app_password)
    try:
        status, data = imap.search(
            None,
            "SINCE", since,
            "BEFORE", before,
            "SUBJECT", MAIL_SUBJECT,
        )
        if status != "OK":
            raise MailError("La recherche des newsletters a échoué.")
        ids = data[0].split() if data and data[0] else []
        ids = ids[-MAIL_MAX:]
        entries = []
        for msg_id in ids:
            status, fetched = imap.fetch(msg_id, "(BODY.PEEK[])")
            if status != "OK":
                continue
            raw = _raw_message(fetched)
            if not raw:
                continue
            try:
                entries.append(parse_message(raw))
            except Exception:
                continue
        return entries
    finally:
        try:
            imap.logout()
        except Exception:
            pass


#flux_rss_email
def connect_mailbox(user_id, address, app_password):
    address, app_password = _clean_login(address, app_password)
    # On n'enregistre le secret qu'après une connexion réussie.
    imap = _open_inbox(address, app_password)
    try:
        imap.logout()
    except Exception:
        pass
    save_mailbox(user_id, address, app_password)


#flux_rss_email
def refresh_mailbox(user_id):
    creds = get_mailbox_credentials(user_id)
    if creds is None:
        return []
    feed = mail_feed(user_id)
    if feed is None or not feed["active"]:
        return []
    try:
        entries = fetch_newsletters(creds["address"], creds["app_password"])
    except MailError as error:
        mark_feed(feed["id"], str(error))
        return [f"Gmail : {error}"]
    except Exception:
        mark_feed(feed["id"], "La lecture de Gmail a échoué.")
        return ["Gmail : la lecture a échoué."]
    #flux_rss_email
    persona = get_user_persona(user_id)
    kept = [
        entry for entry in entries
        if matches_theme(persona, entry["title"], entry["summary"])
    ]
    delete_mail_articles(user_id)
    for entry in kept:
        upsert_article(user_id, feed["id"], **entry)
    mark_feed(feed["id"], None)
    skipped = len(entries) - len(kept)
    if skipped:
        return [f"Gmail : {skipped} newsletter(s) hors thème laissée(s) de côté."]
    return []
