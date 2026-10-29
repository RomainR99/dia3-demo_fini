#avatar
"""Bonnie en haut de la page, et lecture du post branchée sur Audio2Face."""

import base64
import hashlib
import os

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
        _vue(frames=images, token=jeton, key="bonnie", default=None)


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


def _armer(empreinte, suffixe):
    #avatar
    jeton = f"{empreinte}:{suffixe}"
    st.session_state.a2f_token = jeton
    st.session_state.a2f_arm = jeton
    show_avatar()


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
