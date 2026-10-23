# Fonctionnalités

À faire : 8. Faites : 4. Total : 12.

Commits à faire : 8. Un commit par fonctionnalité encore à coder, dans l'ordre de priorité ci-dessous.

Def à avoir : 13. Def faites : 31. Total : 44.

Les 8 def du parcours vidéo restent à coder. Les 5 autres sont le lot `ConversationAgent` de Romain : les noms n'existent pas encore, le comportement est déjà dans d'autres fonctions. Le code à écrire depuis zéro, seulement pour ce lot, est dans `conversation_agent_romain.md`.

## Def à avoir

5 classes, de `Sujet` à `CanvaDesign`, plus `ConversationAgent`. 13 def encore à coder.

| Priorité | Classe | Def | Noms |
| --- | --- | --- | --- |
| Romain | `ConversationAgent` | 5 | `encode_image`, `build_content`, `history_has_image`, `get_conversation_history`, `update_conversation_history` |
| 1 | `Sujet` | 2 | `propose_topics`, `fetch_trends` |
| 2 | `Post` | 2 | `draft_post`, `save_post_edit` |
| 3 | `Video` | 1 | `build_video` |
| 4 | `DiscordServeur` | 1 | `send_discord` |
| 5 | `CanvaDesign` | 2 | `create_canva`, `refresh_canva` |

## Def faites

7 classes. 31 def déjà en place.

| Priorité | Classe | Def | Noms |
| --- | --- | --- | --- |
| 1 | `User` | 3 | `create_user`, `authenticate`, `get_user_persona` |
| 2 | `Message` | 2 | `load_messages`, `add_message` |
| 3 | `Feed` | 4 | `list_feeds`, `set_feed_active`, `fetch_entries`, `refresh_user` |
| 4 | `Article` | 2 | `recent_articles`, `digest_for` |
| 5 | `Mailbox` | 8 | `save_mailbox`, `disconnect_mailbox`, `get_mailbox_credentials`, `connect_mailbox`, `fetch_newsletters`, `matches_theme`, `refresh_mailbox`, `delete_mail_articles` |
| 6 | `Conversation_Manager` | 7 | `ask_llm`, `transcribe`, `speak`, `prepare_image`, `text_for_speech`, `first_spoken_sentence`, `split_for_speech` |
| 7 | `UserInterface` | 5 | `require_user`, `show_veille`, `_show_gmail`, `_handle_turn`, `stream_voice_answer` |

Pour le lot Romain, quatre noms sont déjà le dialogue : `read_file`, `ask_llm`, `transcribe`, `prepare_image`. `read_file` est une méthode de la classe, elle n'est pas dans le compte des 7. `encode_image` est encore à l'intérieur de `prepare_image`. L'historique part en argument : `get_conversation_history` et `update_conversation_history` ne sont pas appelées. `build_content` s'appelle `_user_content`. Le choix du modèle vision est dans `ask_llm`, pas dans `history_has_image`.

## À faire

| Priorité | Fonctionnalité | Commit |
| --- | --- | --- |
| 1 | Proposer des sujets selon le persona, à partir des flux RSS et des newsletters retenues. | 1 |
| 2 | Ajouter les tendances Twitter du thème, sans bloquer les sujets si Twitter ne répond pas. | 1 |
| 3 | Rédiger un texte parlable de 2 à 3 minutes sur le sujet choisi. | 1 |
| 4 | Laisser modifier le texte, et n'envoyer en vidéo que la version validée. | 1 |
| 5 | Monter la vidéo : images, voix et sous-titres alignés sur le texte validé. | 1 |
| 6 | Envoyer la vidéo sur le serveur Discord du compte. Si le fichier est trop lourd, envoyer un lien. | 1 |
| 7 | Créer le design Canva et joindre le lien d'édition au message Discord. | 1 |
| 8 | Reprendre un Canva modifié : même voix, nouveaux visuels, sous-titres. Refuser un lien collé sans identifiant de design. | 1 |

## Faites

| Priorité | Fonctionnalité |
| --- | --- |
| 1 | Comptes et séparation : création, persona techno ou finance, mot de passe, historique propre à chaque compte. |
| 2 | Flux RSS : lecture, rafraîchissement des 8 flux du thème, extrait de titres et de liens pour l'agent. |
| 3 | Gmail et thème : connexion, mois précédent, newsletters retenues selon le persona, les autres laissées de côté. |
| 4 | Dialogue : question, image, transcription, réponse vocale en français, veille du compte dans le contexte. |
