# ConversationAgent — dialogue, image, voix, historique

**9 fonctions** à coder pour ce lot : `read_file`, `encode_image`, `prepare_image`, `build_content`, `history_has_image`, `get_conversation_history`, `update_conversation_history`, `ask_llm`, `transcribe`.

**Environ 8 heures** sans IA, en débutant en orienté objet. Une journée. Le temps passe dans l'image (Pillow, base64) et dans l'appel Groq qui renvoie le texte par morceaux. Les neuf fonctions tiennent dans une classe. Quatre fonctions autour servent seulement à les faire s'appeler : `_client`, `_clear_message`, `messages_for_api`, `_stream`.

Ce guide part de zéro pour ce dialogue seulement. Pas de comptes, pas de flux RSS, pas de Gmail, pas de vidéo. Dans le dépôt actuel, la classe s'appelle `Conversation_Manager` et vit dans `llm_agent.py`. Quatre noms y sont déjà : `read_file`, `ask_llm`, `transcribe`, `prepare_image`. Les cinq autres ne sont pas encore des fonctions séparées. Coller ce guide par-dessus `llm_agent.py` retirerait la veille et la réponse lue à voix haute : on écrit un fichier à part, `conversation_agent.py`.

## Ce que le lot fait

L'utilisateur écrit, dicte, ou joint une photo. La photo est réduite, encodée, puis envoyée avec la question. La dictée devient du texte avant d'entrer dans l'historique. L'objet garde les tours. Au tour suivant, `ask_llm` les renvoie au modèle. Une question de suivi sur la dernière photo n'oblige pas à la joindre encore.

`openai/gpt-oss-120b` lit le texte. Il ne lit pas les images. Dès qu'une photo est dans la requête, l'appel part sur `qwen/qwen3.8-27b`.

## Ordre

1. `requirements.txt`, `.env`, `context.txt`.
2. La classe, dans l'ordre des fonctions ci-dessous.
3. Une seule ligne `agent = ConversationAgent()` au niveau du fichier.
4. La page Streamlit qui appelle `prepare_image`, `transcribe`, `ask_llm`, puis `update_conversation_history`.
5. Les essais en bas de ce guide.

Les fichiers nouveaux s'écrivent avec 4 espaces.

## Fichiers autour

`requirements.txt` pour ce lot seulement :

```text
groq==1.7.0
pillow==12.3.0
python-dotenv==1.2.4
streamlit==1.66.0
```

`.env` contient `GROQ_KEY=`, avec la clé Groq. Le fichier ne se versionne pas.

`context.txt` est le personnage. `read_file` le relit à chaque question. Sans ce fichier, `ask_llm` s'arrête sur `FileNotFoundError`.

Installation, depuis le dossier du projet, avec le Python du dossier `env` :

```bash
env/bin/python -m pip install -r requirements.txt
```

## Le fichier `conversation_agent.py`

À recopier tel quel. Les commentaires disent quelle fonction du lot est laquelle.

```python
import base64
import io
import os

from dotenv import load_dotenv
from groq import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    Groq,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
)
from PIL import Image

load_dotenv()

ENV_KEY = "GROQ_KEY"
CONTEXT_PATH = "context.txt"
TEXT_MODEL = "openai/gpt-oss-120b"
VISION_MODEL = "qwen/qwen3.8-27b"
WHISPER_MODEL = "whisper-large-v3-turbo"
LANGUAGE_INSTRUCTION = (
    "Tu réponds toujours en français. "
    "Tu n'écris jamais en anglais, même pour refuser."
)
MAX_IMAGES = 3
MAX_SIDE = 1280
MAX_JPEG_BYTES = 4 * 1024 * 1024
REQUEST_TIMEOUT = 60
MAX_RETRIES = 1
IMAGE_ONLY_QUESTION = "Que vois-tu sur cette image ?"


class AgentError(Exception):
    """Message déjà rédigé pour la page, sans trace Python."""


def _clear_message(error, *, had_image=False):
    # L'ordre compte : un délai dépassé est aussi une erreur de connexion.
    if isinstance(error, APITimeoutError):
        return "Le délai de réponse est dépassé. Réessaie dans un instant."
    if isinstance(error, APIConnectionError):
        return "Impossible de joindre Groq. La connexion réseau a l'air coupée."
    if isinstance(error, AuthenticationError):
        return "La clé API est refusée. Vérifie GROQ_KEY dans le fichier .env."
    if isinstance(error, PermissionDeniedError):
        return "L'accès à Groq est refusé. Vérifie la clé API et les droits du compte."
    if isinstance(error, RateLimitError):
        return "Le quota Groq est dépassé (erreur 429). Attends un moment, puis réessaie."
    if had_image and isinstance(error, (BadRequestError, UnprocessableEntityError)):
        return "L'image a été refusée. Envoie un PNG ou un JPEG."
    if had_image and isinstance(error, APIStatusError) and error.status_code == 413:
        return "L'image a été refusée : le fichier est trop lourd."
    if isinstance(error, APIStatusError):
        return f"Groq a refusé la requête (erreur {error.status_code}). Réessaie dans un instant."
    return "La requête vers Groq a échoué. Réessaie dans un instant."


class ConversationAgent:
    def __init__(self):
        # Le client est créé au premier appel : une clé absente s'affiche dans la page.
        self.groq_client = None
        self.conversation_history = []

    def _client(self):
        if self.groq_client is None:
            key = os.environ.get(ENV_KEY, "").strip()
            if not key:
                raise AgentError(
                    "La clé API est absente. "
                    "Copie .env.example vers .env et mets ta clé Groq dans GROQ_KEY."
                )
            self.groq_client = Groq(
                api_key=key,
                timeout=REQUEST_TIMEOUT,
                max_retries=MAX_RETRIES,
            )
        return self.groq_client

    # Lot : lire le personnage.
    @staticmethod
    def read_file(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()

    # Lot : octets JPEG vers une data URL.
    @staticmethod
    def encode_image(data):
        encoded = base64.standard_b64encode(data).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    # Lot : photo du téléphone vers le JPEG que encode_image transforme.
    @staticmethod
    def prepare_image(raw):
        try:
            image = Image.open(io.BytesIO(raw))
            image.load()
        except Exception as error:
            raise AgentError(
                "Cette image ne peut pas être lue. Envoie un PNG ou un JPEG."
            ) from error
        image = image.convert("RGB")
        image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)

        quality = 85
        data = b""
        while True:
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=quality, optimize=True)
            data = buffer.getvalue()
            if len(data) <= MAX_JPEG_BYTES:
                break
            if quality > 50:
                quality -= 10
                continue
            width, height = image.size
            if max(width, height) <= 480:
                break
            image = image.resize(
                (max(1, width // 2), max(1, height // 2)),
                Image.Resampling.LANCZOS,
            )
        return ConversationAgent.encode_image(data)

    # Lot : texte seul, ou texte plus blocs image pour Groq.
    @staticmethod
    def build_content(text, images):
        if not images:
            return text
        blocks = [{"type": "text", "text": text}]
        for url in images[:MAX_IMAGES]:
            blocks.append({
                "type": "image_url",
                "image_url": {"url": url},
            })
        return blocks

    # Lot : vrai dès qu'une photo part dans cette requête.
    @staticmethod
    def history_has_image(history, images):
        if images:
            return True
        for message in history:
            if message.get("images"):
                return True
        return False

    # Lot : copie des tours déjà eus. La liste de l'objet ne bouge pas.
    def get_conversation_history(self):
        return list(self.conversation_history)

    # Lot : un tour de plus, après la réponse complète.
    def update_conversation_history(self, role, content, images=None):
        message = {"role": role, "content": content}
        if images:
            message["images"] = list(images)
        self.conversation_history.append(message)

    # Garde les blocs image du dernier tour qui en avait.
    # Les photos plus anciennes deviennent une phrase.
    @staticmethod
    def messages_for_api(history, current_images):
        last_image_index = None
        if not current_images:
            for index, message in enumerate(history):
                if message.get("images"):
                    last_image_index = index

        api_messages = []
        for index, message in enumerate(history):
            text = message.get("content") or ""
            images = message.get("images") or []
            if message["role"] == "user" and images and index == last_image_index:
                api_messages.append({
                    "role": "user",
                    "content": ConversationAgent.build_content(text, images),
                })
                continue
            if message["role"] == "user" and images:
                note = text
                if note:
                    note += "\n"
                note += (
                    "[Photo non renvoyée. "
                    "La réponse de l'assistant qui suit décrit ce qu'elle montrait.]"
                )
                api_messages.append({"role": "user", "content": note})
                continue
            api_messages.append({"role": message["role"], "content": text})
        return api_messages

    # Lot : question, historique, images. Le texte revient par morceaux.
    def ask_llm(self, question, history=None, images=None):
        if history is None:
            history = self.get_conversation_history()
        if images is None:
            images = []

        system = self.read_file(CONTEXT_PATH) + "\n\n" + LANGUAGE_INSTRUCTION
        sees_image = self.history_has_image(history, images)
        messages = [
            {"role": "system", "content": system},
            *self.messages_for_api(history, images),
            {
                "role": "user",
                "content": self.build_content(question, images),
            },
        ]
        model = VISION_MODEL if sees_image else TEXT_MODEL
        yield from self._stream(messages, model, sees_image)

    def _stream(self, messages, model, sees_image):
        request = {
            "messages": messages,
            "model": model,
            "stream": True,
        }
        # include_reasoning est réservé au modèle texte.
        if not sees_image:
            request["include_reasoning"] = False
        try:
            stream = self._client().chat.completions.create(**request)
            for chunk in stream:
                if not chunk.choices:
                    continue
                fragment = chunk.choices[0].delta.content
                if fragment:
                    yield fragment
        except AgentError:
            raise
        except Exception as error:
            raise AgentError(_clear_message(error, had_image=sees_image)) from error

    # Lot : WAV vers le texte qui entrera dans l'historique.
    def transcribe(self, audio):
        raw = audio.getvalue() if hasattr(audio, "getvalue") else audio
        try:
            transcription = self._client().audio.transcriptions.create(
                file=("message.wav", raw),
                model=WHISPER_MODEL,
                language="fr",
            )
        except AgentError:
            raise
        except Exception as error:
            raise AgentError(_clear_message(error, had_image=False)) from error
        return transcription.text.strip()


# Un seul objet pour toute la page. Un objet neuf à chaque question oublie l'historique.
agent = ConversationAgent()


def prepare_image(raw):
    return agent.prepare_image(raw)


def ask_llm(question, history=None, images=None):
    return agent.ask_llm(question, history=history, images=images)


def transcribe(audio):
    return agent.transcribe(audio)


def get_conversation_history():
    return agent.get_conversation_history()


def update_conversation_history(role, content, images=None):
    agent.update_conversation_history(role, content, images=images)
```

## À quoi sert chaque fonction

`read_file` ouvre `context.txt` en lecture et renvoie tout le texte. `ask_llm` l'appelle à chaque question. Le personnage n'est pas recopié dans l'historique : il est relu.

`encode_image` prend les octets JPEG déjà réduits. `base64` les transforme en texte, et le préfixe `data:image/jpeg;base64,` dit au modèle que c'est un JPEG. Cette fonction ne redimensionne rien.

`prepare_image` reçoit les octets de la photo jointe. Pillow les ouvre, passe en RGB, ramène le plus grand côté à 1 280 pixels, puis enregistre un JPEG. Au-dessus de 4 Mo, la qualité baisse, puis les dimensions. Le retour est le résultat de `encode_image`. Un fichier qui n'est pas une image lève `AgentError` avant l'appel Groq. Groq refuse une requête au-delà de 20 Mo, et le base64 ajoute environ un tiers : une photo de téléphone doit passer par ici.

`build_content` laisse le texte tel quel quand il n'y a pas d'image. Avec une image, `content` devient une liste : un bloc `text`, puis un bloc `image_url` par photo, au plus 3. `ask_llm` s'en sert pour la question en cours. `messages_for_api` s'en sert pour la dernière photo déjà posée.

`history_has_image` répond oui si la question en cours a des photos, ou si un tour déjà eu en a. Dans ce cas `ask_llm` choisit le modèle vision. Une photo ancienne est encore renvoyée par `messages_for_api` tant qu'aucune nouvelle photo n'arrive, donc le modèle vision reste le bon pour une question de suivi.

`get_conversation_history` renvoie une copie de la liste. Celui qui modifie cette copie ne change pas l'objet. `ask_llm` l'utilise quand aucun historique n'est passé en argument.

`update_conversation_history` ajoute un dictionnaire `role` / `content`. Les images, si la page en donne, sont les data URL déjà produites par `prepare_image`, pas les octets bruts. On l'appelle deux fois par tour, après que le texte de la réponse est complet : une fois `user`, une fois `assistant`. L'appeler avant la fin du flux enregistre une réponse vide. L'appeler avant `ask_llm` met la question dans l'historique et `ask_llm` l'envoie une deuxième fois.

`ask_llm` assemble le message système (`read_file` + la consigne de français), les tours de `messages_for_api`, puis la question via `build_content`. `stream=True` fait revenir le texte par fragments. `yield` les laisse sortir un par un. La page les affiche avec `st.write_stream`. La question en cours n'est pas encore dans l'historique au moment de l'appel.

`transcribe` envoie le WAV à `whisper-large-v3-turbo`. Le nom `message.wav` dit le format à Groq. `language="fr"` évite qu'il devine l'anglais. Le retour est une chaîne. Le modèle de chat ne voit jamais le fichier audio. L'historique non plus : la page enregistre cette chaîne comme un texte tapé.

`messages_for_api` n'est pas une des 9 fonctions du lot. Sans elle, chaque photo de la séance repartirait à chaque question. Groq compte 2 048 jetons par image, et 3 images maximum. La requête ne garde les blocs image que du dernier tour qui en avait. Les plus anciennes sont remplacées par une phrase. Le texte de l'assistant qui suivait ces photos reste : c'est lui qui dit ce qu'elles montraient.

## La page, pour ce lot seulement

Fichier `conversation_page.py`. Il n'est pas `app.py`. Il sert à vérifier les 9 fonctions sans les comptes ni la veille.

`update_conversation_history` est après `st.write_stream`. `ask_llm` lit donc l'historique d'avant ce tour, et la question n'y est qu'une fois.

```python
import streamlit as st

from conversation_agent import (
    IMAGE_ONLY_QUESTION,
    MAX_IMAGES,
    AgentError,
    ask_llm,
    get_conversation_history,
    prepare_image,
    transcribe,
    update_conversation_history,
)

st.title("Conversation")

for message in get_conversation_history():
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        for url in message.get("images") or []:
            st.image(url)

user_input = st.chat_input(
    "Ton message",
    accept_file="multiple",
    file_type=["png", "jpg", "jpeg"],
    accept_audio=True,
)

if not user_input:
    st.stop()

parts = []
typed = (user_input.text or "").strip()
if typed:
    parts.append(typed)

try:
    if user_input.audio is not None:
        spoken = transcribe(user_input.audio)
        if spoken:
            parts.append(spoken)
    uploads = user_input.files or []
    if len(uploads) > MAX_IMAGES:
        st.warning(f"Seules les {MAX_IMAGES} premières images sont envoyées.")
    images = [
        prepare_image(uploaded.getvalue())
        for uploaded in uploads[:MAX_IMAGES]
    ]
    question = "\n".join(parts)
    if images and not question:
        question = IMAGE_ONLY_QUESTION
    if not question and not images:
        st.stop()

    with st.chat_message("user"):
        st.markdown(question)
        for url in images:
            st.image(url)
    with st.chat_message("assistant"):
        response = st.write_stream(ask_llm(question, images=images))
    update_conversation_history("user", question, images or None)
    update_conversation_history("assistant", response)
except AgentError as error:
    st.error(str(error))
```

Lancement :

```bash
env/bin/python -m streamlit run conversation_page.py
```

## Essais

| Essai | Résultat attendu |
| --- | --- |
| Question texte | Le texte arrive par morceaux, en français. |
| Même fil, deuxième question | La réponse tient compte de la première. `get_conversation_history` a 4 tours. |
| Fichier qui n'est pas une image | `prepare_image` lève « Cette image ne peut pas être lue ». Aucun appel Groq. |
| Photo PNG ou JPEG | `prepare_image` renvoie une chaîne qui commence par `data:image/jpeg;base64,`. |
| Photo, puis une question sans la joindre | `history_has_image` est vrai, le modèle vision répond encore sur cette photo. |
| Deuxième photo | La requête envoie la nouvelle. L'ancienne est la phrase « Photo non renvoyée ». |
| Message seulement dicté | `transcribe` renvoie du français. L'historique contient ce texte, pas le WAV. |
| `GROQ_KEY` vide | La page affiche la phrase sur la clé absente, pas une trace Python. |
| `ConversationAgent()` appelé dans la page à chaque tour | L'historique repart à vide. La ligne `agent = ConversationAgent()` reste au niveau du module. |

`prepare_image` et `history_has_image` se vérifient sans réseau : une image faite avec Pillow, et une liste de deux messages dont un a `images`.

## Pièges

`history=[]` écrit dans la signature est une seule liste partagée entre tous les appels. L'argument par défaut est `None`. La liste vide se crée dans la fonction, ou vient de `get_conversation_history`.

`*self.messages_for_api(...)` enlève les crochets. Sans l'étoile, Groq recevrait une liste dans une liste et refuserait l'appel.

`encode_image` sur la photo d'origine, sans `prepare_image`, envoie un fichier trop lourd. Les deux fonctions restent séparées : l'une réduit, l'autre encode.

La data URL stockée par `update_conversation_history` est celle que `messages_for_api` renverra au tour suivant. Stocker les octets bruts casse `build_content`, qui attend déjà une URL.

Ce lot est un seul dialogue dans la mémoire du processus. Fermer le terminal l'efface. Deux personnes sur le même Streamlit partageraient la même liste. Les comptes et l'historique en base sont un autre guide, `flux_rss.md`.
