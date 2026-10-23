import json
import os
import re
import ssl
import urllib.request

import certifi
from dotenv import load_dotenv
from groq import Groq

from config import (
    ENV_KEY,
    LANGUAGE_INSTRUCTION,
    MAX_TOPICS,
    MAX_TRENDS,
    PERSONAS,
    TEXT_MODEL,
    TRENDS_TIMEOUT,
    WOEID_FRANCE,
    X_TOKEN_KEY,
)

load_dotenv()

_TOPIC_LINE = re.compile(r"^\d+[\.\)]\s*")


#romain2
class SujetError(Exception):
    """Message déjà rédigé pour la page, sans trace Python.

    Levée si le persona est inconnu ou si Groq refuse la proposition de sujets.
    `fetch_trends` ne lève pas cette erreur : Twitter en panne renvoie une liste vide.
    """


#romain2
class Sujet:
    def __init__(self):
        self.groq_client = None

    #romain2
    def _client(self):
        """Crée le client Groq au premier appel.

        Une clé absente lève `SujetError` avec une phrase pour la page.
        """
        if self.groq_client is None:
            key = os.environ.get(ENV_KEY, "").strip()
            if not key:
                raise SujetError(
                    "La clé API est absente. "
                    "Mets ta clé Groq dans GROQ_KEY, dans le fichier .env."
                )
            self.groq_client = Groq(api_key=key, timeout=60, max_retries=1)
        return self.groq_client

    #romain2
    def fetch_trends(self, persona):
        """Renvoie les noms des tendances Twitter en France.

        Sans `X_BEARER_TOKEN`, ou si l'appel échoue, renvoie `[]`.
        Ne lève pas d'erreur : `propose_topics` continue avec les articles.
        L'API ne filtre pas le persona. Le thème est trié plus tard, dans la consigne.
        """
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

    #romain2
    def _sources_text(self, articles, trends):
        """Met les articles et les tendances en texte pour la consigne Groq.

        Chaque article est une ligne `flux` ou `newsletter`, avec son lien.
        Sans tendance, la seconde chaîne dit de ne pas en inventer.
        """
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

    #romain2
    @staticmethod
    def _parse_topics(text):
        """Découpe la réponse du modèle en sujets.

        Chaque ligne retenue a la forme `titre | source | phrase`.
        Une ligne sans `|` est ignorée. Au plus `MAX_TOPICS` sujets.
        """
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

    #romain2
    def propose_topics(self, persona, articles, trends=None):
        """Propose 1 à 5 sujets du persona.

        `articles` sont des dictionnaires `title`, `source`, `link`, `kind`
        (`rss` ou `email`). Si `trends` est omis, appelle `fetch_trends`.
        Sans article et sans tendance, renvoie `[]` sans appeler Groq.
        """
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

        label = PERSONAS[persona]["label"]
        articles_text, trends_text = self._sources_text(articles, trends)
        prompt = (
            f"Tu proposes des sujets de post LinkedIn pour un compte « {label} ».\n"
            "Chaque sujet sert à montrer une compétence à un client, "
            "à partir d'un flux, d'une newsletter ou d'une tendance de la liste. "
            "Tu n'inventes pas un article, un lien ou une tendance.\n"
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


#romain2
sujet = Sujet()


#romain2
def fetch_trends(persona):
    """Même rôle que `Sujet.fetch_trends`."""
    return sujet.fetch_trends(persona)


#romain2
def propose_topics(persona, articles, trends=None):
    """Même rôle que `Sujet.propose_topics`."""
    return sujet.propose_topics(persona, articles, trends=trends)
