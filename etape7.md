# Étape 7 — sortie vocale

## Objectif

Sur option, l'assistant lit sa réponse à voix haute. Une réponse de cinq phrases est lue en entier, en français, sans que les astérisques du markdown soient prononcés.

## L'interrupteur

`st.toggle("Réponse vocale", key="speak")` est sous le titre. La clé `speak` garde le choix dans la session : il reste actif d'un message à l'autre. Tant qu'il est coupé, rien n'est synthétisé. Le texte de la réponse s'affiche dans tous les cas.

## Nettoyer avant de lire

La réponse affichée reste en markdown. La synthèse, elle, reçoit une autre chaîne, produite par `text_for_speech`.

Les blocs de code sont enlevés. Les liens ne gardent que leur texte. Les caractères de markdown `*`, `_`, `#`, `~` et `>` sont retirés, donc `**total**` devient `total` et aucune étoile n'est lue. Les emojis sont retirés aussi. Les espaces en trop sont ramenés à un seul.

## Découper par phrases

Orpheus, le modèle de synthèse de Groq, refuse un texte de plus de 200 caractères. `split_for_speech` coupe d'abord sur `.`, `!` et `?`, puis recoupe une phrase trop longue au dernier espace avant 200 caractères.

Cinq phrases courtes font donc cinq requêtes. Chacune renvoie un WAV. `_concat_wavs` recolle les échantillons dans un seul fichier, avec un seul en-tête. `st.audio` joue ce fichier en entier, pas une phrase puis le silence.

## D'où viennent les octets

`speak` demande d'abord `client.audio.speech.create` au modèle `canopylabs/orpheus-v1-english`, voix `troy`, format `wav`. PlayAI, l'ancien modèle, est retiré. Orpheus est une voix anglaise, et le compte doit accepter ses conditions une fois, sinon l'appel est refusé.

Si Groq refuse, la même phrase part à la voix française `Thomas` du Mac, via `say`, qui écrit un WAV. Les phrases suivantes de la réponse utilisent directement cette voix, sans rappeler Groq. Le texte lu est celui déjà nettoyé. C'est ce WAV que l'application joue, donc la réponse s'entend en français.

## Lecture dans la bulle

`st.audio(..., autoplay=True)` ne concerne que la réponse qui vient d'être produite : le navigateur accepte la lecture automatique parce que l'utilisateur vient d'envoyer un message. Les octets sont aussi rangés dans le message assistant, sous `speech`. Au tour suivant, `show_message` réaffiche le lecteur sans `autoplay`, pour pouvoir réécouter sans relancer toutes les anciennes réponses.

## Commits

Ces commits passent après ceux de l'étape 6. `app.py` et `llm_agent.py` contiennent déjà les étapes précédentes : pour celle-ci, ne versionner que la partie synthèse.

1. `feature: clean the answer before reading it aloud`
   - `llm_agent.py` : `text_for_speech`, retrait du markdown, du code, des emojis et des astérisques

2. `feature: split the spoken text into short sentences`
   - `llm_agent.py` : `split_for_speech`, coupure sur les phrases puis à 200 caractères

3. `feature: synthesize each sentence into one wav`
   - `llm_agent.py` : `speak`, appel Orpheus, repli sur la voix française `Thomas`, collage des WAV

4. `feature: add a voice answer toggle`
   - `app.py` : interrupteur « Réponse vocale », `st.audio` en lecture automatique pour la réponse en cours, lecteur sans autoplay dans l'historique

5. `doc: explain text to speech in etape7.md`
   - `etape7.md`
