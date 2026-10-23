# Créer le post — bouton, trois sujets, accord à l'oral

Les étapes pour ajouter ceci à l'application déjà en place. Le code à recopier depuis zéro, micro compris, est dans `romain4.md`. Chaque changement de code porte le commentaire `#romain4`. Les docstrings disent le rôle de chaque fonction.

**Environ 3 heures** sans IA, en débutant, si le micro et Inspirer existent déjà. Le temps passe dans le classement de la phrase : accord, sujet nouveau, ou conversation.

## Ce que l'utilisateur voit

1. **Inspirer** est sous **Maintenir pour parler**. Un clic affiche jusqu'à 3 boutons, au même endroit.
2. Un clic sur un titre rédige le post tout de suite.
3. Quand une phrase donne un sujet (« les puces NVIDIA cette semaine »), **Créer le post** apparaît sous les titres. Le titre de la phrase est écrit au-dessus du bouton.
4. Dire « oui », « vas-y », ou une autre indication courte rédige ce sujet sans cliquer.
5. Dire « rédige un post sur… » rédige tout de suite, avec cette phrase comme sujet.
6. « Bonjour » ou « merci » ne font pas apparaître le bouton.

## Ordre

1. Dans `post.py`, les listes et `post_intent`.
2. Dans `app.py`, importer `post_intent`.
3. Déplacer Inspirer et les trois titres sous le micro.
4. Ajouter **Créer le post**.
5. Dans `_handle_turn`, traiter l'accord avant l'agent.
6. Vider `offered_topic` en quittant le compte.
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

Les fonctions `_fold`, `_asks_to_write`, `_is_agreement`, `_topic_from`, et les méthodes `post_intent` et `_says_yes`, sont dans `romain4.md`, section « Sujet donné, bouton, accord à l'oral ». Les recopier dans `post.py`, avec `#romain4` au-dessus de chacune. Ajouter `import unicodedata`.

À la fin du fichier, à côté des autres fonctions du module :

```python
#romain4
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
		#romain4
		_show_topics(st.session_state.user_id)
```

Retirer l'ancien appel dans la barre (`show_veille`). Sinon Inspirer apparaît deux fois.

`_choose_topic` pose le sujet et vide `post_for`. Le clic relance la page. `_show_post`, déjà en haut du script, voit le sujet vide de brouillon et appelle `draft_post`.

Le code complet de `_choose_topic` et de `_show_topics` est dans `romain4.md`, section « Trois sujets, pas une liste ».

## 4. Le bouton Créer le post

Il est à la fin de `_show_topics`. Il s'affiche si `offered_topic` existe et si ce titre n'est pas déjà le post en cours (`post_for`). Un clic appelle `_choose_topic` sur ce sujet.

La phrase qui a donné le sujet est gardée dans `_handle_turn` :

```python
		if intent == "offer" and spoken_topic:
			st.session_state.offered_topic = spoken_topic
			st.session_state.refresh_composer = True
```

`refresh_composer` relance la page après un audio, pour que le bouton apparaisse. La voix de la réponse est rejouée une fois (`play_last_speech`), pas deux : pendant cette relance, les morceaux du direct ne partent pas en lecture automatique.

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
		#romain4
		st.session_state.offered_topic = None
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
| Clic sur un titre | Le post se rédige |
| Dire un sujet, puis **Créer le post** | Le post se rédige sur cette phrase |
| Dire un sujet, puis « oui » ou « vas-y » | Même rédaction |
| « oui » sans sujet donné | Conversation, pas de post |
| « Bonjour » | Pas de bouton **Créer le post** |

Relancer avec `env/bin/python -m streamlit run app.py`. Un serveur déjà ouvert ne voit pas `post_intent` tant qu'il n'a pas été arrêté.

## Pièges

Classer « oui » après l'appel à l'agent fait répondre Jarvis au lieu de rédiger.

Un « oui » sans `offered_topic` ne doit pas inventer un sujet.

« Rédige » tout seul est un accord sur le sujet déjà donné. « Rédige un post sur les puces » est un nouveau sujet, rédigé tout de suite. La différence est le texte qui suit le verbe.

Mettre les trois boutons dans la barre les laisse loin du micro. L'appel de `_show_topics` est dans la colonne de `hold_to_talk`.

`post_intent` qui lève une erreur quand Groq ne répond pas bloque la conversation. `_says_yes` renvoie `False`, et la phrase continue comme un message normal.
