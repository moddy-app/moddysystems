# Système de Tickets - Moddy Support

Ce document explique le fonctionnement du système de tickets pour le serveur support de Moddy.

## Vue d'ensemble

Le système de tickets utilise des **threads privés Discord** pour gérer les demandes de support. Tous les embeds sont créés avec les **Composants V2** de Discord.

## Salon de Support

- **ID du salon**: `1404123817365864528`
- Le panel de support est affiché dans ce salon
- Commande `!tickets` pour réafficher le panel si supprimé

## Catégories de Tickets

### 1. Support <:handshake:1448354754366537970>

**Mentions**: <@&1398616524964630662> + utilisateur

**Processus de création**:
1. L'utilisateur choisit si le support concerne:
   - **Serveur**: Demande le lien d'invitation du serveur
   - **Utilisateur**: Crée directement le ticket
   - **Autre chose**: Crée directement le ticket

**Permissions de gestion**:
- Support Agents
- Supervisors (tous)
- Managers

---

### 2. Bug Reports <:bug:1448354755868102726>

**Mentions**: <@&1406147173166354505> + utilisateur

**Processus de création**:
1. Demande si l'utilisateur a un code erreur
2. Si **oui**:
   - Modal pour entrer le code (format: `BB1FE07D` - 8 caractères)
   - Récupère le contexte depuis la DB Moddy (pas le traceback)
   - Affiche: commande, utilisateur, serveur, fichier source, type d'erreur, timestamp
3. Si **non**: Crée directement le ticket

**Permissions de gestion**:
- Devs
- Supervisors (tous)
- Managers

---

### 3. Sanction Appeals <:gavel:1448354751011094611>

**Mentions**: <@&1398618024390692884> + utilisateur

**Processus de création**:
1. L'utilisateur choisit:
   - **Serveur**: Demande le lien d'invitation
   - **Utilisateur (soi-même)**: Récupère les cases de l'utilisateur
2. Récupère toutes les **cases ouvertes** depuis la DB Moddy
3. Menu déroulant pour sélectionner la case
4. Affiche toutes les infos de la case dans le ticket:
   - Case ID
   - Type de case et type de sanction
   - Entité sanctionnée (utilisateur ou serveur)
   - Raison
   - Créée par et quand

**Permissions de gestion**:
- Moderators
- Supervisors (tous)
- Managers

---

### 4. Payments & Billing <:payments:1448354761769353288>

**Mentions**: <@&1398616117181812820> + <@&1398616551938330655> + utilisateur

**Processus de création**: Direct (pas de questions)

**Permissions de gestion**:
- Support Agents
- Supervisors (tous)
- Managers

---

### 5. Legal Requests <:balance:1448354749110816900>

**Mentions**: <@&1398616117181812820> + utilisateur

**Processus de création**:
Menu déroulant avec 4 types de demandes:

1. **Data Access** <:eyes:1448363673742610543>
   - Savoir exactement quelles données Moddy stocke

2. **Rectification** <:edit_square:1448363672358359070>
   - Demander la correction d'informations incorrectes

3. **Deletion / Right to be Forgotten** <:delete:1448363670349283449>
   - Demander la suppression complète des données

4. **Objection** <:block:1448364162592932004>
   - Refuser l'utilisation des données pour certains usages

**Permissions de gestion**:
- Managers
- Supervisors (tous)

---

### 6. Other Request <:question_mark:1448354747836006564>

**Mentions**: <@&1398616524964630662> + utilisateur

**Processus de création**: Direct (pas de questions)

**Permissions de gestion**:
- Tous les staffs Moddy
- Supervisors (tous)
- Managers

---

## Fonctionnalités des Tickets

### Boutons de Contrôle

Chaque ticket a 2 boutons:

#### <:front_hand:1448372509379657860> Claim / Unclaim

- **Claim**: Un staff prend en charge le ticket
- **Unclaim**: Le staff libère le ticket
- Seuls les staffs autorisés pour cette catégorie peuvent claim
- Seul le staff qui a claim, un Supervisor ou un Manager peut unclaim

#### <:archive:1448372506653233162> Archive

- Verrouille le thread (ne le supprime PAS)
- Seuls les staffs autorisés pour cette catégorie peuvent archiver
- Le ticket reste visible mais fermé

### Commande: `!archiverequest`

- **Usage**: Dans un thread de ticket
- **Permissions**: Staffs autorisés pour la catégorie
- **Effet**: Envoie un embed avec boutons Oui/Non pour demander à l'utilisateur s'il accepte l'archivage
- Seul l'utilisateur ayant créé le ticket peut répondre

### Structure des Embeds

#### Embed Principal
- Titre avec émoji de la catégorie
- Utilisateur qui a créé le ticket
- Boutons Claim et Archive

#### Embed d'Informations
- Toutes les infos collectées avant la création
- Données supplémentaires de la DB Moddy si applicable
- Format moderne avec Composants V2

---

## Bases de Données

### ModdySystems DB (`DATABASE_URL`)

Table `tickets`:
```sql
CREATE TABLE tickets (
    thread_id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    category VARCHAR(50) NOT NULL,
    claimed_by BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    archived BOOLEAN DEFAULT FALSE,
    archived_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb
)
```

### Moddy DB (`MODDYDB_URL`)

Utilisé pour:
- Récupérer les infos des codes erreur (`errors` table)
- Récupérer les cases de modération (`moderation_cases` table)
- Vérifier les permissions des staffs (`staff_permissions` table)

---

## Hiérarchie des Permissions

### Par Catégorie

| Catégorie | Rôles Autorisés |
|-----------|-----------------|
| Support | Support Agents |
| Bug Reports | Devs |
| Sanction Appeals | Moderators |
| Legal Requests | Managers |
| Payments & Billing | Support Agents |
| Other Request | Tous les staffs |

### Permissions Globales

**Managers** et **Supervisors** peuvent gérer **tous** les tickets, quelle que soit la catégorie.

---

## Émojis Utilisés

| Nom | Émoji | Usage |
|-----|-------|-------|
| Ticket | <:ticket:1448354813346844672> | Général |
| Done | <:done:1448372515503341568> | Succès |
| Undone | <:undone:1448372510621044970> | Erreur/Refus |
| Front Hand | <:front_hand:1448372509379657860> | Claim |
| Archive | <:archive:1448372506653233162> | Archive |
| Handshake | <:handshake:1448354754366537970> | Support |
| Bug | <:bug:1448354755868102726> | Bug Reports |
| Gavel | <:gavel:1448354751011094611> | Sanction Appeals |
| Payments | <:payments:1448354761769353288> | Payments & Billing |
| Balance | <:balance:1448354749110816900> | Legal Requests |
| Question Mark | <:question_mark:1448354747836006564> | Other Request |
| Eyes | <:eyes:1448363673742610543> | Data Access |
| Edit Square | <:edit_square:1448363672358359070> | Rectification |
| Delete | <:delete:1448363670349283449> | Deletion |
| Block | <:block:1448364162592932004> | Objection |

---

## Installation et Configuration

### 1. Variables d'environnement

Ajouter dans `.env`:
```env
MODDYDB_URL=postgresql://user:pass@host/moddy_db
DATABASE_URL=postgresql://user:pass@host/systems_db
```

### 2. Dépendances

```bash
pip install -r requirements.txt
```

### 3. Démarrage

Le cog se charge automatiquement au démarrage du bot et:
- Connecte aux deux bases de données
- Crée la table `tickets` si elle n'existe pas
- Prêt à recevoir les interactions

### 4. Afficher le Panel

Dans le salon de support (`1404123817365864528`), taper:
```
!tickets
```

---

## Notes Techniques

### Composants V2

Tous les embeds utilisent `ui.LayoutView` avec:
- `ui.Container()` pour structurer
- `ui.TextDisplay()` pour les titres
- `ui.Separator()` pour les espacements
- `ui.ActionRow()` pour les boutons/menus

### Threads Privés

Les tickets sont créés comme **threads privés** avec:
- Auto-archivage après 7 jours (10080 minutes)
- L'utilisateur est automatiquement ajouté au thread
- Les mentions alertent les staffs appropriés

### Lookup d'Invitations

Pour extraire l'ID d'un serveur depuis un lien d'invitation, le système utilise l'API Discord:
```
GET https://discord.com/api/v10/invites/{code}
```

Formats supportés:
- `discord.gg/abc123`
- `https://discord.com/invite/abc123`
- `discordapp.com/invite/abc123`
- Juste le code: `abc123`

---

## Maintenance

### Réafficher le Panel

Si le panel de support est supprimé, n'importe quel staff peut le réafficher avec `!tickets`.

### Archivage Manuel

Un staff peut utiliser `!archiverequest` pour demander poliment l'autorisation d'archiver à l'utilisateur.

### Tickets Bloqués

Si un ticket est claim par un staff absent, un Supervisor ou Manager peut le unclaim.

---

**Version**: 1.0
**Date**: 2025-12-10
**Auteur**: Claude (avec les spécifications de juthing)
