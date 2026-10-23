import os
import re
import unicodedata

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

#romain5
# Phrases entières, sans accent. « oui » et « vas-y » en font partie.
_AGREEMENTS = {
    "oui", "ouais", "ouai", "ok", "okay", "daccord", "dac",
    "vas y", "allez", "allez y", "go", "banco", "parfait",
    "cest bon", "c est bon", "ca marche", "top", "nickel",
    "fais le", "fonce", "valide", "on y va", "bien sur",
    "exactement", "tout a fait", "je confirme", "confirme",
    "oui vas y", "absolument", "evidemment", "lets go",
    "je suis partant", "partant", "carrement", "redige",
    "redige le post", "cree le post", "creer le post",
    "ecris le post", "lance", "lance le post",
}
#romain5
# Ces débuts demandent d'écrire tout de suite, si la suite donne le sujet.
_WRITE_NOW = (
    "redige",
    "ecris le post",
    "ecris un post",
    "cree le post",
    "creer le post",
    "fais le post",
    "fais un post",
    "lance le post",
    "je veux un post",
    "je veux le post",
    "fais moi un post",
)
#romain5
_GREETINGS = {
    "bonjour", "salut", "hello", "merci", "au revoir",
    "bonne journee", "coucou", "bonsoir", "ciao",
}
#romain5
_EMPTY_WRITE = {"", "le", "le post", "un post", "moi le post", "moi un post"}


#romain5
def _fold(text):
    """Minuscules, sans accent, apostrophe ni trait d'union."""
    normalized = unicodedata.normalize("NFD", (text or "").lower())
    folded = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    folded = folded.replace("'", " ").replace("’", " ").replace("-", " ")
    return " ".join(folded.split())


#romain5
def _asks_to_write(folded):
    """Vrai si la phrase demande un post et donne déjà le sujet."""
    for cue in _WRITE_NOW:
        if folded == cue or folded.startswith(cue + " "):
            extra = folded[len(cue):].strip()
            return extra not in _EMPTY_WRITE
    return False


#romain5
def _is_agreement(folded):
    """Vrai si toute la phrase est un accord, pas un nouveau sujet."""
    if folded in _AGREEMENTS:
        return True
    words = folded.split()
    if not words or len(words) > 4:
        return False
    if words[0] in {"oui", "ouais", "ok", "okay"}:
        return True
    if folded.startswith("vas y") or folded.startswith("allez"):
        return True
    return False


#romain5
def _topic_from(text):
    """Sujet tiré de la phrase dite ou tapée."""
    return {
        "title": text.strip(),
        "source": "conversation",
        "reason": "Sujet donné dans la conversation.",
    }


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
        """Écrit un post LinkedIn de 2 à 3 minutes sur le sujet choisi.

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
            f"Tu rédiges un post LinkedIn pour un professionnel en « {label} ».\n"
            f"Sujet : {title}\n"
            f"Source du sujet : {source}\n"
            f"Pourquoi ce sujet : {reason}\n\n"
            "Le lecteur est un client. Le post montre une compétence réelle "
            "et ce qu'elle change pour ce client. Pas de slogan, pas de promesse inventée.\n"
            "Le texte se lit aussi à voix haute en 2 à 3 minutes, "
            f"entre {POST_MIN_WORDS} et {POST_MAX_WORDS} mots.\n"
            "Phrases professionnelles, vouvoiement possible envers le lecteur. "
            "Pas de titre, pas de liste, pas de markdown, pas d'emoji, pas de hashtag.\n"
            "Appuie-toi sur les sources ci-dessous. "
            "Tu n'inventes pas un chiffre, un client, une citation ou un article absent.\n"
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
                        + " Tu écris un post LinkedIn professionnel, "
                        + "qui montre une compétence à un client, sans liste.",
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

    #romain5
    def post_intent(self, text, pending=False):
        """Classe une phrase avant de rédiger.

        `("confirm", None)` : accord pour le sujet déjà donné
        (oui, vas-y, ou une autre indication courte).
        `("draft", sujet)` : la phrase demande d'écrire maintenant
        et contient le sujet.
        `("offer", sujet)` : la phrase donne un sujet, le bouton
        « Créer le post » peut apparaître.
        `("chat", None)` : le reste de la conversation.

        Une indication courte qui n'est pas dans la liste est demandée
        au modèle, qui répond oui ou non. S'il ne répond pas, la phrase
        reste une conversation.
        """
        folded = _fold(text)
        if not folded or folded in _GREETINGS or folded.startswith("merci"):
            return "chat", None
        if _asks_to_write(folded):
            return "draft", _topic_from(text)
        if _is_agreement(folded):
            return "confirm", None
        words = folded.split()
        if pending and 0 < len(words) <= 8:
            if self._says_yes(text):
                return "confirm", None
        if len(words) >= 2:
            return "offer", _topic_from(text)
        return "chat", None

    #romain5
    def _says_yes(self, text):
        """Demande au modèle si la phrase lance la rédaction.

        Répond False si Groq ne renvoie rien d'utilisable.
        """
        prompt = (
            "Un sujet de post est déjà proposé.\n"
            f"L'utilisateur dit : « {text.strip()} ».\n"
            "Est-ce qu'il demande de rédiger ce post maintenant "
            "(accord, ordre ou encouragement) ?\n"
            "Réponds uniquement par oui ou par non."
        )
        try:
            completion = self._client().chat.completions.create(
                model=TEXT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            raw = completion.choices[0].message.content or ""
        except Exception:
            return False
        return _fold(raw).startswith("oui")


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


#romain5
def post_intent(text, pending=False):
    """Même rôle que `Post.post_intent`."""
    return post.post_intent(text, pending=pending)
