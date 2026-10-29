#avatar
"""Bonnie en haut de la page, et lecture du post branchée sur Audio2Face."""

import base64
import hashlib
import os
import shutil
import subprocess

import streamlit as st
import streamlit.components.v1 as components

from avatar.audio2face import Audio2FaceError, animer_levres

#avatar
_DOSSIER = os.path.dirname(__file__)
_vue = components.declare_component(
    "bonnie_view",
    path=os.path.join(_DOSSIER, "view"),
)
_lecteur = components.declare_component(
    "bonnie_player",
    path=os.path.join(_DOSSIER, "player"),
)
#avatar
_film = components.declare_component(
    "bonnie_film",
    path=os.path.join(_DOSSIER, "film"),
)
_boite = None


def mount_avatar(boite):
    #avatar
    """Réserve l'emplacement du haut, créé avant le titre."""
    global _boite
    _boite = boite


def show_avatar():
    #avatar
    """Affiche Bonnie. Sans jeton, la bouche reste au repos."""
    if _boite is None:
        return
    jeton = st.session_state.get("a2f_token") or ""
    empreinte = jeton.split(":", 1)[0]
    images = []
    if empreinte and st.session_state.get("a2f_for") == empreinte:
        images = st.session_state.get("a2f_frames") or []
    with _boite.container():
        message = st.session_state.get("a2f_error") or ""
        if message and empreinte:
            st.caption(message)
        _vue(
            frames=images,
            token=jeton,
            sync=st.session_state.get("a2f_sync") or "audio",
            key="bonnie",
            default=None,
        )


def _assurer(wav, empreinte):
    #avatar
    """Appelle Audio2Face une fois par WAV. Une erreur ne relance pas l'appel."""
    if st.session_state.get("a2f_for") == empreinte:
        return
    try:
        with st.spinner("Audio2Face calcule les lèvres…"):
            images = animer_levres(wav)
    except Audio2FaceError as error:
        st.session_state.a2f_frames = []
        st.session_state.a2f_error = str(error)
    else:
        st.session_state.a2f_frames = images
        st.session_state.a2f_error = ""
    st.session_state.a2f_for = empreinte


def _images_pour(empreinte):
    #avatar
    """Les blendshapes du son en cours. Les autres lecteurs n'en reçoivent pas."""
    jeton = st.session_state.get("a2f_token") or ""
    if not jeton.startswith(empreinte + ":"):
        return []
    if st.session_state.get("a2f_for") != empreinte:
        return []
    return st.session_state.get("a2f_frames") or []


def _armer(empreinte, suffixe, sync="audio"):
    #avatar
    # Pas de second show_avatar : la clé « bonnie » existe déjà en haut de page.
    jeton = f"{empreinte}:{suffixe}"
    st.session_state.a2f_token = jeton
    st.session_state.a2f_arm = jeton
    st.session_state.a2f_sync = sync


def play_speech(wav, autoplay=False, key=None):
    #avatar
    """Lecteur du post. Le clic sur lecture envoie ce WAV à Audio2Face."""
    if not wav:
        return
    empreinte = hashlib.sha256(wav).hexdigest()[:16]
    if autoplay:
        _assurer(wav, empreinte)
        _armer(empreinte, "auto")
    evenement = _lecteur(
        audio=base64.b64encode(wav).decode("ascii"),
        speech_id=empreinte,
        token=st.session_state.get("a2f_token") or "",
        frames=_images_pour(empreinte),
        sync=st.session_state.get("a2f_sync") or "audio",
        autoplay=_doit_lire(empreinte),
        key=key or f"player-{empreinte}",
        default=None,
    )
    if not evenement or evenement.get("action") != "play":
        return
    if evenement.get("id") != empreinte:
        return
    nonce = str(evenement.get("nonce"))
    if st.session_state.get("a2f_nonce") == nonce:
        return
    st.session_state.a2f_nonce = nonce
    _assurer(wav, empreinte)
    _armer(empreinte, nonce)
    st.rerun()


def _doit_lire(empreinte):
    #avatar
    """Vrai une seule fois : le lecteur démarre avec les lèvres, sans rejouer ensuite."""
    jeton = st.session_state.get("a2f_token") or ""
    if st.session_state.get("a2f_arm") != jeton:
        return False
    if not jeton.startswith(empreinte + ":"):
        return False
    st.session_state.a2f_arm = None
    return True


def _ffmpeg():
    #avatar
    trouve = shutil.which("ffmpeg")
    if trouve:
        return trouve
    for candidat in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if os.path.isfile(candidat):
            return candidat
    raise Audio2FaceError(
        "Installe ffmpeg pour lire le son de la vidéo. Sur Mac : brew install ffmpeg."
    )


def _wav_video(chemin, empreinte):
    #avatar
    """Extrait la piste AAC du mp4 en WAV 16 bits, mono."""
    cache = st.session_state.get("a2f_video_wav") or {}
    if cache.get("id") == empreinte and cache.get("wav"):
        return cache["wav"]
    try:
        resultat = subprocess.run(
            [
                _ffmpeg(), "-v", "error", "-i", chemin,
                "-f", "wav", "-ac", "1", "-ar", "22050", "-c:a", "pcm_s16le", "pipe:1",
            ],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise Audio2FaceError("Le son de la vidéo n'a pas pu être lu.") from error
    if not resultat.stdout:
        raise Audio2FaceError("Cette vidéo n'a pas de piste son.")
    st.session_state.a2f_video_wav = {"id": empreinte, "wav": resultat.stdout}
    return resultat.stdout


def play_video(chemin, key="bonnie-video"):
    #avatar
    """Le clic sur lecture de la vidéo anime la bouche de Bonnie pendant le film."""
    if not chemin or not os.path.isfile(chemin):
        return
    signature = f"{chemin}:{os.path.getmtime(chemin)}".encode()
    empreinte = hashlib.sha256(signature).hexdigest()[:16]
    evenement = _film(
        speech_id=empreinte,
        token=st.session_state.get("a2f_token") or "",
        autoplay=_doit_lire(empreinte),
        key=key,
        default=None,
    )
    if not evenement or evenement.get("action") != "play":
        return
    if evenement.get("id") != empreinte:
        return
    nonce = str(evenement.get("nonce"))
    if st.session_state.get("a2f_nonce") == nonce:
        return
    st.session_state.a2f_nonce = nonce
    try:
        with st.spinner("Lecture du son de la vidéo…"):
            wav = _wav_video(chemin, empreinte)
    except Audio2FaceError as error:
        st.session_state.a2f_frames = []
        st.session_state.a2f_error = str(error)
        st.session_state.a2f_for = empreinte
    else:
        _assurer(wav, empreinte)
    _armer(empreinte, nonce, sync="video")
    st.rerun()
