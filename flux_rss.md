# Flux RSS — un compte, un historique, une veille

**27 fonctions** à coder : 24 à écrire, 3 déjà là à modifier (`ask_llm` dans la classe, `ask_llm` du module, `stream_voice_answer`).

**Environ 12 heures** sans IA, en débutant en orienté objet. Souvent deux journées. Presque tout est des fonctions. Le seul geste orienté objet est d'ajouter deux paramètres à la méthode `ask_llm`. Le temps passe dans SQLite, dans les allers-retours de Streamlit, et dans le branchement au chat, pas dans l'invention du code : ce guide le donne.

## Objectif

L'application sert plusieurs personnes. Chacune a son historique de messages et sa propre liste de flux. Deux personae existent dès maintenant :

- `veille_tech` — veille technologique
- `veille_finance` — veille financière et économique

Le Capitaine reste le même personnage. La différence, aujourd'hui, est la veille collée dans le message système. Deux Jarvis, avec deux fichiers de rôle et deux avatars, viendront ensuite : les clés sont déjà prévues, les images non.

La page d'un site n'est pas un flux. Le code télécharge le XML (RSS ou Atom) listé plus bas, le range en base, puis en donne un extrait au modèle à chaque question.

## Pourquoi `session_state` ne suffit plus

`st.session_state` vit le temps d'un onglet. Fermer la page efface l'historique. Deux personnes sur le même serveur n'ont pas de nom, donc pas de veille à elles. Les posts et les flux doivent survivre au redémarrage et se filtrer par utilisateur. SQLite le fait dans un fichier, sans serveur à installer : `sqlite3` est dans la bibliothèque standard. Un autre groupe clone le dépôt, lance Streamlit, et la base se crée au premier compte.

Le fichier s'appelle `data/jarvis.db`. Il ne se versionne pas.

## Ordre pour recoder

1. Ajouter les constantes dans `config.py`.
2. Créer `db.py` (comptes, messages, flux, articles).
3. Ajouter `feedparser==6.0.14` dans `requirements.txt`, puis `pip install -r requirements.txt`.
4. Créer `rss_watcher.py` (télécharger, enregistrer, fabriquer l'extrait).
5. Passer cet extrait à `ask_llm` dans `llm_agent.py`.
6. Brancher le compte, la barre latérale et l'enregistrement des messages dans `app.py`.
7. Ignorer `data/*.db` dans `.gitignore`.
8. Tester un flux en ligne de commande, puis le chat.

Les fichiers nouveaux (`db.py`, `rss_watcher.py`) s'écrivent avec 4 espaces, comme `llm_agent.py`. `app.py` garde ses tabulations.

## Les deux personae

| Clé | Rôle affiché | Sites |
| --- | --- | --- |
| `veille_tech` | Veille technologique | Journal du Net, TechCrunch, The Verge, Frandroid, MIT Technology Review, Y Combinator, InfoQ, DEV |
| `veille_finance` | Veille financière et économique | Investing.com, Business Insider, EasyBourse, BNP Paribas, economie.gouv.fr, Financial Times, Cointelegraph, Cryptoast |

Le persona est choisi à la création du compte et n'est pas modifié ensuite. Ses flux sont copiés dans des lignes à lui. Deux comptes du même persona ont deux listes : décocher un flux chez l'un laisse l'autre intact. Pour avoir les deux Jarvis, on crée deux comptes.

## Adresse du site et adresse du flux

Chaque ligne part du site demandé. La colonne Flux est celle que le code interroge. Les pages « liste de flux » (BNP, economie.gouv.fr) ne contiennent pas les articles.

### Veille technologique

| Site | Flux à télécharger |
| --- | --- |
| https://journaldunet.com | https://www.journaldunet.com/intelligence-artificielle/rss/ |
| https://techcrunch.com | https://techcrunch.com/feed/ |
| https://theverge.com | https://www.theverge.com/rss/index.xml |
| https://frandroid.com | https://www.frandroid.com/feed |
| https://technologyreview.com | https://www.technologyreview.com/feed/ |
| https://ycombinator.com | https://www.ycombinator.com/blog/feed/ |
| https://infoq.com | https://feed.infoq.com/ |
| https://dev.to | https://dev.to/feed |

Le Journal du Net a aussi un flux général, https://www.journaldunet.com/rss/. La veille tech utilise le flux Intelligence artificielle, qui reste sur le même site. Le blog Y Combinator publie peu : le fil Hacker News, https://news.ycombinator.com/rss, peut s'ajouter dans la même liste le jour où il faut une actu quotidienne. Il n'est pas dans le lot de départ.

### Veille financière et économique

| Site | Flux à télécharger |
| --- | --- |
| https://investing.com | https://www.investing.com/rss/news.rss |
| https://businessinsider.com | https://feeds.businessinsider.com/custom/all |
| https://easybourse.com | https://www.easybourse.com/feeds/media/ |
| https://economic-research.bnpparibas.com/RSS/fr-FR | https://economic-research.bnpparibas.com/RSS/fr-FR/Eco-Week |
| https://economie.gouv.fr | https://www.economie.gouv.fr/rss/toutesactualites |
| https://ft.com | https://www.ft.com/rss/home/international |
| https://cointelegraph.com | https://cointelegraph.com/rss |
| https://cryptoast.com | https://cryptoast.fr/feed/ |

Précisions vérifiées le 22 octobre 2026 :

- Business Insider redirige `/rss` vers `feeds.businessinsider.com`. Le flux est de l'Atom. `feedparser` lit RSS et Atom avec la même fonction.
- EasyBourse annonce `text/html` alors que le corps est du RSS gzippé. On ne filtre pas sur le `Content-Type`. L'adresse `/feeds/news/fr/` répondait en erreur 500 : on garde `/feeds/media/`.
- La page BNP est le catalogue. Eco Week est le fil de conjoncture. Les autres fils du même catalogue : `Eco-Flash`, `Eco-Perspectives`, `Eco-Conjoncture`, `EcoTV`, `Eco-Emerging`, `Eco-Charts`, sous le préfixe `https://economic-research.bnpparibas.com/RSS/fr-FR/`.
- `https://www.economie.gouv.fr/rss` est une page HTML. Le XML des actualités est `/rss/toutesactualites`.
- Le Financial Times ne donne qu'un court résumé, et l'article derrière le lien est souvent payant. L'agent cite ce résumé, il n'invente pas la suite.
- Cryptoast se lit sur `cryptoast.fr`. Le flux est `https://cryptoast.fr/feed/`.

## Étape 1 — `config.py`

Coller à la fin du fichier.

```python
# Base locale. Le dossier data/ est créé au premier compte. Le .db n'est pas versionné.
DB_PATH = "data/jarvis.db"

# Un site lent ne bloque pas les autres au-delà de ce délai, en secondes.
RSS_TIMEOUT = 15
RSS_USER_AGENT = "BarbeQuasarVeille/1.0"
# Articles gardés par flux à chaque rafraîchissement, puis nombre envoyé au modèle.
RSS_ITEMS_PER_FEED = 5
RSS_ITEMS_IN_PROMPT = 12
RSS_SUMMARY_CHARS = 400

VEILLE_INSTRUCTION = (
    "Une veille récente est collée sous cette consigne. "
    "Quand tu t'en sers, cite le titre et le lien de l'article. "
    "Si la veille ne contient pas la réponse, dis-le, puis réponds avec ce que tu sais. "
    "Tu n'inventes pas un article, un chiffre ou une citation."
)

# context et avatar restent ceux du Capitaine.
# Deux Jarvis plus tard : un context_tech.txt, un context_finance.txt,
# et une image dans avatar. Le reste du code lit déjà ces clés.
PERSONAS = {
    "veille_tech": {
        "label": "Veille technologique",
        "context": CONTEXT_PATH,
        "avatar": None,
    },
    "veille_finance": {
        "label": "Veille financière et économique",
        "context": CONTEXT_PATH,
        "avatar": None,
    },
}

PERSONA_FEEDS = {
    "veille_tech": [
        ("Journal du Net", "https://journaldunet.com", "https://www.journaldunet.com/intelligence-artificielle/rss/"),
        ("TechCrunch", "https://techcrunch.com", "https://techcrunch.com/feed/"),
        ("The Verge", "https://theverge.com", "https://www.theverge.com/rss/index.xml"),
        ("Frandroid", "https://frandroid.com", "https://www.frandroid.com/feed"),
        ("MIT Technology Review", "https://technologyreview.com", "https://www.technologyreview.com/feed/"),
        ("Y Combinator", "https://ycombinator.com", "https://www.ycombinator.com/blog/feed/"),
        ("InfoQ", "https://infoq.com", "https://feed.infoq.com/"),
        ("DEV", "https://dev.to", "https://dev.to/feed"),
    ],
    "veille_finance": [
        ("Investing.com", "https://investing.com", "https://www.investing.com/rss/news.rss"),
        ("Business Insider", "https://businessinsider.com", "https://feeds.businessinsider.com/custom/all"),
        ("EasyBourse", "https://easybourse.com", "https://www.easybourse.com/feeds/media/"),
        ("BNP Paribas Eco Week", "https://economic-research.bnpparibas.com/RSS/fr-FR", "https://economic-research.bnpparibas.com/RSS/fr-FR/Eco-Week"),
        ("economie.gouv.fr", "https://economie.gouv.fr", "https://www.economie.gouv.fr/rss/toutesactualites"),
        ("Financial Times", "https://ft.com", "https://www.ft.com/rss/home/international"),
        ("Cointelegraph", "https://cointelegraph.com", "https://cointelegraph.com/rss"),
        ("Cryptoast", "https://cryptoast.com", "https://cryptoast.fr/feed/"),
    ],
}
```

Chaque triplet est `(nom affiché, site d'origine, url du flux)`.

## Étape 2 — `db.py`

Quatre tables.

| Table | Rôle |
| --- | --- |
| `users` | nom, mot de passe hashé, persona |
| `feeds` | flux de cet utilisateur (`kind` vaut `rss` aujourd'hui, `email` plus tard) |
| `articles` | billets récupérés, rattachés au flux et à l'utilisateur |
| `messages` | historique du chat (texte, et les images déjà envoyées) |

`guid` identifie un article dans un flux. `UNIQUE(user_id, guid)` empêche de réécrire le même billet à chaque rafraîchissement : on met à jour le titre et le résumé.

Le mot de passe ne part pas en clair. `pbkdf2_hmac` est dans `hashlib`, sans dépendance en plus. Le sel est devant le hash, séparé par `$`.

L'audio des réponses n'est pas stocké : un WAV est lourd, et le modèle n'en a pas besoin au tour suivant. Au rechargement, le texte est là, le lecteur audio non.

```python
import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DB_PATH, PERSONA_FEEDS


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def connect():
    folder = os.path.dirname(DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # Plusieurs rafraîchissements écrivent en même temps : WAL évite les blocages.
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


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


def init_db():
    with db() as conn:
        conn.executescript(SCHEMA)


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


def _check_password(password, stored):
    salt, _digest = stored.split("$", 1)
    return secrets.compare_digest(_hash_password(password, salt), stored)


def _seed_feeds(conn, user_id, persona):
    for name, site, url in PERSONA_FEEDS[persona]:
        conn.execute(
            """
            INSERT OR IGNORE INTO feeds (user_id, name, site, url, kind)
            VALUES (?, ?, ?, ?, 'rss')
            """,
            (user_id, name, site, url),
        )


def create_user(username, password, persona):
    username = username.strip()
    if persona not in PERSONA_FEEDS:
        return None, "Cette veille n'existe pas."
    if len(username) < 3 or len(password) < 4:
        return None, "Le nom fait au moins 3 caractères, le mot de passe au moins 4."
    with db() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO users (username, password_hash, persona, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (username, _hash_password(password), persona, now()),
            )
        except sqlite3.IntegrityError:
            return None, "Ce nom est déjà pris."
        user_id = cursor.lastrowid
        _seed_feeds(conn, user_id, persona)
        return user_id, None


def authenticate(username, password):
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
    if row is None or not _check_password(password, row["password_hash"]):
        return None
    return {"id": row["id"], "username": row["username"], "persona": row["persona"]}


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


def set_feed_active(feed_id, user_id, active):
    with db() as conn:
        conn.execute(
            "UPDATE feeds SET active = ? WHERE id = ? AND user_id = ?",
            (1 if active else 0, feed_id, user_id),
        )


def mark_feed(feed_id, error):
    with db() as conn:
        conn.execute(
            "UPDATE feeds SET last_fetched_at = ?, last_error = ? WHERE id = ?",
            (now(), error, feed_id),
        )


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


def recent_articles(user_id, limit):
    with db() as conn:
        rows = conn.execute(
            """
            SELECT articles.title, articles.link, articles.summary,
                   articles.published_at, feeds.name AS source
            FROM articles
            JOIN feeds ON feeds.id = articles.feed_id
            WHERE articles.user_id = ? AND feeds.active = 1
            ORDER BY articles.published_at DESC, articles.id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]
```

`user_id` est repris dans `set_feed_active` pour qu'un compte ne décoche pas le flux d'un autre.

## Étape 3 — `requirements.txt`

Ajouter une ligne :

```text
feedparser==6.0.14
```

Puis, environnement activé :

```bash
pip install -r requirements.txt
```

## Étape 4 — `rss_watcher.py`

`fetch_entries` ne parle pas à la base : il renvoie des dictionnaires. On peut l'essayer sur une URL avant d'avoir un compte.

`refresh_user` ne lit que les flux `active` et `kind = 'rss'`. Une ligne `email` est ignorée jusqu'à l'étape courrier. Un site en panne remplit `last_error` et les autres flux continuent.

L'extrait pour le modèle est reconstruit à chaque question depuis la base. Il n'est pas copié dans `messages` : sinon la même veille serait renvoyée à chaque tour et finirait par dépasser la fenêtre du modèle (voir `question_prof.md`).

```python
import html
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import feedparser

from config import (
    RSS_ITEMS_IN_PROMPT,
    RSS_ITEMS_PER_FEED,
    RSS_SUMMARY_CHARS,
    RSS_TIMEOUT,
    RSS_USER_AGENT,
    VEILLE_INSTRUCTION,
)
from db import list_feeds, mark_feed, recent_articles, upsert_article

_TAGS = re.compile(r"<[^>]+>")


class RssError(Exception):
    pass


def _plain(value):
    text = html.unescape(_TAGS.sub(" ", value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:RSS_SUMMARY_CHARS]


def _published(entry):
    stamp = entry.get("published_parsed") or entry.get("updated_parsed")
    if not stamp:
        return ""
    return time.strftime("%Y-%m-%d %H:%M", stamp)


def fetch_entries(url):
    # feedparser n'a pas de timeout par appel. Le délai vaut pour le processus.
    socket.setdefaulttimeout(RSS_TIMEOUT)
    parsed = feedparser.parse(url, agent=RSS_USER_AGENT)
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


def refresh_user(user_id):
    feeds = [
        feed for feed in list_feeds(user_id)
        if feed["active"] and feed["kind"] == "rss"
    ]
    errors = []
    socket.setdefaulttimeout(RSS_TIMEOUT)
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
    return errors


def digest_for(user_id):
    rows = recent_articles(user_id, RSS_ITEMS_IN_PROMPT)
    if not rows:
        return ""
    lines = [VEILLE_INSTRUCTION, "", "Veille récente :"]
    for row in rows:
        when = row["published_at"] or "date inconnue"
        lines.append(f"- {row['source']} — {row['title']} ({when})")
        if row["link"]:
            lines.append(f"  {row['link']}")
        if row["summary"]:
            lines.append(f"  {row['summary']}")
    return "\n".join(lines)


if __name__ == "__main__":
    sample = "https://www.frandroid.com/feed"
    for entry in fetch_entries(sample)[:3]:
        print(entry["published_at"], entry["title"])
        print(entry["link"])
        print()
```

Essai sans interface :

```bash
python rss_watcher.py
```

Trois titres Frandroid doivent s'afficher. Si Python dit `CERTIFICATE_VERIFY_FAILED`, le certificat racine manque à cette installation de Python sur macOS : lancer `Install Certificates.command` dans le dossier de Python 3.12 (`/Applications/Python 3.12/`), puis réessayer.

## Étape 5 — la veille dans `ask_llm`

Dans `Conversation_Manager.ask_llm`, ajouter deux paramètres et les utiliser pour le message système. Le reste de la fonction (modèle, voix, images) ne change pas.

Signature :

```python
def ask_llm(self, question, history=None, images=None, voice=False, veille="", context_path=None):
```

Le bloc qui fabrique `system` devient :

```python
        path = context_path or CONTEXT_PATH
        system = self.read_file(path) + "\n\n" + LANGUAGE_INSTRUCTION
        if veille:
            system += "\n\n" + veille
        if voice:
            system += "\n\n" + VOICE_INSTRUCTION
```

`CONTEXT_PATH` est déjà importé depuis `config`. `veille` vide laisse le Capitaine tel qu'il est aujourd'hui.

La fonction module `ask_llm` (celle que `app.py` importe) reprend les mêmes paramètres et les transmet :

```python
def ask_llm(question, history=None, images=None, voice=False, veille="", context_path=None):
    return agent.ask_llm(
        question,
        history=history,
        images=images,
        voice=voice,
        veille=veille,
        context_path=context_path,
    )
```

En mode vocal, la consigne de longueur (150 à 300 caractères) reste après la veille. Le modèle résume, il ne lit pas les douze articles à voix haute.

## Étape 6 — `app.py`

### Imports

Ajouter :

```python
from config import (
	APP_TITLE,
	CHAT_PLACEHOLDER,
	IMAGE_ONLY_QUESTION,
	MAX_IMAGES,
	PAGE_TITLE,
	PERSONAS,
)
from db import (
	add_message,
	authenticate,
	create_user,
	init_db,
	list_feeds,
	load_messages,
	set_feed_active,
)
from rss_watcher import digest_for, refresh_user
```

Garder les imports déjà présents (`llm_agent`, `time`, `base64`, `streamlit`).

### Compte avant le chat

Remplacer le bloc `if "messages" not in st.session_state` par une porte. Tant que personne n'est connecté, `st.stop()` empêche le chat de s'afficher.

```python
def open_message(role):
	avatar = None
	if role == "assistant":
		avatar = PERSONAS[st.session_state.persona]["avatar"]
	if avatar:
		return st.chat_message(role, avatar=avatar)
	return st.chat_message(role)


def require_user():
	init_db()
	if st.session_state.get("user_id"):
		if st.session_state.get("loaded_for") != st.session_state.user_id:
			st.session_state.messages = load_messages(st.session_state.user_id)
			st.session_state.loaded_for = st.session_state.user_id
		return

	st.subheader("Qui monte à bord ?")
	mode = st.radio("Compte", ["Connexion", "Créer un compte"], horizontal=True)
	username = st.text_input("Nom")
	password = st.text_input("Mot de passe", type="password")
	persona = "veille_tech"
	if mode == "Créer un compte":
		persona = st.selectbox(
			"Veille",
			list(PERSONAS),
			format_func=lambda key: PERSONAS[key]["label"],
		)
	if st.button("Entrer"):
		if mode == "Créer un compte":
			user_id, error = create_user(username, password, persona)
			if error:
				st.warning(error)
			else:
				st.session_state.user_id = user_id
				st.session_state.persona = persona
				st.session_state.username = username.strip()
				st.rerun()
		else:
			user = authenticate(username, password)
			if user is None:
				st.warning("Nom ou mot de passe refusé.")
			else:
				st.session_state.user_id = user["id"]
				st.session_state.persona = user["persona"]
				st.session_state.username = user["username"]
				st.rerun()
	st.stop()


require_user()
```

Placer `require_user()` juste après `st.title` et l'interrupteur « Réponse vocale ».

### Barre latérale

```python
def show_veille():
	user_id = st.session_state.user_id
	label = PERSONAS[st.session_state.persona]["label"]
	st.sidebar.header(st.session_state.username)
	st.sidebar.caption(label)
	if st.sidebar.button("Rafraîchir la veille"):
		with st.spinner("Lecture des flux…"):
			errors = refresh_user(user_id)
		for error in errors:
			st.sidebar.warning(error)
		if not errors:
			st.sidebar.success("Veille à jour.")
	if st.sidebar.button("Quitter le bord"):
		st.session_state.user_id = None
		st.session_state.messages = []
		st.session_state.loaded_for = None
		st.rerun()

	st.sidebar.subheader("Flux")
	for feed in list_feeds(user_id):
		checked = st.sidebar.checkbox(
			feed["name"],
			value=bool(feed["active"]),
			key=f"feed-{feed['id']}",
		)
		if checked != bool(feed["active"]):
			set_feed_active(feed["id"], user_id, checked)
			st.rerun()
		if feed["last_error"]:
			st.sidebar.caption(feed["last_error"])

	st.sidebar.subheader("Derniers articles")
	from db import recent_articles
	for article in recent_articles(user_id, 8):
		title = article["title"]
		link = article["link"]
		if link:
			st.sidebar.markdown(f"[{title}]({link})")
		else:
			st.sidebar.write(title)
		st.sidebar.caption(article["source"])


show_veille()
```

Le bouton est volontaire. Un rafraîchissement automatique au login ferait attendre jusqu'à huit sites avant d'afficher le chat. Décocher un flux met `active` à 0 : il sort du prochain téléchargement et de l'extrait envoyé au modèle. La case Streamlit a une clé par flux ; après `st.rerun()`, la clé reprend la valeur déjà choisie et la comparaison avec la base ne boucle pas.

Importer `recent_articles` en haut du fichier avec les autres imports de `db`, plutôt que dans la fonction. Le `import` interne ci-dessus montre seulement l'appel.

### Afficher l'historique avec l'avatar

La boucle actuelle :

```python
for message in st.session_state.messages:
	with st.chat_message(message["role"]):
		show_message(message)
```

devient :

```python
for message in st.session_state.messages:
	with open_message(message["role"]):
		show_message(message)
```

Même remplacement pour les deux `with st.chat_message("user")` et `with st.chat_message("assistant")` dans `_handle_turn` : `open_message("user")` et `open_message("assistant")`. Tant que `avatar` est `None`, le rendu est celui d'aujourd'hui.

### Envoyer la veille, puis enregistrer le tour

Au début de `_handle_turn`, après avoir construit `question` et `images`, préparer les deux arguments :

```python
	veille = digest_for(st.session_state.user_id)
	context_path = PERSONAS[st.session_state.persona]["context"]
```

`stream_voice_answer` reçoit ces arguments et les passe à `ask_llm` :

```python
def stream_voice_answer(question, images, stt_s, veille, context_path):
```

et, dans l'appel :

```python
		for fragment in ask_llm(
			question,
			history=st.session_state.messages,
			images=images,
			voice=True,
			veille=veille,
			context_path=context_path,
		):
```

L'appel texte, dans `answer_stream`, reçoit les mêmes `veille` et `context_path` (la fonction imbriquée les voit, elles sont dans `_handle_turn`).

Là où le code fait déjà :

```python
		st.session_state.messages.append(user_message)
		assistant_message = {"role": "assistant", "content": response}
```

ajouter l'écriture en base juste après les deux `append` (utilisateur puis assistant). On n'écrit qu'une fois la réponse obtenue : un `AgentError` ne laisse pas un demi-tour.

```python
		add_message(st.session_state.user_id, "user", question, images)
		add_message(st.session_state.user_id, "assistant", response)
```

`images` est la liste de data URL déjà construite. Elle peut peser : c'est le prix pour réafficher la photo au prochain login. L'audio (`speech`) et les durées (`stt_s`, `llm_s`, …) restent dans `session_state` pour la session en cours, pas dans la base.

## Étape 7 — `.gitignore`

Sous la ligne `.env`, ajouter :

```text
data/*.db
data/*.db-*
```

`journal_mode = WAL` crée aussi `jarvis.db-wal` et `jarvis.db-shm`. Le motif `data/*.db-*` les couvre.

## Ce que le modèle reçoit

À chaque question, `ask_llm` reconstruit :

1. le texte de `context.txt` (plus tard, le fichier du persona) ;
2. la consigne « réponds en français » ;
3. l'extrait de veille, douze articles au plus, résumé coupé à 400 caractères ;
4. en vocal seulement, la consigne de longueur.

Puis l'historique de **ce** `user_id`, puis la question. Les articles d'un autre compte ne sont pas dans la requête : `recent_articles` filtre sur `user_id`.

Une question du type « quoi de neuf en ce moment » s'appuie sur cet extrait. Une question hors veille reste une réponse du Capitaine, avec la phrase qui dit que la veille ne contenait pas le sujet.

## E-mails, plus tard

La colonne `feeds.kind` vaut `rss` ou, plus tard, `email`. `refresh_user` saute déjà tout ce qui n'est pas `rss`.

Le mot de passe d'une boîte mail ne va ni dans la base, ni dans git, ni dans ce fichier. Le jour venu, une table `mailboxes` (`user_id`, adresse, hôte IMAP, port) décrit la boîte, et le secret reste dans `.env`. Un `mail_watcher.py` lira les messages et appellera le même `upsert_article`, avec un `guid` du type `email:<identifiant du message>`. L'extrait envoyé au modèle ne change pas : il lit `articles`.

## Deux Jarvis, deux avatars, plus tard

Le persona est déjà sur l'utilisateur. Pour séparer les personnages sans retoucher `db.py` :

1. Dupliquer `context.txt` en `context_tech.txt` et `context_finance.txt`, et réécrire le rôle de chacun.
2. Déposer deux images, par exemple `images/avatar_tech.png` et `images/avatar_finance.png`.
3. Dans `PERSONAS`, pointer `context` et `avatar` vers ces fichiers.

`ask_llm` lit `context_path`. `open_message` lit `avatar`. Streamlit accepte un chemin d'image dans `st.chat_message(..., avatar=...)`. Aucune migration SQLite.

## Pièges connus

- Télécharger la page d'accueil HTML ne donne pas les articles. Seule la colonne Flux est passée à `feedparser`.
- EasyBourse ment sur son `Content-Type`. `feedparser` regarde le corps.
- Le délai `socket.setdefaulttimeout` vaut pour tout le processus. Le poser dans `refresh_user`, avant le pool, et laisser les appels Groq sur leur propre `timeout` (déjà `REQUEST_TIMEOUT` dans le client).
- SQLite depuis plusieurs fils : une connexion par appel (`db()`), et `journal_mode = WAL`.
- Avec beaucoup de comptes sur les mêmes URL, le même XML est téléchargé une fois par compte. C'est le prix de listes vraiment séparées. Une table d'articles partagée, avec une table d'abonnements, viendra si les comptes se multiplient.
- Baisser `RSS_ITEMS_IN_PROMPT` si les réponses deviennent lentes : l'extrait est dans chaque appel.

## Vérifier

1. `python rss_watcher.py` affiche trois titres Frandroid.
2. Créer un compte « Veille technologique », cliquer « Rafraîchir la veille ». La barre montre des liens cliquables.
3. Demander « Qu'est-ce qui vient de sortir côté tech ? ». La réponse cite un titre et un lien présents dans la barre.
4. Créer un second compte « Veille financière et économique ». Son historique est vide. Sa barre montre Investing, EasyBourse, le FT, pas Frandroid.
5. Revenir au premier compte : les anciens messages sont réaffichés.
6. Décocher TechCrunch, rafraîchir, reposer une question : TechCrunch n'est plus dans l'extrait.
7. Couper le réseau et rafraîchir : les flux en erreur s'affichent dans la barre, le chat s'ouvre encore, les articles déjà en base restent utilisables.

## Commits

À enchaîner après l'étape 9. `app.py` et `llm_agent.py` contiennent déjà le chat : ne versionner, à chaque commit, que le morceau nommé.

1. `feature: store users feeds and messages in sqlite`
   - `db.py`
   - `config.py` : `DB_PATH`, `PERSONAS`, `PERSONA_FEEDS`
   - `.gitignore` : `data/*.db`

2. `feature: fetch the tech and finance rss feeds`
   - `rss_watcher.py`
   - `requirements.txt` : `feedparser==6.0.14`

3. `feature: give the model the signed-in user's veille`
   - `llm_agent.py` : `veille` et `context_path` sur `ask_llm`
   - `app.py` : compte, barre, enregistrement des messages

4. `doc: explain multi-user rss veille in flux_rss.md`
   - `flux_rss.md`
