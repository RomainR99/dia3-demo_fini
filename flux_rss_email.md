# Gmail — les newsletters du mois dernier dans la veille

**27 fonctions** à coder : 25 à écrire, 2 déjà là à modifier (`recent_articles` et `digest_for`). À faire après `flux_rss.md`.

**Environ 9 heures** sans IA, en débutant en orienté objet. Souvent une journée et demie. Il n'y a pas de classe à écrire ici, seulement des fonctions. Le temps passe dans la lecture IMAP, le découpage d'un e-mail HTML, et le filtre de thème, plus que dans la base, qui reprend le même schéma que les flux.

## Objectif

Chaque compte peut relier sa boîte Gmail à sa veille. Au rafraîchissement, l'application lit les flux RSS déjà en place, puis les e-mails du mois calendaire précédent dont l'objet contient le mot `newsletter`. Ces e-mails deviennent des articles, au même titre qu'un billet RSS. L'agent les reçoit dans un bloc à part, pour qu'ils ne soient pas poussés dehors par les articles du jour.

Le commentaire `#flux_rss_email` est posé au-dessus de chaque fonction et de chaque changement qui sert cette liaison.

Une newsletter n'est gardée que si son sujet ou son résumé contient un mot du thème du compte : veille technologique, ou veille financière et économique. Les autres sont laissées de côté. Seules les retenues pourront servir de source à un post.

Aujourd'hui, 22 octobre 2026, « le mois dernier » est septembre : du 1er septembre inclus au 1er octobre exclu. En janvier, c'est décembre de l'année précédente.

## Ce qu'il faut régler dans Gmail avant de coder

Gmail refuse le mot de passe habituel du compte. Il faut un mot de passe d'application, et IMAP doit être allumé.

1. Dans Gmail : Paramètres, puis « Voir tous les paramètres », onglet « Transfert et POP/IMAP ». Choisir « Activer IMAP », puis enregistrer.
2. Sur le compte Google : la validation en deux étapes doit être active. Sans elle, Google ne propose pas de mot de passe d'application.
3. Ouvrir [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords). Créer un mot de passe nommé par exemple `Barbe-Quasar`. Google affiche 16 lettres, souvent en quatre groupes. Les espaces ne comptent pas : le code les retire.
4. Ce mot de passe n'est pas celui qui ouvre Gmail dans le navigateur. On le colle dans la barre latérale, une fois. Il est enregistré dans `data/jarvis.db`, fichier déjà ignoré par git. Il ne va ni dans `.env`, ni dans ce document, ni dans un commit.

Une adresse Google Workspace (nom de domaine propre) passe par le même serveur `imap.gmail.com`.

## Ordre pour recoder

1. Ajouter les constantes Gmail dans `config.py`.
2. Ajouter la table `mailboxes` et les fonctions dans `db.py`.
3. Créer `mail_watcher.py`.
4. À la fin de `refresh_user`, appeler `refresh_mailbox`. Dans `digest_for`, séparer le bloc RSS et le bloc newsletters.
5. Dans `app.py`, afficher le formulaire Gmail dans la barre latérale.
6. Lancer l'application, connecter la boîte, rafraîchir, poser une question sur les newsletters.

Aucune dépendance nouvelle : `imaplib`, `email` et `ssl` sont dans Python. `certifi` est déjà là pour les flux RSS.

## Étape 1 — `config.py`

Coller ce bloc juste après `RSS_SUMMARY_CHARS`.

```python
#flux_rss_email
# IMAP Gmail. Le mot de passe d'application reste dans la base locale, pas dans git.
GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_IMAP_PORT = 993
MAIL_SUBJECT = "newsletter"
MAIL_MAX = 30
MAIL_ITEMS_IN_PROMPT = 8
MAIL_TIMEOUT = 60
```

`MAIL_SUBJECT` est le mot cherché dans l'objet. `MAIL_MAX` plafonne le nombre de messages téléchargés. `MAIL_ITEMS_IN_PROMPT` est le nombre envoyé au modèle. `MAIL_TIMEOUT` est le délai de la connexion IMAP, en secondes, plus long que celui d'un flux RSS parce qu'une boîte peut être lourde.

## Étape 2 — la table et les fonctions dans `db.py`

`init_db` crée la table au prochain lancement. Un fichier `jarvis.db` déjà présent reçoit la table sans perdre les comptes ni les flux.

Sous le schéma existant :

```python
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
```

Dans `init_db`, après `conn.executescript(SCHEMA)` :

```python
        #flux_rss_email
        conn.executescript(MAILBOX_SCHEMA)
```

Un utilisateur a au plus une boîte (`UNIQUE` sur `user_id`). Le mot de passe d'application est gardé en clair dans cette table : IMAP doit pouvoir le relire. Le fichier est local et ignoré par git.

`recent_articles` prend un argument `kind`. Sans lui, le comportement reste le même. Avec `kind="email"`, seuls les messages Gmail reviennent. Avec `kind="rss"`, seuls les flux.

```python
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
```

Les fonctions suivantes vont à la fin de `db.py`.

```python
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
```

`save_mailbox` crée aussi une ligne dans `feeds`, avec `kind = 'email'` et l'adresse `gmail://adresse`. `refresh_user` ignore déjà tout ce qui n'est pas `rss`, donc cette ligne n'est jamais téléchargée comme un flux XML. Décocher « Gmail — newsletter » dans la liste des flux arrête la lecture des e-mails sans effacer le mot de passe.

Les champs de la ligne `mailboxes` sont copiés avant la fermeture de la connexion, comme pour `authenticate`. Une ligne SQLite n'est plus lisible une fois la connexion fermée.

## Étape 3 — `mail_watcher.py`

Le fichier entier. Il ne parle pas à Groq. Il ouvre IMAP, cherche, transforme chaque message en dictionnaire du même format qu'un article RSS (`guid`, `title`, `link`, `summary`, `published_at`).

La recherche IMAP est :

```text
SINCE 01-Sep-2026 BEFORE 01-Oct-2026 SUBJECT newsletter
```

`SINCE` est inclus, `BEFORE` est exclu. Les mois sont les abréviations anglaises (`Sep`, `Oct`) : une machine en français ne doit pas écrire `sept.`.

`BODY.PEEK[]` lit le message sans le marquer comme lu. `select(..., readonly=True)` va dans le même sens.

Les newsletters sont souvent du HTML sans partie texte. S'il n'y a pas de `text/plain`, le HTML est gardé et les balises sont retirées. Le résumé est coupé à `RSS_SUMMARY_CHARS` (400 caractères).

Le lien n'est pas une page publique. C'est une recherche Gmail sur le `Message-ID`, qui s'ouvre si le navigateur est connecté au même compte :

```text
https://mail.google.com/mail/u/0/#search/rfc822msgid:...
```

```python
import html
import imaplib
import re
import ssl
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
    RSS_SUMMARY_CHARS,
)
from db import (
    get_mailbox_credentials,
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
def last_month_bounds(today=None):
    today = today or datetime.now(timezone.utc).date()
    first_this = today.replace(day=1)
    if first_this.month == 1:
        first_last = first_this.replace(year=first_this.year - 1, month=12)
    else:
        first_last = first_this.replace(month=first_this.month - 1)
    return first_last, first_this


#flux_rss_email
def imap_date(day):
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
    for entry in entries:
        upsert_article(user_id, feed["id"], **entry)
    mark_feed(feed["id"], None)
    return []
```

`connect_mailbox` essaie d'abord l'ouverture. Le secret n'est écrit qu'ensuite. Une adresse vide ou un mot de passe vide lève `MailError` avant tout appel réseau.

`refresh_mailbox` renvoie une liste de phrases. Liste vide : pas de boîte, flux décoché, ou lecture réussie (même s'il n'y a aucun message). Une phrase : la barre latérale l'affiche, et les flux RSS déjà lus restent en base.

Le `guid` commence par `email:` plus le `Message-ID`. `upsert_article` met à jour la même ligne au rafraîchissement suivant au lieu d'en créer une deuxième.

## Étape 4 — brancher la lecture sur le rafraîchissement

Dans `rss_watcher.py`, importer `refresh_mailbox` et `MAIL_ITEMS_IN_PROMPT`.

À la fin de `refresh_user`, après la boucle des flux RSS :

```python
    #flux_rss_email
    errors.extend(refresh_mailbox(user_id))
    return errors
```

`digest_for` ne peut plus prendre les 12 lignes les plus récentes toutes sources confondues. Les articles RSS du jour sont datés d'octobre, les newsletters de septembre : elles disparaîtraient du message envoyé au modèle. Deux requêtes, deux blocs.

```python
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
    mail_rows = recent_articles(user_id, MAIL_ITEMS_IN_PROMPT, kind="email")
    if not rss_rows and not mail_rows:
        return ""
    lines = [VEILLE_INSTRUCTION, ""]
    if rss_rows:
        lines.append("Veille récente :")
        lines.extend(_digest_lines(rss_rows))
    if mail_rows:
        lines.append("")
        lines.append(
            "Newsletters Gmail du mois dernier "
            "(objet contenant « newsletter ») :"
        )
        lines.extend(_digest_lines(mail_rows))
    return "\n".join(lines)
```

`ask_llm` reçoit déjà `veille`. Rien à changer dans `llm_agent.py` : le bloc newsletters voyage avec le bloc RSS, dans le message système, et n'est pas recopié dans l'historique.

## Étape 5 — la barre latérale dans `app.py`

Imports à ajouter :

```python
	disconnect_mailbox,
	get_mailbox_address,
```

dans l'import de `db`, et :

```python
#flux_rss_email
from mail_watcher import MailError, connect_mailbox
```

Le bouton « Rafraîchir la veille » appelle déjà `refresh_user`. Changer seulement le texte d'attente :

```python
	#flux_rss_email
	if st.sidebar.button("Rafraîchir la veille"):
		with st.spinner("Lecture des flux et de Gmail…"):
			errors = refresh_user(user_id)
```

La liste « Derniers articles » demande `kind="rss"`, pour ne pas mélanger les sujets d'e-mail avec les flux. Juste après, appeler `_show_gmail(user_id)`.

```python
#flux_rss_email
def _show_gmail(user_id):
	st.sidebar.subheader("Gmail")
	saved = get_mailbox_address(user_id)
	if saved:
		st.sidebar.caption(f"Connecté : {saved}")
	address = st.sidebar.text_input("Adresse Gmail", key="gmail_address")
	secret = st.sidebar.text_input(
		"Mot de passe d'application",
		type="password",
		key="gmail_app_password",
	)
	if st.sidebar.button("Connecter Gmail"):
		try:
			connect_mailbox(user_id, address, secret)
		except MailError as error:
			st.sidebar.warning(str(error))
		else:
			st.sidebar.success("Gmail connecté. Rafraîchis la veille pour lire les newsletters.")
	if saved and st.sidebar.button("Déconnecter Gmail"):
		disconnect_mailbox(user_id)
		st.rerun()
	st.sidebar.caption("Newsletters du mois dernier")
	for article in recent_articles(user_id, 8, kind="email"):
		title = article["title"]
		link = article["link"]
		if link:
			st.sidebar.markdown(f"[{title}]({link})")
		else:
			st.sidebar.write(title)
```

`app.py` garde ses tabulations. `_show_gmail` peut être défini plus bas dans le fichier : l'appel a lieu quand la page se dessine, après le chargement de tout le script.

« Déconnecter Gmail » retire la boîte, le flux `email` et les articles déjà lus. Les flux RSS du compte restent.

## Ce que l'agent reçoit

À la question suivante, le message système contient :

1. `context.txt`
2. la consigne de citer le titre et le lien
3. jusqu'à 12 articles RSS
4. jusqu'à 8 newsletters retenues pour le thème du compte, avec l'expéditeur dans le résumé et le lien Gmail. Elles sont une source possible pour un post sur ce thème.

Une question du type « qu'est-ce que j'ai reçu comme newsletters le mois dernier ? » s'appuie sur le bloc 4. Si la boîte n'a rien donné, ce bloc est absent et la consigne déjà en place demande de le dire.

## Retenir le thème du compte

Le mot `newsletter` dans l'objet ne suffit pas. Une newsletter Transilien et une newsletter NVIDIA passent toutes les deux ce filtre, mais seule la seconde parle de technologie. Avant d'enregistrer, `matches_theme` compare le sujet et le résumé aux mots de `PERSONA_MAIL_KEYWORDS`, celui du persona du compte. Les accents sont retirés. Le mot doit être entier : `ia` ne sort pas de `via`.

Un compte `veille_tech` ne garde pas une newsletter qui ne parle que d'inflation. Un compte `veille_finance` ne garde pas une newsletter NVIDIA. Une newsletter qui ne parle d'aucun des deux thèmes n'est gardée pour personne. Au rafraîchissement, les anciennes newsletters du compte sont effacées, puis seules les retenues sont réécrites. L'agent ne reçoit que cette liste, avec la consigne de s'en servir comme source d'un post sur ce thème.

Dans `config.py`, après `MAIL_TIMEOUT` :

```python
#flux_rss_email
# Mots sans accent. La newsletter est retenue si l'un d'eux est un mot du sujet ou du résumé.
PERSONA_MAIL_KEYWORDS = {
    "veille_tech": (
        "intelligence artificielle", "ia", "ai", "llm", "nvidia", "gpu",
        "logiciel", "software", "developpeur", "developer", "programmation",
        "python", "javascript", "android", "iphone", "smartphone",
        "startup", "open source", "github", "cloud", "cybersecurite",
        "puce", "semiconducteur", "robot", "algorithme", "devops",
        "framework", "silicon", "chip",
    ),
    "veille_finance": (
        "bourse", "finance", "economie", "inflation", "investissement",
        "invest", "trading", "bitcoin", "crypto", "cryptomonnaie",
        "nasdaq", "cac", "dividende", "banque", "taux", "marche",
        "wall street", "fed", "bce", "pib", "fiscalite", "epargne",
        "patrimoine", "obligation", "fintech", "cotation", "fonds",
    ),
}
```

Dans `db.py` :

```python
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
```

Dans `mail_watcher.py`, avant `last_month_bounds` :

```python
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
```

À la fin de `refresh_mailbox`, à la place de la boucle qui enregistre tout :

```python
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
```

Dans `digest_for`, ne garder que les lignes qui passent encore le filtre, et nommer le thème :

```python
    #flux_rss_email
    persona = get_user_persona(user_id)
    mail_rows = [
        row for row in recent_articles(user_id, MAIL_ITEMS_IN_PROMPT, kind="email")
        if matches_theme(persona, row["title"], row["summary"])
    ]
```

Le titre du bloc devient : « Newsletters Gmail du mois dernier retenues pour la » plus le libellé du persona, puis la phrase qui dit qu'elles peuvent servir de source pour un post sur ce thème.

Dans `_show_gmail`, la légende et la liste utilisent le même filtre :

```python
	#flux_rss_email
	label = PERSONAS[st.session_state.persona]["label"]
	st.sidebar.caption(f"Newsletters du mois dernier retenues pour : {label}")
	kept = [
		article for article in recent_articles(user_id, 8, kind="email")
		if matches_theme(st.session_state.persona, article["title"], article["summary"])
	]
```

## Vérifier

Sans Gmail, dans le dossier du projet :

```bash
env/bin/python -c "
from datetime import date
from mail_watcher import last_month_bounds, imap_date
print(last_month_bounds(date(2026, 10, 22)))
print(imap_date(date(2026, 9, 1)), imap_date(date(2026, 10, 1)))
"
```

Le résultat attendu est `(datetime.date(2026, 9, 1), datetime.date(2026, 10, 1))` puis `01-Sep-2026 01-Oct-2026`.

Avec la boîte :

1. Lancer `env/bin/python -m streamlit run app.py`.
2. Se connecter au compte.
3. Dans la barre, coller l'adresse Gmail et le mot de passe d'application. Cliquer « Connecter Gmail ». La légende `Connecté : ...` apparaît au prochain affichage.
4. Cliquer « Rafraîchir la veille ». La section « Newsletters du mois dernier retenues pour : … » ne liste que les objets du thème du compte. Une newsletter hors thème affiche « laissée de côté » et n'apparaît pas dans la liste.
5. Demander à l'agent ce que contiennent ces newsletters. La réponse cite un objet présent dans la barre.
6. Décocher « Gmail — newsletter », rafraîchir : les e-mails ne sont plus relus.
7. « Déconnecter Gmail » : la section redevient vide, les flux RSS sont toujours là.

Un mot de passe de compte Gmail, à la place du mot de passe d'application, produit : « Gmail a refusé la connexion. Active IMAP dans les réglages Gmail, et utilise un mot de passe d'application, pas le mot de passe du compte. »

## Pièges

- Le mot cherché est `newsletter`, dans l'objet seulement. Un message qui en parle dans le corps, avec un autre objet, n'est pas pris. Changer le mot se fait dans `MAIL_SUBJECT`.
- Après ce filtre, le thème doit encore correspondre. Les mots sont dans `PERSONA_MAIL_KEYWORDS`. Un sujet qui contient `newsletter` mais parle d'autre chose n'est pas enregistré, et ne pourra pas servir de source à un post.
- Le mois est le mois calendaire précédent, pas les trente derniers jours. Pour une fenêtre glissante, `last_month_bounds` est la seule fonction à réécrire.
- Gmail renvoie les identifiants du plus ancien au plus récent. On garde les `MAIL_MAX` derniers.
- Une newsletter uniquement en HTML a quand même un résumé : les balises sont retirées.
- Le lien ouvre Gmail. Il ne montre pas l'e-mail à quelqu'un qui n'est pas connecté à cette boîte.
- Deux comptes de l'application ont deux boîtes. L'un ne voit pas les newsletters de l'autre : `user_id` filtre les articles.
- Décocher le flux et déconnecter ne font pas la même chose. Décocher suspend la lecture. Déconnecter efface le secret et les articles Gmail de ce compte.
