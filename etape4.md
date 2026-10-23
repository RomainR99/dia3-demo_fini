# Étape 4 — afficher la réponse au fil de l'eau

## Objectif

La réponse s'affiche au fur et à mesure, au lieu d'arriver d'un seul bloc une fois que le modèle a fini.

## Ce qui change

Sans `stream`, `chat.completions.create` attend la réponse entière, puis renvoie un objet dont on lit `choices[0].message.content`. L'écran reste vide pendant toute la génération.

Avec `stream=True`, le même appel renvoie un flux. Chaque élément est un fragment (`chunk`). Le texte du fragment est dans `chunk.choices[0].delta.content`, pas dans `message.content`. Certains fragments n'ont pas de texte : le premier annonce souvent seulement le rôle, le dernier porte la fin du message. On ne garde que les fragments dont `content` est une chaîne non vide, et on les `yield`.

`ask_llm` ne renvoie donc plus une chaîne. C'est un générateur : il produit les morceaux un par un. Celui qui l'appelle décide quoi en faire.

## Pourquoi `st.write_stream`

Streamlit sait afficher un flux. Dans la bulle de l'assistant, `st.write_stream` parcourt le générateur et écrit chaque morceau dès qu'il arrive. Les premiers mots peuvent apparaître en moins d'une seconde, parce qu'on n'attend plus la fin de la réponse pour commencer à l'afficher.

`st.write_stream` renvoie aussi le texte recollé, dans `response`. C'est cette chaîne complète qu'on range dans l'historique :

```python
response = st.write_stream(ask_llm(user_input, history=st.session_state.messages))
st.session_state.messages.append({"role": "assistant", "content": response})
```

On ne stocke pas le générateur. Une fois parcouru, il est épuisé : on ne peut pas le réafficher. Le tour suivant a besoin du texte entier, au même format que les tours précédents (`role` / `content`), pour le renvoyer au modèle via `*history`.

L'ajout dans `st.session_state.messages` se fait après `st.write_stream`. Avant, la liste ne contient que les tours déjà terminés. `ask_llm` ajoute lui-même la question en cours. Si on ajoutait la question avant l'appel, elle partirait deux fois.

## Ce qu'on voit à l'écran

Au moment où la réponse s'écrit, seule la bulle en cours est un flux. Les messages déjà dans `st.session_state.messages` sont réaffichés par la boucle du haut, avec `st.markdown` sur `message["content"]`.

Après une nouvelle question, le script repart du début. La réponse précédente est déjà une chaîne complète dans la session, donc elle réapparaît en entier. Seule la nouvelle réponse défile.

Dans le terminal, `print(fragment, end="", flush=True)` fait la même chose : `end=""` évite un retour à la ligne entre les morceaux, `flush=True` force l'affichage tout de suite.

## Commits

Ces trois commits passent avant ceux de l'étape 5. `app.py` et `llm_agent.py` contiennent déjà le flux et les images : pour cette étape, ne versionner que la partie flux.

1. `feature: stream the llm response by fragments`
   - `llm_agent.py` : `stream=True`, `yield` de chaque fragment, affichage dans le terminal avec `end=""` et `flush=True`

2. `feature: display the stream in the chat and keep the full text`
   - `app.py` : `st.write_stream` dans la bulle de l'assistant, puis `append` du texte recollé dans `st.session_state.messages`

3. `doc: explain streaming in etape4.md`
   - `etape4.md`
