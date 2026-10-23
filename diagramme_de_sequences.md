# Diagramme de séquences — requêtes HTTP

IMAP vers Gmail n'est pas une requête HTTP. Il est dessiné à part, parce que la veille e-mail passe par lui.

Les séquences marquées **prévu** décrivent la cible. Le code ne les fait pas.

## Déjà en place

### Question, avec la veille déjà en base

```mermaid
sequenceDiagram
    actor U as Utilisateur
    participant App as Streamlit
    participant DB as SQLite
    participant Groq as API Groq

    U->>App: POST message du chat
    App->>DB: SELECT articles du user_id
    DB-->>App: RSS et newsletters retenues
    App->>Groq: POST /openai/v1/chat/completions
    Groq-->>App: fragments de la réponse
    App->>DB: INSERT messages du tour
    App-->>U: texte de la réponse
```

L'appel Groq part de `ask_llm`. Le corps contient `context.txt`, l'extrait de `digest_for`, l'historique de ce compte, puis la question. L'extrait n'est pas réenregistré dans l'historique.

### Réponse vocale

```mermaid
sequenceDiagram
    actor U as Utilisateur
    participant App as Streamlit
    participant Groq as API Groq
    participant Mac as voix locale

    U->>App: audio ou texte
    App->>Groq: POST /openai/v1/audio/transcriptions
    Groq-->>App: texte
    App->>Groq: POST /openai/v1/chat/completions
    Groq-->>App: première phrase
    App->>Groq: POST /openai/v1/audio/speech
    alt Groq refuse la voix française
        App->>Mac: say, voix Thomas
        Mac-->>App: WAV
    else Groq renvoie un WAV
        Groq-->>App: WAV
    end
    App-->>U: lecture
```

### Rafraîchir les flux RSS

```mermaid
sequenceDiagram
    actor U as Utilisateur
    participant App as Streamlit
    participant DB as SQLite
    participant Site as site du flux

    U->>App: Rafraîchir la veille
    App->>DB: SELECT feeds kind=rss du compte
    loop chaque flux actif
        App->>Site: GET url XML
        Site-->>App: RSS ou Atom
        App->>DB: INSERT ou UPDATE articles
    end
    App-->>U: liste des articles, ou l'erreur du flux
```

Huit GET partent en parallèle, quatre à la fois. Une adresse en échec ne coupe pas les autres.

### Lire les newsletters

```mermaid
sequenceDiagram
    actor U as Utilisateur
    participant App as Streamlit
    participant DB as SQLite
    participant Gmail as imap.gmail.com

    U->>App: Connecter Gmail
    App->>Gmail: IMAP login, port 993
    Gmail-->>App: OK ou refus
    App->>DB: INSERT mailbox et feed kind=email
    U->>App: Rafraîchir la veille
    App->>Gmail: SEARCH mois dernier, SUBJECT newsletter
    Gmail-->>App: messages
    App->>App: matches_theme selon le persona
    App->>DB: DELETE anciennes newsletters, INSERT retenues
    App-->>U: liste retenue, nombre laissé de côté
```

Le mot de passe d'application ne sort pas de SQLite. Il n'est pas dans une requête HTTP.

## Cible

### Proposer des sujets, écrire le post, monter la vidéo

```mermaid
sequenceDiagram
    actor U as Utilisateur
    participant App as Streamlit
    participant DB as SQLite
    participant RSS as sites RSS
    participant X as API X
    participant Groq as API Groq
    participant Canva as API Canva
    participant Discord as API Discord

    U->>App: Proposer des sujets
    App->>DB: SELECT persona et articles
    App->>RSS: GET flux du thème
    App->>X: GET tendances du thème
    App->>Groq: POST chat, demande de sujets
    Groq-->>App: sujets
    App-->>U: liste
    U->>App: sujet choisi
    App->>Groq: POST chat, post de 2 à 3 minutes
    Groq-->>U: brouillon
    U->>App: texte modifié puis validé
    App->>App: voix, sous-titres, montage
    opt l'utilisateur veut des slides
        App->>Canva: POST design
        Canva-->>App: design_id et lien d'édition
        App->>Canva: POST export des pages
        Canva-->>App: images
        App->>App: images dans la vidéo
    end
    App->>Discord: POST fichier ou lien, webhook du compte
    Discord-->>U: message sur son serveur
```

### Reprendre le Canva modifié

```mermaid
sequenceDiagram
    actor U as Utilisateur
    participant Canva as Canva
    participant App as Streamlit
    participant Discord as API Discord

    U->>Canva: modifie les slides via le lien
    U->>App: Reprendre mon Canva
    App->>Canva: POST export du même design_id
    Canva-->>App: nouvelles images
    App->>App: reconstruit vidéo, voix et sous-titres
    App->>Discord: POST la nouvelle vidéo
```

Canva n'envoie pas d'appel à l'application quand l'utilisateur enregistre. L'export part au moment où l'utilisateur demande de reprendre les slides.

## Limites des requêtes prévues

| Service | Requête | Contrainte |
| --- | --- | --- |
| X | tendances | accès API payant, pas un simple GET public |
| Canva | créer, exporter | OAuth du compte Canva et identifiant du design |
| Discord | envoyer la vidéo | un webhook par compte ; un fichier trop lourd passe par un lien, pas par une pièce jointe |
| Groq | post de 2 à 3 minutes | appel déjà utilisé pour le chat, avec une consigne de durée différente de la réponse vocale courte |
