# Crédits NVIDIA pour Audio2Face

NVIDIA met à disposition des crédits gratuits, en général **1 000 crédits** à l'inscription, sur le portail [NVIDIA Build](https://build.nvidia.com/). Ils servent à tester les API NIM, dont [Audio2Face](https://build.nvidia.com/nvidia/audio2face-3d/api).

Pour Bonnie, ces crédits suffisent à peaufiner l'avatar et à valider le code sur Mac pendant des mois.

## Sommaire

- [Branchements dans l'application](#branchements)
- [Pendant le développement](#developpement)
- [Quand l'application est en ligne](#en-ligne)

## Branchements dans l'application

Bonnie est le fichier `asset/Bonnie1.blend`. Il n'a ni armature ni clés de forme. `avatar/export_bonnie.py` lui ajoute six clés de bouche (JawOpen, MouthClose, MouthFunnel, MouthPucker, MouthSmileLeft, MouthSmileRight) et écrit `avatar/view/bonnie.glb`.

Les maillages affichés avaient un matériau gris. Les teintes sont sur `skin.001` (peau) et `hair.001` (cheveux). L'export les recopie dans les couleurs de sommets, sinon la page reste grise.

L'avatar est affiché en haut de chaque page, y compris la connexion. Le lecteur du post remplace l'ancien `st.audio`. Un clic sur lecture envoie ce WAV à Audio2Face. La réponse vocale qui démarre toute seule fait le même appel avant de jouer le son.

Le bouton lecture de la vidéo fait la même chose avec la piste son du mp4. Pendant le film, la bouche suit le temps de la vidéo.

Avec « Réponse vocale » allumé, un nouveau post est lu dès qu'il apparaît. La bouche suit cette lecture. Allumer l'interrupteur alors qu'un post est déjà à l'écran le lit aussi.

`avatar/audio2face.py` lit `NVIDIA_API_KEY` dans `.env`. La clé n'est pas dans le code. Le terminal qui a lancé Streamlit affiche la structure reçue : noms ARKit, nombre d'images, poids de la première image, et le maximum de JawOpen.

Installation, depuis le dossier du projet, environnement activé :

```bash
pip install grpcio==1.85.0
pip install --no-deps https://github.com/NVIDIA/Audio2Face-3D-Samples/raw/main/proto/sample_wheel/nvidia_ace-1.2.0-py3-none-any.whl
```

`--no-deps` est obligatoire. Le paquet NVIDIA demande protobuf 4.24, et cette version casse Streamlit.

Pour refaire le GLB après un changement du .blend :

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background asset/Bonnie1.blend --python avatar/export_bonnie.py
```

## Pendant le développement

Gratuit.

1. Créer un compte gratuit sur [NVIDIA Build](https://build.nvidia.com/) ou [NGC](https://ngc.nvidia.com/).
2. Récupérer une clé API.
3. Depuis le Mac, dans Unity ou dans le code web, envoyer l'audio du professeur de langue à NVIDIA avec cette clé. Les serveurs calculent les mouvements des lèvres et renvoient le résultat à l'écran.

## Quand l'application est en ligne

Payant à l'usage, à partir de l'ouverture au public. Le tarif des API NIM suit l'utilisation des cartes graphiques dans le cloud, à la microseconde.

| Poste | Montant |
| --- | --- |
| Animation générée | environ 0,001 $ à 0,003 $ par minute |
| Un élève, 10 heures de parole dans le mois | environ 1,20 $ |
| Abonnement utilisateur | 20 $ par mois |

Le coût Audio2Face est couvert par l'abonnement.
