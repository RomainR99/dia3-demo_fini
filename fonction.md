# Fonctionnalités

À faire : 4. Faites : 8. Total : 12.

Commits à faire : 4. Un commit par fonctionnalité encore à coder, dans l'ordre de priorité ci-dessous.

Def à avoir : 4. Def faites : 43. Total : 47.

Les 4 def qui restent sont la vidéo, Discord et Canva. `draft_post` et `save_post_edit` sont dans `post.py`. Le guide depuis zéro est `romain3.md`.

## Def à avoir

3 classes, de `Video` à `CanvaDesign`. 4 def encore à coder.

| Priorité | Classe | Def | Noms |
| --- | --- | --- | --- |
| 3 | `Video` | 1 | `build_video` |
| 4 | `DiscordServeur` | 1 | `send_discord` |
| 5 | `CanvaDesign` | 2 | `create_canva`, `refresh_canva` |

## Def faites

9 classes. 43 def déjà en place.

| Priorité | Classe | Def | Noms |
| --- | --- | --- | --- |
| 1 | `User` | 3 | `create_user`, `authenticate`, `get_user_persona` |
| 2 | `Message` | 2 | `load_messages`, `add_message` |
| 3 | `Feed` | 4 | `list_feeds`, `set_feed_active`, `fetch_entries`, `refresh_user` |
| 4 | `Article` | 2 | `recent_articles`, `digest_for` |
| 5 | `Mailbox` | 8 | `save_mailbox`, `disconnect_mailbox`, `get_mailbox_credentials`, `connect_mailbox`, `fetch_newsletters`, `matches_theme`, `refresh_mailbox`, `delete_mail_articles` |
| 6 | `Conversation_Manager` | 12 | `ask_llm`, `transcribe`, `speak`, `prepare_image`, `text_for_speech`, `first_spoken_sentence`, `split_for_speech`, `encode_image`, `build_content`, `history_has_image`, `get_conversation_history`, `update_conversation_history` |
| 7 | `UserInterface` | 8 | `require_user`, `show_veille`, `_show_gmail`, `_handle_turn`, `stream_voice_answer`, `_show_topics`, `_post_articles`, `_show_post` |
| 8 | `Sujet` | 2 | `propose_topics`, `fetch_trends` |
| 9 | `Post` | 2 | `draft_post`, `save_post_edit` |

## À faire

| Priorité | Fonctionnalité | Commit |
| --- | --- | --- |
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
| 5 | Sujets : proposition selon le persona, à partir des flux RSS et des newsletters retenues. |
| 6 | Tendances Twitter du thème. Si Twitter ne répond pas, les sujets partent quand même des articles. |
| 7 | Post : texte parlable de 2 à 3 minutes sur le sujet choisi. |
| 8 | Le texte modifié et enregistré est la seule version prévue pour la vidéo. |
