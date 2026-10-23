"""Bouton micro : on maintient pour parler, on relâche pour envoyer."""

import os

import streamlit.components.v1 as components

#romain4
_component = components.declare_component(
    "hold_talk",
    path=os.path.join(os.path.dirname(__file__), "frontend"),
)


#romain4
def hold_to_talk(min_seconds, min_peak, key=None):
    """Affiche le bouton à maintenir.

    Au relâchement, renvoie un dictionnaire avec un `id` unique.
    `audio` est un WAV en base64 si l'enregistrement est assez long et audible.
    `error` vaut `short`, `silent` ou `denied` sinon.
    Avant le premier relâchement, renvoie `None`.
    """
    return _component(
        min_seconds=min_seconds,
        min_peak=min_peak,
        key=key,
        default=None,
    )
