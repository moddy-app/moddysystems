import discord
from discord.ext import commands
from discord import ui
import asyncpg
import os
import re
import logging
from typing import Optional, Dict, List
import aiohttp

logger = logging.getLogger('ModdySystems.Tickets')

# IDs des rôles staff
ROLES = {
    'SUPPORT_AGENT': 1398616524964630662,
    'DEV': 1406147173166354505,
    'MODERATOR': 1398618024390692884,
    'MANAGER': 1398616117181812820,
    'SUPERVISOR': 1398616551938330655,
}

# ID du salon de support
SUPPORT_CHANNEL_ID = 1404123817365864528

# Émojis personnalisés
EMOJIS = {
    'handshake': '<:handshake:1448354754366537970>',
    'bug': '<:bug:1448354755868102726>',
    'gavel': '<:gavel:1448354751011094611>',
    'payments': '<:payments:1448354761769353288>',
    'balance': '<:balance:1448354749110816900>',
    'question_mark': '<:question_mark:1448354747836006564>',
    'ticket': '<:ticket:1448354813346844672>',
    'done': '<:done:1448372515503341568>',
    'undone': '<:undone:1448372510621044970>',
    'front_hand': '<:front_hand:1448372509379657860>',
    'archive': '<:archive:1448372506653233162>',
    'eyes': '<:eyes:1448363673742610543>',
    'edit_square': '<:edit_square:1448363672358359070>',
    'delete': '<:delete:1448363670349283449>',
    'block': '<:block:1448364162592932004>',
}


class TicketDatabase:
    """Gère les connexions aux bases de données"""

    def __init__(self):
        self.moddy_pool: Optional[asyncpg.Pool] = None
        self.systems_pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Connecte aux deux bases de données"""
        try:
            # Connexion à la DB de Moddy
            moddy_url = os.getenv('MODDYDB_URL')
            if moddy_url:
                self.moddy_pool = await asyncpg.create_pool(
                    moddy_url,
                    min_size=2,
                    max_size=10
                )
                logger.info("✅ Connected to Moddy database")

            # Connexion à la DB de ModdySystems
            systems_url = os.getenv('DATABASE_URL')
            if systems_url:
                self.systems_pool = await asyncpg.create_pool(
                    systems_url,
                    min_size=2,
                    max_size=10
                )
                logger.info("✅ Connected to ModdySystems database")

                # Créer la table tickets si elle n'existe pas
                async with self.systems_pool.acquire() as conn:
                    await conn.execute('''
                        CREATE TABLE IF NOT EXISTS tickets (
                            thread_id BIGINT PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            category VARCHAR(50) NOT NULL,
                            claimed_by BIGINT,
                            created_at TIMESTAMPTZ DEFAULT NOW(),
                            archived BOOLEAN DEFAULT FALSE,
                            archived_at TIMESTAMPTZ,
                            metadata JSONB DEFAULT '{}'::jsonb
                        )
                    ''')
                    logger.info("✅ Tickets table ready")

        except Exception as e:
            logger.error(f"❌ Database connection error: {e}")

    async def close(self):
        """Ferme les connexions aux bases de données"""
        if self.moddy_pool:
            await self.moddy_pool.close()
        if self.systems_pool:
            await self.systems_pool.close()

    async def get_error_info(self, error_code: str) -> Optional[Dict]:
        """Récupère les infos d'une erreur depuis la DB Moddy"""
        if not self.moddy_pool:
            return None

        try:
            async with self.moddy_pool.acquire() as conn:
                error = await conn.fetchrow(
                    "SELECT * FROM errors WHERE error_code = $1",
                    error_code.upper()
                )

                if error:
                    return dict(error)
                return None
        except Exception as e:
            logger.error(f"Error fetching error info: {e}")
            return None

    async def get_user_cases(self, user_id: int) -> List[Dict]:
        """Récupère les cases ouvertes d'un utilisateur"""
        if not self.moddy_pool:
            return []

        try:
            async with self.moddy_pool.acquire() as conn:
                cases = await conn.fetch(
                    """
                    SELECT * FROM moderation_cases
                    WHERE entity_type = 'user'
                    AND entity_id = $1
                    AND status = 'open'
                    ORDER BY created_at DESC
                    """,
                    user_id
                )
                return [dict(case) for case in cases]
        except Exception as e:
            logger.error(f"Error fetching user cases: {e}")
            return []

    async def get_guild_cases(self, guild_id: int) -> List[Dict]:
        """Récupère les cases ouvertes d'un serveur"""
        if not self.moddy_pool:
            return []

        try:
            async with self.moddy_pool.acquire() as conn:
                cases = await conn.fetch(
                    """
                    SELECT * FROM moderation_cases
                    WHERE entity_type = 'guild'
                    AND entity_id = $1
                    AND status = 'open'
                    ORDER BY created_at DESC
                    """,
                    guild_id
                )
                return [dict(case) for case in cases]
        except Exception as e:
            logger.error(f"Error fetching guild cases: {e}")
            return []

    async def get_staff_info(self, user_id: int) -> Optional[Dict]:
        """Récupère les infos d'un staff depuis la DB Moddy"""
        if not self.moddy_pool:
            return None

        try:
            async with self.moddy_pool.acquire() as conn:
                staff = await conn.fetchrow(
                    "SELECT * FROM staff_permissions WHERE user_id = $1",
                    user_id
                )

                if staff:
                    return dict(staff)
                return None
        except Exception as e:
            logger.error(f"Error fetching staff info: {e}")
            return None

    async def create_ticket(self, thread_id: int, user_id: int, category: str, metadata: Dict = None):
        """Crée un ticket dans la DB"""
        if not self.systems_pool:
            return

        try:
            async with self.systems_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO tickets (thread_id, user_id, category, metadata)
                    VALUES ($1, $2, $3, $4)
                    """,
                    thread_id, user_id, category, metadata or {}
                )
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")

    async def get_ticket(self, thread_id: int) -> Optional[Dict]:
        """Récupère un ticket depuis la DB"""
        if not self.systems_pool:
            return None

        try:
            async with self.systems_pool.acquire() as conn:
                ticket = await conn.fetchrow(
                    "SELECT * FROM tickets WHERE thread_id = $1",
                    thread_id
                )

                if ticket:
                    return dict(ticket)
                return None
        except Exception as e:
            logger.error(f"Error fetching ticket: {e}")
            return None

    async def claim_ticket(self, thread_id: int, user_id: int):
        """Claim un ticket"""
        if not self.systems_pool:
            return

        try:
            async with self.systems_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE tickets SET claimed_by = $1 WHERE thread_id = $2",
                    user_id, thread_id
                )
        except Exception as e:
            logger.error(f"Error claiming ticket: {e}")

    async def unclaim_ticket(self, thread_id: int):
        """Unclaim un ticket"""
        if not self.systems_pool:
            return

        try:
            async with self.systems_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE tickets SET claimed_by = NULL WHERE thread_id = $1",
                    thread_id
                )
        except Exception as e:
            logger.error(f"Error unclaiming ticket: {e}")

    async def archive_ticket(self, thread_id: int):
        """Archive un ticket"""
        if not self.systems_pool:
            return

        try:
            async with self.systems_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE tickets SET archived = TRUE, archived_at = NOW() WHERE thread_id = $1",
                    thread_id
                )
        except Exception as e:
            logger.error(f"Error archiving ticket: {e}")


# Instance globale de la database
db = TicketDatabase()


# Fonctions utilitaires
async def get_guild_id_from_invite(invite_url: str) -> Optional[int]:
    """Extrait l'ID du serveur depuis un lien d'invitation"""
    # Extraire le code d'invitation
    invite_code = invite_url.strip()

    # Patterns pour les liens Discord
    patterns = [
        r'discord\.gg/([a-zA-Z0-9-]+)',
        r'discord\.com/invite/([a-zA-Z0-9-]+)',
        r'discordapp\.com/invite/([a-zA-Z0-9-]+)',
    ]

    code = None
    for pattern in patterns:
        match = re.search(pattern, invite_code)
        if match:
            code = match.group(1)
            break

    if not code:
        # Si c'est juste le code
        code = invite_code

    try:
        # Utiliser l'API Discord pour récupérer les infos de l'invitation
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://discord.com/api/v10/invites/{code}') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if 'guild' in data and 'id' in data['guild']:
                        return int(data['guild']['id'])
    except Exception as e:
        logger.error(f"Error fetching invite info: {e}")

    return None


def get_staff_roles(staff_info: Optional[Dict]) -> List[str]:
    """Extrait les rôles d'un staff depuis ses infos"""
    if not staff_info or 'roles' not in staff_info:
        return []

    roles = staff_info['roles']
    if isinstance(roles, list):
        return roles
    return []


def can_manage_ticket(staff_roles: List[str], category: str) -> bool:
    """Vérifie si un staff peut gérer un ticket d'une catégorie donnée"""
    # Manager et Supervisor peuvent tout gérer
    if 'Manager' in staff_roles or 'Supervisor_Mod' in staff_roles or 'Supervisor_Com' in staff_roles or 'Supervisor_Sup' in staff_roles:
        return True

    # Permissions par catégorie
    permissions = {
        'support': ['Support'],
        'bug_report': ['Dev'],
        'sanction_appeal': ['Moderator'],
        'legal_request': ['Manager'],
        'payments_billing': ['Support'],
        'other_request': ['Support', 'Communication', 'Moderator', 'Dev'],
    }

    if category in permissions:
        for role in staff_roles:
            if role in permissions[category]:
                return True

    return False


# Modals
class ErrorCodeModal(ui.Modal, title="Code Erreur"):
    """Modal pour entrer un code erreur"""

    error_code = ui.TextInput(
        label="Code Erreur",
        placeholder="Ex: BB1FE07D",
        min_length=8,
        max_length=8,
        required=True
    )

    def __init__(self, callback_func):
        super().__init__()
        self.callback_func = callback_func

    async def on_submit(self, interaction: discord.Interaction):
        code = self.error_code.value.upper().strip()

        # Vérifier le format
        if not re.match(r'^[A-Z0-9]{8}$', code):
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Le code erreur doit contenir exactement 8 caractères (lettres majuscules ou chiffres).",
                ephemeral=True
            )
            return

        await self.callback_func(interaction, code)


class ServerInviteModal(ui.Modal, title="Lien d'invitation du serveur"):
    """Modal pour entrer un lien d'invitation Discord"""

    invite_link = ui.TextInput(
        label="Lien d'invitation",
        placeholder="Ex: discord.gg/abc123 ou https://discord.gg/abc123",
        required=True
    )

    def __init__(self, callback_func):
        super().__init__()
        self.callback_func = callback_func

    async def on_submit(self, interaction: discord.Interaction):
        invite = self.invite_link.value.strip()
        await self.callback_func(interaction, invite)


# Views pour les différentes étapes
class SupportTypeView(ui.LayoutView):
    """Vue pour choisir le type de support (serveur/utilisateur/autre)"""

    def __init__(self, user: discord.User):
        super().__init__(timeout=300)
        self.user = user
        self.selected_type = None

        container = ui.Container()
        container.add_item(ui.TextDisplay(
            f"**{EMOJIS['ticket']} Création de ticket - Support**\n"
            "-# Veuillez sélectionner le type de support dont vous avez besoin"
        ))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        # Boutons
        button_row = ui.ActionRow()

        @button_row.button(label="Serveur", style=discord.ButtonStyle.primary)
        async def server_button(interaction: discord.Interaction, button: ui.Button):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(
                    f"{EMOJIS['undone']} Seul l'utilisateur ayant initié cette action peut répondre.",
                    ephemeral=True
                )
                return

            self.selected_type = "server"
            # Demander le lien d'invitation
            modal = ServerInviteModal(self.on_server_invite_submit)
            await interaction.response.send_modal(modal)

        @button_row.button(label="Utilisateur", style=discord.ButtonStyle.primary)
        async def user_button(interaction: discord.Interaction, button: ui.Button):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(
                    f"{EMOJIS['undone']} Seul l'utilisateur ayant initié cette action peut répondre.",
                    ephemeral=True
                )
                return

            self.selected_type = "user"
            await self.create_ticket(interaction, {"type": "user"})

        @button_row.button(label="Autre", style=discord.ButtonStyle.primary)
        async def other_button(interaction: discord.Interaction, button: ui.Button):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(
                    f"{EMOJIS['undone']} Seul l'utilisateur ayant initié cette action peut répondre.",
                    ephemeral=True
                )
                return

            self.selected_type = "other"
            await self.create_ticket(interaction, {"type": "other"})

        container.add_item(button_row)
        self.add_item(container)

    async def on_server_invite_submit(self, interaction: discord.Interaction, invite: str):
        """Callback quand l'utilisateur soumet le lien d'invitation"""
        await interaction.response.defer(ephemeral=True)

        # Extraire l'ID du serveur
        guild_id = await get_guild_id_from_invite(invite)

        if not guild_id:
            await interaction.followup.send(
                f"{EMOJIS['undone']} Impossible de récupérer les informations du serveur. Vérifiez le lien d'invitation.",
                ephemeral=True
            )
            return

        await self.create_ticket(interaction, {
            "type": "server",
            "guild_id": guild_id,
            "invite_link": invite
        })

    async def create_ticket(self, interaction: discord.Interaction, metadata: Dict):
        """Crée le ticket de support"""
        await create_support_ticket(interaction, self.user, metadata)


class BugReportHasCodeView(ui.LayoutView):
    """Vue pour demander si l'utilisateur a un code erreur"""

    def __init__(self, user: discord.User):
        super().__init__(timeout=300)
        self.user = user

        container = ui.Container()
        container.add_item(ui.TextDisplay(
            f"**{EMOJIS['ticket']} Création de ticket - Bug Report**\n"
            "-# Avez-vous un code erreur à fournir ?"
        ))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        # Boutons
        button_row = ui.ActionRow()

        @button_row.button(label="Oui, j'ai un code erreur", style=discord.ButtonStyle.primary)
        async def yes_button(interaction: discord.Interaction, button: ui.Button):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(
                    f"{EMOJIS['undone']} Seul l'utilisateur ayant initié cette action peut répondre.",
                    ephemeral=True
                )
                return

            # Afficher le modal pour entrer le code
            modal = ErrorCodeModal(self.on_error_code_submit)
            await interaction.response.send_modal(modal)

        @button_row.button(label="Non, je n'ai pas de code", style=discord.ButtonStyle.secondary)
        async def no_button(interaction: discord.Interaction, button: ui.Button):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(
                    f"{EMOJIS['undone']} Seul l'utilisateur ayant initié cette action peut répondre.",
                    ephemeral=True
                )
                return

            await self.create_ticket(interaction, {})

        container.add_item(button_row)
        self.add_item(container)

    async def on_error_code_submit(self, interaction: discord.Interaction, error_code: str):
        """Callback quand l'utilisateur soumet un code erreur"""
        await interaction.response.defer(ephemeral=True)

        # Récupérer les infos de l'erreur
        error_info = await db.get_error_info(error_code)

        if not error_info:
            await interaction.followup.send(
                f"{EMOJIS['undone']} Code erreur introuvable dans la base de données.",
                ephemeral=True
            )
            return

        await self.create_ticket(interaction, {
            "error_code": error_code,
            "error_info": error_info
        })

    async def create_ticket(self, interaction: discord.Interaction, metadata: Dict):
        """Crée le ticket de bug report"""
        await create_bug_report_ticket(interaction, self.user, metadata)


class SanctionAppealTypeView(ui.LayoutView):
    """Vue pour choisir le type de sanction appeal (serveur/utilisateur)"""

    def __init__(self, user: discord.User):
        super().__init__(timeout=300)
        self.user = user

        container = ui.Container()
        container.add_item(ui.TextDisplay(
            f"**{EMOJIS['ticket']} Création de ticket - Sanction Appeal**\n"
            "-# Souhaitez-vous faire appel d'une sanction concernant un serveur ou vous-même ?"
        ))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        # Boutons
        button_row = ui.ActionRow()

        @button_row.button(label="Serveur", style=discord.ButtonStyle.primary)
        async def server_button(interaction: discord.Interaction, button: ui.Button):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(
                    f"{EMOJIS['undone']} Seul l'utilisateur ayant initié cette action peut répondre.",
                    ephemeral=True
                )
                return

            # Demander le lien d'invitation
            modal = ServerInviteModal(self.on_server_invite_submit)
            await interaction.response.send_modal(modal)

        @button_row.button(label="Moi-même (utilisateur)", style=discord.ButtonStyle.primary)
        async def user_button(interaction: discord.Interaction, button: ui.Button):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(
                    f"{EMOJIS['undone']} Seul l'utilisateur ayant initié cette action peut répondre.",
                    ephemeral=True
                )
                return

            await interaction.response.defer(ephemeral=True)

            # Récupérer les cases de l'utilisateur
            cases = await db.get_user_cases(self.user.id)

            if not cases:
                await interaction.followup.send(
                    f"{EMOJIS['undone']} Vous n'avez aucune case ouverte.",
                    ephemeral=True
                )
                return

            # Afficher le menu déroulant des cases
            view = CaseSelectView(self.user, cases, "user")
            await interaction.followup.send(
                f"{EMOJIS['ticket']} **Sélection de la case**\nVeuillez sélectionner la case pour laquelle vous souhaitez faire appel :",
                view=view,
                ephemeral=True
            )

        container.add_item(button_row)
        self.add_item(container)

    async def on_server_invite_submit(self, interaction: discord.Interaction, invite: str):
        """Callback quand l'utilisateur soumet le lien d'invitation"""
        await interaction.response.defer(ephemeral=True)

        # Extraire l'ID du serveur
        guild_id = await get_guild_id_from_invite(invite)

        if not guild_id:
            await interaction.followup.send(
                f"{EMOJIS['undone']} Impossible de récupérer les informations du serveur. Vérifiez le lien d'invitation.",
                ephemeral=True
            )
            return

        # Récupérer les cases du serveur
        cases = await db.get_guild_cases(guild_id)

        if not cases:
            await interaction.followup.send(
                f"{EMOJIS['undone']} Ce serveur n'a aucune case ouverte.",
                ephemeral=True
            )
            return

        # Afficher le menu déroulant des cases
        view = CaseSelectView(self.user, cases, "server", invite_link=invite)
        await interaction.followup.send(
            f"{EMOJIS['ticket']} **Sélection de la case**\nVeuillez sélectionner la case pour laquelle vous souhaitez faire appel :",
            view=view,
            ephemeral=True
        )


class CaseSelectView(ui.LayoutView):
    """Vue avec menu déroulant pour sélectionner une case"""

    def __init__(self, user: discord.User, cases: List[Dict], entity_type: str, invite_link: str = None):
        super().__init__(timeout=300)
        self.user = user
        self.cases = cases
        self.entity_type = entity_type
        self.invite_link = invite_link

        container = ui.Container()
        container.add_item(ui.TextDisplay(
            f"**{EMOJIS['gavel']} Sélection de la case**\n"
            f"-# {len(cases)} case(s) ouverte(s) trouvée(s)"
        ))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        # Menu déroulant
        select_row = ui.ActionRow()
        case_select = ui.Select(
            placeholder="Sélectionnez une case...",
            options=[
                discord.SelectOption(
                    label=f"Case {case['case_id']} - {case['sanction_type']}",
                    description=f"{case['reason'][:100] if case['reason'] else 'Pas de raison'}",
                    value=case['case_id']
                )
                for case in cases[:25]  # Max 25 options
            ]
        )
        case_select.callback = self.on_case_select
        select_row.add_item(case_select)
        container.add_item(select_row)

        self.add_item(container)

    async def on_case_select(self, interaction: discord.Interaction):
        """Callback quand une case est sélectionnée"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Seul l'utilisateur ayant initié cette action peut répondre.",
                ephemeral=True
            )
            return

        case_id = interaction.data['values'][0]

        # Trouver la case sélectionnée
        selected_case = None
        for case in self.cases:
            if case['case_id'] == case_id:
                selected_case = case
                break

        if not selected_case:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Erreur lors de la récupération de la case.",
                ephemeral=True
            )
            return

        # Créer le ticket
        metadata = {
            "case_id": case_id,
            "case_info": selected_case,
            "entity_type": self.entity_type
        }

        if self.invite_link:
            metadata["invite_link"] = self.invite_link

        await create_sanction_appeal_ticket(interaction, self.user, metadata)


class LegalRequestTypeView(ui.LayoutView):
    """Vue pour choisir le type de demande légale"""

    def __init__(self, user: discord.User):
        super().__init__(timeout=300)
        self.user = user

        container = ui.Container()
        container.add_item(ui.TextDisplay(
            f"**{EMOJIS['ticket']} Création de ticket - Legal Request**\n"
            "-# Veuillez sélectionner le type de demande légale"
        ))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        # Menu déroulant
        select_row = ui.ActionRow()
        legal_select = ui.Select(
            placeholder="Sélectionnez un type de demande...",
            options=[
                discord.SelectOption(
                    label="Data Access",
                    description="Know exactly what data Moddy stores about you (ID, logs, settings, etc.) and why.",
                    value="data_access",
                    emoji=EMOJIS['eyes']
                ),
                discord.SelectOption(
                    label="Rectification",
                    description="Request the correction of any incorrect information.",
                    value="rectification",
                    emoji=EMOJIS['edit_square']
                ),
                discord.SelectOption(
                    label="Deletion / Right to be Forgotten",
                    description="Request that all your data be permanently deleted from Moddy's database.",
                    value="deletion",
                    emoji=EMOJIS['delete']
                ),
                discord.SelectOption(
                    label="Objection",
                    description="Refuse the use of your data for certain purposes (e.g., analytics, statistics).",
                    value="objection",
                    emoji=EMOJIS['block']
                ),
            ]
        )
        legal_select.callback = self.on_legal_type_select
        select_row.add_item(legal_select)
        container.add_item(select_row)

        self.add_item(container)

    async def on_legal_type_select(self, interaction: discord.Interaction):
        """Callback quand un type de demande légale est sélectionné"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Seul l'utilisateur ayant initié cette action peut répondre.",
                ephemeral=True
            )
            return

        legal_type = interaction.data['values'][0]

        # Créer le ticket
        metadata = {
            "legal_type": legal_type
        }
        await create_legal_request_ticket(interaction, self.user, metadata)


class SupportPanelView(ui.LayoutView):
    """Vue principale du panel de support"""

    def __init__(self):
        super().__init__(timeout=None)  # Pas de timeout pour le panel principal

        container = ui.Container()
        container.add_item(ui.TextDisplay(
            f"**{EMOJIS['ticket']} Moddy Support Panel**\n"
            "Please select the category that matches your request below.\n"
            "Our team will get back to you as soon as possible."
        ))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        # Ligne 1: Support, Bug Reports
        row1 = ui.ActionRow()

        @row1.button(label="Support", style=discord.ButtonStyle.primary, emoji=EMOJIS['handshake'], custom_id="ticket:support")
        async def support_button(interaction: discord.Interaction, button: ui.Button):
            # Afficher la vue pour choisir le type de support
            view = SupportTypeView(interaction.user)
            await interaction.response.send_message(
                f"{EMOJIS['ticket']} **Création de ticket - Support**",
                view=view,
                ephemeral=True
            )

        @row1.button(label="Bug Reports", style=discord.ButtonStyle.primary, emoji=EMOJIS['bug'], custom_id="ticket:bug_report")
        async def bug_report_button(interaction: discord.Interaction, button: ui.Button):
            # Afficher la vue pour demander le code erreur
            view = BugReportHasCodeView(interaction.user)
            await interaction.response.send_message(
                f"{EMOJIS['ticket']} **Création de ticket - Bug Report**",
                view=view,
                ephemeral=True
            )

        container.add_item(row1)

        # Ligne 2: Sanction Appeals, Payments & Billing
        row2 = ui.ActionRow()

        @row2.button(label="Sanction Appeals", style=discord.ButtonStyle.primary, emoji=EMOJIS['gavel'], custom_id="ticket:sanction_appeal")
        async def sanction_appeal_button(interaction: discord.Interaction, button: ui.Button):
            # Afficher la vue pour choisir serveur/utilisateur
            view = SanctionAppealTypeView(interaction.user)
            await interaction.response.send_message(
                f"{EMOJIS['ticket']} **Création de ticket - Sanction Appeal**",
                view=view,
                ephemeral=True
            )

        @row2.button(label="Payments & Billing", style=discord.ButtonStyle.primary, emoji=EMOJIS['payments'], custom_id="ticket:payments_billing")
        async def payments_billing_button(interaction: discord.Interaction, button: ui.Button):
            # Créer directement le ticket
            await create_payments_billing_ticket(interaction, interaction.user, {})

        container.add_item(row2)

        # Ligne 3: Legal Requests, Other Request
        row3 = ui.ActionRow()

        @row3.button(label="Legal Requests", style=discord.ButtonStyle.primary, emoji=EMOJIS['balance'], custom_id="ticket:legal_request")
        async def legal_request_button(interaction: discord.Interaction, button: ui.Button):
            # Afficher le menu déroulant pour choisir le type de demande
            view = LegalRequestTypeView(interaction.user)
            await interaction.response.send_message(
                f"{EMOJIS['ticket']} **Création de ticket - Legal Request**",
                view=view,
                ephemeral=True
            )

        @row3.button(label="Other Request", style=discord.ButtonStyle.primary, emoji=EMOJIS['question_mark'], custom_id="ticket:other_request")
        async def other_request_button(interaction: discord.Interaction, button: ui.Button):
            # Créer directement le ticket
            await create_other_request_ticket(interaction, interaction.user, {})

        container.add_item(row3)

        self.add_item(container)


class TicketControlView(ui.LayoutView):
    """Vue avec les boutons Claim et Archive pour les tickets"""

    def __init__(self, thread_id: int, category: str, is_claimed: bool = False):
        super().__init__(timeout=None)
        self.thread_id = thread_id
        self.category = category

        # Boutons Claim et Archive
        button_row = ui.ActionRow()

        @button_row.button(
            label="Unclaim" if is_claimed else "Claim",
            style=discord.ButtonStyle.primary,
            emoji=EMOJIS['front_hand'],
            custom_id=f"ticket:claim:{thread_id}"
        )
        async def claim_button(interaction: discord.Interaction, button: ui.Button):
            await self.handle_claim(interaction)

        @button_row.button(
            label="Archive",
            style=discord.ButtonStyle.secondary,
            emoji=EMOJIS['archive'],
            custom_id=f"ticket:archive:{thread_id}"
        )
        async def archive_button(interaction: discord.Interaction, button: ui.Button):
            await self.handle_archive(interaction)

        self.add_item(button_row)

    async def handle_claim(self, interaction: discord.Interaction):
        """Gère le claim/unclaim d'un ticket"""
        # Récupérer les infos du staff
        staff_info = await db.get_staff_info(interaction.user.id)

        if not staff_info:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Vous n'êtes pas membre du staff.",
                ephemeral=True
            )
            return

        staff_roles = get_staff_roles(staff_info)

        # Vérifier les permissions
        if not can_manage_ticket(staff_roles, self.category):
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Vous n'avez pas la permission de gérer ce type de ticket.",
                ephemeral=True
            )
            return

        # Récupérer le ticket
        ticket = await db.get_ticket(self.thread_id)

        if not ticket:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Ticket introuvable.",
                ephemeral=True
            )
            return

        # Si le ticket est déjà claim
        if ticket['claimed_by']:
            # Vérifier si c'est le même staff ou un supervisor/manager
            is_supervisor_or_manager = 'Manager' in staff_roles or any(role.startswith('Supervisor_') for role in staff_roles)

            if ticket['claimed_by'] == interaction.user.id or is_supervisor_or_manager:
                # Unclaim
                await db.unclaim_ticket(self.thread_id)
                await interaction.response.send_message(
                    f"{EMOJIS['done']} Ticket unclaimed avec succès.",
                    ephemeral=True
                )

                # Créer une nouvelle vue avec le bon label
                new_view = TicketControlView(self.thread_id, self.category, is_claimed=False)
                await interaction.message.edit(view=new_view)
            else:
                claimed_user = interaction.guild.get_member(ticket['claimed_by'])
                claimed_name = claimed_user.mention if claimed_user else f"<@{ticket['claimed_by']}>"
                await interaction.response.send_message(
                    f"{EMOJIS['undone']} Ce ticket est déjà claim par {claimed_name}. Seul un Supervisor/Manager peut l'unclaim.",
                    ephemeral=True
                )
        else:
            # Claim
            await db.claim_ticket(self.thread_id, interaction.user.id)
            await interaction.response.send_message(
                f"{EMOJIS['done']} Ticket claim avec succès.",
                ephemeral=True
            )

            # Créer une nouvelle vue avec le bon label
            new_view = TicketControlView(self.thread_id, self.category, is_claimed=True)
            await interaction.message.edit(view=new_view)

    async def handle_archive(self, interaction: discord.Interaction):
        """Gère l'archivage d'un ticket"""
        # Récupérer les infos du staff
        staff_info = await db.get_staff_info(interaction.user.id)

        if not staff_info:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Vous n'êtes pas membre du staff.",
                ephemeral=True
            )
            return

        staff_roles = get_staff_roles(staff_info)

        # Vérifier les permissions
        if not can_manage_ticket(staff_roles, self.category):
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Vous n'avez pas la permission de gérer ce type de ticket.",
                ephemeral=True
            )
            return

        # Archiver le ticket dans la DB
        await db.archive_ticket(self.thread_id)

        # Verrouiller le thread
        thread = interaction.guild.get_thread(self.thread_id)
        if thread:
            await thread.edit(archived=True, locked=True)

        await interaction.response.send_message(
            f"{EMOJIS['done']} Ticket archivé avec succès.",
            ephemeral=True
        )


class ArchiveRequestView(ui.LayoutView):
    """Vue pour demander l'archivage d'un ticket"""

    def __init__(self, thread_id: int):
        super().__init__(timeout=None)
        self.thread_id = thread_id

        container = ui.Container()
        container.add_item(ui.TextDisplay(
            f"**{EMOJIS['archive']} Archive Request**\n"
            "L'équipe souhaite archiver ce ticket. Êtes-vous d'accord ?"
        ))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        # Boutons Oui/Non
        button_row = ui.ActionRow()

        @button_row.button(
            label="Oui",
            style=discord.ButtonStyle.success,
            emoji=EMOJIS['done'],
            custom_id=f"archive_request:yes:{thread_id}"
        )
        async def yes_button(interaction: discord.Interaction, button: ui.Button):
            # Récupérer le ticket
            ticket = await db.get_ticket(self.thread_id)

            if not ticket:
                await interaction.response.send_message(
                    f"{EMOJIS['undone']} Ticket introuvable.",
                    ephemeral=True
                )
                return

            # Vérifier que c'est l'utilisateur du ticket
            if interaction.user.id != ticket['user_id']:
                await interaction.response.send_message(
                    f"{EMOJIS['undone']} Seul l'utilisateur ayant créé le ticket peut répondre.",
                    ephemeral=True
                )
                return

            # Archiver le ticket
            await db.archive_ticket(self.thread_id)

            # Verrouiller le thread
            thread = interaction.guild.get_thread(self.thread_id)
            if thread:
                await thread.edit(archived=True, locked=True)

            await interaction.response.send_message(
                f"{EMOJIS['done']} Le ticket a été archivé.",
                ephemeral=False
            )

        @button_row.button(
            label="Non",
            style=discord.ButtonStyle.danger,
            emoji=EMOJIS['undone'],
            custom_id=f"archive_request:no:{thread_id}"
        )
        async def no_button(interaction: discord.Interaction, button: ui.Button):
            # Récupérer le ticket
            ticket = await db.get_ticket(self.thread_id)

            if not ticket:
                await interaction.response.send_message(
                    f"{EMOJIS['undone']} Ticket introuvable.",
                    ephemeral=True
                )
                return

            # Vérifier que c'est l'utilisateur du ticket
            if interaction.user.id != ticket['user_id']:
                await interaction.response.send_message(
                    f"{EMOJIS['undone']} Seul l'utilisateur ayant créé le ticket peut répondre.",
                    ephemeral=True
                )
                return

            await interaction.response.send_message(
                f"{EMOJIS['done']} La demande d'archivage a été refusée.",
                ephemeral=False
            )

        container.add_item(button_row)
        self.add_item(container)


# Fonctions de création de tickets
async def create_support_ticket(interaction: discord.Interaction, user: discord.User, metadata: Dict):
    """Crée un ticket de support"""
    await interaction.response.defer(ephemeral=True)

    # Créer le thread privé
    channel = interaction.guild.get_channel(SUPPORT_CHANNEL_ID)
    if not channel:
        await interaction.followup.send(
            f"{EMOJIS['undone']} Salon de support introuvable.",
            ephemeral=True
        )
        return

    # Nom du thread
    thread_name = f"{EMOJIS['ticket']} Support - {user.name}"

    # Créer le thread
    thread = await channel.create_thread(
        name=thread_name,
        type=discord.ChannelType.private_thread,
        auto_archive_duration=10080  # 7 jours
    )

    # Ajouter l'utilisateur au thread
    await thread.add_user(user)

    # Créer l'embed principal
    embed = discord.Embed(
        title=f"{EMOJIS['ticket']} Nouveau Ticket - Support",
        description=f"Ticket créé par {user.mention}",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Utilisateur", value=f"{user.mention} (`{user.id}`)", inline=False)

    # Envoyer l'embed avec les boutons
    view = TicketControlView(thread.id, "support")
    await thread.send(
        content=f"<@&{ROLES['SUPPORT_AGENT']}> {user.mention}",
        embed=embed,
        view=view
    )

    # Créer l'embed avec les infos collectées
    info_embed = discord.Embed(
        title=f"{EMOJIS['ticket']} Informations du ticket",
        color=discord.Color.green()
    )

    info_embed.add_field(
        name="Type de support",
        value=metadata.get('type', 'Inconnu').capitalize(),
        inline=True
    )

    if metadata.get('type') == 'server' and metadata.get('guild_id'):
        info_embed.add_field(
            name="Serveur concerné",
            value=f"ID: `{metadata['guild_id']}`\nInvitation: {metadata.get('invite_link', 'N/A')}",
            inline=False
        )

    await thread.send(embed=info_embed)

    # Enregistrer dans la DB
    await db.create_ticket(thread.id, user.id, "support", metadata)

    await interaction.followup.send(
        f"{EMOJIS['done']} Votre ticket a été créé : {thread.mention}",
        ephemeral=True
    )


async def create_bug_report_ticket(interaction: discord.Interaction, user: discord.User, metadata: Dict):
    """Crée un ticket de bug report"""
    await interaction.response.defer(ephemeral=True)

    # Créer le thread privé
    channel = interaction.guild.get_channel(SUPPORT_CHANNEL_ID)
    if not channel:
        await interaction.followup.send(
            f"{EMOJIS['undone']} Salon de support introuvable.",
            ephemeral=True
        )
        return

    # Nom du thread
    thread_name = f"{EMOJIS['bug']} Bug Report - {user.name}"

    # Créer le thread
    thread = await channel.create_thread(
        name=thread_name,
        type=discord.ChannelType.private_thread,
        auto_archive_duration=10080  # 7 jours
    )

    # Ajouter l'utilisateur au thread
    await thread.add_user(user)

    # Créer l'embed principal
    embed = discord.Embed(
        title=f"{EMOJIS['bug']} Nouveau Ticket - Bug Report",
        description=f"Ticket créé par {user.mention}",
        color=discord.Color.red(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Utilisateur", value=f"{user.mention} (`{user.id}`)", inline=False)

    # Envoyer l'embed avec les boutons
    view = TicketControlView(thread.id, "bug_report")
    await thread.send(
        content=f"<@&{ROLES['DEV']}> {user.mention}",
        embed=embed,
        view=view
    )

    # Créer l'embed avec les infos collectées
    info_embed = discord.Embed(
        title=f"{EMOJIS['ticket']} Informations du ticket",
        color=discord.Color.orange()
    )

    if metadata.get('error_code'):
        error_info = metadata.get('error_info', {})

        info_embed.add_field(
            name="Code Erreur",
            value=f"`{metadata['error_code']}`",
            inline=True
        )

        if error_info:
            # Contexte de l'erreur (PAS le traceback)
            context_parts = []

            if error_info.get('command'):
                context_parts.append(f"**Commande:** `{error_info['command']}`")

            if error_info.get('user_id'):
                context_parts.append(f"**Utilisateur:** <@{error_info['user_id']}> (`{error_info['user_id']}`)")

            if error_info.get('guild_id'):
                context_parts.append(f"**Serveur:** `{error_info['guild_id']}`")

            if error_info.get('file_source') and error_info.get('line_number'):
                context_parts.append(f"**Fichier:** `{error_info['file_source']}:{error_info['line_number']}`")

            if error_info.get('error_type'):
                context_parts.append(f"**Type:** `{error_info['error_type']}`")

            if error_info.get('timestamp'):
                timestamp = int(error_info['timestamp'].timestamp()) if hasattr(error_info['timestamp'], 'timestamp') else 0
                if timestamp:
                    context_parts.append(f"**Quand:** <t:{timestamp}:F>")

            if context_parts:
                info_embed.add_field(
                    name="Contexte de l'erreur",
                    value="\n".join(context_parts),
                    inline=False
                )
    else:
        info_embed.add_field(
            name="Code Erreur",
            value="Aucun code erreur fourni",
            inline=False
        )

    await thread.send(embed=info_embed)

    # Enregistrer dans la DB
    await db.create_ticket(thread.id, user.id, "bug_report", metadata)

    await interaction.followup.send(
        f"{EMOJIS['done']} Votre ticket a été créé : {thread.mention}",
        ephemeral=True
    )


async def create_sanction_appeal_ticket(interaction: discord.Interaction, user: discord.User, metadata: Dict):
    """Crée un ticket de sanction appeal"""
    await interaction.response.defer(ephemeral=True)

    # Créer le thread privé
    channel = interaction.guild.get_channel(SUPPORT_CHANNEL_ID)
    if not channel:
        await interaction.followup.send(
            f"{EMOJIS['undone']} Salon de support introuvable.",
            ephemeral=True
        )
        return

    # Nom du thread
    thread_name = f"{EMOJIS['gavel']} Sanction Appeal - {user.name}"

    # Créer le thread
    thread = await channel.create_thread(
        name=thread_name,
        type=discord.ChannelType.private_thread,
        auto_archive_duration=10080  # 7 jours
    )

    # Ajouter l'utilisateur au thread
    await thread.add_user(user)

    # Créer l'embed principal
    embed = discord.Embed(
        title=f"{EMOJIS['gavel']} Nouveau Ticket - Sanction Appeal",
        description=f"Ticket créé par {user.mention}",
        color=discord.Color.orange(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Utilisateur", value=f"{user.mention} (`{user.id}`)", inline=False)

    # Envoyer l'embed avec les boutons
    view = TicketControlView(thread.id, "sanction_appeal")
    await thread.send(
        content=f"<@&{ROLES['MODERATOR']}> {user.mention}",
        embed=embed,
        view=view
    )

    # Créer l'embed avec les infos de la case
    case_info = metadata.get('case_info', {})

    info_embed = discord.Embed(
        title=f"{EMOJIS['ticket']} Informations de la case",
        color=discord.Color.red()
    )

    if case_info:
        info_embed.add_field(
            name="Case ID",
            value=f"`{case_info['case_id']}`",
            inline=True
        )

        info_embed.add_field(
            name="Type de case",
            value=case_info.get('case_type', 'N/A').capitalize(),
            inline=True
        )

        info_embed.add_field(
            name="Type de sanction",
            value=case_info.get('sanction_type', 'N/A').replace('_', ' ').title(),
            inline=True
        )

        info_embed.add_field(
            name="Statut",
            value=case_info.get('status', 'N/A').capitalize(),
            inline=True
        )

        entity_type = case_info.get('entity_type', 'N/A')
        entity_id = case_info.get('entity_id', 'N/A')

        if entity_type == 'user':
            info_embed.add_field(
                name="Utilisateur sanctionné",
                value=f"<@{entity_id}> (`{entity_id}`)",
                inline=True
            )
        elif entity_type == 'guild':
            info_embed.add_field(
                name="Serveur sanctionné",
                value=f"`{entity_id}`",
                inline=True
            )

        if case_info.get('reason'):
            info_embed.add_field(
                name="Raison",
                value=case_info['reason'][:1024],
                inline=False
            )

        if case_info.get('created_by'):
            created_timestamp = int(case_info['created_at'].timestamp()) if case_info.get('created_at') and hasattr(case_info['created_at'], 'timestamp') else 0
            info_embed.add_field(
                name="Créée par",
                value=f"<@{case_info['created_by']}>" + (f" (<t:{created_timestamp}:R>)" if created_timestamp else ""),
                inline=False
            )

    await thread.send(embed=info_embed)

    # Enregistrer dans la DB
    await db.create_ticket(thread.id, user.id, "sanction_appeal", metadata)

    await interaction.followup.send(
        f"{EMOJIS['done']} Votre ticket a été créé : {thread.mention}",
        ephemeral=True
    )


async def create_legal_request_ticket(interaction: discord.Interaction, user: discord.User, metadata: Dict):
    """Crée un ticket de legal request"""
    await interaction.response.defer(ephemeral=True)

    # Créer le thread privé
    channel = interaction.guild.get_channel(SUPPORT_CHANNEL_ID)
    if not channel:
        await interaction.followup.send(
            f"{EMOJIS['undone']} Salon de support introuvable.",
            ephemeral=True
        )
        return

    # Nom du thread
    thread_name = f"{EMOJIS['balance']} Legal Request - {user.name}"

    # Créer le thread
    thread = await channel.create_thread(
        name=thread_name,
        type=discord.ChannelType.private_thread,
        auto_archive_duration=10080  # 7 jours
    )

    # Ajouter l'utilisateur au thread
    await thread.add_user(user)

    # Créer l'embed principal
    embed = discord.Embed(
        title=f"{EMOJIS['balance']} Nouveau Ticket - Legal Request",
        description=f"Ticket créé par {user.mention}",
        color=discord.Color.purple(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Utilisateur", value=f"{user.mention} (`{user.id}`)", inline=False)

    # Envoyer l'embed avec les boutons
    view = TicketControlView(thread.id, "legal_request")
    await thread.send(
        content=f"<@&{ROLES['MANAGER']}> {user.mention}",
        embed=embed,
        view=view
    )

    # Créer l'embed avec le type de demande
    legal_type = metadata.get('legal_type', 'unknown')

    legal_types_names = {
        'data_access': 'Data Access',
        'rectification': 'Rectification',
        'deletion': 'Deletion / Right to be Forgotten',
        'objection': 'Objection'
    }

    info_embed = discord.Embed(
        title=f"{EMOJIS['ticket']} Informations du ticket",
        color=discord.Color.purple()
    )

    info_embed.add_field(
        name="Type de demande légale",
        value=legal_types_names.get(legal_type, legal_type.capitalize()),
        inline=False
    )

    await thread.send(embed=info_embed)

    # Enregistrer dans la DB
    await db.create_ticket(thread.id, user.id, "legal_request", metadata)

    await interaction.followup.send(
        f"{EMOJIS['done']} Votre ticket a été créé : {thread.mention}",
        ephemeral=True
    )


async def create_payments_billing_ticket(interaction: discord.Interaction, user: discord.User, metadata: Dict):
    """Crée un ticket de payments & billing"""
    await interaction.response.defer(ephemeral=True)

    # Créer le thread privé
    channel = interaction.guild.get_channel(SUPPORT_CHANNEL_ID)
    if not channel:
        await interaction.followup.send(
            f"{EMOJIS['undone']} Salon de support introuvable.",
            ephemeral=True
        )
        return

    # Nom du thread
    thread_name = f"{EMOJIS['payments']} Payments & Billing - {user.name}"

    # Créer le thread
    thread = await channel.create_thread(
        name=thread_name,
        type=discord.ChannelType.private_thread,
        auto_archive_duration=10080  # 7 jours
    )

    # Ajouter l'utilisateur au thread
    await thread.add_user(user)

    # Créer l'embed principal
    embed = discord.Embed(
        title=f"{EMOJIS['payments']} Nouveau Ticket - Payments & Billing",
        description=f"Ticket créé par {user.mention}",
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Utilisateur", value=f"{user.mention} (`{user.id}`)", inline=False)

    # Envoyer l'embed avec les boutons
    view = TicketControlView(thread.id, "payments_billing")
    await thread.send(
        content=f"<@&{ROLES['MANAGER']}> <@&{ROLES['SUPERVISOR']}> {user.mention}",
        embed=embed,
        view=view
    )

    # Enregistrer dans la DB
    await db.create_ticket(thread.id, user.id, "payments_billing", metadata)

    await interaction.followup.send(
        f"{EMOJIS['done']} Votre ticket a été créé : {thread.mention}",
        ephemeral=True
    )


async def create_other_request_ticket(interaction: discord.Interaction, user: discord.User, metadata: Dict):
    """Crée un ticket de other request"""
    await interaction.response.defer(ephemeral=True)

    # Créer le thread privé
    channel = interaction.guild.get_channel(SUPPORT_CHANNEL_ID)
    if not channel:
        await interaction.followup.send(
            f"{EMOJIS['undone']} Salon de support introuvable.",
            ephemeral=True
        )
        return

    # Nom du thread
    thread_name = f"{EMOJIS['question_mark']} Other Request - {user.name}"

    # Créer le thread
    thread = await channel.create_thread(
        name=thread_name,
        type=discord.ChannelType.private_thread,
        auto_archive_duration=10080  # 7 jours
    )

    # Ajouter l'utilisateur au thread
    await thread.add_user(user)

    # Créer l'embed principal
    embed = discord.Embed(
        title=f"{EMOJIS['question_mark']} Nouveau Ticket - Other Request",
        description=f"Ticket créé par {user.mention}",
        color=discord.Color.light_grey(),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="Utilisateur", value=f"{user.mention} (`{user.id}`)", inline=False)

    # Envoyer l'embed avec les boutons
    view = TicketControlView(thread.id, "other_request")
    await thread.send(
        content=f"<@&{ROLES['SUPPORT_AGENT']}> {user.mention}",
        embed=embed,
        view=view
    )

    # Enregistrer dans la DB
    await db.create_ticket(thread.id, user.id, "other_request", metadata)

    await interaction.followup.send(
        f"{EMOJIS['done']} Votre ticket a été créé : {thread.mention}",
        ephemeral=True
    )


class Tickets(commands.Cog):
    """Système de tickets pour Moddy Support"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Appelé quand le cog est chargé"""
        # Connecter à la base de données
        await db.connect()
        logger.info("Tickets cog loaded")

    async def cog_unload(self):
        """Appelé quand le cog est déchargé"""
        # Fermer la connexion à la base de données
        await db.close()
        logger.info("Tickets cog unloaded")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Écoute les messages pour la commande !tickets"""
        # Ignorer les bots
        if message.author.bot:
            return

        # Vérifier si c'est dans le bon salon
        if message.channel.id != SUPPORT_CHANNEL_ID:
            return

        # Vérifier si c'est la commande !tickets
        if message.content.strip() == '!tickets':
            # Vérifier si l'utilisateur est un staff
            staff_info = await db.get_staff_info(message.author.id)

            if not staff_info:
                await message.reply(
                    f"{EMOJIS['undone']} Vous n'avez pas la permission d'utiliser cette commande.",
                    delete_after=5
                )
                return

            # Supprimer le message de commande
            try:
                await message.delete()
            except:
                pass

            # Envoyer le panel de support
            view = SupportPanelView()
            await message.channel.send(view=view)

    @commands.command(name='archiverequest')
    async def archive_request(self, ctx: commands.Context):
        """Commande pour demander l'archivage d'un ticket"""
        # Vérifier si c'est dans un thread
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.reply(
                f"{EMOJIS['undone']} Cette commande ne peut être utilisée que dans un thread de ticket.",
                delete_after=5
            )
            return

        # Vérifier si l'utilisateur est un staff
        staff_info = await db.get_staff_info(ctx.author.id)

        if not staff_info:
            await ctx.reply(
                f"{EMOJIS['undone']} Vous n'avez pas la permission d'utiliser cette commande.",
                delete_after=5
            )
            return

        # Récupérer le ticket
        ticket = await db.get_ticket(ctx.channel.id)

        if not ticket:
            await ctx.reply(
                f"{EMOJIS['undone']} Ce thread n'est pas un ticket valide.",
                delete_after=5
            )
            return

        # Vérifier les permissions
        staff_roles = get_staff_roles(staff_info)
        if not can_manage_ticket(staff_roles, ticket['category']):
            await ctx.reply(
                f"{EMOJIS['undone']} Vous n'avez pas la permission de gérer ce type de ticket.",
                delete_after=5
            )
            return

        # Supprimer le message de commande
        try:
            await ctx.message.delete()
        except:
            pass

        # Envoyer la demande d'archivage
        view = ArchiveRequestView(ctx.channel.id)
        await ctx.send(view=view)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
