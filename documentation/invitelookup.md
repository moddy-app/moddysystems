Pour le **lookup d'invitations Discord**, voici comment ça fonctionne :

## **Système de requêtes**

Le lookup d'invitations utilise **uniquement des requêtes JavaScript côté client**, pas de requêtes serveur côté backend PHP :

### **Requête JavaScript directe vers Discord**
```javascript
function fetchInvite(inviteCode, eventId) {
    if (!inviteCode) return;
    $.ajax({
        type: 'GET',
        url: 'https://discord.com/api/v10/invites/' + inviteCode + 
             '?with_counts=true&with_expiration=true' + 
             ((eventId !== '' && eventId != null) ? '&guild_scheduled_event_id=' + eventId : ''),
        success: (respond) => Livewire.emit('processInviteJson', respond),
        error: () => Livewire.emit('processInviteJson', null),
    });
}
```

**Endpoint :** `GET /invites/{invite_code}`  
**Authentification :** **Aucune** (endpoint public)

**Paramètres URL :**
- `with_counts=true` : Inclut les compteurs de membres
- `with_expiration=true` : Inclut les infos d'expiration  
- `guild_scheduled_event_id={event_id}` : Pour les événements spécifiques

## **Types d'invitations supportées**

**1. Invitations de serveur normales :**
- Format : `discord.gg/CODE` ou `discordapp.com/invite/CODE`
- Exemple : `easypoll`, `minecraft`

**2. Vanity URLs :**
- URLs personnalisées des serveurs boostés
- Exemple : `discord.gg/discord` (serveur officiel Discord)

**3. Invitations avec événements :**
- Format : `discord.gg/CODE?event=EVENT_ID`
- Support des événements programmés du serveur

## **Données récupérées**

**Informations sur l'invitation :**
- Type d'invitation (`type`, `typeName`)
- Flags (`flags`) - ex: contourner les applications de rejoindre
- Date d'expiration (`expiresAt`, `expiresAtFormatted`)

**Informations sur le serveur :**
- Détails de base (nom, description, icône, bannière)
- Compteurs (membres totaux, membres en ligne)
- Features, niveau de boost, statut NSFW
- Vanity URL du serveur

**Informations sur l'événement (si présent) :**
- Nom, description, créateur
- Statut, dates de début/fin
- Type d'entité (VOICE, STAGE_INSTANCE, EXTERNAL)
- Localisation (pour les événements externes)

## **Enrichissement des données**

Après récupération de l'invitation, le système **enrichit** les données en appelant les APIs serveur :

```php
public function processInviteJson($json)
{
    $this->inviteData = parseInviteJson($json);
    if($this->inviteData)
    {
        $guildId = $this->inviteData['guild']['id'];
        if($guildId)
        {
            // Enrichissement avec Guild Widget API
            $guildWidget = getGuildWidget($guildId);
            
            // Enrichissement avec Guild Preview API  
            $guildPreview = getGuildPreview($guildId);
            
            // Fusion des données (priorité aux données de l'invitation)
        }
    }
}
```

## **Parsing avancé**

La fonction `parseInviteJson()` traite :

**Types d'invitations :**
- `0` : Guild
- `1` : Group DM
- `2` : Friend

**Flags des invitations :**
```php
// Exemple: Bypass Join Applications
if(($inviteData['flags'] & (1 << 3)) == (1 << 3)) {
    // Cette invitation contourne les applications de rejoindre
}
```

**Événements programmés :**
- Status (SCHEDULED, ACTIVE, COMPLETED, CANCELLED)
- Types d'entité (VOICE, STAGE, EXTERNAL)
- Métadonnées (localisation pour événements externes)

## **Avantages de cette approche**

**Côté client :**
- **Pas de rate limiting** serveur
- **Temps réel** - données toujours fraîches
- **Pas de cache** - informations instantanées

**Combine avec backend :**
- **Enrichissement** avec données supplémentaires du serveur
- **Parsing avancé** des types d'invitations et événements
- **Interface utilisateur** riche avec preview des membres connectés

Cette approche hybride (client + serveur) offre le **meilleur des deux mondes** : fraîcheur des données + enrichissement intelligent !
