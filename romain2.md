# Sujet — proposer des sujets, avec ou sans Twitter

**2 fonctions** à coder pour ce lot : `fetch_trends`, `propose_topics`.

**Environ 4 heures** sans IA, en débutant en orienté objet. Une demi-journée. Le temps passe dans l'appel Groq et dans le cas où Twitter ne répond pas. Les deux fonctions tiennent dans une classe `Sujet`. Trois fonctions autour servent seulement à les faire s'appeler : `_client`, `_sources_text`, `_parse_topics`.

Ce guide part de zéro pour ces deux fonctions seulement. Pas de vidéo, pas de Discord, pas de Canva, pas de base de données. Dans le dépôt actuel, aucun fichier Python ne contient `propose_topics` ni `fetch_trends`. On écrit un fichier à part, `sujet.py`. On ne le colle pas dans `rss_watcher.py`.

## Ce que le lot fait

Le compte a un persona : `veille_tech` ou `veille_finance`. `propose_topics` reçoit les articles déjà lus (flux RSS et newsletters retenues) et propose 3 à 5 sujets de ce thème. Chaque sujet cite une source de la liste.

`fetch_trends` demande les tendances Twitter de la France. Si la clé est absente, si Twitter refuse, ou si le délai est dépassé, la fonction renvoie une liste vide. Elle ne lève pas d'erreur. `propose_topics` continue avec les articles seuls.

L'API Twitter ne filtre pas « techno » ou « finance ». Elle renvoie les tendances d'un lieu. Le tri par persona se fait dans la consigne envoyée à Groq : un sujet hors thème est interdit, une tendance hors thème est ignorée.

## Ordre

1. `requirements.txt` et `.env`.
2. La classe `Sujet`, dans l'ordre du fichier ci-dessous.
3. Une seule ligne `sujet = Sujet()` au niveau du fichier.
4. La page qui appelle `propose_topics`.
5. Les essais en bas de ce guide.

Les fichiers nouveaux s'écrivent avec 4 espaces.

## Fichiers autour

`requirements.txt` pour ce lot seulement :

```text
groq==1.7.0
python-dotenv==1.2.4
streamlit==1.66.0
certifi==2026.10.18
```

`.env` :

```text
GROQ_KEY=
X_BEARER_TOKEN=
```

`GROQ_KEY` est obligatoire pour `propose_topics`. `X_BEARER_TOKEN` est le jeton de l'API X. Sans lui, `fetch_trends` renvoie `[]` et les sujets partent quand même des articles. Le fichier `.env` ne se versionne pas.

Installation :

```bash
env/bin/python -m pip install -r requirements.txt
```

## Le fichier `sujet.py`

À recopier tel quel.

```python
import json
import os
import re
import ssl
import urllib.request

import certifi
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

ENV_KEY = "GROQ_KEY"
X_TOKEN_KEY = "X_BEARER_TOKEN"
TEXT_MODEL = "openai/gpt-oss-120b"
LANGUAGE_INSTRUCTION = (
    "Tu réponds toujours en français. "
    "Tu n'écris jamais en anglais, même pour refuser."
)
PERSONAS = {
    "veille_tech": "Veille technologique",
    "veille_finance": "Veille financière et économique",
}
# France. L'API ne connaît pas le persona, seulement un lieu.
WOEID_FRANCE = 23424819
TRENDS_TIMEOUT = 8
MAX_TRENDS = 10
MAX_TOPICS = 5

_TOPIC_LINE = re.compile(r"^\d+[\.\)]\s*")


class SujetError(Exception):
    """Message déjà rédigé pour la page, sans trace Python."""


class Sujet:
    def __init__(self):
        self.groq_client = None

    def _client(self):
        if self.groq_client is None:
            key = os.environ.get(ENV_KEY, "").strip()
            if not key:
                raise SujetError(
                    "La clé API est absente. "
                    "Mets ta clé Groq dans GROQ_KEY, dans le fichier .env."
                )
            self.groq_client = Groq(api_key=key, timeout=60, max_retries=1)
        return self.groq_client

    # Lot : tendances Twitter. Une liste vide si Twitter ne répond pas.
    def fetch_trends(self, persona):
        if persona not in PERSONAS:
            return []
        token = os.environ.get(X_TOKEN_KEY, "").strip()
        if not token:
            return []
        url = (
            f"https://api.x.com/2/trends/by/woeid/{WOEID_FRANCE}"
            f"?max_trends={MAX_TRENDS}&trend.fields=trend_name"
        )
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "Barbe-Quasar",
            },
        )
        try:
            context = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(
                request, timeout=TRENDS_TIMEOUT, context=context
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            return []
        names = []
        for row in payload.get("data") or []:
            if not isinstance(row, dict):
                continue
            name = (row.get("trend_name") or row.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
        return names[:MAX_TRENDS]

    def _sources_text(self, articles, trends):
        lines = []
        for article in articles:
            kind = "newsletter" if article.get("kind") == "email" else "flux"
            source = article.get("source") or ""
            title = article.get("title") or "(sans titre)"
            lines.append(f"- [{kind}] {source} — {title}")
            link = article.get("link") or ""
            if link:
                lines.append(f"  {link}")
        block = "\n".join(lines) if lines else "Aucun article."
        if trends:
            trend_lines = "\n".join(f"- {name}" for name in trends)
        else:
            trend_lines = "Aucune. N'invente pas de tendance Twitter."
        return block, trend_lines

    @staticmethod
    def _parse_topics(text):
        topics = []
        for raw in (text or "").splitlines():
            line = _TOPIC_LINE.sub("", raw.strip())
            parts = [part.strip() for part in line.split("|")]
            if len(parts) < 2 or not parts[0]:
                continue
            topics.append({
                "title": parts[0],
                "source": parts[1],
                "reason": parts[2] if len(parts) > 2 else "",
            })
            if len(topics) == MAX_TOPICS:
                break
        return topics

    # Lot : 3 à 5 sujets du persona, à partir des articles et des tendances.
    def propose_topics(self, persona, articles, trends=None):
        if persona not in PERSONAS:
            raise SujetError(
                "Persona inconnu. Utilise veille_tech ou veille_finance."
            )
        articles = list(articles or [])
        if trends is None:
            trends = self.fetch_trends(persona)
        else:
            trends = list(trends)
        if not articles and not trends:
            return []

        label = PERSONAS[persona]
        articles_text, trends_text = self._sources_text(articles, trends)
        prompt = (
            f"Tu proposes des sujets pour un compte « {label} ».\n"
            "Chaque sujet s'appuie sur un flux, une newsletter ou une tendance "
            "de la liste. Tu n'inventes pas un article, un lien ou une tendance.\n"
            "Techno seulement pour la veille technologique. "
            "Économie et finance seulement pour la veille financière. "
            "Ignore une tendance qui n'est pas du thème.\n"
            "Propose entre 3 et 5 sujets. "
            "S'il y a moins de sources, propose moins, au moins 1.\n"
            "Réponds uniquement avec des lignes de cette forme, "
            "sans phrase avant ni après :\n"
            "1. Titre du sujet | source exacte | une phrase\n\n"
            f"Sources :\n{articles_text}\n\n"
            f"Tendances Twitter :\n{trends_text}\n"
        )
        try:
            completion = self._client().chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": LANGUAGE_INSTRUCTION
                        + " Tu n'inventes pas de source.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
            )
            text = completion.choices[0].message.content or ""
        except SujetError:
            raise
        except Exception as error:
            raise SujetError(
                "La proposition de sujets a échoué. Réessaie dans un instant."
            ) from error
        return self._parse_topics(text)


sujet = Sujet()


def fetch_trends(persona):
    return sujet.fetch_trends(persona)


def propose_topics(persona, articles, trends=None):
    return sujet.propose_topics(persona, articles, trends=trends)
```

## À quoi sert chaque fonction

`fetch_trends` lit `X_BEARER_TOKEN`. Sans jeton, elle s'arrête tout de suite et renvoie `[]`. Avec un jeton, elle appelle `GET https://api.x.com/2/trends/by/woeid/23424819`. `23424819` est la France. Le délai est de 8 secondes. Une erreur réseau, un refus, un JSON inattendu : le `except` renvoie `[]`. Le nom de chaque tendance est le champ `trend_name`, ou `name` si l'API emploie l'autre. Au plus 10 noms.

`propose_topics` prend le persona, la liste d'articles, et les tendances. Si `trends` n'est pas passé, elle appelle `fetch_trends`. Si les deux listes sont vides, elle renvoie `[]` sans appeler Groq. Sinon elle envoie la consigne au modèle texte `openai/gpt-oss-120b`. La réponse attendue est une ligne par sujet, avec trois morceaux séparés par `|` : le titre, la source, une phrase. `_parse_topics` découpe ces lignes et s'arrête à 5. Un persona autre que `veille_tech` ou `veille_finance` lève `SujetError` avant tout appel.

Un article est un dictionnaire. Les clés lues sont `title`, `source`, `link`, `kind`. `kind` vaut `"rss"` ou `"email"`. Les autres clés sont ignorées.

## La page, pour ce lot seulement

Fichier `sujets_page.py`. Trois articles sont écrits dans le fichier pour pouvoir lancer sans la base. Twitter peut être vide : le bouton propose quand même.

```python
import streamlit as st

from sujet import PERSONAS, SujetError, propose_topics

SAMPLE = [
    {
        "kind": "rss",
        "source": "Frandroid",
        "title": "Un nouveau modèle d'IA tient dans un téléphone",
        "link": "https://www.frandroid.com/exemple",
    },
    {
        "kind": "rss",
        "source": "TechCrunch",
        "title": "A startup raises funds for open models",
        "link": "https://techcrunch.com/exemple",
    },
    {
        "kind": "email",
        "source": "Gmail — newsletter",
        "title": "NVIDIA Training Newsletter: Put Your AI Skills Into Practice",
        "link": "",
    },
]

st.title("Sujets")
persona = st.radio(
    "Veille",
    list(PERSONAS),
    format_func=lambda key: PERSONAS[key],
)
if st.button("Proposer des sujets"):
    try:
        topics = propose_topics(persona, SAMPLE)
    except SujetError as error:
        st.error(str(error))
    else:
        if not topics:
            st.warning("Aucun sujet. Ajoute des articles, ou réessaie.")
        for topic in topics:
            st.subheader(topic["title"])
            st.caption(topic["source"])
            if topic["reason"]:
                st.write(topic["reason"])
```

Lancement :

```bash
env/bin/python -m streamlit run sujets_page.py
```

## Plus tard, avec la base du projet

Quand les articles sont déjà en SQLite, on ne réécrit pas `fetch_trends`. On passe les lignes du compte :

```python
rss = recent_articles(user_id, 12, kind="rss")
mail = recent_articles(user_id, 8, kind="email")
for row in rss:
    row["kind"] = "rss"
for row in mail:
    row["kind"] = "email"
topics = propose_topics(persona, rss + mail)
```

`persona` est celui du compte, `veille_tech` ou `veille_finance`. `propose_topics` appelle `fetch_trends` tout seul. Si Twitter ne répond pas, `rss + mail` suffisent.

## Essais

| Essai | Résultat attendu |
| --- | --- |
| `fetch_trends("veille_tech")` sans `X_BEARER_TOKEN` | `[]`, tout de suite, sans erreur. |
| `fetch_trends("veille_finance")` avec un jeton faux | `[]`. La fonction ne lève pas. |
| `propose_topics("veille_tech", [], trends=[])` | `[]`. Groq n'est pas appelé. |
| `propose_topics("autre", SAMPLE)` | `SujetError` : persona inconnu. |
| Bouton avec les 3 articles d'exemple, sans Twitter | 1 à 5 sujets techno. Aucun sujet bourse. |
| Même bouton en `veille_finance` avec des articles finance | Sujets économie. Le titre Frandroid sur l'IA n'est pas repris. |
| `_parse_topics` sur `1. Puce | Frandroid | Une phrase` | Un dictionnaire `title`, `source`, `reason`. |
| Twitter en panne et des articles présents | Des sujets quand même, seulement depuis les articles. |

Le dernier essai se fait en laissant `X_BEARER_TOKEN` vide. C'est le même chemin que Twitter en panne : `fetch_trends` renvoie `[]`.

## Pièges

`fetch_trends` qui lève une erreur empêche les sujets. Tout échec Twitter reste dans le `except` et devient `[]`.

Appeler Groq quand il n'y a ni article ni tendance envoie une liste vide et le modèle invente. Le `return []` avant `_client` évite ça.

L'API Twitter ne prend pas le persona. Mettre `veille_tech` dans l'URL ne filtre rien. Le filtre est la phrase de la consigne.

Une tendance hors thème peut arriver dans `fetch_trends`. `propose_topics` a le droit de l'ignorer. Elle n'a pas le droit d'en inventer une autre.

`|` est le séparateur des trois morceaux. Un titre qui contient `|` casse la ligne. La consigne demande un titre sans ce signe. Si une ligne n'a pas deux morceaux, `_parse_topics` la saute.

Coller `sujet.py` dans `llm_agent.py` mélange deux classes. Ce lot reste un fichier à part.
