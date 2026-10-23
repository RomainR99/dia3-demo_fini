# Rapport — mémoire de l'agent et points vus en session

## Sommaire

**Mise en route**

- [1. La branche locale et le remote](#branche-locale)
- [2. Installer `requirements.txt`](#installer-requirements)

**Mémoire de la conversation**

- [3. Écrire dans un fichier ne donne pas de mémoire au modèle](#enregistrer-reponse)
  - [Corriger l'appel](#corriger-appel)
  - [Relire le fichier avant chaque question](#relire-fichier)
- [4. À quoi sert `*history`](#etoile-history)
- [5. Passer l'historique à `ask_llm`](#historique-ask-llm)
- [7. Ajouter un tour avec `append`](#session-state-append)
- [11. `*history` en détail](#history-detail)
- [14. Pourquoi `history=None`](#history-none)
- [15. Si l'historique dépasse la fenêtre de contexte](#fenetre-contexte)

**La classe et l'interface**

- [6. Pourquoi `agent = Conversation_Manager()`](#agent-conversation-manager)
- [8. À quoi correspond `st`](#alias-st)

**Détails du code**

- [9. Pourquoi `choices[0]`](#choices-zero)
- [10. Pourquoi `import os`](#import-os)
- [12. À quoi sert `print("\n")`](#print-newline)
- [13. Le `"r"` de `open`](#open-mode-r)

**Réponse vocale**

- [16. La ligne STT · LLM · TTS · début de l'audio](#latence-vocale)

**Boîte Gmail**

- [17. Le mot de passe d'application](#mot-de-passe-application)

**Micro sur téléphone**

- [18. Simuler le bouton comme sur un téléphone](#simuler-telephone)

**Streamlit**

- [19. Pourquoi relancer le serveur après un changement](#relancer-streamlit)

<a id="branche-locale"></a>

## 1. La branche locale et le remote

La branche locale `feature/user-interface-for-llm-agent` n'était pas la branche distante. Elle a été créée à partir de `main` (le commit `Initial commit`) et n'avait pas d'upstream : `git status` affichait le nom de la branche sans `[origin/...]`.

Sur GitHub, `origin/feature/user-interface-for-llm-agent` était 4 commits plus loin :

- `requirements.txt`
- appel LLM via API
- personnalité de l'agent
- v1 de l'interface (`app.py`, `context.txt`, `llm_agent.py`)

Pour s'aligner sur le remote :

```bash
git checkout feature/user-interface-for-llm-agent
git branch -u origin/feature/user-interface-for-llm-agent
git pull
```

<a id="installer-requirements"></a>

## 2. Installer `requirements.txt`

`pip install requirements.txt` et `pip install requirements` demandent à pip un paquet qui porte ce nom. Le paquet n'existe pas.

Le drapeau `-r` dit à pip de lire le fichier et d'installer les paquets listés (`groq`, `python-dotenv`, `streamlit`) :

```bash
pip install -r requirements.txt
```

<a id="enregistrer-reponse"></a>

## 3. Enregistrer une réponse ne donne pas de mémoire au modèle

Écrire dans `memory.txt` et faire se souvenir le modèle sont deux actions distinctes. Le modèle ne voit que ce qu'on met dans `messages`.

`generate_response_memory` écrivait l'échange, mais :

- dans `app.py`, Streamlit n'appelait que `ask_llm` ;
- dans le bloc `if __name__ == "__main__"`, l'appel était `generate_response_memeory(response)` : le nom était faux, et la question n'était pas passée ;
- `ask_llm` n'envoyait que `context.txt` et la question du tour en cours.

`memory.txt` pouvait donc rester vide, et même rempli il était ignoré.

<a id="corriger-appel"></a>

### Corriger l'appel

La fonction attend la question et la réponse. On l'appelle une fois que `ask_llm` a renvoyé le texte, avec les deux arguments. `print(generate_response_memory(...))` affichait `None`, parce que la fonction écrit dans le fichier et ne renvoie rien : on l'appelle sans `print`.

`open(file_path="./memory.txt", "a")` est invalide. Le premier argument de `open` s'appelle `file`, pas `file_path`. La forme correcte est `open("./memory.txt", "a")`.

La fonction était aussi indentée après le `return` de `ask_llm`, donc jamais définie. Elle doit être au niveau du module.

<a id="relire-fichier"></a>

### Relire le fichier avant chaque question

Cette relecture se place au début de `ask_llm`, avant la création du client Groq. Un `return read_file(...)` à la fin de `generate_response_memory` arrive trop tard : la réponse est déjà partie.

1. Déclarer une variable `memory` juste sous `def ask_llm(question):`.
2. Tester si `./memory.txt` existe avec `os.path.isfile` (`os` est déjà importé). `read_file` fait un `open` en lecture : si le fichier n'existe pas, Python lève `FileNotFoundError`.
3. S'il existe, `memory = read_file("./memory.txt")`. Sinon, `memory = ""`. Un fichier vide renvoie déjà `""`.
4. Ajouter `memory` au message `system`, à la suite de `context.txt`, avec une phrase du type « voici la conversation déjà eue ». Tant que ce texte n'est dans aucun `messages`, la lecture ne change rien pour le modèle.

Au premier message, le fichier est vide : seul `context.txt` part. Aux tours suivants, l'historique est renvoyé au modèle.

<a id="etoile-history"></a>

## 4. À quoi sert `*history`

`ask_llm` peut recevoir une liste `history` de tours déjà eus. Chaque tour est un dictionnaire `role` / `content`.

`*history` déplie cette liste et place ses dictionnaires, un par un, dans `messages`, entre le personnage et la nouvelle question :

```python
messages = [
    {"role": "system", "content": "...contexte..."},
    {"role": "user", "content": "salut"},
    {"role": "assistant", "content": "Ahoy, moussaillon"},
    {"role": "user", "content": "tu te souviens de moi ?"},
]
```

Sans l'étoile, Python mettrait la liste entière comme un seul élément. L'API attend une suite de dictionnaires, pas une liste imbriquée.

Si `history` est vide, `*history` n'ajoute rien : il ne reste que le message système et la question.

Deux erreurs empêchaient cette liste de se construire :

- `*histoty` pointait vers un nom qui n'existe pas. Le bon nom est `*history`.
- Il manquait la virgule après cet élément, donc Python ne pouvait pas enchaîner avec le message utilisateur.

`history=[]` en argument par défaut est remplacé par `None`, puis une liste vide est créée dans la fonction. Une liste écrite dans la signature est partagée entre tous les appels.

<a id="historique-ask-llm"></a>

## 5. Historique passé à `ask_llm`

`app.py` garde les tours dans `st.session_state.messages`. À chaque question, cette liste est passée à `ask_llm` dans `history`, avant d'y ajouter le nouveau message. `*history` déplie donc les tours précédents dans l'appel Groq.

Chaque tour enregistré a le rôle `user` ou `assistant`. Groq attend `assistant` pour les réponses du modèle. Après l'appel, la question et la réponse sont ajoutées à `st.session_state.messages`, puis affichées. Au prochain message, elles font partie de l'historique.

<a id="agent-conversation-manager"></a>

## 6. Pourquoi `agent = Conversation_Manager()`

Le nom `agent` garde cet objet. Ensuite `agent.ask_llm(...)` rappelle le même objet, avec le même client Groq et la même `conversation_history`. Le nom pourrait être `manager` : ce qui compte, c'est de ranger le résultat.

Écrire `Conversation_Manager().ask_llm(...)` directement marche pour un seul appel, mais chaque question construit un objet neuf. L'historique posé sur cet objet repart à vide et disparaît à la fin de l'appel.

<a id="session-state-append"></a>

## 7. `st.session_state.messages.append(...)`

`st.session_state.messages.append({"role": "user", "content": user_input})` ajoute ta question à la liste gardée dans la session, pour que le tour suivant puisse la renvoyer au modèle.

`st.session_state.messages` est la liste des tours de cet onglet. `append` colle un élément à la fin. L'élément est un dictionnaire avec deux champs :

- `role` vaut `"user"`, pour dire que c'est toi qui parles.
- `content` vaut `user_input`, le texte tapé dans le chat.

La ligne d'après fait la même chose avec la réponse, en `"assistant"`. Au message suivant, cette liste part dans `history`, et `*history` la déplie dans l'appel à Groq.

<a id="alias-st"></a>

## 8. À quoi correspond `st`

`st` est le raccourci du module Streamlit. La première ligne de `app.py` fait `import streamlit as st`, donc `st.session_state` signifie `streamlit.session_state`.

Le nom `st` n'a rien de spécial : c'est l'alias choisi à l'import. `st.chat_input`, `st.title` et `st.session_state` sont des fonctions et des objets fournis par Streamlit.

<a id="choices-zero"></a>

## 9. Pourquoi `choices[0]`

`choices` est une liste. L'API peut renvoyer plusieurs réponses possibles pour la même question, et `[0]` prend la première.

Par défaut, Groq n'en produit qu'une seule, donc la liste ne contient qu'un élément, à l'index `0`. `.message.content` est le texte de cette réponse. Sans `[0]`, tu aurais la liste entière, pas le message.

<a id="import-os"></a>

## 10. Pourquoi `import os`

`import os` sert à lire la clé API dans les variables d'environnement. Dans `llm_agent.py`, la seule utilisation est `os.environ["GROQ_KEY"]`.

`load_dotenv()` charge le fichier `.env` et y place `GROQ_KEY`. `os.environ` est le dictionnaire de Python qui contient ces variables. Sans `import os`, cette ligne ne peut pas s'exécuter : `os` n'existerait pas.

<a id="history-detail"></a>

## 11. `*history` en détail

`*history` déplie la liste des tours précédents et les place, un par un, dans `messages`, entre le personnage et la nouvelle question.

`history` est une liste de dictionnaires `role` / `content`. L'étoile enlève les crochets. La liste envoyée à Groq ressemble alors à ceci : le message `system` avec `context.txt`, puis chaque tour déjà eu, puis la question en cours.

La virgule après `*history` sépare cet élément du message utilisateur, comme la virgule après le dictionnaire `system`.

Sans l'étoile, Python mettrait la liste entière comme un seul élément. L'API attend une suite de dictionnaires, pas une liste imbriquée. Si `history` est vide, `*history` n'ajoute rien.

<a id="print-newline"></a>

## 12. À quoi sert `print("\n")`

`print("\n")` affiche une ligne vide entre la question et la réponse, dans le bloc qui tourne quand tu lances `llm_agent.py` directement.

`\n` est le caractère « retour à la ligne ». `print` en ajoute un deuxième à la fin, donc le texte de la réponse commence une ligne plus bas, séparé de ce que tu viens de taper. Ça ne change rien pour le modèle, ni pour Streamlit : `app.py` n'appelle pas cette ligne.

<a id="open-mode-r"></a>

## 13. Le `"r"` de `open`

`"r"` veut dire read : ouvrir le fichier seulement pour le lire. `open` peut alors lire le texte, pas le modifier ni l'effacer.

`with` ferme le fichier tout seul à la fin du bloc, même en cas d'erreur. `as file` donne le nom `file` à ce fichier ouvert, et `file.read()` en renvoie tout le contenu sous forme d'une chaîne.

Les autres modes courants : `"w"` écrit en remplaçant ce qui était déjà dans le fichier, `"a"` ajoute à la fin. `"r"` est aussi le mode par défaut d'`open` quand on n'en donne pas.

<a id="history-none"></a>

## 14. Pourquoi `history=None`

`history=None` rend l'argument facultatif. On peut appeler `ask_llm(question)` sans liste, comme dans le bloc `if __name__` ou au premier message. Avec seulement `history`, chaque appel devrait en fournir une, même vide.

La valeur par défaut est `None` et pas `[]`, parce qu'une liste écrite dans la signature est créée une seule fois et partagée entre tous les appels. `None` veut dire « rien n'a été passé ». Le `if` crée alors une liste vide neuve, uniquement pour cet appel.

<a id="fenetre-contexte"></a>

## 15. Si l'historique dépasse la fenêtre de contexte

Si le total dépasse la fenêtre du modèle, Groq refuse l'appel. La réponse n'arrive pas. Le message `system` n'est pas dans `history` : il est relu dans `context.txt` à chaque fois, donc il n'est pas le premier élément que l'on pourrait couper.

<a id="latence-vocale"></a>

## 16. La ligne STT · LLM · TTS · début de l'audio

Sous une réponse vocale, la page affiche quatre durées. Deux relevés de la session :

`STT 0,2 s · LLM 0,5 s · TTS 0,0 s · début de l'audio 1,2 s`

`STT — · LLM 0,8 s · TTS 0,1 s · début de l'audio 1,3 s`

Le nombre à comparer aux 5 secondes est le dernier : le temps jusqu'au début du son.

**STT** est la transcription. Dans le premier relevé, Whisper a mis 0,2 s : le message a été dicté. Le tiret du second relevé veut dire qu'il n'y a pas eu d'audio. Le message a été tapé, et l'interrupteur « Réponse vocale » a fait lire la réponse.

**LLM** s'arrête à la première phrase complète. 0,5 s et 0,8 s ne couvrent pas toute la génération. C'est le moment où la synthèse de cette phrase peut commencer. La suite du texte continue de s'écrire après.

**TTS** est la synthèse de cette première phrase seulement. 0,1 s, c'est la voix française du Mac, produite sur la machine. 0,0 s est le même cas, affiché avec une seule décimale : en dessous de 0,05 s, le chiffre affiché est 0,0.

**début de l'audio** part plus tôt que les trois autres, au moment où la page se relance parce que le message est arrivé. Dans le premier relevé, 0,2 + 0,5 + 0,0 font 0,7 s. Le passage à 1,2 s, c'est le temps de relancer la page avant la transcription. Dans le second, 0,8 + 0,1 font 0,9 s, et 1,3 s inclut le même temps de relance. Le tiret de STT n'entre pas dans cette addition.

<a id="mot-de-passe-application"></a>

## 17. Le mot de passe d'application

Dans le champ « Mot de passe d'application », colle le code de 16 lettres que Google génère, pas le mot de passe avec lequel tu ouvres Gmail. Il ressemble à `abcd efgh ijkl mnop`. Les espaces peuvent rester.

Pour l'obtenir :

1. Active la validation en deux étapes sur le compte Google. Sans elle, Google ne propose pas ce code.
2. Ouvre [Mots de passe des applications](https://myaccount.google.com/apppasswords).
3. Crée-en un, nomme-le par exemple `Barbe-Quasar`, puis copie les 16 lettres. Google ne les réaffiche pas.
4. Dans la barre de l'application, mets ton adresse Gmail et ce code, puis clique sur **Connecter Gmail**.

Le détail est sur l'aide Google : [Se connecter avec des mots de passe d'application](https://support.google.com/mail/answer/185833?hl=fr).

Si la page des mots de passe d'application n'existe pas, c'est en général un compte d'école ou d'entreprise, la Protection Avancée, ou une validation en deux étapes limitée aux clés de sécurité. Dans ce cas Google ne fournit pas ce code, et cette connexion IMAP ne peut pas aboutir.

<a id="simuler-telephone"></a>

## 18. Simuler le bouton comme sur un téléphone

Aucune bibliothèque à importer. Le bouton utilise déjà les événements du doigt (`pointerdown` / `pointerup`), les mêmes qu'un téléphone.

Pour le simuler sur le Mac :

1. Ouvre http://localhost:8503 dans Chrome, connecte-toi.
2. Ouvre les outils de développement (⌥⌘I).
3. Active la barre d'appareil (l'icône téléphone, ou ⇧⌘M).
4. Choisis un iPhone. Coche **Touch** s'il est proposé.
5. Maintiens le bouton rouge avec la souris, parle, puis relâche. Le micro utilisé est celui du Mac, parce que la page est en `localhost`.

Sur un vrai téléphone, ouvre l'URL « Network » affichée par Streamlit, sur le même Wi-Fi. Le bouton et la mise en page se voient. Le micro, lui, est refusé : le navigateur n'autorise l'enregistrement qu'en `https` ou en `localhost`, pas sur une adresse du type `http://192.168…`.

<a id="relancer-streamlit"></a>

## 19. Pourquoi relancer le serveur après un changement

Streamlit sait relire un fichier enregistré. Couper le terminal à chaque sauvegarde veut dire qu'une des trois situations suivantes bloque ce rafraîchissement.

### Always Rerun n'est pas activé

La première fois que le fichier principal change, Streamlit propose en haut à droite **Rerun** ou **Always Rerun**.

**Always Rerun** relance la page tout seul à chaque enregistrement (⌘S). Sans ce choix, la page attend un clic sur **Rerun**.

### Le processus s'est arrêté

Une erreur de syntaxe s'affiche dans la page. Le serveur, lui, reste lancé : il peut encore voir l'enregistrement suivant.

Si le terminal affiche le prompt et plus l'adresse locale, le processus est arrêté. Plus rien n'écoute les fichiers. Corrige l'erreur, puis relance `env/bin/python -m streamlit run app.py`. Le linter de l'éditeur signale la syntaxe avant l'enregistrement.

### Un fichier importé a changé

`streamlit run app.py` surveille d'abord `app.py`. La logique est dans d'autres fichiers : `gamma_client.py`, `config.py`, `post.py`, `llm_agent.py`. Python garde en mémoire le module déjà importé. Un nom nouveau, comme `post_intent` ou `GAMMA_LANGUAGES`, produit alors `ImportError` alors que le fichier sur le disque est à jour.

`--server.runOnSave true` relance le script quand un fichier surveillé est enregistré. Sur ce Mac, le terminal demande aussi d'installer `watchdog`. Sans ce paquet, un fichier secondaire passe souvent inaperçu, et l'ancienne version reste en mémoire. Dans ce cas, couper le processus et le relancer est le moyen de recharger le module.

```bash
env/bin/python -m pip install watchdog
env/bin/python -m streamlit run app.py --server.runOnSave true
```

Le même réglage peut vivre dans `.streamlit/config.toml`, à la racine du projet :

```toml
[server]
runOnSave = true
```

| Situation | Comportement | Action |
| --- | --- | --- |
| Fichier principal `app.py` | La page peut se relancer à l'enregistrement | **Always Rerun** dans le navigateur |
| Fichier importé (`post.py`, `config.py`, `gamma_client.py`) | L'ancienne version peut rester en mémoire | `watchdog`, puis `--server.runOnSave true`. Sinon, relancer le processus |
| Le terminal n'affiche plus l'adresse locale | Le processus est arrêté | Corriger l'erreur, puis relancer |
