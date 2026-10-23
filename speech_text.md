# Speech vers texte

## Pourquoi je ne peux pas avoir `messages=self.conversation_history` au lieu de `messages=messages` ?

Tu peux écrire `messages=self.conversation_history` tant que chaque élément n'a que `role` et `content`. C'est le cas aujourd'hui, parce que `speech` n'est ajouté que lorsqu'il y a un WAV.

La liste `messages` sert au moment où un tour contient aussi `speech`. Groq n'accepte dans cet appel que `role` et `content`. Un fichier audio dans le même dictionnaire fait rejeter la requête, comme l'objet du micro l'a fait pour `content`. La boucle recopie seulement ces deux champs avant l'envoi. L'historique complet, avec le son, reste dans `self.conversation_history` pour l'affichage.
