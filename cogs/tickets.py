import discord
from discord.ext import commands
from discord import ui
import asyncpg
import os
import re
import logging
from typing import Optional, Dict, List
import aiohttp
import json

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
    """Manages database connections"""

    def __init__(self):
        self.moddy_pool: Optional[asyncpg.Pool] = None
        self.systems_pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Connects to both databases"""
        # Connection to Moddy DB
        moddy_url = os.getenv('MODDYDB_URL')
        if not moddy_url:
            logger.warning("⚠️ MODDYDB_URL not set - Moddy database features will be disabled")
            logger.warning("   (Error codes, moderation cases, and staff permissions won't work)")
        else:
            try:
                self.moddy_pool = await asyncpg.create_pool(
                    moddy_url,
                    min_size=2,
                    max_size=10
                )
                logger.info("✅ Connected to Moddy database")
            except Exception as e:
                logger.error(f"❌ Failed to connect to Moddy database: {e}")
                logger.error("   Error codes, moderation cases, and staff permissions won't work")

        # Connection to ModdySystems DB
        systems_url = os.getenv('DATABASE_URL')
        if not systems_url:
            logger.warning("⚠️ DATABASE_URL not set - Ticket system database will be disabled")
            logger.warning("   (Tickets won't be saved to database)")
        else:
            try:
                self.systems_pool = await asyncpg.create_pool(
                    systems_url,
                    min_size=2,
                    max_size=10
                )
                logger.info("✅ Connected to ModdySystems database")

                # Create tickets table if it doesn't exist
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
                logger.error(f"❌ Failed to connect to ModdySystems database: {e}")
                logger.error("   Tickets won't be saved to database")

    async def close(self):
        """Closes database connections"""
        if self.moddy_pool:
            await self.moddy_pool.close()
        if self.systems_pool:
            await self.systems_pool.close()

    async def get_error_info(self, error_code: str) -> Optional[Dict]:
        """Retrieves error information from Moddy DB"""
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
        """Retrieves open cases for a user"""
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
        """Retrieves open cases for a server"""
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
        """Retrieves staff information from Moddy DB"""
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
        """Creates a ticket in DB"""
        if not self.systems_pool:
            return

        try:
            # Convert metadata dict to JSON string
            metadata_json = json.dumps(metadata or {})

            async with self.systems_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO tickets (thread_id, user_id, category, metadata)
                    VALUES ($1, $2, $3, $4::jsonb)
                    """,
                    thread_id, user_id, category, metadata_json
                )
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")

    async def get_ticket(self, thread_id: int) -> Optional[Dict]:
        """Retrieves a ticket from DB"""
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
        """Claims a ticket"""
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
        """Unclaims a ticket"""
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
        """Archives a ticket"""
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

    async def unarchive_ticket(self, thread_id: int):
        """Unarchives a ticket"""
        if not self.systems_pool:
            return

        try:
            async with self.systems_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE tickets SET archived = FALSE, archived_at = NULL WHERE thread_id = $1",
                    thread_id
                )
        except Exception as e:
            logger.error(f"Error unarchiving ticket: {e}")


# Global database instance
db = TicketDatabase()


# Utility functions
async def update_thread_status_indicator(thread: discord.Thread, status: str):
    """Updates the thread name with a status indicator emoji

    Args:
        thread: The thread to update
        status: One of 'unclaimed', 'claimed', 'archive_request', 'archived'
    """
    indicators = {
        'unclaimed': '⚪',
        'claimed': '🟢',
        'archive_request': '🟡',
        'archived': '🔴'
    }

    indicator = indicators.get(status, '⚪')

    # Remove any existing indicator from the name
    current_name = thread.name
    for emoji in indicators.values():
        current_name = current_name.replace(f"{emoji} ", "").strip()

    # Add the new indicator
    new_name = f"{indicator} {current_name}"

    try:
        await thread.edit(name=new_name)
    except Exception as e:
        logger.error(f"Error updating thread name: {e}")


async def get_guild_id_from_invite(invite_url: str) -> Optional[int]:
    """Extracts server ID from invitation link"""
    # Extract invitation code
    invite_code = invite_url.strip()

    # Patterns for Discord links
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
        # If it's just the code
        code = invite_code

    try:
        # Use Discord API to retrieve invitation information
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
    """Extracts staff roles from their information"""
    if not staff_info or 'roles' not in staff_info:
        return []

    roles = staff_info['roles']

    # If roles is a string (JSON), parse it
    if isinstance(roles, str):
        try:
            roles = json.loads(roles)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse roles JSON: {roles}")
            return []

    # If roles is a list, return it
    if isinstance(roles, list):
        return roles

    return []


def can_manage_ticket(staff_roles: List[str], category: str) -> bool:
    """Checks if a staff member can manage a ticket of a given category"""
    # Manager and any Supervisor can manage everything
    if 'Manager' in staff_roles:
        return True

    # Check if user has any Supervisor role (Supervisor_Mod, Supervisor_Com, Supervisor_Sup)
    for role in staff_roles:
        if role.startswith('Supervisor_'):
            return True

    # Permissions by category
    permissions = {
        'support': ['Support'],
        'bug_report': ['Dev'],
        'sanction_appeal': ['Moderator'],
        'legal_request': ['Manager'],  # Already checked above
        'payments_billing': ['Support'],
        'other_request': ['Support', 'Communication', 'Moderator', 'Dev'],
    }

    if category in permissions:
        for role in staff_roles:
            if role in permissions[category]:
                return True

    return False


# Modals
class ErrorCodeModal(ui.Modal, title="Error Code"):
    """Modal pour entrer un code erreur"""

    error_code = ui.TextInput(
        label="Error Code",
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

        # Check le format
        if not re.match(r'^[A-Z0-9]{8}$', code):
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Le code erreur doit contenir exactement 8 caractères (lettres majuscules ou chiffres).",
                ephemeral=True
            )
            return

        await self.callback_func(interaction, code)


class ServerInviteModal(ui.Modal, title="Server Invitation Link"):
    """Modal to enter a Discord invitation link"""

    invite_link = ui.TextInput(
        label="Invitation Link",
        placeholder="Ex: discord.gg/abc123 or https://discord.gg/abc123",
        required=True
    )

    def __init__(self, callback_func):
        super().__init__()
        self.callback_func = callback_func

    async def on_submit(self, interaction: discord.Interaction):
        invite = self.invite_link.value.strip()
        await self.callback_func(interaction, invite)


# Views for different steps
class SupportTypeView(ui.View):
    """View to choose support type (server/user/other)"""

    def __init__(self, user: discord.User):
        super().__init__(timeout=300)
        self.user = user
        self.selected_type = None

    @discord.ui.button(label="Server", style=discord.ButtonStyle.primary, row=0)
    async def server_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Only the user who initiated this action can respond.",
                ephemeral=True
            )
            return

        self.selected_type = "server"
        # Ask for invitation link
        modal = ServerInviteModal(self.on_server_invite_submit)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="User", style=discord.ButtonStyle.primary, row=0)
    async def user_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Only the user who initiated this action can respond.",
                ephemeral=True
            )
            return

        self.selected_type = "user"
        await self.create_ticket(interaction, {"type": "user"})

    @discord.ui.button(label="Other", style=discord.ButtonStyle.primary, row=0)
    async def other_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Only the user who initiated this action can respond.",
                ephemeral=True
            )
            return

        self.selected_type = "other"
        await self.create_ticket(interaction, {"type": "other"})

    async def on_server_invite_submit(self, interaction: discord.Interaction, invite: str):
        """Callback quand l'utilisateur soumet le lien d'invitation"""
        await interaction.response.defer(ephemeral=True)

        # Extraire l'ID du serveur
        guild_id = await get_guild_id_from_invite(invite)

        if not guild_id:
            await interaction.followup.send(
                f"{EMOJIS['undone']} Unable to retrieve server information. Check the invitation link.",
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


class BugReportHasCodeView(ui.View):
    """View to ask if user has an error code"""

    def __init__(self, user: discord.User):
        super().__init__(timeout=300)
        self.user = user

    @discord.ui.button(label="Yes, I have an error code", style=discord.ButtonStyle.primary, row=0)
    async def yes_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Only the user who initiated this action can respond.",
                ephemeral=True
            )
            return

        # Show modal to enter the code
        modal = ErrorCodeModal(self.on_error_code_submit)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="No, I don't have a code", style=discord.ButtonStyle.secondary, row=0)
    async def no_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Only the user who initiated this action can respond.",
                ephemeral=True
            )
            return

        await self.create_ticket(interaction, {})

    async def on_error_code_submit(self, interaction: discord.Interaction, error_code: str):
        """Callback quand l'utilisateur soumet un code erreur"""
        await interaction.response.defer(ephemeral=True)

        # Retrieve information de l'erreur
        error_info = await db.get_error_info(error_code)

        if not error_info:
            await interaction.followup.send(
                f"{EMOJIS['undone']} Error code not found in database.",
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


class SanctionAppealTypeView(ui.View):
    """View to choose sanction appeal type (server/user)"""

    def __init__(self, user: discord.User):
        super().__init__(timeout=300)
        self.user = user

    @discord.ui.button(label="Server", style=discord.ButtonStyle.primary, row=0)
    async def server_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Only the user who initiated this action can respond.",
                ephemeral=True
            )
            return

        # Ask for invitation link
        modal = ServerInviteModal(self.on_server_invite_submit)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Myself (user)", style=discord.ButtonStyle.primary, row=0)
    async def user_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Only the user who initiated this action can respond.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Retrieve user cases
        cases = await db.get_user_cases(self.user.id)

        if not cases:
            await interaction.followup.send(
                f"{EMOJIS['undone']} You have no open cases.",
                ephemeral=True
            )
            return

        # Show dropdown menu of cases
        view = CaseSelectView(self.user, cases, "user")
        await interaction.followup.send(
            view=view,
            ephemeral=True
        )

    async def on_server_invite_submit(self, interaction: discord.Interaction, invite: str):
        """Callback quand l'utilisateur soumet le lien d'invitation"""
        await interaction.response.defer(ephemeral=True)

        # Extraire l'ID du serveur
        guild_id = await get_guild_id_from_invite(invite)

        if not guild_id:
            await interaction.followup.send(
                f"{EMOJIS['undone']} Unable to retrieve server information. Check the invitation link.",
                ephemeral=True
            )
            return

        # Retrieve server cases
        cases = await db.get_guild_cases(guild_id)

        if not cases:
            await interaction.followup.send(
                f"{EMOJIS['undone']} This server has no open cases.",
                ephemeral=True
            )
            return

        # Show dropdown menu of cases
        view = CaseSelectView(self.user, cases, "server", invite_link=invite)
        await interaction.followup.send(
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
            f"**{EMOJIS['gavel']} Case Selection**\n"
            f"-# {len(cases)} open case(s) found"
        ))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        # Dropdown menu
        select_row = ui.ActionRow()
        case_select = ui.Select(
            placeholder="Select a case...",
            options=[
                discord.SelectOption(
                    label=f"Case {case['case_id']} - {case['sanction_type']}",
                    description=f"{case['reason'][:100] if case['reason'] else 'No reason'}",
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
                f"{EMOJIS['undone']} Only the user who initiated this action can respond.",
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
                f"{EMOJIS['undone']} Error retrieving the case.",
                ephemeral=True
            )
            return

        # Create le ticket
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
            f"**{EMOJIS['ticket']} Creating Ticket - Legal Request**\n"
            "-# Please select the type of legal request"
        ))

        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))

        # Dropdown menu
        select_row = ui.ActionRow()
        legal_select = ui.Select(
            placeholder="Select a request type...",
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
                f"{EMOJIS['undone']} Only the user who initiated this action can respond.",
                ephemeral=True
            )
            return

        legal_type = interaction.data['values'][0]

        # Create le ticket
        metadata = {
            "legal_type": legal_type
        }
        await create_legal_request_ticket(interaction, self.user, metadata)


class SupportPanelView(ui.LayoutView):
    """Vue principale du panel de support"""

    def __init__(self):
        super().__init__(timeout=None)  # No timeout for main panel

        # Create container
        container = ui.Container()

        # Panel header
        container.add_item(ui.TextDisplay(
            f"### {EMOJIS['ticket']} Moddy Support Panel\n"
            "Please select the category that matches your request below.\n"
            "Our team will get back to you as soon as possible."
        ))

        # First row of buttons
        row1 = ui.ActionRow()

        support_btn = ui.Button(
            label="Support",
            style=discord.ButtonStyle.secondary,
            emoji="<:handshake:1448354754366537970>",
            custom_id="ticket_panel:support"
        )
        support_btn.callback = self.support_button

        bug_btn = ui.Button(
            label="Bug Reports",
            style=discord.ButtonStyle.secondary,
            emoji="<:bug:1448354755868102726>",
            custom_id="ticket_panel:bug_report"
        )
        bug_btn.callback = self.bug_report_button

        row1.add_item(support_btn)
        row1.add_item(bug_btn)
        container.add_item(row1)

        # Second row of buttons
        row2 = ui.ActionRow()

        sanction_btn = ui.Button(
            label="Sanction Appeals",
            style=discord.ButtonStyle.secondary,
            emoji="<:gavel:1448354751011094611>",
            custom_id="ticket_panel:sanction_appeal"
        )
        sanction_btn.callback = self.sanction_appeal_button

        payments_btn = ui.Button(
            label="Payments & Billing",
            style=discord.ButtonStyle.secondary,
            emoji="<:payments:1448354761769353288>",
            custom_id="ticket_panel:payments_billing"
        )
        payments_btn.callback = self.payments_billing_button

        row2.add_item(sanction_btn)
        row2.add_item(payments_btn)
        container.add_item(row2)

        # Third row of buttons
        row3 = ui.ActionRow()

        legal_btn = ui.Button(
            label="Legal Requests",
            style=discord.ButtonStyle.secondary,
            emoji="<:balance:1448354749110816900>",
            custom_id="ticket_panel:legal_request"
        )
        legal_btn.callback = self.legal_request_button

        other_btn = ui.Button(
            label="Other Request",
            style=discord.ButtonStyle.secondary,
            emoji="<:question_mark:1448354747836006564>",
            custom_id="ticket_panel:other_request"
        )
        other_btn.callback = self.other_request_button

        row3.add_item(legal_btn)
        row3.add_item(other_btn)
        container.add_item(row3)

        self.add_item(container)

    async def support_button(self, interaction: discord.Interaction):
        # Show view to choose support type
        view = SupportTypeView(interaction.user)
        await interaction.response.send_message(
            f"{EMOJIS['ticket']} **Creating Ticket - Support**\n-# Please select the type of support you need",
            view=view,
            ephemeral=True
        )

    async def bug_report_button(self, interaction: discord.Interaction):
        # Show view to ask for error code
        view = BugReportHasCodeView(interaction.user)
        await interaction.response.send_message(
            f"{EMOJIS['ticket']} **Creating Ticket - Bug Report**\n-# Do you have an error code to provide?",
            view=view,
            ephemeral=True
        )

    async def sanction_appeal_button(self, interaction: discord.Interaction):
        # Show view to choose server/user
        view = SanctionAppealTypeView(interaction.user)
        await interaction.response.send_message(
            f"{EMOJIS['ticket']} **Creating Ticket - Sanction Appeal**\n-# Do you want to appeal a sanction concerning a server or yourself?",
            view=view,
            ephemeral=True
        )

    async def payments_billing_button(self, interaction: discord.Interaction):
        # Create ticket directly
        await create_payments_billing_ticket(interaction, interaction.user, {})

    async def legal_request_button(self, interaction: discord.Interaction):
        # Show dropdown menu to choose request type
        view = LegalRequestTypeView(interaction.user)
        await interaction.response.send_message(
            view=view,
            ephemeral=True
        )

    async def other_request_button(self, interaction: discord.Interaction):
        # Create ticket directly
        await create_other_request_ticket(interaction, interaction.user, {})


class TicketControlView(ui.LayoutView):
    """View with ticket info, Claim and Archive buttons"""

    def __init__(self, thread_id: int, category: str, user: discord.User, emoji: str, title: str, mentions: str = "", is_claimed: bool = False, bot=None):
        super().__init__(timeout=None)
        self.thread_id = thread_id
        self.category = category
        self.user = user
        self.emoji = emoji
        self.title = title
        self.mentions = mentions
        self.bot = bot

        # Create container
        container = ui.Container()

        # Mentions at the top if provided
        if mentions:
            container.add_item(ui.TextDisplay(mentions))

        # Header with ticket info
        container.add_item(ui.TextDisplay(
            f"### {emoji} {title}\n"
            f"**User:** {user.mention} (`{user.id}`)\n"
            f"**Created:** <t:{int(discord.utils.utcnow().timestamp())}:F>"
        ))

        # Claim and Archive buttons
        button_row = ui.ActionRow()

        # Create buttons as instances (not decorators)
        claim_button = ui.Button(
            label="Unclaim" if is_claimed else "Claim",
            style=discord.ButtonStyle.primary,
            emoji=EMOJIS['front_hand'],
            custom_id=f"ticket:claim:{thread_id}"
        )
        claim_button.callback = self.handle_claim

        archive_button = ui.Button(
            label="Archive",
            style=discord.ButtonStyle.secondary,
            emoji=EMOJIS['archive'],
            custom_id=f"ticket:archive:{thread_id}"
        )
        archive_button.callback = self.handle_archive

        button_row.add_item(claim_button)
        button_row.add_item(archive_button)
        container.add_item(button_row)
        self.add_item(container)

    async def handle_claim(self, interaction: discord.Interaction):
        """Gère le claim/unclaim d'un ticket"""
        # Retrieve information du staff
        staff_info = await db.get_staff_info(interaction.user.id)

        if not staff_info:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} You are not a staff member.",
                ephemeral=True
            )
            return

        staff_roles = get_staff_roles(staff_info)
        logger.info(f"User {interaction.user.id} has roles: {staff_roles} for category {self.category}")

        # Check les permissions
        if not can_manage_ticket(staff_roles, self.category):
            await interaction.response.send_message(
                f"{EMOJIS['undone']} You do not have permission to manage this type of ticket.",
                ephemeral=True
            )
            return

        # Retrieve le ticket
        ticket = await db.get_ticket(self.thread_id)

        if not ticket:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Ticket not found.",
                ephemeral=True
            )
            return

        # Si le ticket est déjà claim
        if ticket['claimed_by']:
            # Check si c'est le même staff ou un supervisor/manager
            is_supervisor_or_manager = 'Manager' in staff_roles or any(role.startswith('Supervisor_') for role in staff_roles)

            if ticket['claimed_by'] == interaction.user.id or is_supervisor_or_manager:
                # Unclaim
                await db.unclaim_ticket(self.thread_id)

                # Update thread status indicator
                thread = interaction.guild.get_thread(self.thread_id)
                if thread:
                    try:
                        await update_thread_status_indicator(thread, 'unclaimed')
                    except Exception as e:
                        logger.warning(f"Could not update thread status indicator (rate limit?): {e}")

                await interaction.response.send_message(
                    f"{EMOJIS['done']} Ticket unclaimed successfully.",
                    ephemeral=True
                )

                # Send status message to thread
                if thread:
                    await thread.send(f"{EMOJIS['front_hand']} {interaction.user.mention} has unclaimed this ticket")

                # Create une nouvelle vue avec le bon label
                new_view = TicketControlView(self.thread_id, self.category, self.user, self.emoji, self.title, self.mentions, is_claimed=False, bot=self.bot)
                if self.bot:
                    self.bot.add_view(new_view)
                await interaction.message.edit(view=new_view)
            else:
                claimed_user = interaction.guild.get_member(ticket['claimed_by'])
                claimed_name = claimed_user.mention if claimed_user else f"<@{ticket['claimed_by']}>"
                await interaction.response.send_message(
                    f"{EMOJIS['undone']} This ticket is already claimed by {claimed_name}. Only a Supervisor/Manager can unclaim it.",
                    ephemeral=True
                )
        else:
            # Claim
            await db.claim_ticket(self.thread_id, interaction.user.id)

            # Update thread status indicator
            thread = interaction.guild.get_thread(self.thread_id)
            if thread:
                try:
                    await update_thread_status_indicator(thread, 'claimed')
                except Exception as e:
                    logger.warning(f"Could not update thread status indicator (rate limit?): {e}")

            await interaction.response.send_message(
                f"{EMOJIS['done']} Ticket claimed successfully.",
                ephemeral=True
            )

            # Send status message to thread
            if thread:
                await thread.send(f"{EMOJIS['front_hand']} {interaction.user.mention} has claimed this ticket")

            # Create une nouvelle vue avec le bon label
            new_view = TicketControlView(self.thread_id, self.category, self.user, self.emoji, self.title, self.mentions, is_claimed=True, bot=self.bot)
            if self.bot:
                self.bot.add_view(new_view)
            await interaction.message.edit(view=new_view)

    async def handle_archive(self, interaction: discord.Interaction):
        """Gère l'archivage d'un ticket"""
        # Retrieve information du staff
        staff_info = await db.get_staff_info(interaction.user.id)

        if not staff_info:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} You are not a staff member.",
                ephemeral=True
            )
            return

        staff_roles = get_staff_roles(staff_info)

        # Check les permissions
        if not can_manage_ticket(staff_roles, self.category):
            await interaction.response.send_message(
                f"{EMOJIS['undone']} You do not have permission to manage this type of ticket.",
                ephemeral=True
            )
            return

        # Respond to interaction BEFORE archiving the thread
        await interaction.response.send_message(
            f"{EMOJIS['done']} Ticket archived successfully.",
            ephemeral=True
        )

        # Archive le ticket to DB
        await db.archive_ticket(self.thread_id)

        # Lock thread and update status indicator
        thread = interaction.guild.get_thread(self.thread_id)
        if thread:
            # Send status message before locking
            await thread.send(f"{EMOJIS['archive']} {interaction.user.mention} has archived this ticket")

            # Update thread status indicator (may hit rate limit, but that's ok)
            try:
                await update_thread_status_indicator(thread, 'archived')
            except Exception as e:
                logger.warning(f"Could not update thread status indicator (rate limit?): {e}")

            await thread.edit(archived=True, locked=True)


class ArchiveRequestView(ui.LayoutView):
    """View to request ticket archival (Components V2)"""

    def __init__(self, thread_id: int, user: discord.User):
        super().__init__(timeout=None)
        self.thread_id = thread_id
        self.user = user

        container = ui.Container()

        # Message asking for confirmation
        container.add_item(ui.TextDisplay(
            f"### {EMOJIS['archive']} Archive Request\n"
            f"The team would like to archive this ticket. Do you agree?"
        ))

        # Buttons row
        button_row = ui.ActionRow()

        yes_button = ui.Button(
            label="Yes",
            style=discord.ButtonStyle.success,
            emoji=EMOJIS['done'],
            custom_id=f"archive_request:yes:{thread_id}"
        )
        yes_button.callback = self.yes_button

        no_button = ui.Button(
            label="No",
            style=discord.ButtonStyle.danger,
            emoji=EMOJIS['undone'],
            custom_id=f"archive_request:no:{thread_id}"
        )
        no_button.callback = self.no_button

        button_row.add_item(yes_button)
        button_row.add_item(no_button)
        container.add_item(button_row)
        self.add_item(container)

    async def yes_button(self, interaction: discord.Interaction):
        # Retrieve ticket
        ticket = await db.get_ticket(self.thread_id)

        if not ticket:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Ticket not found.",
                ephemeral=True
            )
            return

        # Check that it's the ticket user
        if interaction.user.id != ticket['user_id']:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Only the user who created the ticket can respond.",
                ephemeral=True
            )
            return

        # Respond BEFORE archiving
        await interaction.response.send_message(
            f"{EMOJIS['done']} The ticket has been archived.",
            ephemeral=False
        )

        # Archive ticket
        await db.archive_ticket(self.thread_id)

        # Lock thread and update status indicator
        thread = interaction.guild.get_thread(self.thread_id)
        if thread:
            try:
                await update_thread_status_indicator(thread, 'archived')
            except Exception as e:
                logger.warning(f"Could not update thread status indicator (rate limit?): {e}")

            await thread.edit(archived=True, locked=True)

    async def no_button(self, interaction: discord.Interaction):
        # Retrieve ticket
        ticket = await db.get_ticket(self.thread_id)

        if not ticket:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Ticket not found.",
                ephemeral=True
            )
            return

        # Check that it's the ticket user
        if interaction.user.id != ticket['user_id']:
            await interaction.response.send_message(
                f"{EMOJIS['undone']} Only the user who created the ticket can respond.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"{EMOJIS['done']} The archive request has been declined.",
            ephemeral=False
        )

        # Update thread status indicator back to claimed or unclaimed
        thread = interaction.guild.get_thread(self.thread_id)
        if thread:
            status = 'claimed' if ticket['claimed_by'] else 'unclaimed'
            try:
                await update_thread_status_indicator(thread, status)
            except Exception as e:
                logger.warning(f"Could not update thread status indicator (rate limit?): {e}")


# Ticket creation functions
async def create_support_ticket(interaction: discord.Interaction, user: discord.User, metadata: Dict):
    """Creates a support ticket"""
    # Check if interaction hasn't been responded to yet
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    # Create private thread
    channel = interaction.guild.get_channel(SUPPORT_CHANNEL_ID)
    if not channel:
        await interaction.followup.send(
            f"{EMOJIS['undone']} Support channel not found.",
            ephemeral=True
        )
        return

    # Nom du thread
    thread_name = f"Support - {user.name}"

    # Create thread
    thread = await channel.create_thread(
        name=thread_name,
        type=discord.ChannelType.private_thread,
        auto_archive_duration=10080  # 7 days
    )

    # Update thread status indicator (unclaimed)
    await update_thread_status_indicator(thread, 'unclaimed')

    # Add user to thread
    await thread.add_user(user)

    # Main message avec boutons (Components V2)
    mentions = f"<@&{ROLES['SUPPORT_AGENT']}> {user.mention}"
    view = TicketControlView(thread.id, "support", user, EMOJIS['handshake'], "New Ticket - Support", mentions, bot=interaction.client)
    interaction.client.add_view(view)
    await thread.send(view=view)

    # Message with information collectées (Components V2)
    info_view = ui.LayoutView(timeout=None)
    info_container = ui.Container()

    # Title
    info_container.add_item(ui.TextDisplay(f"### {EMOJIS['ticket']} Ticket Information"))

    # Support Type
    support_type = metadata.get('type', 'Unknown').capitalize()
    info_container.add_item(ui.TextDisplay(f"**Support Type:** {support_type}"))

    # Server info if applicable
    if metadata.get('type') == 'server' and metadata.get('guild_id'):
        info_container.add_item(ui.TextDisplay(
            f"\n**Concerned Server:**\n"
            f"• ID: `{metadata['guild_id']}`\n"
            f"• Invite: {metadata.get('invite_link', 'N/A')}"
        ))

    info_view.add_item(info_container)
    await thread.send(view=info_view)

    # Save to DB
    await db.create_ticket(thread.id, user.id, "support", metadata)

    await interaction.followup.send(
        f"{EMOJIS['done']} Your ticket has been created, here is the link: {thread.mention}",
        ephemeral=True
    )


async def create_bug_report_ticket(interaction: discord.Interaction, user: discord.User, metadata: Dict):
    """Creates a bug report ticket"""
    # Check if interaction hasn't been responded to yet
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    # Create private thread
    channel = interaction.guild.get_channel(SUPPORT_CHANNEL_ID)
    if not channel:
        await interaction.followup.send(
            f"{EMOJIS['undone']} Support channel not found.",
            ephemeral=True
        )
        return

    # Nom du thread
    thread_name = f"Bug Report - {user.name}"

    # Create thread
    thread = await channel.create_thread(
        name=thread_name,
        type=discord.ChannelType.private_thread,
        auto_archive_duration=10080  # 7 days
    )

    # Update thread status indicator (unclaimed)
    await update_thread_status_indicator(thread, 'unclaimed')

    # Add user to thread
    await thread.add_user(user)

    # Main message avec boutons (Components V2)
    mentions = f"<@&{ROLES['DEV']}> {user.mention}"
    view = TicketControlView(thread.id, "bug_report", user, EMOJIS['bug'], "New Ticket - Bug Report", mentions, bot=interaction.client)
    interaction.client.add_view(view)
    await thread.send(view=view)

    # Message with information collectées (Components V2)
    info_view = ui.LayoutView(timeout=None)
    info_container = ui.Container()

    # Title
    info_container.add_item(ui.TextDisplay(f"### {EMOJIS['ticket']} Ticket Information"))

    if metadata.get('error_code'):
        error_info = metadata.get('error_info', {})
        info_container.add_item(ui.TextDisplay(f"**Error Code:** `{metadata['error_code']}`"))

        if error_info:
            # Error Context (PAS le traceback)
            context_parts = ["\n**Error Context:**"]

            if error_info.get('command'):
                context_parts.append(f"• **Command:** `{error_info['command']}`")

            if error_info.get('user_id'):
                context_parts.append(f"• **User:** <@{error_info['user_id']}> (`{error_info['user_id']}`)")

            if error_info.get('guild_id'):
                context_parts.append(f"• **Server:** `{error_info['guild_id']}`")

            if error_info.get('file_source') and error_info.get('line_number'):
                context_parts.append(f"• **File:** `{error_info['file_source']}:{error_info['line_number']}`")

            if error_info.get('error_type'):
                context_parts.append(f"• **Type:** `{error_info['error_type']}`")

            if error_info.get('timestamp'):
                timestamp = int(error_info['timestamp'].timestamp()) if hasattr(error_info['timestamp'], 'timestamp') else 0
                if timestamp:
                    context_parts.append(f"• **When:** <t:{timestamp}:F>")

            info_container.add_item(ui.TextDisplay('\n'.join(context_parts)))
    else:
        info_container.add_item(ui.TextDisplay("**Error Code:** No error code provided"))

    info_view.add_item(info_container)
    await thread.send(view=info_view)

    # Save to DB
    await db.create_ticket(thread.id, user.id, "bug_report", metadata)

    await interaction.followup.send(
        f"{EMOJIS['done']} Your ticket has been created, here is the link: {thread.mention}",
        ephemeral=True
    )


async def create_sanction_appeal_ticket(interaction: discord.Interaction, user: discord.User, metadata: Dict):
    """Creates a sanction appeal ticket"""
    # Check if interaction hasn't been responded to yet
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    # Create private thread
    channel = interaction.guild.get_channel(SUPPORT_CHANNEL_ID)
    if not channel:
        await interaction.followup.send(
            f"{EMOJIS['undone']} Support channel not found.",
            ephemeral=True
        )
        return

    # Nom du thread
    thread_name = f"Sanction Appeal - {user.name}"

    # Create thread
    thread = await channel.create_thread(
        name=thread_name,
        type=discord.ChannelType.private_thread,
        auto_archive_duration=10080  # 7 days
    )

    # Update thread status indicator (unclaimed)
    await update_thread_status_indicator(thread, 'unclaimed')

    # Add user to thread
    await thread.add_user(user)

    # Main message avec boutons (Components V2)
    mentions = f"<@&{ROLES['MODERATOR']}> {user.mention}"
    view = TicketControlView(thread.id, "sanction_appeal", user, EMOJIS['gavel'], "New Ticket - Sanction Appeal", mentions, bot=interaction.client)
    interaction.client.add_view(view)
    await thread.send(view=view)

    # Message with information of the case (Components V2)
    case_info = metadata.get('case_info', {})
    info_view = ui.LayoutView(timeout=None)
    info_container = ui.Container()

    # Title
    info_container.add_item(ui.TextDisplay(f"### {EMOJIS['ticket']} Case Information"))

    if case_info:
        # Basic info
        basic_info = [
            f"**Case ID:** `{case_info['case_id']}`",
            f"**Case Type:** {case_info.get('case_type', 'N/A').capitalize()}",
            f"**Sanction Type:** {case_info.get('sanction_type', 'N/A').replace('_', ' ').title()}",
            f"**Status:** {case_info.get('status', 'N/A').capitalize()}"
        ]
        info_container.add_item(ui.TextDisplay('\n'.join(basic_info)))

        # Entity info
        entity_type = case_info.get('entity_type', 'N/A')
        entity_id = case_info.get('entity_id', 'N/A')

        if entity_type == 'user':
            info_container.add_item(ui.TextDisplay(f"\n**Sanctioned User:** <@{entity_id}> (`{entity_id}`)"))
        elif entity_type == 'guild':
            info_container.add_item(ui.TextDisplay(f"\n**Sanctioned Server:** `{entity_id}`"))

        # Reason
        if case_info.get('reason'):
            info_container.add_item(ui.TextDisplay(f"\n**Reason:**\n{case_info['reason'][:1024]}"))

        # Created by
        if case_info.get('created_by'):
            created_timestamp = int(case_info['created_at'].timestamp()) if case_info.get('created_at') and hasattr(case_info['created_at'], 'timestamp') else 0
            created_by_text = f"<@{case_info['created_by']}>"
            if created_timestamp:
                created_by_text += f" (<t:{created_timestamp}:R>)"
            info_container.add_item(ui.TextDisplay(f"\n**Created by:** {created_by_text}"))

    info_view.add_item(info_container)
    await thread.send(view=info_view)

    # Save to DB
    await db.create_ticket(thread.id, user.id, "sanction_appeal", metadata)

    await interaction.followup.send(
        f"{EMOJIS['done']} Your ticket has been created, here is the link: {thread.mention}",
        ephemeral=True
    )


async def create_legal_request_ticket(interaction: discord.Interaction, user: discord.User, metadata: Dict):
    """Creates a legal request ticket"""
    # Check if interaction hasn't been responded to yet
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    # Create private thread
    channel = interaction.guild.get_channel(SUPPORT_CHANNEL_ID)
    if not channel:
        await interaction.followup.send(
            f"{EMOJIS['undone']} Support channel not found.",
            ephemeral=True
        )
        return

    # Nom du thread
    thread_name = f"Legal Request - {user.name}"

    # Create thread
    thread = await channel.create_thread(
        name=thread_name,
        type=discord.ChannelType.private_thread,
        auto_archive_duration=10080  # 7 days
    )

    # Update thread status indicator (unclaimed)
    await update_thread_status_indicator(thread, 'unclaimed')

    # Add user to thread
    await thread.add_user(user)

    # Main message avec boutons (Components V2)
    mentions = f"<@&{ROLES['MANAGER']}> {user.mention}"
    view = TicketControlView(thread.id, "legal_request", user, EMOJIS['balance'], "New Ticket - Legal Request", mentions, bot=interaction.client)
    interaction.client.add_view(view)
    await thread.send(view=view)

    # Message with le type de demande (Components V2)
    legal_type = metadata.get('legal_type', 'unknown')

    legal_types_names = {
        'data_access': 'Data Access',
        'rectification': 'Rectification',
        'deletion': 'Deletion / Right to be Forgotten',
        'objection': 'Objection'
    }

    info_view = ui.LayoutView(timeout=None)
    info_container = ui.Container()

    # Title
    info_container.add_item(ui.TextDisplay(f"### {EMOJIS['ticket']} Ticket Information"))

    # Legal request type
    info_container.add_item(ui.TextDisplay(
        f"**Legal Request Type:** {legal_types_names.get(legal_type, legal_type.capitalize())}"
    ))

    info_view.add_item(info_container)
    await thread.send(view=info_view)

    # Save to DB
    await db.create_ticket(thread.id, user.id, "legal_request", metadata)

    await interaction.followup.send(
        f"{EMOJIS['done']} Your ticket has been created, here is the link: {thread.mention}",
        ephemeral=True
    )


async def create_payments_billing_ticket(interaction: discord.Interaction, user: discord.User, metadata: Dict):
    """Creates a payments & billing ticket"""
    # Check if interaction hasn't been responded to yet
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    # Create private thread
    channel = interaction.guild.get_channel(SUPPORT_CHANNEL_ID)
    if not channel:
        await interaction.followup.send(
            f"{EMOJIS['undone']} Support channel not found.",
            ephemeral=True
        )
        return

    # Nom du thread
    thread_name = f"Payments & Billing - {user.name}"

    # Create thread
    thread = await channel.create_thread(
        name=thread_name,
        type=discord.ChannelType.private_thread,
        auto_archive_duration=10080  # 7 days
    )

    # Update thread status indicator (unclaimed)
    await update_thread_status_indicator(thread, 'unclaimed')

    # Add user to thread
    await thread.add_user(user)

    # Main message avec boutons (Components V2)
    mentions = f"<@&{ROLES['MANAGER']}> <@&{ROLES['SUPERVISOR']}> {user.mention}"
    view = TicketControlView(thread.id, "payments_billing", user, EMOJIS['payments'], "New Ticket - Payments & Billing", mentions, bot=interaction.client)
    interaction.client.add_view(view)
    await thread.send(view=view)

    # Message with information (Components V2)
    info_view = ui.LayoutView(timeout=None)
    info_container = ui.Container()

    # Title
    info_container.add_item(ui.TextDisplay(f"### {EMOJIS['ticket']} Ticket Information"))

    # Basic info
    info_container.add_item(ui.TextDisplay(
        f"**Category:** Payments & Billing\n"
        f"-# Please provide details about your payment or billing inquiry"
    ))

    info_view.add_item(info_container)
    await thread.send(view=info_view)

    # Save to DB
    await db.create_ticket(thread.id, user.id, "payments_billing", metadata)

    await interaction.followup.send(
        f"{EMOJIS['done']} Your ticket has been created, here is the link: {thread.mention}",
        ephemeral=True
    )


async def create_other_request_ticket(interaction: discord.Interaction, user: discord.User, metadata: Dict):
    """Creates an other request ticket"""
    # Check if interaction hasn't been responded to yet
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    # Create private thread
    channel = interaction.guild.get_channel(SUPPORT_CHANNEL_ID)
    if not channel:
        await interaction.followup.send(
            f"{EMOJIS['undone']} Support channel not found.",
            ephemeral=True
        )
        return

    # Nom du thread
    thread_name = f"Other Request - {user.name}"

    # Create thread
    thread = await channel.create_thread(
        name=thread_name,
        type=discord.ChannelType.private_thread,
        auto_archive_duration=10080  # 7 days
    )

    # Update thread status indicator (unclaimed)
    await update_thread_status_indicator(thread, 'unclaimed')

    # Add user to thread
    await thread.add_user(user)

    # Main message avec boutons (Components V2)
    mentions = f"<@&{ROLES['SUPPORT_AGENT']}> {user.mention}"
    view = TicketControlView(thread.id, "other_request", user, EMOJIS['question_mark'], "New Ticket - Other Request", mentions, bot=interaction.client)
    interaction.client.add_view(view)
    await thread.send(view=view)

    # Message with information (Components V2)
    info_view = ui.LayoutView(timeout=None)
    info_container = ui.Container()

    # Title
    info_container.add_item(ui.TextDisplay(f"### {EMOJIS['ticket']} Ticket Information"))

    # Basic info
    info_container.add_item(ui.TextDisplay(
        f"**Category:** Other Request\n"
        f"-# Please describe your request in detail"
    ))

    info_view.add_item(info_container)
    await thread.send(view=info_view)

    # Save to DB
    await db.create_ticket(thread.id, user.id, "other_request", metadata)

    await interaction.followup.send(
        f"{EMOJIS['done']} Your ticket has been created, here is the link: {thread.mention}",
        ephemeral=True
    )


class Tickets(commands.Cog):
    """Système de tickets pour Moddy Support"""

    def __init__(self, bot):
        self.bot = bot
        self.support_panel_view = SupportPanelView()

    async def cog_load(self):
        """Appelé quand le cog est chargé"""
        # Connecter à la base de données
        await db.connect()

        # Register persistent views
        self.bot.add_view(self.support_panel_view)
        logger.info("✅ Registered persistent SupportPanelView")

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

        # Check si c'est dans le bon salon
        if message.channel.id != SUPPORT_CHANNEL_ID:
            return

        # Check si c'est la commande !tickets
        if message.content.strip() == '!tickets':
            # Check si l'utilisateur est un staff
            staff_info = await db.get_staff_info(message.author.id)

            if not staff_info:
                await message.reply(
                    f"{EMOJIS['undone']} You do not have permission to use this command.",
                    delete_after=5
                )
                return

            # Delete command message
            try:
                await message.delete()
            except:
                pass

            # Send support panel
            await message.channel.send(view=self.support_panel_view)

    @commands.command(name='archiverequest')
    async def archive_request(self, ctx: commands.Context):
        """Command pour demander l'archivage d'un ticket"""
        # Check si c'est dans un thread
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.reply(
                f"{EMOJIS['undone']} This command can only be used in a ticket thread.",
                delete_after=5
            )
            return

        # Check si l'utilisateur est un staff
        staff_info = await db.get_staff_info(ctx.author.id)

        if not staff_info:
            await ctx.reply(
                f"{EMOJIS['undone']} You do not have permission to use this command.",
                delete_after=5
            )
            return

        # Retrieve le ticket
        ticket = await db.get_ticket(ctx.channel.id)

        if not ticket:
            await ctx.reply(
                f"{EMOJIS['undone']} This thread is not a valid ticket.",
                delete_after=5
            )
            return

        # Check les permissions
        staff_roles = get_staff_roles(staff_info)
        if not can_manage_ticket(staff_roles, ticket['category']):
            await ctx.reply(
                f"{EMOJIS['undone']} You do not have permission to manage this type of ticket.",
                delete_after=5
            )
            return

        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        # Update thread status indicator to archive_request
        if isinstance(ctx.channel, discord.Thread):
            try:
                await update_thread_status_indicator(ctx.channel, 'archive_request')
            except Exception as e:
                logger.warning(f"Could not update thread status indicator (rate limit?): {e}")

        # Get ticket user
        ticket_user = ctx.guild.get_member(ticket['user_id']) or await ctx.guild.fetch_member(ticket['user_id'])

        # Send archive request (Components V2 - no content parameter)
        view = ArchiveRequestView(ctx.channel.id, ticket_user)
        await ctx.send(view=view)

    @commands.command(name='unarchive')
    async def unarchive_ticket_command(self, ctx: commands.Context):
        """Command to unarchive a ticket"""
        # Check if it's in a thread
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.reply(
                f"{EMOJIS['undone']} This command can only be used in a ticket thread.",
                delete_after=5
            )
            return

        # Check if user is staff
        staff_info = await db.get_staff_info(ctx.author.id)

        if not staff_info:
            await ctx.reply(
                f"{EMOJIS['undone']} You do not have permission to use this command.",
                delete_after=5
            )
            return

        # Retrieve ticket
        ticket = await db.get_ticket(ctx.channel.id)

        if not ticket:
            await ctx.reply(
                f"{EMOJIS['undone']} This thread is not a valid ticket.",
                delete_after=5
            )
            return

        # Check permissions
        staff_roles = get_staff_roles(staff_info)
        if not can_manage_ticket(staff_roles, ticket['category']):
            await ctx.reply(
                f"{EMOJIS['undone']} You do not have permission to manage this type of ticket.",
                delete_after=5
            )
            return

        # Unarchive ticket in DB
        await db.unarchive_ticket(ctx.channel.id)

        # Unlock and unarchive thread
        thread = ctx.channel
        await thread.edit(archived=False, locked=False)

        # Update thread status indicator
        status = 'claimed' if ticket['claimed_by'] else 'unclaimed'
        await update_thread_status_indicator(thread, status)

        # Delete command message
        try:
            await ctx.message.delete()
        except:
            pass

        await ctx.send(f"{EMOJIS['done']} Ticket has been unarchived successfully.")


async def setup(bot):
    await bot.add_cog(Tickets(bot))
