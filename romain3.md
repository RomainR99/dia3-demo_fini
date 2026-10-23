# Post — rédiger, modifier, valider

**2 fonctions** à coder pour ce lot : `draft_post`, `save_post_edit`.

**Environ 5 heures** sans IA, en débutant en orienté objet. Une demi-journée, un peu plus si l'appel Groq et la zone de texte de Streamlit coincent. Les deux fonctions tiennent dans une classe `Post`. Autour, pour que l'appel parte : `_client`, `_prompt`, `_ask`, `_articles_text`, `_word_count`, `_plain_post`, `spoken_minutes`, `clear_post`.

Ce guide part de zéro pour le post seulement. Pas de vidéo, pas de Discord, pas de Canva. Dans le dépôt, le fichier est `post.py`. La page qui l'appelle est dans `app.py`, avec le commentaire `#romain3`.

## Ce que le lot fait

L'utilisateur a déjà choisi un sujet, celui que `propose_topics` a proposé. `draft_post` écrit un texte qui se dit en 2 à 3 minutes, en français, sans liste. Il s'appuie sur les flux et les newsletters du compte. Il n'invente pas un chiffre.

L'utilisateur peut changer le texte. `save_post_edit` garde cette version. C'est elle, et pas le brouillon d'origine, qui est prévue pour la vidéo. La vidéo n'existe pas encore : le bouton enregistre seulement.

Un nouveau brouillon efface la version validée. Il faut cliquer encore sur **Enregistrer la version validée**.

150 mots font environ une minute à l'oral. La fourchette est 280 à 480 mots.

## Ordre

1. Ajouter les trois constantes dans `config.py`.
2. Écrire `post.py`.
3. Une seule ligne `post = Post()` au niveau du fichier.
4. Dans la page : bouton **Rédiger** sur un sujet, zone de texte, bouton **Enregistrer la version validée**.
5. Les essais en bas de ce guide.

Les fichiers nouveaux s'écrivent avec 4 espaces. `app.py` garde ses tabulations.

## Constantes

Dans `config.py`, sous les constantes Twitter :

```python
#romain3
# 150 mots par minute à l'oral. 280 à 480 mots font environ 2 à 3 minutes.
POST_WORDS_PER_MINUTE = 150
POST_MIN_WORDS = 280
POST_MAX_WORDS = 480
```

`GROQ_KEY` dans `.env` suffit. Ce lot n'appelle pas Twitter.

## Le fichier `post.py`

À recopier tel quel. Les docstrings disent le rôle de chaque fonction. Le commentaire `#romain3` est au-dessus de chaque fonction de ce lot.

```python
import os
import re

from dotenv import load_dotenv
from groq import Groq

from config import (
    ENV_KEY,
    LANGUAGE_INSTRUCTION,
    PERSONAS,
    POST_MAX_WORDS,
    POST_MIN_WORDS,
    POST_WORDS_PER_MINUTE,
    TEXT_MODEL,
)

load_dotenv()

_FENCE = re.compile(r"^```[a-z]*\n?|```$", re.IGNORECASE)


#romain3
class PostError(Exception):
    """Message déjà rédigé pour la page, sans trace Python.

    Levée si le persona ou le sujet est inutilisable, si Groq ne renvoie pas
    de texte, ou si la version à enregistrer est vide.
    """


#romain3
class Post:
    """Brouillon parlable, puis texte validé par l'utilisateur.

    `draft` est la dernière proposition. `validated` est le texte enregistré.
    Seul `validated` est prévu pour la vidéo. Un nouveau brouillon le remet à vide.
    """

    def __init__(self):
        self.groq_client = None
        self.draft = ""
        self.validated = ""

    #romain3
    def _client(self):
        """Crée le client Groq au premier appel.

        La clé lue est `GROQ_KEY`. Une clé absente lève `PostError`.
        """
        if self.groq_client is None:
            key = os.environ.get(ENV_KEY, "").strip()
            if not key:
                raise PostError(
                    "La clé API est absente. "
                    "Mets ta clé Groq dans GROQ_KEY, dans le fichier .env."
                )
            self.groq_client = Groq(api_key=key, timeout=60, max_retries=1)
        return self.groq_client

    #romain3
    def draft_post(self, persona, topic, articles):
        """Écrit un texte parlable de 2 à 3 minutes sur le sujet choisi.

        `topic` est un dictionnaire `title`, `source`, `reason`, comme ceux
        de `propose_topics`. `articles` sont les flux et newsletters du compte.
        Le texte n'a pas de liste ni de markdown : il est prévu pour être dit.
        Hors de la fourchette de mots, un second appel demande de réécrire.
        Le brouillon remplace `validated` : il faut réenregistrer après.
        """
        if persona not in PERSONAS:
            raise PostError(
                "Persona inconnu. Utilise veille_tech ou veille_finance."
            )
        title = (topic or {}).get("title", "").strip()
        if not title:
            raise PostError("Choisis un sujet avant de rédiger.")
        source = (topic or {}).get("source") or ""
        reason = (topic or {}).get("reason") or ""
        label = PERSONAS[persona]["label"]
        articles_text = _articles_text(articles or [])
        prompt = self._prompt(label, title, source, reason, articles_text)
        text = self._ask(prompt)
        words = _word_count(text)
        if words < POST_MIN_WORDS or words > POST_MAX_WORDS:
            text = self._ask(
                prompt
                + f"\nTon texte faisait {words} mots. "
                + f"Réécris-le entre {POST_MIN_WORDS} et {POST_MAX_WORDS} mots."
            )
        if not text:
            raise PostError("Le modèle n'a pas renvoyé de texte. Réessaie.")
        self.draft = text
        self.validated = ""
        return text

    #romain3
    def _prompt(self, label, title, source, reason, articles_text):
        """Construit la consigne : durée, thème, et sources autorisées."""
        return (
            f"Tu rédiges un post oral pour un compte « {label} ».\n"
            f"Sujet : {title}\n"
            f"Source du sujet : {source}\n"
            f"Pourquoi ce sujet : {reason}\n\n"
            "Le texte se dit à voix haute en 2 à 3 minutes, "
            f"entre {POST_MIN_WORDS} et {POST_MAX_WORDS} mots.\n"
            "Phrases courtes. Pas de titre, pas de liste, pas de markdown, "
            "pas d'emoji.\n"
            "Appuie-toi sur les sources ci-dessous. "
            "Tu n'inventes pas un chiffre, une citation ou un article absent.\n"
            "Si les sources ne couvrent pas le sujet, dis-le dans le post "
            "et reste sur ce qu'elles contiennent.\n\n"
            f"Sources :\n{articles_text}\n"
        )

    #romain3
    def _ask(self, prompt):
        """Envoie la consigne à Groq et renvoie le texte nettoyé."""
        try:
            completion = self._client().chat.completions.create(
                model=TEXT_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": LANGUAGE_INSTRUCTION
                        + " Tu écris un texte à dire, sans liste.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
            )
            raw = completion.choices[0].message.content or ""
        except PostError:
            raise
        except Exception as error:
            raise PostError(
                "La rédaction du post a échoué. Réessaie dans un instant."
            ) from error
        return _plain_post(raw)

    #romain3
    def save_post_edit(self, text):
        """Garde le texte modifié par l'utilisateur comme version validée.

        Les espaces en trop sont retirés. Un texte vide lève `PostError`.
        C'est cette chaîne, et non le brouillon d'origine, qui est prévue
        pour la vidéo.
        """
        cleaned = (text or "").strip()
        if not cleaned:
            raise PostError("Le texte validé est vide.")
        self.draft = cleaned
        self.validated = cleaned
        return cleaned

    #romain3
    def clear_post(self):
        """Oublie le brouillon et la version validée.

        À appeler quand l'utilisateur quitte le compte.
        """
        self.draft = ""
        self.validated = ""


#romain3
post = Post()


#romain3
def _articles_text(articles):
    """Met les flux et les newsletters en lignes pour la consigne.

    Chaque ligne commence par `flux` ou `newsletter`, puis la source et le titre.
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
    return "\n".join(lines) if lines else "Aucune source."


#romain3
def _word_count(text):
    """Compte les mots séparés par des espaces."""
    return len((text or "").split())


#romain3
def _plain_post(text):
    """Retire une éventuelle clôture ``` autour de la réponse du modèle."""
    cleaned = (text or "").strip()
    cleaned = _FENCE.sub("", cleaned).strip()
    return cleaned


#romain3
def spoken_minutes(text):
    """Estime la durée orale en minutes, à `POST_WORDS_PER_MINUTE` mots."""
    return _word_count(text) / POST_WORDS_PER_MINUTE


#romain3
def draft_post(persona, topic, articles):
    """Même rôle que `Post.draft_post`."""
    return post.draft_post(persona, topic, articles)


#romain3
def save_post_edit(text):
    """Même rôle que `Post.save_post_edit`."""
    return post.save_post_edit(text)


#romain3
def clear_post():
    """Même rôle que `Post.clear_post`."""
    post.clear_post()
```

## À quoi sert chaque fonction du lot

`draft_post` refuse un persona autre que `veille_tech` ou `veille_finance`, et un sujet sans titre, avant d'appeler Groq. Elle envoie le titre, la source, et les articles. Si le nombre de mots sort de 280 à 480, elle redemande une fois. Le texte renvoyé est aussi dans `post.draft`. `post.validated` redevient vide.

`save_post_edit` prend le texte de la zone, pas celui du modèle. Elle enlève les espaces aux bords. Vide, elle lève `PostError` et ne change pas la version déjà validée... si l'appel lève avant l'affectation. Elle renvoie la chaîne gardée. `post.validated` et `post.draft` deviennent ce texte.

`spoken_minutes` sert à la page : 150 mots, une minute. Ce n'est pas une des deux fonctions du lot. La page l'affiche sous la zone.

`clear_post` vide les deux champs quand l'utilisateur quitte le compte. Le suivant ne récupère pas le post précédent sur l'objet. La session Streamlit est vidée à part.

## La page

Dans `app.py`, chaque sujet proposé a un bouton **Rédiger**. Il pose le sujet dans `st.session_state.chosen_topic` et force un nouveau brouillon avec `post_for = None`.

`_show_post` est appelé après la barre, dans la page. Si le sujet a changé, elle appelle `draft_post`, puis affiche `st.text_area`. Le bouton **Enregistrer la version validée** appelle `save_post_edit` avec le contenu de la zone, donc avec les modifications.

Quitter le bord remet `chosen_topic`, `post_text` et `validated_post` à vide, et appelle `clear_post`.

Un article passé à `draft_post` a les clés `title`, `source`, `link`, `kind`. `kind` vaut `"rss"` ou `"email"`.

## Essais

| Essai | Résultat attendu |
| --- | --- |
| `draft_post("autre", {"title": "Puce"}, [])` | `PostError`, persona inconnu. Groq n'est pas appelé. |
| `draft_post("veille_tech", {}, [])` | `PostError`, sujet sans titre. |
| `save_post_edit("   ")` | `PostError`, texte vide. |
| `save_post_edit("  bonjour le large public  ")` | La chaîne sans espaces aux bords. `post.validated` est cette chaîne. |
| `spoken_minutes` sur 150 mots | `1.0`. |
| **Rédiger** sur un sujet techno | Une zone de texte, une durée affichée autour de 2 à 3 minutes. |
| Modifier un mot puis **Enregistrer** | Le message « Version validée enregistrée ». |
| **Rédiger** un autre sujet | L'ancienne version validée disparaît tant qu'on n'a pas réenregistré. |
| Quitter le bord, revenir | Plus de zone de post. |

Les quatre premiers essais se lancent sans réseau :

```bash
env/bin/python - << 'PY'
from post import PostError, draft_post, save_post_edit, spoken_minutes, post, clear_post
try:
    draft_post("autre", {"title": "Puce"}, [])
except PostError as error:
    print(error)
try:
    save_post_edit("   ")
except PostError as error:
    print(error)
print(save_post_edit("  bonjour le large public  "))
print(post.validated)
print(spoken_minutes("mot " * 150))
clear_post()
print(post.validated == "")
PY
```

## Pièges

La consigne vocale du chat demande 150 à 300 caractères. Ce lot demande 2 à 3 minutes. Ce n'est pas le même appel. `draft_post` n'utilise pas `voice=True`.

Enregistrer avant d'avoir lu le texte fige le brouillon. La vidéo, plus tard, lira `post.validated`, pas la zone si elle a encore changé après le clic.

Un second **Rédiger** remet `validated` à vide dans `draft_post`. L'ancien texte validé ne part pas en vidéo.

`post = Post()` est au niveau du fichier. Un `Post()` dans la page à chaque clic oublie `validated` même sans `clear_post`.

Coller ce fichier dans `sujet.py` mélange deux classes. Le post reste dans `post.py`.
