# Audio2Face pour le client final

Pour le client final, ça va être lourd s'il doit avoir Audio2Face ?

Non. L'utilisateur final n'aura rien à installer. Son application sera aussi légère qu'une application classique comme Duolingo ou TikTok.

Il y a deux architectures possibles, et dans les deux cas le client final n'installe pas Audio2Face.

## 1. Tout est calculé sur le serveur

C'est la méthode utilisée par Praktika. L'application sur le téléphone de l'utilisateur ne fait qu'afficher de la vidéo ou des données 3D légères.

- **Sur le téléphone** : l'application est très légère. L'utilisateur parle dans son micro, le son est envoyé au serveur.
- **Sur le serveur** : c'est là que se trouvent le modèle de conversation, la voix et NVIDIA Audio2Face. Le serveur calcule l'animation des lèvres en quelques millisecondes, puis l'envoie au téléphone sous forme de flux de données (les coordonnées des mouvements) ou de flux vidéo.
- **Résultat** : l'utilisateur peut avoir un vieux smartphone ou un ordinateur d'entrée de gamme. L'avatar fonctionnera de manière fluide.

## 2. Sur l'appareil du client

Si l'animation tourne plus tard directement sur l'appareil de l'utilisateur (pour économiser les coûts de serveur), on n'utilise pas le logiciel lourd Audio2Face.

Le SDK de NVIDIA permet d'exporter uniquement le réseau de neurones entraîné sous la forme d'un fichier de quelques mégaoctets. Ce fichier est intégré directement dans l'application. Elle calcule alors le mouvement des lèvres localement sur le téléphone, sans nécessiter l'installation d'Audio2Face par l'utilisateur.
