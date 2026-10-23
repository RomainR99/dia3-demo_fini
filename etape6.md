# Étape 6 — entrée vocale

## Objectif

L'utilisateur enregistre un message vocal. Il est transcrit, affiché dans sa bulle, puis traité comme un message écrit.

## La même barre que le texte et les images

Depuis Streamlit 1.52, `st.chat_input` accepte le micro avec `accept_audio=True`. Texte, fichiers et voix partent du même champ. Ici les trois sont ouverts en même temps : `accept_file="multiple"` et `accept_audio=True`.

Quand l'utilisateur envoie, `user_input` est un `ChatInputValue`.

- `user_input.text` est ce qu'il a tapé. C'est une chaîne vide s'il n'a fait qu'enregistrer.
- `user_input.audio` est le fichier du micro, ou `None` s'il n'a pas enregistré. Streamlit le fournit en WAV.
- `user_input.files` reste la liste des images.

## Transcrire avant l'historique

Whisper ne parle pas au modèle de chat. `transcribe` envoie le WAV à `whisper-large-v3-turbo`, puis renvoie une chaîne. Le fichier est nommé `message.wav` : Groq s'en sert pour reconnaître le format.

`language="fr"` dit au modèle que l'audio est en français. Sans ça, il devine la langue et bascule souvent vers l'anglais, ce qui abîme un message dicté en français.

```python
transcription = self.groq_client.audio.transcriptions.create(
    file=("message.wav", raw),
    model=WHISPER_MODEL,
    language="fr",
)
return transcription.text.strip()
```

Cette chaîne est collée au texte tapé, s'il y en a un. C'est elle qui devient `question`. `ask_llm` la reçoit comme n'importe quel message écrit : le modèle de chat ne voit jamais le WAV.

L'historique non plus. `st.session_state.messages` enregistre `question`, donc le texte transcrit, pas le fichier audio. Au tour suivant, `*history` renvoie cette phrase, comme si elle avait été tapée.

## Ce qu'on voit dans la bulle

`show_message` affiche `message["content"]`. On construit ce contenu avant d'afficher la bulle, donc la transcription est déjà dedans. L'utilisateur voit ce qui a été compris, puis la réponse arrive au fil de l'eau, comme pour un message écrit.

Si la transcription est vide et qu'il n'y a ni texte ni image, rien n'est envoyé.

## Le temps de réponse après l'audio

Le chrono ne concerne qu'un message qui contient un enregistrement. Il part au début du script, au moment où Streamlit relance l'application parce que le WAV vient d'arriver. C'est le moment le plus proche de la fin de l'enregistrement : le fichier est déjà là, la transcription et la réponse n'ont pas commencé.

Trois durées sont mesurées avec `time.perf_counter()` :

- la transcription, juste après `transcribe` ;
- les premiers mots, au premier fragment renvoyé par `ask_llm` ;
- la réponse complète, quand `st.write_stream` a fini.

Ces trois nombres sont écrits sous la réponse, puis rangés sur le message assistant (`first_s`, `transcript_s`, `total_s`). Au tour suivant, `show_message` réaffiche la même ligne. Un message seulement tapé n'a pas ces champs, donc pas de chrono.

Le premier instant est gardé dans un dictionnaire, `seen`, et pas avec `nonlocal`. `answer_stream` est une fonction dans le script, pas dans une autre fonction : `nonlocal` n'a rien à viser et le fichier ne se lance pas.

## Commits

Ces commits passent après ceux de l'étape 5. `app.py` et `llm_agent.py` contiennent déjà le flux, les images et la voix : pour cette étape, ne versionner que la partie audio.

1. `feature: transcribe a wav message in french`
   - `llm_agent.py` : `transcribe`, modèle `whisper-large-v3-turbo`, fichier `message.wav`, `language="fr"`

2. `feature: record a voice message in the chat`
   - `app.py` : `accept_audio=True`, la transcription devient le texte du message, affichée dans la bulle, puis envoyée à `ask_llm`

3. `feature: show how long the answer takes after the audio`
   - `app.py` : chrono depuis la réception du WAV, trois durées sous la réponse (transcription, premiers mots, réponse complète), gardées dans l'historique

4. `doc: explain speech to text in etape6.md`
   - `etape6.md`
