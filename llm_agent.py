import base64
import io
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
import wave

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

from config import (
    CONTEXT_PATH,
    ENV_KEY,
    FAST_MODEL,
    FRENCH_VOICE,
    LANGUAGE_INSTRUCTION,
    MAX_IMAGES,
    MAX_JPEG_BYTES,
    MAX_RETRIES,
    MAX_SIDE,
    REQUEST_TIMEOUT,
    TEXT_MODEL,
    TTS_MAX_CHARS,
    TTS_MODEL,
    TTS_VOICE,
    VISION_MODEL,
    VOICE_INSTRUCTION,
    VOICE_RETRY,
    WHISPER_MODEL,
)

load_dotenv()


class AgentError(Exception):
    """Message déjà rédigé pour l'interface, sans trace Python."""


def _clear_message(error, *, had_image=False):
    # L'ordre compte : le délai dépassé est aussi une erreur de connexion.
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


class Conversation_Manager:
    def __init__(self):
        # Le client est créé au premier appel : une clé absente s'affiche dans l'interface.
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

    @staticmethod #self n'est pas appélé ici donc la méthode est statique
    def read_file(file_path):
        with open(file_path, "r") as file:
            return file.read()

    #romain1
    @staticmethod
    def encode_image(data):
        """Transforme des octets JPEG en data URL `data:image/jpeg;base64,...`.

        Ne redimensionne pas. `prepare_image` appelle cette fonction après la réduction.
        """
        encoded = base64.standard_b64encode(data).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"

    #romain1
    @staticmethod
    def build_content(text, images):
        """Construit le `content` d'un message Groq.

        Sans image, renvoie le texte. Avec des images, renvoie une liste :
        un bloc texte, puis un bloc `image_url` par photo, au plus `MAX_IMAGES`.
        """
        if not images:
            return text
        blocks = [{"type": "text", "text": text}]
        for url in images[:MAX_IMAGES]:
            blocks.append({
                "type": "image_url",
                "image_url": {"url": url},
            })
        return blocks

    #romain1
    @staticmethod
    def history_has_image(history, images):
        """Dit si cette requête contient une photo.

        Vrai si la question en cours a des images, ou si un tour déjà eu en a.
        `ask_llm` choisit alors le modèle vision.
        """
        if images:
            return True
        for message in history:
            if message.get("images"):
                return True
        return False

    #romain1
    def get_conversation_history(self):
        """Renvoie une copie des tours gardés sur l'objet.

        Modifier la liste renvoyée ne change pas l'objet.
        `ask_llm` l'utilise seulement quand aucun historique n'est passé.
        """
        return list(self.conversation_history)

    #romain1
    def update_conversation_history(self, role, content, images=None):
        """Ajoute un tour à la fin de l'historique de l'objet.

        `images` sont des data URL déjà produites par `prepare_image`.
        On l'appelle après la réponse complète, une fois pour l'utilisateur
        et une fois pour l'assistant.
        """
        message = {"role": role, "content": content}
        if images:
            message["images"] = list(images)
        self.conversation_history.append(message)

    #flux RSS
    #persona
    def ask_llm(self, question, history=None, images=None, voice=False, veille="", context_path=None):
        # Liste vide par défaut : on n'en crée pas une partagée entre les appels.
        #romain1
        if history is None:
            history = self.get_conversation_history()
        if images is None:
            images = []

        #persona
        path = context_path or CONTEXT_PATH
        system = self.read_file(path) + "\n\n" + LANGUAGE_INSTRUCTION
        #flux RSS
        # L'extrait est reconstruit à chaque appel. Il n'entre pas dans l'historique.
        if veille:
            system += "\n\n" + veille
        if voice:
            system += "\n\n" + VOICE_INSTRUCTION

        messages = [
            {
                "role": "system",
                "content": system
            },
            *_history_for_api(history, images),
            {
                "role": "user",
                #romain1
                "content": self.build_content(question, images),
            },
        ]

        # Un bloc image impose le modèle vision, y compris pour une question de suivi.
        # Sans image, le mode vocal prend le modèle le plus petit.
        #romain1
        sees_image = self.history_has_image(history, images)
        if sees_image:
            model = VISION_MODEL
        elif voice:
            model = FAST_MODEL
        else:
            model = TEXT_MODEL

        if not voice:
            yield from self._stream(messages, model, sees_image)
            return

        # On retient les premiers mots : un refus anglais tout fait ne doit pas s'afficher.
        held = []
        released = False
        for fragment in self._stream(messages, model, sees_image):
            if released:
                yield fragment
                continue
            held.append(fragment)
            text = "".join(held)
            if len(text) >= 150 and not _ENGLISH_REFUSAL.search(text):
                released = True
                yield from held
                held = []
        if released:
            return
        text = "".join(held).strip()
        if _voice_reply_is_weak(text):
            messages[0] = {
                "role": "system",
                "content": messages[0]["content"] + "\n\n" + VOICE_RETRY,
            }
            yield from self._stream(messages, model, sees_image)
            return
        yield from held

    def _stream(self, messages, model, sees_image):
        request = {
            "messages": messages,
            "model": model,
            "stream": True,
        }
        if not sees_image:
            request["include_reasoning"] = False

        # stream=True : Groq envoie la réponse par fragments, dès qu'ils sont prêts.
        try:
            stream = self._client().chat.completions.create(**request)
            for chunk in stream:
                # Le dernier fragment n'a parfois pas de choice, seulement l'usage.
                if not chunk.choices:
                    continue
                fragment = chunk.choices[0].delta.content
                if fragment:
                    yield fragment
        except AgentError:
            raise
        except Exception as error:
            raise AgentError(_clear_message(error, had_image=sees_image)) from error

    def transcribe(self, audio):
        # Le nom .wav dit à Groq le format. language="fr" évite qu'il devine l'anglais.
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

    def speak(self, text):
        pieces = split_for_speech(text_for_speech(text))
        if not pieces:
            return None
        chunks = [self._synthesize(piece) for piece in pieces]
        return _concat_wavs(chunks)

    def _synthesize(self, piece):
        # Groq d'abord. S'il refuse, la voix française du Mac produit le WAV.
        if _tts_prefers_groq():
            try:
                audio = self._client().audio.speech.create(
                    model=TTS_MODEL,
                    voice=TTS_VOICE,
                    input=piece,
                    response_format="wav",
                )
                return audio.read()
            except Exception:
                _remember_tts("say")
        return _say_french(piece)


agent = Conversation_Manager()


def prepare_image(raw):
    """Réduit une photo puis la passe à `encode_image`.

    Le plus grand côté est ramené à `MAX_SIDE`. Le JPEG reste sous `MAX_JPEG_BYTES`.
    Un fichier illisible lève `AgentError` avant l'appel Groq.
    """
    # JPEG plus petit, et le type de la data URL correspond aux octets envoyés.
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

    #romain1
    return agent.encode_image(data)


#romain1
def _user_content(text, images):
    return agent.build_content(text, images)


def _history_for_api(history, current_images):
    # Sans nouvelle photo, on renvoie encore la dernière. Les plus anciennes deviennent du texte.
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
                #romain1
                "content": agent.build_content(text, images),
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


#flux RSS
#persona
def ask_llm(question, history=None, images=None, voice=False, veille="", context_path=None):
    return agent.ask_llm(
        question,
        history=history,
        images=images,
        voice=voice,
        veille=veille,
        context_path=context_path,
    )


def transcribe(audio):
    return agent.transcribe(audio)


#romain1
def encode_image(data):
    """Même rôle que `Conversation_Manager.encode_image`."""
    return agent.encode_image(data)


#romain1
def build_content(text, images):
    """Même rôle que `Conversation_Manager.build_content`."""
    return agent.build_content(text, images)


#romain1
def history_has_image(history, images):
    """Même rôle que `Conversation_Manager.history_has_image`."""
    return agent.history_has_image(history, images)


#romain1
def get_conversation_history():
    """Même rôle que `Conversation_Manager.get_conversation_history`."""
    return agent.get_conversation_history()


#romain1
def update_conversation_history(role, content, images=None):
    """Même rôle que `Conversation_Manager.update_conversation_history`."""
    agent.update_conversation_history(role, content, images=images)


#romain1
def reset_conversation_history(messages):
    """Remplace l'historique de l'objet par les tours d'un compte.

    À appeler quand l'utilisateur se connecte, pour ne pas mélanger deux comptes.
    `messages` vient de la session ou de la base.
    """
    agent.conversation_history = []
    for message in messages:
        agent.update_conversation_history(
            message["role"],
            message.get("content") or "",
            message.get("images"),
        )


_CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`]*)`")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARKDOWN = re.compile(r"[*_#~>]+")
_EMOJI = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "]+"
)
_SPACES = re.compile(r"\s+")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_FIRST_SENTENCE = re.compile(r"(.+?(?<!\d)[.!?](?!\d))(?:\s|$)")
_ENGLISH_REFUSAL = re.compile(r"i['’]?m sorry|i can(?:not|['’]t) help", re.IGNORECASE)


def _voice_reply_is_weak(text):
    # Le petit modèle vocal renvoie parfois un refus anglais d'une seule phrase.
    if not text or _ENGLISH_REFUSAL.search(text):
        return True
    return len(text) < 150
_tts_backend = "groq"


def text_for_speech(text):
    # Le markdown, le code et les emojis seraient lus tels quels, y compris les étoiles.
    cleaned = _CODE_BLOCK.sub(" ", text)
    cleaned = _INLINE_CODE.sub(r"\1", cleaned)
    cleaned = _LINK.sub(r"\1", cleaned)
    cleaned = _MARKDOWN.sub("", cleaned)
    cleaned = _EMOJI.sub("", cleaned)
    cleaned = re.sub(r"[\u200d\ufe0e\ufe0f]", "", cleaned)
    cleaned = "".join(
        char for char in cleaned
        if unicodedata.category(char) not in {"So", "Sk", "Cs", "Co", "Cn"}
    )
    return _SPACES.sub(" ", cleaned).strip()


def first_spoken_sentence(text):
    # Le point d'un nombre (12.40) n'est pas la fin de la phrase.
    match = _FIRST_SENTENCE.search(text)
    if not match:
        return None
    sentence = match.group(1).strip()
    if len(text_for_speech(sentence)) < 2:
        return None
    return sentence


def split_for_speech(text):
    pieces = []
    for sentence in _SENTENCE_END.split(text):
        sentence = sentence.strip()
        while len(sentence) > TTS_MAX_CHARS:
            cut = sentence.rfind(" ", 0, TTS_MAX_CHARS)
            if cut <= 0:
                cut = TTS_MAX_CHARS
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            pieces.append(sentence)
    return pieces


def _tts_prefers_groq():
    return _tts_backend == "groq"


def _remember_tts(backend):
    global _tts_backend
    _tts_backend = backend


def _say_french(piece):
    if shutil.which("say") is None:
        raise AgentError(
            "La lecture vocale est indisponible sur cette machine. "
            "La réponse reste affichée en texte."
        )
    descriptor, path = tempfile.mkstemp(suffix=".wav")
    os.close(descriptor)
    try:
        subprocess.run(
            [
                "say",
                "-v", FRENCH_VOICE,
                "-o", path,
                "--file-format=WAVE",
                "--data-format=LEI16@22050",
                piece,
            ],
            check=True,
        )
        with open(path, "rb") as audio_file:
            return audio_file.read()
    except (OSError, subprocess.CalledProcessError) as error:
        raise AgentError(
            "La voix française n'a pas pu être produite. "
            "La réponse reste affichée en texte."
        ) from error
    finally:
        os.remove(path)


def _concat_wavs(chunks):
    if len(chunks) == 1:
        return chunks[0]
    params = None
    frames = []
    for raw in chunks:
        with wave.open(io.BytesIO(raw), "rb") as source:
            if params is None:
                params = source.getparams()
            frames.append(source.readframes(source.getnframes()))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as target:
        target.setparams(params)
        for frame in frames:
            target.writeframes(frame)
    return buffer.getvalue()


def speak(text):
    return agent.speak(text)


def wav_seconds(raw):
    with wave.open(io.BytesIO(raw), "rb") as source:
        rate = source.getframerate() or 1
        return source.getnframes() / rate


def combine_speech(chunks):
    chunks = [chunk for chunk in chunks if chunk]
    if not chunks:
        return None
    return _concat_wavs(chunks)


if __name__ == "__main__":
    question = input("Pose ta question :\n")
    print("\n")
    for fragment in ask_llm(question):
        print(fragment, end="", flush=True)
    print()
