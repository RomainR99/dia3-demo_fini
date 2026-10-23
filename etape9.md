# Étape 9 — une base qu'un autre groupe peut lancer

## Objectif

Le dépôt se fork, s'installe et se lance en ne lisant que le README. Une erreur prévisible n'affiche plus une trace Python : la page dit ce qui s'est passé.

## Tout est dans `config.py`

Les noms de modèles, la consigne vocale, la voix, le nombre d'images, la taille du JPEG, le délai d'un appel, le fichier `context.txt`, le nom de la variable `GROQ_KEY`, le titre de la page et le texte du champ de saisie sont des constantes de `config.py`.

`llm_agent.py` et `app.py` les importent. Changer de modèle, ou le délai, se fait dans ce fichier seul. `REQUEST_TIMEOUT` est le délai passé au client Groq, en secondes. Passé ce délai, Groq lève une erreur de timeout, et l'interface la traduit.

## Aucun appel Groq dans `app.py`

`app.py` importe `ask_llm`, `transcribe`, `speak` et `prepare_image`. Il ne importe pas `groq`. La création du client, la clé et les requêtes restent dans `llm_agent.py`. Le client n'est plus construit au chargement du module : `_client` le crée au premier appel. Une clé absente n'empêche donc pas la page de s'ouvrir.

## Le message à la place de la trace

Les erreurs Groq deviennent un `AgentError`. Son texte est déjà la phrase à montrer. `app.py` l'attrape autour du tour en cours et appelle `st.error`. Les autres exceptions ne sont pas masquées : un vrai bug de code garde sa trace.

`_clear_message` choisit la phrase selon le type :

| Situation | Exception Groq | Phrase affichée |
| --- | --- | --- |
| Clé absente | — (avant l'appel) | copier `.env.example` et remplir `GROQ_KEY` |
| Clé refusée | `AuthenticationError` (401) | vérifier `GROQ_KEY` dans `.env` |
| Quota | `RateLimitError` (429) | le quota est dépassé, réessayer plus tard |
| Délai | `APITimeoutError` | le délai de réponse est dépassé |
| Réseau coupé | `APIConnectionError` | Groq est injoignable |
| Image refusée par l'API | `BadRequestError` alors qu'une image était dans la requête | envoyer un PNG ou un JPEG |
| Fichier qui n'est pas une image | Pillow, dans `prepare_image` | cette image ne peut pas être lue |

Le délai est testé avant la coupure réseau, parce que `APITimeoutError` hérite de `APIConnectionError`. Une image illisible est refusée avant l'appel : `prepare_image` lève `AgentError`, et les octets ne partent pas.

## Installation

Le README donne l'ordre : créer `env`, installer `requirements.txt` (versions figées), copier `.env.example` vers `.env`, y mettre la clé, lancer `streamlit run app.py` depuis le dossier du projet. `.env` est dans `.gitignore`. La clé d'un groupe ne part pas avec le fork.

## Commits

Ces commits passent après ceux de l'étape 8. `app.py`, `llm_agent.py` et `README.md` contiennent déjà les étapes précédentes : pour celle-ci, ne versionner que la configuration, les erreurs et l'installation.

1. `feature: group the settings in config.py`
   - `config.py` : modèles, voix, images, délai, textes de l'interface
   - `llm_agent.py` et `app.py` : ces valeurs sont importées, plus écrites sur place

2. `feature: show a clear message when the api fails`
   - `llm_agent.py` : `AgentError`, clé absente ou refusée, quota 429, délai, réseau, image refusée
   - `app.py` : `st.error` à la place de la trace

3. `doc: explain install and launch in the readme`
   - `README.md` : installation, lancement, lien vers `config.py`
   - `requirements.txt` : versions figées
   - `.env.example`

4. `doc: explain the clean base in etape9.md`
   - `etape9.md`
