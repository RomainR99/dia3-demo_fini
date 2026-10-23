# Créer le post — bouton, trois sujets, accord à l'oral

Les étapes pour ajouter ceci à l'application déjà en place. Le code à recopier depuis zéro, micro compris, est dans `romain4.md`. Chaque changement de ce lot porte le commentaire `#romain5`. Les docstrings disent le rôle de chaque fonction.

**Environ 3 heures** sans IA, en débutant, si le micro et Inspirer existent déjà. Le temps passe dans le classement de la phrase : accord, sujet nouveau, ou conversation.

## Ce que l'utilisateur voit

1. **Inspirer** est sous **Maintenir pour parler**. Un clic affiche jusqu'à 3 boutons, au même endroit.
2. Un clic sur un titre relance la page et rédige le post. Une zone de texte permet de le modifier.
3. **Créer le post**, sous cette zone, enregistre le texte modifié. C'est l'entrée du futur flux vidéo et des visuels. Rien n'est monté pour l'instant.
4. Dire « oui », « vas-y », ou une autre indication courte rédige le sujet déjà donné, sans cliquer un titre.
5. Dire « rédige un post sur… » rédige tout de suite, avec cette phrase comme sujet.
6. « Bonjour » ou « merci » ne donnent pas de sujet.

## Ordre

1. Dans `post.py`, les listes et `post_intent`.
2. Dans `app.py`, importer `post_intent`.
3. Déplacer Inspirer et les trois titres sous le micro. Un clic sur un titre relance la page.
4. Afficher le post dans une zone modifiable. **Créer le post** enregistre ce texte pour la vidéo, sans la lancer.
5. Dans `_handle_turn`, traiter l'accord avant l'agent.
6. Vider `offered_topic` et `video_source` en quittant le compte.
7. Les essais.

`post.py` s'écrit avec 4 espaces. `app.py` garde ses tabulations.

## 1. Classer la phrase

`app.py` ne doit pas appeler Groq. Le classement est une méthode de `Post`.

`post_intent(text, pending=False)` renvoie un couple :

| Couple | Sens |
| --- | --- |
| `("confirm", None)` | accord : oui, vas-y, ou une indication courte |
| `("draft", sujet)` | la phrase demande d'écrire et contient le sujet |
| `("offer", sujet)` | la phrase donne un sujet, sans demander encore la rédaction |
| `("chat", None)` | salutation, remerciement, ou un mot isolé |

`pending=True` seulement s'il y a déjà un sujet en attente. Une indication courte absente de la liste (« je suis partant ») est alors demandée au modèle, qui répond oui ou non. S'il échoue, la phrase reste une conversation.

Le sujet est un dictionnaire `title`, `source`, `reason`. `source` vaut `conversation`. Le titre est la phrase elle-même.

Les fonctions `_fold`, `_asks_to_write`, `_is_agreement`, `_topic_from`, et les méthodes `post_intent` et `_says_yes`, sont dans `romain4.md`, section « Sujet donné, bouton, accord à l'oral ». Les recopier dans `post.py`, avec `#romain5` au-dessus de chacune. Ajouter `import unicodedata`.

À la fin du fichier, à côté des autres fonctions du module :

```python
#romain5
def post_intent(text, pending=False):
    """Même rôle que `Post.post_intent`."""
    return post.post_intent(text, pending=pending)
```

Essai sans la page, dans le terminal :

```bash
env/bin/python -c "from post import post_intent; print(post_intent('vas-y', pending=True)); print(post_intent('les puces NVIDIA'))"
```

Attendu : `('confirm', None)` puis `('offer', ...)` avec le titre `les puces NVIDIA`.

## 2. Importer

Dans `app.py` :

```python
from post import (
	PostError,
	clear_post,
	draft_post,
	post_intent,
	save_post_edit,
	spoken_minutes,
)
```

## 3. Les boutons sous le micro

`_show_topics` ne passe plus par `st.sidebar`. Elle est appelée dans la colonne du micro, juste après `hold_to_talk` :

```python
		recording = hold_to_talk(
			AUDIO_MIN_SECONDS,
			AUDIO_MIN_PEAK,
			key="hold_mic",
		)
		#romain5
		_show_topics(st.session_state.user_id)
```

Retirer l'ancien appel dans la barre (`show_veille`). Sinon Inspirer apparaît deux fois.

`_choose_topic` pose le sujet, vide `post_for` et oublie `video_source`. `_show_post` est appelé juste après les trois boutons, dans le même passage. Le post s'écrit sous ces boutons, pas en haut de la page. Pas de `st.rerun()` ici : il couperait l'affichage avant la zone de texte.

```python
#romain5
def _choose_topic(topic):
	"""Retient le sujet et force une nouvelle rédaction.

	`post_for` vide fait rappeler `draft_post` dans `_show_post`.
	L'ancienne source vidéo est oubliée : elle ne correspond plus à ce sujet.
	"""
	st.session_state.chosen_topic = topic
	st.session_state.post_for = None
	st.session_state.video_source = ""
```

```python
	for index, topic in enumerate(st.session_state.get("topics") or []):
		#romain5
		if st.button(topic["title"], key=f"inspire-{index}"):
			_choose_topic(topic)
	#romain5
	_show_post(user_id)
```

Ne pas appeler `_show_post` aussi en haut du script. Deux zones avec la même clé `post_text` font une erreur Streamlit. **Créer le post** n'est pas sous Inspirer : il est sur le texte rédigé.

## 4. Le post modifiable, puis la vidéo

`_show_post` suit les trois boutons. Au clic, `post_for` est vide, donc `draft_post` écrit le texte dans le même passage. Il est posé dans `post_text` avant la zone, pour que les phrases déjà écrites s'affichent. L'utilisateur les change dans la zone.

**Créer le post** lit cette zone, y compris les changements, et la garde dans `video_source`. Plus tard, le flux vidéo et les visuels liront cette chaîne. Ce bouton ne monte pas la vidéo et n'ouvre pas Canva.

```python
#romain5
def _start_video_flow(text):
	"""Garde le texte modifié comme source du futur flux vidéo.

	Le texte édité est enregistré. Aucune vidéo ni aucun visuel n'est produit :
	ce bouton est seulement l'entrée de cette étape, à brancher plus tard.
	"""
	saved = save_post_edit(text)
	st.session_state.validated_post = saved
	st.session_state.video_source = saved
	return saved
```

À la fin de `_show_post`, après la zone de texte :

```python
	st.text_area(
		"Post LinkedIn, 2 à 3 minutes à l'oral. Vous pouvez le modifier.",
		key="post_text",
		height=320,
	)
	#romain5
	if st.button("Créer le post", key="create_post"):
		try:
			_start_video_flow(st.session_state.post_text)
		except PostError as error:
			st.warning(str(error))
	if st.session_state.get("video_source"):
		st.success(
			"Texte enregistré. Il partira vers la vidéo et les visuels. "
			"Cette étape n'est pas encore branchée."
		)
```

Ne pas assigner `post_text` après la zone dans le même passage : Streamlit le refuse. Le clic sur **Créer le post** lit la valeur déjà mise à jour par la zone.

## 5. L'accord, avant l'agent

Toujours dans `_handle_turn`, avant `ask_llm`, et seulement s'il y a du texte et pas d'image :

- `confirm` et un sujet en attente : `_choose_topic`, une ligne « Je rédige le post. » dans l'historique, puis `st.rerun()`. L'agent n'est pas appelé.
- `draft` : le sujet est la phrase elle-même, même suite.
- `offer` : on garde le sujet, puis la conversation continue.

`_remember_turn` enregistre la phrase de l'utilisateur et « Je rédige le post. » dans la session, dans l'historique de l'agent, et dans la base. La docstring le dit.

`clear_keyboard = True` avant `st.rerun()` vide la zone au passage suivant.

« oui » sans sujet en attente ne rentre pas dans ce cas. La phrase continue vers l'agent.

## 6. Quitter le compte

Avec les autres remises à zéro du bouton **Quitter le bord** :

```python
		#romain5
		st.session_state.offered_topic = None
		st.session_state.video_source = ""
```

## 7. Essais

| Essai | Résultat |
| --- | --- |
| `post_intent("oui", pending=True)` | `confirm` |
| `post_intent("vas-y", pending=True)` | `confirm` |
| `post_intent("bonjour")` | `chat` |
| `post_intent("les puces NVIDIA")` | `offer`, titre = la phrase |
| `post_intent("rédige un post sur les puces NVIDIA")` | `draft` |
| Inspirer | 1 à 3 boutons sous le micro |
| Clic sur un titre | Une zone de texte, modifiable, avec le post rédigé |
| Modifier la zone, puis **Créer le post** | Le texte modifié est gardé. Message : il partira vers la vidéo et les visuels. Pas de montage. |
| Dire un sujet, puis « oui » ou « vas-y » | Le post se rédige sur le sujet déjà donné |
| « oui » sans sujet donné | Conversation, pas de post |
| « Bonjour » | Conversation, pas de sujet |

Relancer avec `env/bin/python -m streamlit run app.py`. Un serveur déjà ouvert ne voit pas `post_intent` tant qu'il n'a pas été arrêté.

## Pièges

Classer « oui » après l'appel à l'agent fait répondre Jarvis au lieu de rédiger.

Un « oui » sans `offered_topic` ne doit pas inventer un sujet.

« Rédige » tout seul est un accord sur le sujet déjà donné. « Rédige un post sur les puces » est un nouveau sujet, rédigé tout de suite. La différence est le texte qui suit le verbe.

Mettre les trois boutons dans la barre les laisse loin du micro. L'appel de `_show_topics` est dans la colonne de `hold_to_talk`.

Appeler `_show_post` avant les trois boutons rédige trop tôt : le clic n'a pas encore choisi le sujet. L'appeler une seconde fois en haut du script duplique la zone de texte.

**Créer le post** ne rédige pas. Il lit la zone. Le brancher tout de suite à une vidéo ou à Canva sort de ce lot : `video_source` attend le flux suivant.

`post_intent` qui lève une erreur quand Groq ne répond pas bloque la conversation. `_says_yes` renvoie `False`, et la phrase continue comme un message normal.
