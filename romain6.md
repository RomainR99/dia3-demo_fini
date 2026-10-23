# Gamma — slides du compte, sous-titres

**8 fonctions** à coder pour ce lot : `slide_count`, `owner_key`, `create_generation`, `poll_generation`, `build_subtitles`, `send_approved`, `refresh_generation`, `_show_gamma`. Autour : `_request`, `_chunks`, `_stamp`, `_translate`, et les fonctions de base `gamma_view`, `save_gamma_languages`, `save_gamma_job`.

**Environ 6 heures** sans IA, en débutant. Le temps passe dans la clé API et dans l'attente de Gamma, pas dans le calcul des 15 slides.

Ce guide part de zéro pour ce lot. Chaque changement porte le commentaire `#romain6`. Les docstrings disent le rôle de chaque fonction. `gamma_client.py` s'écrit avec 4 espaces. `app.py` garde ses tabulations.

## Ce que l'utilisateur voit

1. Dans les réglages : la langue des slides et la langue des sous-titres. La clé n'apparaît pas.
2. La langue des slides est aussi la langue de la vidéo.
3. Les sous-titres sont en français, sauf si une autre langue est choisie.
4. **Créer le post** approuve le texte modifié.
5. **Envoyer à Gamma** envoie ce texte. Gamma fait une présentation 16:9.
6. Une slide toutes les 10 secondes. Au-delà de 2 minutes 30, on s'arrête à 15 slides.
7. Un fichier `.srt` est écrit à côté, un sous-titre par slide.
8. Le lien des slides s'affiche sous le post. La vidéo n'est pas encore montée.

## Obtenir la clé, sur le compte Gamma

Gamma refuse le mot de passe du site. Il faut une clé API, propre au compte.

1. Ouvre [gamma.app](https://gamma.app) et connecte-toi au compte personnel.
2. L'API est proposée sur les offres qui incluent les crédits de génération. Sans crédits, Gamma répond qu'il n'en reste plus.
3. Dans les réglages du compte, ouvre la page des clés API : [developers.gamma.app](https://developers.gamma.app).
4. Crée une clé. Copie-la une fois : Gamma ne la réaffiche pas toujours.
5. Colle-la dans `.env`, sur la ligne `GAMMA_API_KEY=`. Le fichier reste sur la machine : git l'ignore.

Tous les comptes de l'application créent les slides avec cette clé. Les crédits dépensés sont ceux de ce compte Gamma. Chaque utilisateur garde ses langues et son lien de slides.

## Ordre

1. Les constantes dans `config.py`.
2. La table `gamma_accounts` et les fonctions de `db.py`.
3. Le fichier `gamma_client.py`.
4. Les réglages et le bouton **Envoyer à Gamma** dans `app.py`.
5. Ignorer `data/subtitles/` dans `.gitignore`.
6. Les essais en bas.

## Constantes

```python
#romain6
# Une slide toutes les 10 secondes. 2 min 30 font 15 slides, pas plus.
GAMMA_API_BASE = "https://public-api.gamma.app/v1.0"
SLIDE_SECONDS = 10
VIDEO_MAX_SECONDS = 150
GAMMA_TIMEOUT = 60
GAMMA_POLL_SECONDS = 5
GAMMA_POLL_TRIES = 6
DEFAULT_SLIDE_LANGUAGE = "fr"
DEFAULT_SUBTITLE_LANGUAGE = "fr"
GAMMA_LANGUAGES = {
    "fr": "Français",
    "en": "Anglais",
    "es": "Espagnol",
    "de": "Allemand",
    "it": "Italien",
    "pt-br": "Portugais (Brésil)",
    "ja": "Japonais",
}
```

Les codes viennent de la liste Gamma `textOptions.language`. `fr` est le français. Si le code est absent de cette liste, Gamma peut refuser la génération. Le fichier du projet en contient un peu plus : arabe, chinois, coréen, hindi, vietnamien, russe, turc, néerlandais, polonais, anglais britannique.

## La base

Dans `init_db`, après les boîtes mail :

```python
#romain6
conn.executescript(GAMMA_SCHEMA)
```

```python
#romain6
GAMMA_SCHEMA = """
CREATE TABLE IF NOT EXISTS gamma_accounts (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    api_key TEXT NOT NULL DEFAULT '',
    slide_language TEXT NOT NULL DEFAULT 'fr',
    subtitle_language TEXT NOT NULL DEFAULT 'fr',
    connected_at TEXT,
    generation_id TEXT,
    gamma_url TEXT,
    slide_count INTEGER,
    job_status TEXT,
    subtitle_path TEXT
);
"""
```

| Fonction | Rôle |
| --- | --- |
| `gamma_view` | langues, lien, statut. Jamais la clé. |
| `save_gamma_languages` | langue des slides et langue des sous-titres, par compte. |
| `save_gamma_job` | identifiant, statut, lien, nombre de slides, chemin du `.srt`. |

La clé n'est pas dans cette table. `owner_key` la lit dans `.env`, variable `GAMMA_API_KEY`.

Les docstrings de ces fonctions sont dans `db.py`.

## Le fichier `gamma_client.py`

À recopier. L'en-tête d'appel est `X-API-KEY`. L'adresse est `POST /v1.0/generations`, puis `GET /v1.0/generations/{id}` toutes les 5 secondes.

`slide_count` : mots / 150 = minutes, fois 60 = secondes, divisées par 10, arrondi au-dessus, maximum 15.

`create_generation` envoie le texte approuvé, `format` = `presentation`, `numCards` = ce nombre, `textOptions.language` = la langue des slides. Gamma réécrit les slides dans cette langue, même si le post est en français.

`poll_generation` s'arrête sur `completed` ou `failed`. Après 6 essais, `pending` n'est pas une erreur : le bouton **Vérifier les slides** rappellera.

`build_subtitles` écrit `data/subtitles/{user_id}.srt`. Un bloc dure 10 secondes, comme une slide. En français, le texte approuvé est découpé. Dans une autre langue, Groq traduit d'abord, avec `GROQ_KEY`.

`send_approved` enchaîne : texte non vide, clé présente, sous-titres, génération, attente, enregistrement.

`refresh_generation` reprend un `generation_id` déjà gardé.

`GammaError` est le seul message montré sur la page.

Le fichier complet du dépôt est `gamma_client.py`. Les noms à avoir, dans l'ordre :

1. `GammaError`
2. `slide_count`
3. `owner_key`
4. `_request`
5. `create_generation`
6. `poll_generation`
7. `_chunks`
8. `_stamp`
9. `_translate`
10. `build_subtitles`
11. `send_approved`
12. `refresh_generation`

## La page

Imports : `GAMMA_LANGUAGES`, `gamma_view`, `save_gamma_languages`, `GammaError`, `owner_key`, `refresh_generation`, `send_approved`.

`_show_gamma(user_id)` est appelée dans la barre, après Gmail. Deux listes : **Langue des slides et de la vidéo**, **Langue des sous-titres**. Pas de champ pour la clé. **Vérifier les slides** seulement si le statut est `pending`. Si `GAMMA_API_KEY` est vide, la barre le dit.

Quitter le compte retire `gamma_slide_language` et `gamma_subtitle_language`, pour ne pas les laisser au compte suivant sur le même navigateur.

Sous le post, une fois le texte approuvé (`video_source`) :

```python
		#romain6
		if st.button("Envoyer à Gamma", key="send_gamma"):
			try:
				with st.spinner("Gamma prépare les slides…"):
					send_approved(
						st.session_state.user_id,
						st.session_state.video_source,
					)
			except GammaError as error:
				st.warning(str(error))
			else:
				st.rerun()
```

Le lien affiché est `gamma_url`. On n'affiche pas d'URL d'export : Gamma la traite comme un secret, et elle expire.

Dans `.gitignore` :

```
data/subtitles/
```

## Essais

| Essai | Résultat |
| --- | --- |
| `slide_count("")` | `0` |
| `slide_count` de 150 mots | `6` slides (60 secondes) |
| `slide_count` de 480 mots | `15` slides, pas 20 |
| `GAMMA_API_KEY` vide | « Mets la clé Gamma du projet dans GAMMA_API_KEY, dans le fichier .env. » |
| **Envoyer à Gamma** sans texte approuvé | « Approuve le texte avant de l'envoyer à Gamma. » |
| **Envoyer à Gamma** sans clé | le même message que la ligne `GAMMA_API_KEY` vide |
| Langue des slides = anglais, sous-titres = français | Les slides partent en `en`. Le `.srt` reste en français, une ligne toutes les 10 secondes. |
| Génération encore `pending` | **Vérifier les slides** redemande le lien. |

Les deux premiers essais de durée se lancent sans réseau :

```bash
env/bin/python -c "from gamma_client import slide_count; print(slide_count('mot '*150)); print(slide_count('mot '*480))"
```

Attendu : `6` puis `15`.

L'envoi réel se vérifie dans le navigateur, avec une vraie clé et des crédits Gamma. Relancer avec `env/bin/python -m streamlit run app.py` : un serveur déjà ouvert ne voit pas `gamma_client`.

## Pièges

La clé vit dans `.env`, pas dans ce guide et pas dans la base. `.env` n'est pas versionné. La coller ici la partagerait avec le dépôt.

`numCards` sans plafond dépasse 2 minutes 30 dès que le post oral dure plus longtemps. `slide_count` coupe à 15.

Demander un export `png` ou `pdf` renvoie une adresse que n'importe qui peut télécharger pendant une semaine. Ce lot ne demande pas d'export. Il garde `gammaUrl`.

Afficher la clé dans la barre la laisse visible. La page ne la demande pas.

Écrire le `.srt` avant de savoir que Gamma a accepté la clé fait un fichier inutile si la clé est refusée. Ici les sous-titres sont écrits après la vérification de la clé, avant l'attente longue. Si Gamma échoue ensuite, le fichier existe quand même : il correspond au texte approuvé.

Coller `gamma_client.py` dans `app.py` mélange l'appel HTTP et la page. L'appel reste dans `gamma_client.py`.
