# Questions

## Que se passe-t-il quand l'historique dépasse la fenêtre de contexte ? Les premiers messages sont-ils enlevés, donc le prompt system ?

Si le total dépasse la fenêtre du modèle, Groq refuse l'appel. La réponse n'arrive pas. Le message `system` n'est pas dans `history` : il est relu dans `context.txt` à chaque fois, donc il n'est pas le premier élément que l'on pourrait couper.
