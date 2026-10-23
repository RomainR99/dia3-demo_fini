import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from config import (
    DB_PATH,
    DEFAULT_SLIDE_LANGUAGE,
    DEFAULT_SUBTITLE_LANGUAGE,
    PERSONA_FEEDS,
)


# Base de données
def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# Base de données
def connect():
    folder = os.path.dirname(DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Plusieurs rafraîchissements écrivent en même temps.
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


# Base de données
@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# Base de données
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    persona TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feeds (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    site TEXT NOT NULL,
    url TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'rss',
    active INTEGER NOT NULL DEFAULT 1,
    last_fetched_at TEXT,
    last_error TEXT,
    UNIQUE(user_id, url)
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY,
    feed_id INTEGER NOT NULL REFERENCES feeds(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    guid TEXT NOT NULL,
    title TEXT NOT NULL,
    link TEXT NOT NULL,
    summary TEXT NOT NULL,
    published_at TEXT,
    fetched_at TEXT NOT NULL,
    UNIQUE(user_id, guid)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    images_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_articles_user_date
    ON articles(user_id, published_at);
CREATE INDEX IF NOT EXISTS idx_messages_user
    ON messages(user_id, id);
"""

#flux_rss_email
MAILBOX_SCHEMA = """
CREATE TABLE IF NOT EXISTS mailboxes (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id),
    address TEXT NOT NULL,
    app_password TEXT NOT NULL,
    connected_at TEXT NOT NULL
);
"""

#romain6
GAMMA_SCHEMA = """
CREATE TABLE IF NOT EXISTS gamma_accounts (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    api_key TEXT NOT NULL DEFAULT '',
    slide_language TEXT NOT NULL DEFAULT 'fr',
    subtitle_language TEXT NOT NULL DEFAULT 'fr',
    connected_at TEXT,
    generation_id TEXT,
    gamma_url TEXT,
    slide_count INTEGER,
    job_status TEXT,
    subtitle_path TEXT
);
"""


# Base de données
def init_db():
    with db() as conn:
        conn.executescript(SCHEMA)
        #flux_rss_email
        conn.executescript(MAILBOX_SCHEMA)
        #romain6
        conn.executescript(GAMMA_SCHEMA)


# Base de données
def _hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        200_000,
    ).hex()
    return f"{salt}${digest}"


# Base de données
def _check_password(password, stored):
    salt, _digest = stored.split("$", 1)
    return secrets.compare_digest(_hash_password(password, salt), stored)


#persona
def _seed_feeds(conn, user_id, persona):
    for name, site, url in PERSONA_FEEDS[persona]:
        conn.execute(
            """
            INSERT OR IGNORE INTO feeds (user_id, name, site, url, kind)
            VALUES (?, ?, ?, ?, 'rss')
            """,
            (user_id, name, site, url),
        )


# Base de données
#persona
def create_user(username, password, persona):
    username = username.strip()
    if persona not in PERSONA_FEEDS:
        return None, "Cette veille n'existe pas."
    if len(username) < 3 or len(password) < 4:
        return None, "Le nom fait au moins 3 caractères, le mot de passe au moins 4."
    with db() as conn:
        taken = conn.execute(
            "SELECT 1 FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if taken:
            return None, "Ce nom est déjà pris."
        cursor = conn.execute(
            """
            INSERT INTO users (username, password_hash, persona, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (username, _hash_password(password), persona, now()),
        )
        user_id = cursor.lastrowid
        _seed_feeds(conn, user_id, persona)
        return user_id, None


# Base de données
def authenticate(username, password):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
        if row is None:
            return None
        stored = row["password_hash"]
        user = {
            "id": row["id"],
            "username": row["username"],
            "persona": row["persona"],
        }
    if not _check_password(password, stored):
        return None
    return user


# Base de données
def load_messages(user_id):
    with db() as conn:
        rows = conn.execute(
            """
            SELECT role, content, images_json
            FROM messages
            WHERE user_id = ?
            ORDER BY id
            """,
            (user_id,),
        ).fetchall()
        messages = []
        for row in rows:
            message = {"role": row["role"], "content": row["content"]}
            if row["images_json"]:
                message["images"] = json.loads(row["images_json"])
            messages.append(message)
        return messages


# Base de données
def add_message(user_id, role, content, images=None):
    payload = json.dumps(images) if images else None
    with db() as conn:
        conn.execute(
            """
            INSERT INTO messages (user_id, role, content, images_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, role, content, payload, now()),
        )


#flux RSS
# Base de données
def list_feeds(user_id):
    with db() as conn:
        rows = conn.execute(
            """
            SELECT id, name, site, url, kind, active, last_fetched_at, last_error
            FROM feeds
            WHERE user_id = ?
            ORDER BY id
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


#flux RSS
# Base de données
def set_feed_active(feed_id, user_id, active):
    with db() as conn:
        conn.execute(
            "UPDATE feeds SET active = ? WHERE id = ? AND user_id = ?",
            (1 if active else 0, feed_id, user_id),
        )


#flux RSS
# Base de données
def mark_feed(feed_id, error):
    with db() as conn:
        conn.execute(
            "UPDATE feeds SET last_fetched_at = ?, last_error = ? WHERE id = ?",
            (now(), error, feed_id),
        )


#flux RSS
# Base de données
def upsert_article(user_id, feed_id, guid, title, link, summary, published_at):
    with db() as conn:
        conn.execute(
            """
            INSERT INTO articles (
                feed_id, user_id, guid, title, link, summary, published_at, fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, guid) DO UPDATE SET
                title = excluded.title,
                link = excluded.link,
                summary = excluded.summary,
                published_at = excluded.published_at,
                fetched_at = excluded.fetched_at
            """,
            (feed_id, user_id, guid, title, link, summary, published_at, now()),
        )


#flux_rss_email
#flux RSS
# Base de données
def recent_articles(user_id, limit, kind=None):
    sql = """
        SELECT articles.title, articles.link, articles.summary,
               articles.published_at, feeds.name AS source
        FROM articles
        JOIN feeds ON feeds.id = articles.feed_id
        WHERE articles.user_id = ? AND feeds.active = 1
    """
    params = [user_id]
    #flux_rss_email
    if kind:
        sql += " AND feeds.kind = ?"
        params.append(kind)
    sql += " ORDER BY articles.published_at DESC, articles.id DESC LIMIT ?"
    params.append(limit)
    with db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


#flux_rss_email
def get_user_persona(user_id):
    with db() as conn:
        row = conn.execute(
            "SELECT persona FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return row["persona"] if row else None


#flux_rss_email
def delete_mail_articles(user_id):
    with db() as conn:
        conn.execute(
            """
            DELETE FROM articles
            WHERE user_id = ?
              AND feed_id IN (
                  SELECT id FROM feeds
                  WHERE user_id = ? AND kind = 'email'
              )
            """,
            (user_id, user_id),
        )


#flux_rss_email
def get_mailbox_address(user_id):
    with db() as conn:
        row = conn.execute(
            "SELECT address FROM mailboxes WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row["address"] if row else None


#flux_rss_email
def get_mailbox_credentials(user_id):
    with db() as conn:
        row = conn.execute(
            "SELECT address, app_password FROM mailboxes WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return {"address": row["address"], "app_password": row["app_password"]}


#flux_rss_email
def save_mailbox(user_id, address, app_password):
    url = f"gmail://{address}"
    with db() as conn:
        conn.execute(
            """
            INSERT INTO mailboxes (user_id, address, app_password, connected_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                address = excluded.address,
                app_password = excluded.app_password,
                connected_at = excluded.connected_at
            """,
            (user_id, address, app_password, now()),
        )
        existing = conn.execute(
            """
            SELECT id FROM feeds
            WHERE user_id = ? AND kind = 'email'
            """,
            (user_id,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE feeds
                SET name = ?, site = ?, url = ?, active = 1, last_error = NULL
                WHERE id = ?
                """,
                ("Gmail — newsletter", "https://mail.google.com", url, existing["id"]),
            )
            return existing["id"]
        cursor = conn.execute(
            """
            INSERT INTO feeds (user_id, name, site, url, kind)
            VALUES (?, ?, ?, ?, 'email')
            """,
            (user_id, "Gmail — newsletter", "https://mail.google.com", url),
        )
        return cursor.lastrowid


#flux_rss_email
def mail_feed(user_id):
    with db() as conn:
        row = conn.execute(
            """
            SELECT id, active FROM feeds
            WHERE user_id = ? AND kind = 'email'
            """,
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


#flux_rss_email
def disconnect_mailbox(user_id):
    with db() as conn:
        feed = conn.execute(
            "SELECT id FROM feeds WHERE user_id = ? AND kind = 'email'",
            (user_id,),
        ).fetchone()
        if feed:
            conn.execute("DELETE FROM articles WHERE feed_id = ?", (feed["id"],))
            conn.execute("DELETE FROM feeds WHERE id = ?", (feed["id"],))
        conn.execute("DELETE FROM mailboxes WHERE user_id = ?", (user_id,))


#romain6
def gamma_view(user_id):
    """Langues, état et lien Gamma, sans la clé API.

    `connected` est vrai seulement si une clé est enregistrée.
    Sans ligne, les langues reviennent au français.
    """
    with db() as conn:
        row = conn.execute(
            """
            SELECT api_key, slide_language, subtitle_language, connected_at,
                   generation_id, gamma_url, slide_count, job_status, subtitle_path
            FROM gamma_accounts WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    if row is None:
        return {
            "connected": False,
            "slide_language": DEFAULT_SLIDE_LANGUAGE,
            "subtitle_language": DEFAULT_SUBTITLE_LANGUAGE,
            "generation_id": "",
            "gamma_url": "",
            "slide_count": 0,
            "job_status": "",
            "subtitle_path": "",
        }
    return {
        "connected": bool((row["api_key"] or "").strip()),
        "slide_language": row["slide_language"],
        "subtitle_language": row["subtitle_language"],
        "generation_id": row["generation_id"] or "",
        "gamma_url": row["gamma_url"] or "",
        "slide_count": row["slide_count"] or 0,
        "job_status": row["job_status"] or "",
        "subtitle_path": row["subtitle_path"] or "",
    }


#romain6
def gamma_api_key(user_id):
    """Clé du compte, lue seulement pour appeler Gamma."""
    with db() as conn:
        row = conn.execute(
            "SELECT api_key FROM gamma_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return ""
    return (row["api_key"] or "").strip()


#romain6
def save_gamma_key(user_id, api_key):
    """Enregistre la clé personnelle. Les langues déjà choisies restent."""
    with db() as conn:
        conn.execute(
            """
            INSERT INTO gamma_accounts (user_id, api_key, connected_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                api_key = excluded.api_key,
                connected_at = excluded.connected_at
            """,
            (user_id, api_key.strip(), now()),
        )


#romain6
def save_gamma_languages(user_id, slide_language, subtitle_language):
    """Garde la langue des slides (et de la vidéo) et celle des sous-titres."""
    with db() as conn:
        conn.execute(
            """
            INSERT INTO gamma_accounts (
                user_id, api_key, slide_language, subtitle_language
            )
            VALUES (?, '', ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                slide_language = excluded.slide_language,
                subtitle_language = excluded.subtitle_language
            """,
            (user_id, slide_language, subtitle_language),
        )


#romain6
def save_gamma_job(user_id, generation_id, status, gamma_url, slide_count, subtitle_path):
    """Mémorise la génération en cours ou le lien des slides."""
    with db() as conn:
        conn.execute(
            """
            UPDATE gamma_accounts
            SET generation_id = ?, job_status = ?, gamma_url = ?,
                slide_count = ?, subtitle_path = ?
            WHERE user_id = ?
            """,
            (generation_id, status, gamma_url, slide_count, subtitle_path, user_id),
        )


#romain6
def disconnect_gamma(user_id):
    """Oublie la clé et le dernier lien. Les langues choisies restent."""
    with db() as conn:
        conn.execute(
            """
            UPDATE gamma_accounts
            SET api_key = '', connected_at = NULL,
                generation_id = NULL, gamma_url = NULL,
                slide_count = NULL, job_status = NULL
            WHERE user_id = ?
            """,
            (user_id,),
        )
