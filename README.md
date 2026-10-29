# Barbe-Quasar

Agent de conversation en Streamlit, branché sur l'API Groq. Le texte passe par `openai/gpt-oss-120b`. Dès qu'une image est dans la requête, l'appel passe sur `qwen/qwen3.8-27b`.

`app.py` affiche le chat. Il n'appelle pas Groq. Les requêtes sont dans `llm_agent.py`. Les modèles, les tailles d'image, le délai et les textes de l'interface sont dans `config.py`.

## Installation

Il faut Python 3.12. Depuis le dossier du projet :

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Sous Windows, l'activation s'écrit `env\Scripts\activate`.

Ouvre `.env` et colle ta clé Groq après le signe `=`. La clé se crée sur [console.groq.com/keys](https://console.groq.com/keys). Le nom de la variable est `GROQ_KEY`. Le fichier `.env` reste sur ta machine : il est ignoré par git.

## Lancement

Toujours depuis le dossier du projet, avec l'environnement activé :

```bash
streamlit run app.py
```

Le navigateur s'ouvre sur http://localhost:8501. Si ce port est déjà pris :

```bash
streamlit run app.py --server.port 8502
```

Une clé fausse, un quota dépassé, un délai trop long, une coupure réseau ou une image illisible s'affichent comme un message dans la page. La trace Python ne remplace pas ce message.

La réponse vocale en français utilise la voix `Thomas` de macOS quand Groq ne fournit pas de voix française. Sur une autre machine, le texte de la réponse s'affiche quand même.

## Images

### Taille

Les photos de téléphone dépassent souvent la taille acceptée par l'API. Groq refuse une requête qui contient une image au-delà de 20 Mo, et l'encodage base64 grossit le fichier d'environ un tiers : une photo déjà lourde peut faire échouer l'appel avant même que le modèle la voie.

Avant l'envoi, Pillow réduit la photo. Le plus grand côté est ramené à `MAX_SIDE` (1 280 pixels), l'image est convertie en JPEG, et le résultat est plafonné à `MAX_JPEG_BYTES` (4 Mo). Ces deux valeurs sont dans `config.py`. Une photo de plus de 5 Mo est donc acceptée. Le préfixe de la data URL est `image/jpeg`, parce que ce sont des octets JPEG qui partent, y compris si le fichier d'origine était un PNG.

### Historique

Renvoyer toutes les anciennes images à chaque tour coûte cher : chez ce modèle, chaque image compte 2 048 jetons, et une requête en accepte au plus `MAX_IMAGES` (3).

On ne renvoie les pixels que du dernier message qui contenait des photos. Les photos des tours précédents sont retirées de la requête et remplacées par une phrase. La réponse déjà donnée par l'assistant reste dans l'historique : elle sert de description de ce que ces anciennes photos montraient, sans payer un nouvel envoi.

La dernière photo, elle, reste dans l'historique envoyé. Une question de suivi sur cette photo fonctionne sans que l'utilisateur la joigne à nouveau. Dès qu'il joint une nouvelle photo, c'est celle-là qui devient la dernière, et les précédentes passent en texte.

## Avatar

L'animation du visage à partir de la voix passe par Audio2Face. Le téléchargement gratuit est ici : [Audio2Face](https://www.reallusion.com/iclone/nvidia-omniverse/Audio2Face.html#free-download).

La bouche de Bonnie est calculée par l'API cloud NVIDIA, qui parle en gRPC, pas en HTTP. Depuis le dossier du projet, environnement activé :

```bash
pip install grpcio==1.85.0
pip install --no-deps https://github.com/NVIDIA/Audio2Face-3D-Samples/raw/main/proto/sample_wheel/nvidia_ace-1.2.0-py3-none-any.whl
```

`grpcio` est le client qui ouvre la connexion vers `grpc.nvcf.nvidia.com`. La version `1.85.0` est celle qui tourne avec Python 3.12 du projet.

`nvidia-ace` apporte les messages protobuf d'Audio2Face : l'envoi du WAV et la lecture des blendshapes. `--no-deps` est obligatoire. Sans ce drapeau, pip installe aussi protobuf 4.24, alors que Streamlit utilise protobuf 7. La version 4.24 casse l'application. Les messages protobuf, eux, se chargent quand même avec la version déjà présente.
