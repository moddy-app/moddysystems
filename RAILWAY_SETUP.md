# Configuration Railway pour Moddy Systems

Ce guide explique comment configurer les variables d'environnement sur Railway pour le bot Moddy Systems.

## Variables d'environnement requises

### 1. DISCORD_TOKEN (Requis)
Le token de votre bot Discord.

**Comment l'obtenir:**
1. Allez sur https://discord.com/developers/applications
2. Sélectionnez votre application
3. Allez dans "Bot"
4. Cliquez sur "Reset Token" ou copiez le token existant

**Sur Railway:**
```
DISCORD_TOKEN=votre_token_ici
```

### 2. STATUS (Optionnel)
Le statut personnalisé du bot.

**Exemple:**
```
STATUS=Private app
```

Si non défini, le bot affichera "Watching X servers".

### 3. MODDYDB_URL (Requis pour le système de tickets)
URL de connexion à la base de données PostgreSQL de Moddy.

**Format:**
```
postgresql://username:password@host:port/database
```

**Exemple Railway:**
```
MODDYDB_URL=postgresql://postgres:mdp@containers-us-west-123.railway.app:5432/railway
```

**Ce qui ne fonctionnera pas sans cette variable:**
- Récupération des codes erreur (Bug Reports)
- Récupération des cases de modération (Sanction Appeals)
- Vérification des permissions staff (tous les tickets)

### 4. DATABASE_URL (Requis pour le système de tickets)
URL de connexion à la base de données PostgreSQL de ModdySystems (la DB du bot de support).

**Format:**
```
postgresql://username:password@host:port/database
```

**Exemple Railway:**
```
DATABASE_URL=postgresql://postgres:mdp@containers-us-west-456.railway.app:5432/railway
```

**Ce qui ne fonctionnera pas sans cette variable:**
- Sauvegarde des tickets
- Système de claim/unclaim
- Historique des tickets

---

## Configuration sur Railway

### Option 1: Via l'interface web

1. Allez sur votre projet Railway
2. Cliquez sur votre service (ModdySystems)
3. Allez dans l'onglet "Variables"
4. Cliquez sur "New Variable"
5. Ajoutez chaque variable une par une:
   - `DISCORD_TOKEN`
   - `STATUS`
   - `MODDYDB_URL`
   - `DATABASE_URL`

### Option 2: Via Railway CLI

```bash
# Installer Railway CLI
npm i -g @railway/cli

# Se connecter
railway login

# Lier au projet
railway link

# Ajouter les variables
railway variables set DISCORD_TOKEN="votre_token"
railway variables set STATUS="Private app"
railway variables set MODDYDB_URL="postgresql://..."
railway variables set DATABASE_URL="postgresql://..."
```

---

## Création des bases de données sur Railway

### Pour MODDYDB_URL (Base de données Moddy)

Si vous avez déjà le bot Moddy déployé sur Railway:

1. Allez sur le projet du bot Moddy
2. Notez l'URL de connexion PostgreSQL dans les variables
3. Utilisez cette même URL pour `MODDYDB_URL`

### Pour DATABASE_URL (Base de données ModdySystems)

Créez une nouvelle base de données PostgreSQL:

1. Dans votre projet Railway
2. Cliquez sur "+ New"
3. Sélectionnez "Database" → "PostgreSQL"
4. Railway générera automatiquement une variable `DATABASE_URL`
5. Cette variable sera automatiquement disponible pour votre bot

**Note:** Railway peut créer automatiquement `DATABASE_URL` quand vous ajoutez PostgreSQL à votre projet.

---

## Vérification de la configuration

Une fois les variables configurées, redéployez votre bot. Vous devriez voir dans les logs:

```
✅ Connected to Moddy database
✅ Connected to ModdySystems database
✅ Tickets table ready
```

### Si vous voyez des warnings:

**Warning: MODDYDB_URL not set**
```
⚠️ MODDYDB_URL not set - Moddy database features will be disabled
   (Error codes, moderation cases, and staff permissions won't work)
```
→ Ajoutez la variable `MODDYDB_URL`

**Warning: DATABASE_URL not set**
```
⚠️ DATABASE_URL not set - Ticket system database will be disabled
   (Tickets won't be saved to database)
```
→ Ajoutez une base de données PostgreSQL au projet Railway

---

## Structure des bases de données

### Moddy DB (MODDYDB_URL)
Cette base contient:
- `errors` - Codes d'erreur du bot Moddy
- `moderation_cases` - Cases de modération
- `staff_permissions` - Permissions des staffs
- `users` - Données utilisateurs
- `guilds` - Données serveurs

**Note:** Cette base est partagée avec le bot Moddy principal.

### ModdySystems DB (DATABASE_URL)
Cette base contient:
- `tickets` - Tickets créés par le système

**Note:** La table `tickets` sera créée automatiquement au démarrage du bot.

---

## Dépannage

### Le bot ne se connecte pas
- Vérifiez que `DISCORD_TOKEN` est correct
- Vérifiez les logs Railway pour voir l'erreur exacte

### Les tickets ne fonctionnent pas
- Vérifiez que `DATABASE_URL` est définie
- Vérifiez les logs pour voir `✅ Connected to ModdySystems database`

### Les codes erreur ne fonctionnent pas
- Vérifiez que `MODDYDB_URL` est définie
- Vérifiez que vous avez accès à la base de données Moddy
- Vérifiez les logs pour voir `✅ Connected to Moddy database`

### Les permissions staff ne fonctionnent pas
- Vérifiez que `MODDYDB_URL` est définie
- Vérifiez que la table `staff_permissions` existe dans la DB Moddy
- Utilisez la commande SQL pour vérifier:
  ```sql
  SELECT * FROM staff_permissions WHERE user_id = VOTRE_USER_ID;
  ```

---

## Support

Pour plus d'informations:
- **Documentation Railway**: https://docs.railway.app/
- **Documentation du système de tickets**: `documentation/TICKETS.md`
- **Documentation de la DB Moddy**: `documentation/MODDY_DATABASE.md`

---

**Version:** 1.0
**Date:** 2025-12-10
