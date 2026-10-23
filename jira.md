# Jira

## Vérifier qu'un utilisateur ne peut pas accéder à la boîte mail d'un autre

**Type :** test  
**Composant :** Gmail, comptes

### Description

Deux comptes de l'application ont chacun leur boîte. Le compte B ne doit voir ni l'adresse Gmail du compte A, ni ses newsletters, ni les recevoir dans la réponse de l'agent.

La lecture des e-mails et la liste envoyée au modèle partent de l'identifiant du compte connecté (`user_id`).

### Étapes

1. Se connecter avec le compte A. Connecter Gmail, cliquer sur **Rafraîchir la veille**, et noter un objet affiché sous « Newsletters du mois dernier ».
2. Cliquer sur **Quitter le bord**.
3. Se connecter avec le compte B, un compte qui n'a pas connecté de boîte.
4. Regarder la barre latérale.
5. Demander à l'agent : « Quelles newsletters Gmail as-tu du mois dernier ? »

Contrôle en base, depuis le dossier du projet :

```bash
env/bin/python -c "
import sqlite3
c = sqlite3.connect('data/jarvis.db')
for row in c.execute('''
    SELECT users.username, mailboxes.address, articles.title
    FROM articles
    JOIN feeds ON feeds.id = articles.feed_id
    JOIN users ON users.id = articles.user_id
    LEFT JOIN mailboxes ON mailboxes.user_id = users.id
    WHERE feeds.kind = \"email\"
'''):
    print(row)
"
```

### Résultat attendu

- La barre du compte B ne dit pas `Connecté :` avec l'adresse du compte A.
- La liste « Newsletters du mois dernier » du compte B est vide. L'objet noté à l'étape 1 n'y est pas.
- L'agent ne cite pas cet objet.
- Dans la base, chaque objet de newsletter est à côté d'un seul nom de compte.
