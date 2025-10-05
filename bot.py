import discord
from discord.ext import commands
import os
import asyncio
import logging
from dotenv import load_dotenv
import aiohttp

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('ModdySystems')

# Charger les variables d'environnement
load_dotenv()


class ModdySystems(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(
            command_prefix='/',  # Slash uniquement - pas de préfixe textuel
            intents=intents,
            help_command=None,  # Désactiver la commande help par défaut
            case_insensitive=True,
            owner_ids=set(),  # Sera rempli avec les IDs de l'équipe
            enable_debug_events=True  # Pour debug les commandes slash
        )

        self.session = None
        self.team_members = set()  # IDs des membres de l'équipe de développement
        self.application_id = None

    async def setup_hook(self):
        """Hook appelé lors de l'initialisation du bot"""
        # Créer une session aiohttp pour les requêtes HTTP
        self.session = aiohttp.ClientSession()

        # Charger les informations de l'équipe de développement
        await self.load_team_members()

        # Charger tous les cogs
        await self.load_cogs()

        # Synchroniser les commandes slash si nécessaire
        try:
            synced = await self.tree.sync()
            logger.info(f"Synchronisé {len(synced)} commandes slash")
        except Exception as e:
            logger.error(f"Erreur lors de la synchronisation des commandes: {e}")

    async def load_team_members(self):
        """Charge les membres de l'équipe de développement depuis l'API Discord"""
        try:
            # Récupérer les informations de l'application
            app_info = await self.application_info()
            self.application_id = app_info.id

            # Si l'app a une équipe, récupérer les membres
            if app_info.team:
                for member in app_info.team.members:
                    self.team_members.add(member.id)
                    logger.info(f"Membre de l'équipe ajouté: {member.name} ({member.id})")
            else:
                # Si pas d'équipe, ajouter seulement l'owner
                self.team_members.add(app_info.owner.id)
                logger.info(f"Owner ajouté: {app_info.owner.name} ({app_info.owner.id})")

            # Mettre à jour les owner_ids pour les commandes
            self.owner_ids = self.team_members

        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'équipe: {e}")

    async def load_cogs(self):
        """Charge tous les cogs depuis le dossier cogs/"""
        cogs_dir = './cogs'

        # Créer le dossier cogs s'il n'existe pas
        if not os.path.exists(cogs_dir):
            os.makedirs(cogs_dir)
            logger.warning(f"Dossier '{cogs_dir}' créé car il n'existait pas")
            return

        # Charger chaque fichier .py dans le dossier cogs
        for filename in os.listdir(cogs_dir):
            if filename.endswith('.py') and not filename.startswith('_'):
                extension_name = f'cogs.{filename[:-3]}'
                try:
                    await self.load_extension(extension_name)
                    logger.info(f"Cog chargé: {extension_name}")
                except Exception as e:
                    logger.error(f"Échec du chargement de {extension_name}: {e}")

    async def on_ready(self):
        """Événement déclenché quand le bot est prêt"""
        logger.info(f"{'=' * 50}")
        logger.info(f"Bot connecté en tant que {self.user}")
        logger.info(f"ID: {self.user.id}")
        logger.info(f"Serveurs: {len(self.guilds)}")
        logger.info(f"Membres de l'équipe: {len(self.team_members)}")
        logger.info(f"{'=' * 50}")

        # Définir le statut du bot
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} serveurs"
            ),
            status=discord.Status.online
        )

    async def on_guild_join(self, guild):
        """Événement déclenché quand le bot rejoint un serveur"""
        logger.info(f"Bot ajouté au serveur: {guild.name} ({guild.id})")

        # Vérifier si l'owner fait partie de l'équipe de développement
        if guild.owner_id in self.team_members:
            logger.info(f"✅ L'owner {guild.owner} fait partie de l'équipe de développement")

            # Envoyer un message de bienvenue personnalisé si possible
            try:
                if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
                    embed = discord.Embed(
                        title="🎉 Moddy Systems - Équipe de Développement",
                        description=f"Salut {guild.owner.mention}! Ravi de voir un membre de l'équipe!\n\n"
                                    f"Le bot est maintenant opérationnel sur ce serveur.",
                        color=discord.Color.green()
                    )
                    embed.set_footer(text="Moddy Systems Support Bot")
                    await guild.system_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Impossible d'envoyer le message de bienvenue: {e}")
        else:
            logger.warning(f"⚠️ L'owner {guild.owner} ({guild.owner_id}) ne fait PAS partie de l'équipe")

            # Optionnel: Envoyer un message standard
            try:
                if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
                    embed = discord.Embed(
                        title="👋 Moddy Systems Support Bot",
                        description="Merci d'avoir ajouté Moddy Systems à votre serveur!\n\n"
                                    "Ce bot est conçu pour fournir un support complet.",
                        color=discord.Color.blue()
                    )
                    embed.set_footer(text="Moddy Systems Support Bot")
                    await guild.system_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Impossible d'envoyer le message de bienvenue: {e}")

        # Mettre à jour le statut
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} serveurs"
            )
        )

    async def on_guild_remove(self, guild):
        """Événement déclenché quand le bot est retiré d'un serveur"""
        logger.info(f"Bot retiré du serveur: {guild.name} ({guild.id})")

        # Mettre à jour le statut
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} serveurs"
            )
        )

    async def close(self):
        """Fermeture propre du bot"""
        if self.session:
            await self.session.close()
        await super().close()

    def is_team_member(self, user_id: int) -> bool:
        """Vérifie si un utilisateur fait partie de l'équipe de développement"""
        return user_id in self.team_members


async def main():
    """Fonction principale pour démarrer le bot"""
    bot = ModdySystems()

    # Récupérer le token depuis les variables d'environnement
    token = os.getenv('DISCORD_TOKEN')

    if not token:
        logger.error("TOKEN Discord non trouvé! Assurez-vous d'avoir un fichier .env avec DISCORD_TOKEN=votre_token")
        return

    try:
        await bot.start(token)
    except discord.LoginFailure:
        logger.error("Token invalide! Vérifiez votre token Discord.")
    except Exception as e:
        logger.error(f"Erreur lors du démarrage du bot: {e}")
    finally:
        await bot.close()


if __name__ == "__main__":
    # Lancer le bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot arrêté manuellement")
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")