# Étape 8 — conversation entièrement vocale

## Objectif

On parle, l'assistant répond à voix haute, sans toucher au clavier. Moins de 5 secondes doivent séparer la fin de la parole du début de la réponse audio.

## Les trois durées s'additionnent

Entre la fin de l'enregistrement et le premier son, trois étapes se suivent :

1. **STT** : `transcribe` envoie le WAV à Whisper. `stt_s` est le temps de cet appel seul.
2. **LLM** : le modèle écrit la réponse. En mode vocal, on ne mesure pas toute la génération. `llm_s` s'arrête à la première phrase complète, parce que c'est le moment où la synthèse peut commencer.
3. **TTS** : `speak` transforme cette phrase en WAV. `tts_s` est le temps de cette première synthèse.

`début de l'audio` est l'horloge murale depuis le début du script, donc depuis que le WAV est arrivé. Elle inclut les trois durées et le temps de relancer la page. C'est ce nombre qui doit rester sous 5 secondes. Les trois autres disent quel maillon pèse.

Après l'échange, la ligne sous la réponse ressemble à ceci :

`STT 0,4 s · LLM 1,1 s · TTS 0,8 s · début de l'audio 2,6 s`

Elle est gardée sur le message assistant (`stt_s`, `llm_s`, `tts_s`, `audio_s`) et réaffichée au tour suivant.

## Sans le clavier

Si le message contient un audio et pas de texte tapé, `voice_reply` est vrai même quand l'interrupteur « Réponse vocale » est coupé. L'interrupteur sert encore à faire lire une réponse à un message tapé.

## Trois leviers

La consigne vocale est ajoutée au message système seulement dans ce mode : chaque réplique fait entre 150 et 300 caractères, environ 2 à 4 phrases courtes, en français, sans liste, sans markdown, sans emoji. Un refus suit la même longueur et reste en français. Si le modèle renvoie quand même la formule anglaise « I'm sorry, but I can't help with that », ou une réplique de moins de 150 caractères, l'appel est refait une fois avec cette consigne. Elle ne coupe pas la réponse à la première phrase. Le texte affiché reste la réponse du modèle. La synthèse en reçoit une copie nettoyée, comme à l'étape 7.

Sans image, le modèle passe de `openai/gpt-oss-120b` à `openai/gpt-oss-20b`. Une image garde le modèle vision.

`stream_voice_answer` affiche les fragments au fur et à mesure. Dès que `first_spoken_sentence` trouve un `.`, un `!` ou un `?` qui n'est pas le point d'un nombre, `speak` de cette phrase part dans un fil à part. Le fil du modèle n'attend pas ce WAV : la suite du texte continue de s'écrire. Quand le WAV de la première phrase est prêt, `st.audio(..., autoplay=True)` le joue. Chaque phrase suivante attend la fin du morceau déjà lancé, puis part à son tour : un nouveau lecteur ne coupe pas le précédent. La réplique visée fait 150 à 300 caractères, et cette longueur prime sur celle du personnage.

La première synthèse du processus essaie encore Orpheus. S'il refuse, la voix française `Thomas` prend le relais pour les phrases suivantes, comme à l'étape 7. Ce premier refus allonge un échange, pas les suivants.

## Commits

Ces commits passent après ceux de l'étape 7. `app.py` et `llm_agent.py` contiennent déjà les étapes précédentes : pour celle-ci, ne versionner que la partie conversation vocale.

1. `feature: shorten voice answers with a smaller model`
   - `llm_agent.py` : `voice=True`, consigne ajoutée au message système, modèle `openai/gpt-oss-20b` sans image

2. `feature: speak the first sentence as soon as it is generated`
   - `llm_agent.py` : `first_spoken_sentence`
   - `app.py` : un audio seul déclenche la réponse vocale, `stream_voice_answer` lance `speak` dès la première phrase

3. `feature: show the STT LLM and TTS durations`
   - `app.py` : `stt_s` autour de `transcribe`, `llm_s` jusqu'à la première phrase, `tts_s` sur cette synthèse, ligne `STT · LLM · TTS · début de l'audio`

4. `doc: explain the full voice loop in etape8.md`
   - `etape8.md`
