#avatar
"""Envoie le WAV déjà lu par l'application à Audio2Face et récupère les blendshapes.

La clé NVIDIA_API_KEY est lue dans .env. Elle n'est jamais écrite dans le code
ni affichée. Le service cloud renvoie des poids ARKit (JawOpen, MouthFunnel…),
pas un maillage déformé.
"""

import array
import io
import os
import sys
import wave

from dotenv import load_dotenv

from config import A2F_FUNCTION_ID, A2F_TARGET, NVIDIA_KEY

#avatar
# Un paquet gRPC peut dépasser la limite par défaut quand le post est long.
_GRPC_OCTETS = 32 * 1024 * 1024
_VISAGE = {
    "upperFaceStrength": 1.0,
    "upperFaceSmoothing": 0.001,
    "lowerFaceStrength": 1.25,
    "lowerFaceSmoothing": 0.006,
    "faceMaskLevel": 0.6,
    "faceMaskSoftness": 0.0085,
    "skinStrength": 1.0,
    "eyelidOpenOffset": 0.0,
    "lipOpenOffset": 0.0,
    "tongueStrength": 1.0,
    "tongueHeightOffset": 0.0,
    "tongueDepthOffset": 0.0,
}
_EMOTION_NEUTRE = {
    "amazement": 0.0,
    "anger": 0.0,
    "cheekiness": 0.0,
    "disgust": 0.0,
    "fear": 0.0,
    "grief": 0.0,
    "joy": 0.0,
    "outofbreath": 0.0,
    "pain": 0.0,
    "sadness": 0.0,
}


class Audio2FaceError(Exception):
    #avatar
    """Audio2Face n'a pas pu animer ce WAV."""


def _cle():
    #avatar
    load_dotenv()
    cle = os.getenv(NVIDIA_KEY, "").strip()
    if not cle:
        raise Audio2FaceError(
            "La clé NVIDIA est absente. "
            "Ajoute NVIDIA_API_KEY dans le fichier .env, sans guillemets."
        )
    return cle


def _pcm_mono(wav_bytes):
    #avatar
    """Ramène le WAV du post en PCM 16 bits, mono, comme l'exige le service."""
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as source:
            canaux = source.getnchannels()
            frequence = source.getframerate()
            largeur = source.getsampwidth()
            trames = source.readframes(source.getnframes())
    except wave.Error as error:
        raise Audio2FaceError("Le son du post n'est pas un WAV lisible.") from error
    if largeur != 2:
        raise Audio2FaceError(
            "Audio2Face attend un WAV PCM 16 bits. "
            f"Celui du post est en {largeur * 8} bits."
        )
    if frequence <= 0 or not trames:
        raise Audio2FaceError("Le WAV du post est vide.")
    echantillons = array.array("h")
    echantillons.frombytes(trames)
    if sys.byteorder != "little":
        echantillons.byteswap()
    if canaux == 1:
        return frequence, echantillons
    mono = array.array("h", (
        sum(echantillons[index:index + canaux]) // canaux
        for index in range(0, len(echantillons) - canaux + 1, canaux)
    ))
    return frequence, mono


def _paquets(echantillons, frequence):
    #avatar
    # Un paquet correspond à une seconde. La taille exacte n'a pas d'importance.
    pas = max(frequence, 1)
    for debut in range(0, len(echantillons), pas):
        morceau = echantillons[debut:debut + pas]
        if morceau:
            yield morceau.tobytes()


def _demandes(frequence, echantillons):
    #avatar
    from nvidia_ace.a2f.v1_pb2 import (
        AudioWithEmotion,
        BlendShapeParameters,
        EmotionPostProcessingParameters,
        FaceParameters,
    )
    from nvidia_ace.audio.v1_pb2 import AudioHeader
    from nvidia_ace.controller.v1_pb2 import AudioStream, AudioStreamHeader
    from nvidia_ace.emotion_with_timecode.v1_pb2 import EmotionWithTimeCode

    yield AudioStream(
        audio_stream_header=AudioStreamHeader(
            audio_header=AudioHeader(
                samples_per_second=frequence,
                bits_per_sample=16,
                channel_count=1,
                audio_format=AudioHeader.AUDIO_FORMAT_PCM,
            ),
            face_params=FaceParameters(float_params=_VISAGE),
            emotion_post_processing_params=EmotionPostProcessingParameters(
                emotion_contrast=1.0,
                live_blend_coef=0.7,
                enable_preferred_emotion=False,
                preferred_emotion_strength=0.5,
                emotion_strength=0.6,
                max_emotions=3,
            ),
            blendshape_params=BlendShapeParameters(enable_clamping_bs_weight=False),
        )
    )
    premier = True
    for paquet in _paquets(echantillons, frequence):
        if premier:
            premier = False
            yield AudioStream(
                audio_with_emotion=AudioWithEmotion(
                    audio_buffer=paquet,
                    emotions=[EmotionWithTimeCode(time_code=0.0, emotion=_EMOTION_NEUTRE)],
                )
            )
        else:
            yield AudioStream(
                audio_with_emotion=AudioWithEmotion(audio_buffer=paquet)
            )
    yield AudioStream(end_of_audio=AudioStream.EndOfAudio())


def _afficher_structure(noms, images):
    #avatar
    """Écrit dans le terminal la forme des données, pour vérifier la synchro."""
    bouches = (
        "JawOpen",
        "MouthClose",
        "MouthFunnel",
        "MouthPucker",
        "MouthSmileLeft",
        "MouthSmileRight",
    )
    print("Audio2Face — structure reçue", flush=True)
    print(f"  blendshapes: {len(noms)} noms ARKit", flush=True)
    print(f"  noms: {noms}", flush=True)
    print(f"  images: {len(images)}", flush=True)
    if not images:
        print("  aucune image d'animation", flush=True)
        return
    premiere = images[0]
    print(f"  premiere_image.time_code: {premiere['time_code']}", flush=True)
    print(f"  premiere_image.poids: {premiere['weights']}", flush=True)
    print(f"  derniere_image.time_code: {images[-1]['time_code']}", flush=True)
    for nom in bouches:
        if nom not in noms and nom not in premiere["weights"]:
            continue
        pic = max(image["weights"].get(nom, 0.0) for image in images)
        print(f"  max {nom}: {pic:.3f}", flush=True)


def _alleger(images):
    #avatar
    # 25 images par seconde suffisent à la bouche. Les poids nuls ne partent pas.
    if not images:
        return []
    gardees = [images[0]]
    for image in images[1:]:
        if image["time_code"] - gardees[-1]["time_code"] >= 0.04:
            gardees.append(image)
    if gardees[-1] is not images[-1]:
        gardees.append(images[-1])
    legeres = []
    for image in gardees:
        poids = {
            nom: round(valeur, 3)
            for nom, valeur in image["weights"].items()
            if valeur >= 0.01
        }
        legeres.append({"time_code": round(image["time_code"], 3), "weights": poids})
    return legeres


def animer_levres(wav_bytes):
    #avatar
    """Envoie le WAV et renvoie les images {time_code, weights} pour Bonnie.

    Affiche aussi la structure complète de la première image dans le terminal
    qui a lancé Streamlit.
    """
    try:
        import grpc
        from nvidia_ace.services.a2f_controller.v1_pb2_grpc import A2FControllerServiceStub
    except ImportError as error:
        raise Audio2FaceError(
            "Le client Audio2Face n'est pas installé. "
            "Les commandes sont dans avatar.md."
        ) from error

    frequence, echantillons = _pcm_mono(wav_bytes)
    canal = grpc.secure_channel(
        A2F_TARGET,
        grpc.ssl_channel_credentials(),
        options=(("grpc.max_receive_message_length", _GRPC_OCTETS),),
    )
    stub = A2FControllerServiceStub(canal)
    noms = []
    images = []
    try:
        reponses = stub.ProcessAudioStream(
            _demandes(frequence, echantillons),
            metadata=(
                ("authorization", "Bearer " + _cle()),
                ("function-id", A2F_FUNCTION_ID),
            ),
            timeout=120,
        )
        for message in reponses:
            if message.HasField("animation_data_stream_header"):
                entete = message.animation_data_stream_header
                if entete.HasField("skel_animation_header"):
                    noms = list(entete.skel_animation_header.blend_shapes)
            elif message.HasField("animation_data"):
                animation = message.animation_data.skel_animation
                for courbe in animation.blend_shape_weights:
                    poids = dict(zip(noms, (float(valeur) for valeur in courbe.values)))
                    images.append({"time_code": float(courbe.time_code), "weights": poids})
            elif message.HasField("status") and message.status.code == 3:
                raise Audio2FaceError(
                    "Audio2Face a renvoyé une erreur : "
                    + (message.status.message or "échec sans détail")
                )
    except Audio2FaceError:
        raise
    except grpc.RpcError as error:
        raise Audio2FaceError(
            "Audio2Face n'a pas répondu. "
            f"{error.code().name} : {error.details()}"
        ) from error
    finally:
        canal.close()

    _afficher_structure(noms, images)
    return _alleger(images)
