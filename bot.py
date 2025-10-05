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
        self.app_id = None  # ID de l'application (renommé)

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
            logger.info(f"Synced {len(synced)} slash commands")
        except Exception as e:
            logger.error(f"Error syncing commands: {e}")

    async def load_team_members(self):
        """Charge les membres de l'équipe de développement depuis l'API Discord"""
        try:
            # Récupérer les informations de l'application
            app_info = await self.application_info()
            self.app_id = app_info.id

            # Si l'app a une équipe, récupérer les membres
            if app_info.team:
                for member in app_info.team.members:
                    self.team_members.add(member.id)
                    logger.info(f"Team member added: {member.name} ({member.id})")
            else:
                # Si pas d'équipe, ajouter seulement l'owner
                self.team_members.add(app_info.owner.id)
                logger.info(f"Owner added: {app_info.owner.name} ({app_info.owner.id})")

            # Mettre à jour les owner_ids pour les commandes
            self.owner_ids = self.team_members

        except Exception as e:
            logger.error(f"Error loading team: {e}")

    async def load_cogs(self):
        """Charge tous les cogs depuis le dossier cogs/"""
        cogs_dir = './cogs'

        # Créer le dossier cogs s'il n'existe pas
        if not os.path.exists(cogs_dir):
            os.makedirs(cogs_dir)
            logger.warning(f"Created '{cogs_dir}' folder as it didn't exist")
            return

        # Charger chaque fichier .py dans le dossier cogs
        for filename in os.listdir(cogs_dir):
            if filename.endswith('.py') and not filename.startswith('_'):
                extension_name = f'cogs.{filename[:-3]}'
                try:
                    await self.load_extension(extension_name)
                    logger.info(f"Cog loaded: {extension_name}")
                except Exception as e:
                    logger.error(f"Failed to load {extension_name}: {e}")

    async def on_ready(self):
        """Événement déclenché quand le bot est prêt"""
        logger.info(f"{'=' * 50}")
        logger.info(f"Bot connected as {self.user}")
        logger.info(f"ID: {self.user.id}")
        logger.info(f"Servers: {len(self.guilds)}")
        logger.info(f"Team members: {len(self.team_members)}")
        logger.info(f"{'=' * 50}")

        # Définir le statut du bot depuis la variable d'environnement
        custom_status = os.getenv('STATUS')
        if custom_status:
            # Utiliser un Custom Activity pour du texte simple
            await self.change_presence(
                activity=discord.CustomActivity(name=custom_status),
                status=discord.Status.online
            )
            logger.info(f"Custom status set: {custom_status}")
        else:
            # Statut par défaut si STATUS n'est pas défini
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"{len(self.guilds)} servers"
                ),
                status=discord.Status.online
            )
            logger.info(f"Default status: Watching {len(self.guilds)} servers")

    async def on_guild_join(self, guild):
        """Événement déclenché quand le bot rejoint un serveur"""
        logger.info(f"Bot added to server: {guild.name} ({guild.id})")

        # Vérifier si l'owner fait partie de l'équipe de développement
        if guild.owner_id in self.team_members:
            logger.info(f"✅ Owner {guild.owner} is part of the development team")

            # Envoyer un message de bienvenue personnalisé si possible
            try:
                if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
                    embed = discord.Embed(
                        title="🎉 Moddy Systems - Development Team",
                        description=f"Hey {guild.owner.mention}! Nice to see a team member!\n\n"
                                    f"The bot is now operational on this server.",
                        color=discord.Color.green()
                    )
                    embed.set_footer(text="Moddy Systems Support Bot")
                    await guild.system_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Unable to send welcome message: {e}")
        else:
            logger.warning(f"⚠️ Owner {guild.owner} ({guild.owner_id}) is NOT part of the team")

            # Optionnel: Envoyer un message standard
            try:
                if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
                    embed = discord.Embed(
                        title="👋 Moddy Systems Support Bot",
                        description="Thanks for adding Moddy Systems to your server!\n\n"
                                    "This bot is designed to provide comprehensive support.",
                        color=discord.Color.blue()
                    )
                    embed.set_footer(text="Moddy Systems Support Bot")
                    await guild.system_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Unable to send welcome message: {e}")

        # Mettre à jour le statut seulement si STATUS n'est pas défini
        if not os.getenv('STATUS'):
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"{len(self.guilds)} servers"
                )
            )

    async def on_guild_remove(self, guild):
        """Événement déclenché quand le bot est retiré d'un serveur"""
        logger.info(f"Bot removed from server: {guild.name} ({guild.id})")

        # Mettre à jour le statut seulement si STATUS n'est pas défini
        if not os.getenv('STATUS'):
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"{len(self.guilds)} servers"
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
        logger.error("Discord TOKEN not found! Make sure you have a .env file with DISCORD_TOKEN=your_token")
        return

    try:
        await bot.start(token)
    except discord.LoginFailure:
        logger.error("Invalid token! Check your Discord token.")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
    finally:
        await bot.close()


if __name__ == "__main__":
    # Lancer le bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually")
    except Exception as e:
        logger.error(f"Fatal error: {e}")