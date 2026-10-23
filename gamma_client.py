"""Slides Gamma du propriétaire, puis sous-titres calés sur les slides."""

import json
import math
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

import certifi
from dotenv import load_dotenv
from groq import Groq

from config import (
    DEFAULT_SLIDE_LANGUAGE,
    DEFAULT_SUBTITLE_LANGUAGE,
    ENV_KEY,
    GAMMA_API_BASE,
    GAMMA_KEY,
    GAMMA_LANGUAGES,
    GAMMA_POLL_SECONDS,
    GAMMA_POLL_TRIES,
    GAMMA_TIMEOUT,
    POST_WORDS_PER_MINUTE,
    SLIDE_SECONDS,
    TEXT_MODEL,
    VIDEO_MAX_SECONDS,
    #romain7
    EXPORT_POLL_TRIES,
)
from db import (
    gamma_view,
    save_gamma_job,
)

load_dotenv()


#romain6
class GammaError(Exception):
    """Message déjà rédigé pour la page, sans trace Python.

    Levée si la clé manque, si Gamma refuse, ou si le texte approuvé est vide.
    """


#romain6
def slide_count(text):
    """Nombre de slides : une toutes les 10 secondes, 15 au plus.

    La durée vient du nombre de mots, à 150 mots par minute.
    Au-delà de 2 minutes 30, la vidéo et le nombre de slides s'arrêtent.
    Un texte vide renvoie 0.
    """
    words = len((text or "").split())
    if words == 0:
        return 0
    seconds = min(words / POST_WORDS_PER_MINUTE * 60, VIDEO_MAX_SECONDS)
    count = math.ceil(seconds / SLIDE_SECONDS)
    maximum = VIDEO_MAX_SECONDS // SLIDE_SECONDS
    return max(1, min(maximum, count))


#romain6
def owner_key():
    """Clé Gamma du propriétaire, lue dans .env.

    Tous les comptes créent les slides avec cette clé. Elle n'est pas
    demandée dans la page, ni écrite dans la base.
    """
    load_dotenv(override=True)
    key = os.environ.get(GAMMA_KEY, "").strip()
    if len(key) >= 2 and key[0] == key[-1] and key[0] in "'\"":
        key = key[1:-1].strip()
    return key


#romain6
def _request(method, path, api_key, payload=None):
    """Appelle l'API Gamma. La clé part dans l'en-tête, pas dans l'adresse."""
    body = None
    headers = {
        "X-API-KEY": api_key,
        "Accept": "application/json",
        #romain6
        # Sans ce nom, Cloudflare répond 403 et la clé paraît refusée.
        "User-Agent": "Barbe-Quasar/1.0",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        GAMMA_API_BASE + path,
        data=body,
        headers=headers,
        method=method,
    )
    #romain6
    # Python.org sur macOS n'a pas les certificats du système. certifi les fournit.
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(request, timeout=GAMMA_TIMEOUT, context=context) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        if error.code == 401:
            raise GammaError("Clé Gamma refusée. Vérifie GAMMA_API_KEY dans le fichier .env.") from error
        if error.code == 403:
            raise GammaError("Gamma bloque l'appel. Réessaie dans un instant.") from error
        if error.code == 402:
            raise GammaError("Plus assez de crédits Gamma sur le compte du projet.") from error
        raise GammaError("Gamma n'a pas accepté la demande. Réessaie.") from error
    except urllib.error.URLError as error:
        raise GammaError("Gamma ne répond pas. Réessaie dans un instant.") from error
    if not raw:
        return {}
    return json.loads(raw)


#romain6
def create_generation(api_key, text, language, count):
    """Lance les slides. Renvoie l'identifiant à interroger ensuite.

    `language` est le code Gamma des slides. La vidéo parlera cette langue.
    `count` est le nombre de cartes, déjà plafonné à 15.
    """
    if language not in GAMMA_LANGUAGES:
        raise GammaError("Cette langue de slides n'est pas disponible.")
    payload = {
        "inputText": text,
        "textMode": "generate",
        "format": "presentation",
        "numCards": count,
        "cardSplit": "auto",
        "cardOptions": {"dimensions": "16x9"},
        "textOptions": {
            "language": language,
            "amount": "medium",
            "tone": "professionnel",
            "audience": "clients",
        },
        "additionalInstructions": (
            "Une slide toutes les 10 secondes, pour une vidéo d'au plus "
            "2 minutes 30. Chaque slide porte une seule idée. "
            "N'invente pas de chiffre, de client ou de citation."
        ),
    }
    data = _request("POST", "/generations", api_key, payload)
    generation_id = data.get("generationId") or data.get("id") or ""
    if not generation_id:
        raise GammaError("Gamma n'a pas renvoyé de génération. Réessaie.")
    return generation_id


#romain6
def poll_generation(api_key, generation_id):
    """Interroge Gamma jusqu'au lien, ou jusqu'à la fin des essais.

    Un statut `pending` après les essais n'est pas une erreur : la page
    pourra rappeler cette fonction. `failed` lève `GammaError`.
    """
    last = {"status": "pending", "gammaUrl": ""}
    for attempt in range(GAMMA_POLL_TRIES):
        if attempt:
            time.sleep(GAMMA_POLL_SECONDS)
        data = _request("GET", f"/generations/{generation_id}", api_key)
        status = data.get("status") or "pending"
        last = data
        if status == "completed":
            return data
        if status == "failed":
            message = (data.get("error") or {}).get("message") or ""
            raise GammaError(message or "Gamma n'a pas pu créer les slides.")
    return last


#romain6
def _chunks(text, count):
    """Découpe le texte en `count` parts, une par slide."""
    words = (text or "").split()
    if count <= 0:
        return []
    if not words:
        return [""] * count
    size = max(1, math.ceil(len(words) / count))
    parts = []
    for index in range(count):
        piece = words[index * size:(index + 1) * size]
        parts.append(" ".join(piece))
    return parts


#romain6
def _stamp(seconds):
    """Horodatage SRT, à la seconde près."""
    whole = max(0, int(seconds))
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},000"


#romain6
def _translate(text, language):
    """Traduit le texte approuvé vers la langue des sous-titres.

    Le français reste tel quel : le post est déjà en français.
    """
    if language == DEFAULT_SUBTITLE_LANGUAGE:
        return text
    label = GAMMA_LANGUAGES.get(language, language)
    key = os.environ.get(ENV_KEY, "").strip()
    if not key:
        raise GammaError(
            "La clé Groq manque pour traduire les sous-titres. "
            "Mets GROQ_KEY dans le fichier .env."
        )
    client = Groq(api_key=key, timeout=GAMMA_TIMEOUT, max_retries=1)
    try:
        completion = client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[{
                "role": "user",
                "content": (
                    f"Traduis ce texte en {label}. "
                    "Garde le sens. N'invente pas un chiffre, un client "
                    "ou une citation. Pas de liste, pas de markdown.\n\n"
                    f"{text}"
                ),
            }],
            temperature=0.2,
        )
        translated = (completion.choices[0].message.content or "").strip()
    except Exception as error:
        raise GammaError(
            "Les sous-titres n'ont pas pu être traduits. Réessaie."
        ) from error
    if not translated:
        raise GammaError("Les sous-titres n'ont pas pu être traduits. Réessaie.")
    return translated


#romain6
def build_subtitles(user_id, text, subtitle_language, count):
    """Écrit un fichier SRT : un sous-titre toutes les 10 secondes.

    La langue est celle des réglages. Le fichier est sous `data/subtitles`,
    qui n'est pas versionné. Renvoie le chemin.
    """
    if subtitle_language not in GAMMA_LANGUAGES:
        raise GammaError("Cette langue de sous-titres n'est pas disponible.")
    spoken = _translate(text, subtitle_language)
    cues = _chunks(spoken, count)
    lines = []
    for index, cue in enumerate(cues):
        start = index * SLIDE_SECONDS
        end = start + SLIDE_SECONDS
        lines.append(str(index + 1))
        lines.append(f"{_stamp(start)} --> {_stamp(end)}")
        lines.append(cue or "…")
        lines.append("")
    folder = os.path.join("data", "subtitles")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{user_id}.srt")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    return path


#romain6
def send_approved(user_id, text):
    """Envoie le texte approuvé avec la clé Gamma du propriétaire.

    La langue des slides est celle des réglages de l'utilisateur : la vidéo
    parlera la même. Les sous-titres suivent l'autre réglage, français
    par défaut. Si Gamma n'a pas fini, `status` vaut `pending` et
    `gamma_url` est vide.
    """
    approved = (text or "").strip()
    if not approved:
        raise GammaError("Approuve le texte avant de l'envoyer à Gamma.")
    key = owner_key()
    if not key:
        raise GammaError("Mets la clé Gamma du projet dans GAMMA_API_KEY, dans le fichier .env.")
    view = gamma_view(user_id)
    slide_language = view["slide_language"] or DEFAULT_SLIDE_LANGUAGE
    subtitle_language = view["subtitle_language"] or DEFAULT_SUBTITLE_LANGUAGE
    count = slide_count(approved)
    path = build_subtitles(user_id, approved, subtitle_language, count)
    generation_id = create_generation(key, approved, slide_language, count)
    result = poll_generation(key, generation_id)
    status = result.get("status") or "pending"
    url = result.get("gammaUrl") or ""
    save_gamma_job(user_id, generation_id, status, url, count, path)
    return {
        "status": status,
        "gamma_url": url,
        "slide_count": count,
        "slide_language": slide_language,
        "subtitle_language": subtitle_language,
        "subtitle_path": path,
        "generation_id": generation_id,
    }


#romain6
def refresh_generation(user_id):
    """Relit une génération encore en cours et met le lien à jour."""
    key = owner_key()
    view = gamma_view(user_id)
    generation_id = view.get("generation_id") or ""
    if not key or not generation_id:
        raise GammaError("Aucune génération Gamma à vérifier.")
    result = poll_generation(key, generation_id)
    status = result.get("status") or "pending"
    url = result.get("gammaUrl") or view.get("gamma_url") or ""
    save_gamma_job(
        user_id,
        generation_id,
        status,
        url,
        view.get("slide_count") or 0,
        view.get("subtitle_path") or "",
    )
    return {"status": status, "gamma_url": url}


#romain7
def start_png_export(api_key, gamma_id):
    """Lance l'export PNG des slides déjà créées.

    Gamma renvoie un identifiant d'export, pas encore le fichier.
    L'archive finale contient une image par slide.
    """
    data = _request(
        "POST",
        f"/gammas/{urllib.parse.quote(gamma_id)}/export",
        api_key,
        {"exportAs": "png"},
    )
    export_id = data.get("exportId") or ""
    if not export_id:
        raise GammaError("Gamma n'a pas lancé l'export des slides.")
    return export_id


#romain7
def wait_png_export(api_key, export_id):
    """Attend l'archive PNG. L'adresse de téléchargement ne se garde pas.

    Elle expire au bout d'une semaine et suffit à télécharger le fichier.
    Seul l'appelant l'utilise, le temps du téléchargement.
    """
    for attempt in range(EXPORT_POLL_TRIES):
        if attempt:
            time.sleep(GAMMA_POLL_SECONDS)
        data = _request(
            "GET",
            f"/exports/{urllib.parse.quote(export_id)}",
            api_key,
        )
        status = data.get("status") or "pending"
        if status == "completed":
            url = data.get("exportUrl") or ""
            if not url:
                raise GammaError("Gamma n'a pas renvoyé les images.")
            return url
        if status == "failed":
            message = (data.get("error") or {}).get("message") or ""
            raise GammaError(message or "Gamma n'a pas pu exporter les slides.")
    raise GammaError("L'export des slides n'est pas fini. Réessaie.")
