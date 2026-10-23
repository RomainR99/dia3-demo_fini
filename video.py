"""Vidéo : une image Gamma toutes les 10 secondes, voix du post, sous-titres."""

import os
import re
import shutil
import ssl
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import zipfile

import certifi
from PIL import Image, ImageDraw, ImageFont

from config import SLIDE_SECONDS, VIDEO_DOWNLOAD_TIMEOUT
from db import gamma_view, save_video_path
from gamma_client import (
    GammaError,
    owner_key,
    start_png_export,
    wait_png_export,
)
from llm_agent import AgentError, speak, wav_seconds


#romain7
class VideoError(Exception):
    """Message déjà rédigé pour la page, sans trace Python.

    Levée si les slides manquent, si la voix échoue, ou si ffmpeg est absent.
    """


#romain7
def gamma_id_from_url(url):
    """Identifiant lu dans le lien Gamma, pas dans une adresse d'export.

    `https://gamma.app/docs/abc` donne `abc`. Un segment `edit` final
    est ignoré.
    """
    path = urllib.parse.urlparse(url or "").path.strip("/")
    parts = [part for part in path.split("/") if part]
    if not parts:
        return ""
    if parts[-1] in {"edit", "view"} and len(parts) > 1:
        return parts[-2]
    return parts[-1]


#romain7
def _ffmpeg():
    """Chemin de ffmpeg, ou un message si le montage est impossible."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if os.path.isfile(candidate):
            return candidate
    raise VideoError(
        "Installe ffmpeg pour monter la vidéo. Sur Mac : brew install ffmpeg."
    )


#romain7
def _run(cmd, cwd=None):
    """Lance ffmpeg. L'échec devient un message court, sans le journal."""
    try:
        subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as error:
        raise VideoError("Le montage de la vidéo a échoué.") from error


#romain7
def _download(url, dest):
    """Télécharge l'archive des slides. L'adresse n'est pas écrite ailleurs."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Barbe-Quasar/1.0"},
    )
    context = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(
            request,
            timeout=VIDEO_DOWNLOAD_TIMEOUT,
            context=context,
        ) as response:
            data = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError) as error:
        raise VideoError("Le téléchargement des slides a échoué.") from error
    if len(data) > 80_000_000:
        raise VideoError("Les slides sont trop lourdes pour la vidéo.")
    with open(dest, "wb") as handle:
        handle.write(data)


#romain7
def _natural(name):
    """Tri qui place slide-2 avant slide-10."""
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", name)
    ]


#romain7
def _unpack_slides(archive, folder):
    """Une image par slide, dans l'ordre. L'archive est effacée ensuite."""
    with open(archive, "rb") as handle:
        magic = handle.read(8)
    if magic.startswith(b"\x89PNG"):
        dest = os.path.join(folder, "01.png")
        os.replace(archive, dest)
        return [dest]
    images = []
    try:
        with zipfile.ZipFile(archive) as bundle:
            names = [
                name for name in bundle.namelist()
                if name.lower().endswith(".png")
                and ".." not in name
                and not name.startswith("__MACOSX")
            ]
            names.sort(key=_natural)
            for index, name in enumerate(names, start=1):
                dest = os.path.join(folder, f"{index:02d}.png")
                with bundle.open(name) as source, open(dest, "wb") as target:
                    target.write(source.read())
                images.append(dest)
    except zipfile.BadZipFile as error:
        raise VideoError("Gamma n'a pas renvoyé d'images de slides.") from error
    finally:
        if os.path.isfile(archive):
            os.remove(archive)
    return images


#romain7
def export_slides(api_key, gamma_url, folder):
    """Images des slides déjà créées sur Gamma.

    L'adresse d'export sert seulement au téléchargement, puis elle est oubliée.
    """
    gamma_id = gamma_id_from_url(gamma_url)
    if not gamma_id:
        raise VideoError("Le lien Gamma ne contient pas d'identifiant.")
    os.makedirs(folder, exist_ok=True)
    try:
        export_id = start_png_export(api_key, gamma_id)
        export_url = wait_png_export(api_key, export_id)
    except GammaError as error:
        raise VideoError(str(error)) from error
    archive = os.path.join(folder, "slides.zip")
    _download(export_url, archive)
    return _unpack_slides(archive, folder)


#romain7
def read_cues(path):
    """Textes des sous-titres, dans l'ordre, sans les horodatages."""
    if not path or not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as handle:
        raw = handle.read().replace("\r\n", "\n").strip()
    cues = []
    for block in re.split(r"\n\s*\n", raw):
        lines = []
        for line in block.splitlines():
            if "-->" in line or line.strip().isdigit():
                continue
            if line.strip():
                lines.append(line.strip())
        if lines:
            cues.append(" ".join(lines))
    return cues


#romain7
def _split(text, count):
    """Découpe le texte en `count` parts, une par slide."""
    words = (text or "").split()
    if count <= 0:
        return []
    if not words:
        return [""] * count
    size = max(1, (len(words) + count - 1) // count)
    return [" ".join(words[index * size:(index + 1) * size]) for index in range(count)]


#romain7
def cues_for(images, subtitle_path, post_text):
    """Un texte de sous-titre par image.

    Si le fichier a déjà une ligne par slide, il est gardé. Sinon le texte
    des sous-titres, ou le post, est redécoupé.
    """
    count = len(images)
    cues = read_cues(subtitle_path)
    if len(cues) == count:
        return cues
    source = " ".join(cues) if cues else post_text
    return _split(source, count)


#romain7
def _stamp(seconds):
    """Horodatage SRT, à la seconde près."""
    whole = max(0, int(seconds))
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},000"


#romain7
def write_srt(cues, path):
    """Sous-titres calés : un bloc de 10 secondes par slide."""
    lines = []
    for index, cue in enumerate(cues):
        start = index * SLIDE_SECONDS
        end = start + SLIDE_SECONDS
        lines.append(str(index + 1))
        lines.append(f"{_stamp(start)} --> {_stamp(end)}")
        lines.append(cue or "…")
        lines.append("")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


#romain7
def _atempo(source_seconds, target):
    """Filtres pour faire tenir la voix dans la durée d'une slide.

    ffmpeg n'accepte `atempo` qu'entre 0,5 et 2. Au-delà, on enchaîne.
    `apad` complète si la voix reste plus courte.
    """
    if source_seconds <= 0 or target <= 0:
        return "apad"
    remaining = source_seconds / target
    factors = []
    guard = 0
    while remaining > 2 and guard < 8:
        factors.append(2.0)
        remaining /= 2
        guard += 1
    while remaining < 0.5 and guard < 8:
        factors.append(0.5)
        remaining /= 0.5
        guard += 1
    if abs(remaining - 1) > 0.03:
        factors.append(round(remaining, 4))
    if not factors:
        return "apad"
    return ",".join(f"atempo={factor}" for factor in factors) + ",apad"


#romain7
def _silence(ffmpeg, dest):
    """Dix secondes sans voix, pour une slide dont le texte est vide."""
    _run([
        ffmpeg, "-y",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=22050",
        "-t", str(SLIDE_SECONDS),
        "-c:a", "pcm_s16le",
        dest,
    ])


#romain7
def _fit_chunk(ffmpeg, piece, dest):
    """Voix de ce morceau du post, étirée ou raccourcie à 10 secondes."""
    piece = (piece or "").strip()
    if not piece:
        _silence(ffmpeg, dest)
        return
    try:
        raw = speak(piece)
    except AgentError as error:
        raise VideoError(str(error)) from error
    if not raw:
        _silence(ffmpeg, dest)
        return
    src = dest + ".src.wav"
    with open(src, "wb") as handle:
        handle.write(raw)
    try:
        _run([
            ffmpeg, "-y", "-i", src,
            "-af", _atempo(wav_seconds(raw), SLIDE_SECONDS),
            "-t", str(SLIDE_SECONDS),
            "-ar", "22050", "-ac", "1", "-c:a", "pcm_s16le",
            dest,
        ])
    finally:
        if os.path.isfile(src):
            os.remove(src)


#romain7
def _concat_wavs(ffmpeg, wavs, dest):
    """Une seule piste, dans l'ordre des slides."""
    listing = dest + ".txt"
    lines = ["ffconcat version 1.0"]
    for wav in wavs:
        lines.append(f"file '{wav}'")
    with open(listing, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    _run([
        ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", listing,
        "-c", "copy", dest,
    ])


#romain7
def _font(size):
    """Police lisible. La police du Mac est utilisée quand elle est là."""
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Geneva.ttf",
    ):
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


#romain7
def _wrap(draw, text, font, width):
    """Découpe le sous-titre pour qu'il tienne dans l'image."""
    words = (text or "…").split()
    if not words:
        return ["…"]
    lines = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines[:4]


#romain7
def _paint_cue(image_path, cue, dest):
    """Incruste le sous-titre en bas de la slide.

    ffmpeg installé par Homebrew n'a pas le filtre `subtitles`.
    Le texte est donc dessiné sur l'image avant le montage.
    """
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    size = max(18, image.width // 42)
    font = _font(size)
    lines = _wrap(draw, cue, font, image.width - 80)
    line_height = size + 8
    bar = line_height * len(lines) + 28
    top = image.height - bar
    draw.rectangle((0, top, image.width, image.height), fill=(0, 0, 0))
    y = top + 14
    for line in lines:
        length = draw.textlength(line, font=font)
        x = max(20, (image.width - length) / 2)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))
        y += line_height
    image.save(dest)


#romain7
def _assemble(ffmpeg, images, voice, work, duration):
    """Images, voix et sous-titres incrustés. Le mp4 est écrit dans `work`."""
    listing = os.path.join(work, "slides.txt")
    lines = ["ffconcat version 1.0"]
    for image in images:
        lines.append(f"file '{image}'")
        lines.append(f"duration {SLIDE_SECONDS}")
    lines.append(f"file '{images[-1]}'")
    with open(listing, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    # Homebrew ffmpeg n'inclut pas le filtre subtitles. Le texte est déjà sur l'image.
    framed = (
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,"
        "fps=5"
    )
    _run([
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0", "-i", "slides.txt",
        "-i", voice,
        "-vf", framed,
        "-map", "0:v", "-map", "1:a",
        "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        "video.mp4",
    ], cwd=work)


#romain7
def build_video(user_id, text):
    """Monte le mp4 du compte à partir des slides Gamma déjà prêtes.

    La voix lit le post, un morceau par slide, calé sur 10 secondes.
    Les sous-titres déjà écrits sont incrustés. Le fichier reste dans
    `data/videos`. L'adresse d'export Gamma n'est pas conservée.
    """
    approved = (text or "").strip()
    if not approved:
        raise VideoError("Le texte du post manque. Crée à nouveau le post.")
    key = owner_key()
    if not key:
        raise VideoError(
            "Mets la clé Gamma du projet dans GAMMA_API_KEY, dans le fichier .env."
        )
    view = gamma_view(user_id)
    if not view.get("gamma_url"):
        raise VideoError("Envoie d'abord le texte à Gamma.")
    ffmpeg = _ffmpeg()
    work = os.path.join("data", "videos", f"work-{user_id}")
    if os.path.isdir(work):
        shutil.rmtree(work)
    os.makedirs(work, exist_ok=True)
    out = os.path.join("data", "videos", f"{user_id}.mp4")
    try:
        images = export_slides(key, view["gamma_url"], os.path.join(work, "slides"))
        if not images:
            raise VideoError("Gamma n'a pas renvoyé d'images de slides.")
        cues = cues_for(images, view.get("subtitle_path"), approved)
        write_srt(cues, os.path.join(work, "captions.srt"))
        painted = []
        for index, (image, cue) in enumerate(zip(images, cues), start=1):
            dest = os.path.join(work, f"frame-{index:02d}.png")
            _paint_cue(image, cue, dest)
            painted.append(dest)
        parts = _split(approved, len(images))
        wavs = []
        for index, piece in enumerate(parts):
            dest = os.path.join(work, f"voice-{index:02d}.wav")
            _fit_chunk(ffmpeg, piece, dest)
            wavs.append(dest)
        _concat_wavs(ffmpeg, wavs, os.path.join(work, "voice.wav"))
        _assemble(ffmpeg, painted, "voice.wav", work, len(images) * SLIDE_SECONDS)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        os.replace(os.path.join(work, "video.mp4"), out)
        save_video_path(user_id, out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return {"video_path": out, "slide_count": len(images)}
