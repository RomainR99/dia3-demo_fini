# Étape 5 — compréhension d'images

## Objectif

L'utilisateur joint une image et pose une question dessus. Une question suivante sur la même image fonctionne sans qu'il la joigne à nouveau.

## Le message n'est plus une simple chaîne

Sans image, `content` reste le texte de la question. Avec une image, `content` devient une liste de blocs. Le premier bloc est le texte. Chaque image est un bloc `image_url` :

```python
{
    "type": "image_url",
    "image_url": {"url": "data:image/jpeg;base64,..."},
}
```

L'image ne part pas comme un fichier à part. Elle est encodée en base64, puis collée dans une data URL. Le préfixe `data:image/jpeg;base64,` dit au modèle que les octets sont un JPEG. Après redimensionnement, on réencode toujours en JPEG, donc le type annoncé est `image/jpeg`, le même que les octets.

Groq limite une requête à 3 images. Au-delà, l'interface prévient et n'envoie que les trois premières.

## Deux modèles

`openai/gpt-oss-120b` répond au texte. Il ne lit pas les images. Dès qu'un message de la requête contient un bloc image, l'appel part sur `qwen/qwen3.8-27b`, le modèle vision disponible sur le compte. Ça vaut aussi pour une question de suivi : la photo est encore dans l'historique envoyé, donc c'est encore le modèle vision qui répond.

`include_reasoning=False` reste réservé au modèle texte. Le modèle vision n'utilise pas ce paramètre.

## La taille

Une photo de téléphone dépasse souvent ce qu'on peut mettre dans la requête. Groq refuse une requête image au-delà de 20 Mo, et le base64 ajoute environ un tiers au poids du fichier. `prepare_image` ouvre la photo avec Pillow, la passe en RGB, ramène le plus grand côté à 1 280 pixels, puis l'enregistre en JPEG. Si le fichier dépasse encore 4 Mo, la qualité baisse, puis les dimensions. Une photo de plus de 5 Mo part donc dans un JPEG bien plus léger, et l'appel est accepté.

## L'historique

Chaque image compte 2 048 jetons, même une fois réduite. Renvoyer toutes les photos de la conversation à chaque tour alourdit la requête, et la limite de 3 images serait vite atteinte.

La séance garde les photos, pour les réafficher. La requête, elle, ne garde les blocs image que du dernier tour qui en avait. Les photos plus anciennes sont remplacées par une phrase. Le texte de l'assistant qui suivait ces photos reste dans l'historique : c'est lui qui dit ce que l'ancienne photo montrait, sans la renvoyer.

Si le nouveau message n'a pas de photo, la dernière photo déjà posée est remise dans la requête. L'utilisateur n'a pas à la joindre à nouveau pour poser une question de suivi.

## Commits

Ces commits passent après les trois de l'étape 4. `app.py` et `llm_agent.py` mélangent encore le flux et les images : pour cette étape, ne versionner que la partie image.

1. `feature: adding pillow`
   - `requirements.txt`

2. `feature: resize photos before the api call`
   - `llm_agent.py` : `prepare_image` (Pillow, côté max 1 280 px, JPEG plafonné à 4 Mo, data URL `image/jpeg`)

3. `feature: send images to a vision model`
   - `llm_agent.py` : blocs `image_url`, bascule vers `qwen/qwen3.8-27b` dès qu'une image est dans la requête, `openai/gpt-oss-120b` sinon

4. `feature: keep only the last image in the request history`
   - `llm_agent.py` : `_history_for_api`, les photos plus anciennes remplacées par une phrase, la dernière renvoyée pour la question de suivi

5. `feature: attach images in the chat`
   - `app.py` : `accept_file`, affichage des photos, envoi à `ask_llm`, au plus 3 images

6. `doc: justify image size and history`
   - `README.md` : les deux décisions, taille et historique

7. `doc: explain image understanding in etape5.md`
   - `etape5.md`
