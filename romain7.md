# Vidéo — slides Gamma, voix du post, sous-titres

**1 fonction** visible sur la page : `build_video`. Autour : `gamma_id_from_url`, `export_slides`, `read_cues`, `cues_for`, `write_srt`, `_paint_cue`, `_fit_chunk`, `_assemble`, et dans `gamma_client.py` `start_png_export`, `wait_png_export`. En base : `_ensure_column`, `save_video_path`.

**Environ 8 heures** sans IA, en débutant. Le temps passe dans l'export Gamma et dans ffmpeg, pas dans le découpage du texte.

Ce guide part de zéro pour ce lot. Chaque changement porte le commentaire `#romain7`. Les docstrings disent le rôle de chaque fonction. `video.py` s'écrit avec 4 espaces. `app.py` garde ses tabulations.

La voix n'est pas réécrite. `build_video` appelle `speak`, déjà dans `llm_agent.py` : Orpheus d'abord, puis la voix française Thomas du Mac si Groq refuse.

## Ce que l'utilisateur voit

1. Le texte est déjà approuvé (**Créer le post**) et les slides existent (**Envoyer à Gamma**).
2. **Créer la vidéo** apparaît sous le lien Gamma.
3. Chaque slide reste 10 secondes. La voix lit le morceau du post qui correspond à cette slide.
4. Le sous-titre de cette slide est dessiné en bas de l'image, en blanc sur un bandeau noir.
5. Le lecteur apparaît sous le post. Le fichier est `data/videos/{user_id}.mp4`.
6. La voix lit le post, même si les sous-titres sont dans une autre langue.

## Installer ffmpeg

Le montage ne se fait pas en Python pur.

```bash
brew install ffmpeg
```

Le `ffmpeg` de Homebrew n'a pas le filtre `subtitles`. Les sous-titres sont donc dessinés avec Pillow sur chaque image, avant l'appel ffmpeg. Pillow est déjà dans `requirements.txt`.

## Ordre

1. `EXPORT_POLL_TRIES` et `VIDEO_DOWNLOAD_TIMEOUT` dans `config.py`.
2. La colonne `video_path` et `save_video_path` dans `db.py`.
3. `start_png_export` et `wait_png_export` dans `gamma_client.py`.
4. Le fichier `video.py`.
5. Le bouton **Créer la vidéo** dans `app.py`.
6. Ignorer `data/videos/` dans `.gitignore`.

## Constantes

```python
#romain7
# L'export PNG est une archive, une image par slide. Trois minutes d'attente.
EXPORT_POLL_TRIES = 36
VIDEO_DOWNLOAD_TIMEOUT = 120
```

`SLIDE_SECONDS` vaut déjà 10. On ne le change pas.

## La base

La table `gamma_accounts` existe déjà. Une base créée avant ce lot n'a pas `video_path`. `CREATE TABLE IF NOT EXISTS` n'ajoute pas une colonne.

```python
#romain7
def _ensure_column(conn, table, column, declaration):
    """Ajoute une colonne si la table existait déjà sans elle."""
    found = conn.execute(f"PRAGMA table_info({table})").fetchall()
    names = {row["name"] for row in found}
    if column not in names:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
```

Dans `init_db`, après `GAMMA_SCHEMA` :

```python
#romain7
_ensure_column(conn, "gamma_accounts", "video_path", "TEXT")
```

`gamma_view` renvoie aussi `video_path`. Jamais la clé, jamais l'adresse d'export.

```python
#romain7
def save_video_path(user_id, video_path):
    """Mémorise le mp4 du compte. Le fichier reste sur la machine."""
    with db() as conn:
        conn.execute(
            "UPDATE gamma_accounts SET video_path = ? WHERE user_id = ?",
            (video_path, user_id),
        )
```

## Exporter les slides

Gamma a déjà créé la présentation. On ne relance pas une génération.

1. L'identifiant est le dernier morceau du lien. `https://gamma.app/docs/abc` donne `abc`.
2. `POST /v1.0/gammas/{id}/export` avec `{"exportAs": "png"}`. La réponse est un `exportId`.
3. `GET /v1.0/exports/{id}` toutes les 5 secondes, jusqu'à `completed` ou `failed`. 36 essais.
4. `completed` contient `exportUrl`. C'est une archive zip, une image PNG par slide. Cette adresse expire au bout d'une semaine et n'importe qui peut la télécharger. On ne l'écrit ni dans la base, ni dans la page, ni dans un journal.
5. On télécharge, on extrait les PNG, on efface le zip.

L'appel reprend l'en-tête `User-Agent: Barbe-Quasar/1.0` et les certificats `certifi`, comme le reste de Gamma.

## Le fichier `video.py`

À écrire. Les noms, dans l'ordre utile :

1. `VideoError`
2. `gamma_id_from_url`
3. `export_slides`
4. `read_cues`
5. `cues_for`
6. `write_srt`
7. `_paint_cue`
8. `_fit_chunk`
9. `_assemble`
10. `build_video`

`build_video(user_id, text)` enchaîne :

1. Texte non vide, clé `.env` présente, lien Gamma présent.
2. Images exportées.
3. Un sous-titre par image. Si le `.srt` a déjà le bon nombre de blocs, on le garde. Sinon on redécoupe.
4. Le sous-titre est dessiné en bas de l'image.
5. Le post est découpé en autant de morceaux que d'images. `speak` lit chaque morceau. ffmpeg ramène chaque morceau à 10 secondes (`atempo` entre 0,5 et 2, enchaîné si besoin, puis `apad`).
6. Les images durent 10 secondes chacune. La piste audio est collée dans le même ordre.
7. Le mp4 est `data/videos/{user_id}.mp4`. Le dossier de travail est effacé.

ffmpeg, pour les images :

```text
ffconcat version 1.0
file 'frame-01.png'
duration 10
file 'frame-02.png'
duration 10
file 'frame-02.png'
```

La dernière image est répétée sans durée. Sans cette ligne, ffmpeg coupe la fin.

Puis :

```text
scale=1920:1080, bandeaux noirs si l'image n'est pas 16:9, 5 images par seconde,
voix en AAC, image en H.264, pix_fmt yuv420p
```

## La page

Imports : `VideoError`, `build_video`, et `os` pour vérifier que le fichier existe.

Sous le lien Gamma, dans `_show_post` :

```python
		#romain7
		if sent.get("gamma_url") and st.button("Créer la vidéo", key="build_video"):
			try:
				with st.spinner("Montage de la vidéo…"):
					build_video(
						st.session_state.user_id,
						st.session_state.video_source,
					)
			except VideoError as error:
				st.warning(str(error))
			else:
				st.rerun()
		video_path = sent.get("video_path") or ""
		if video_path and os.path.isfile(video_path):
			st.video(video_path)
```

Dans `.gitignore` :

```text
data/videos/
```

Relancer avec `env/bin/python -m streamlit run app.py`. Un serveur déjà ouvert ne voit pas `video.py`.

## Essais

| Essai | Résultat |
| --- | --- |
| `gamma_id_from_url("https://gamma.app/docs/abc123")` | `abc123` |
| `gamma_id_from_url("https://gamma.app/docs/abc123/edit")` | `abc123` |
| `_split("un deux trois quatre", 2)` | deux parts égales |
| `_atempo(10, 10)` | `apad` |
| Montage local : 1 image, 10 secondes de silence, un sous-titre dessiné | un mp4 avec une piste vidéo et une piste audio, durée 10 secondes |
| **Créer la vidéo** sans lien Gamma | « Envoie d'abord le texte à Gamma. » |
| ffmpeg absent | « Installe ffmpeg pour monter la vidéo. Sur Mac : brew install ffmpeg. » |

Le montage local se vérifie sans appeler Gamma. L'envoi réel se vérifie dans le navigateur, après **Envoyer à Gamma**, avec des crédits encore disponibles.

## Pièges

Garder `exportUrl` dans la base ou dans la page la laisse téléchargeable par quiconque possède le lien.

Demander `exportAs` pendant la génération du lot précédent mélangeait le lien secret et le lien de lecture. Ici l'export est une étape à part, lancée seulement au montage, et l'adresse est oubliée après le téléchargement.

`atempo=3` est refusé par ffmpeg. On coupe le facteur en morceaux de 2 au plus, et de 0,5 au moins.

Oublier de répéter la dernière image dans `slides.txt` raccourcit la dernière slide.

Le filtre `subtitles` de ffmpeg manque dans la formule Homebrew. Pillow dessine le texte. Un bandeau noir en bas garde les lettres lisibles sur une slide claire.

La voix lit le post. Les sous-titres peuvent être la traduction choisie dans les réglages. Les deux sont calés sur les mêmes 10 secondes, mais les phrases ne sont pas une traduction mot à mot de ce qui se dit si la langue des sous-titres n'est pas celle du post.

Le mp4 ne va pas dans git. `data/videos/` est ignoré, comme `data/subtitles/`.
