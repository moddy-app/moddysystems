import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
from typing import Optional, List, Dict, Literal
from datetime import datetime, timedelta
import re
import json
import os
import asyncio
from enum import Enum

# Channel ID for status updates
STATUS_CHANNEL_ID = 1398625686301704323


# Status configurations
class IncidentStatus(Enum):
    ONGOING = ("ongoing", "<:rstatus:1424029736048267317>", "Ongoing")
    INVESTIGATING = ("investigating", "<:ystatus:1424029739496112200>", "Investigating")
    IDENTIFIED = ("identified", "<:ystatus:1424029739496112200>", "Identified")
    MONITORING = ("monitoring", "<:ystatus:1424029739496112200>", "Monitoring")
    PARTIALLY_RESOLVED = ("partially_resolved", "<:ystatus:1424029739496112200>", "Partially Resolved")
    REMAINS_UNSTABLE = ("remains_unstable", "<:ystatus:1424029739496112200>", "Remains Unstable")
    KNOWN_ISSUES = ("known_issues", "<:ystatus:1424029739496112200>", "Known Issues")
    RESOLVED = ("resolved", "<:ystatus:1424029739496112200>", "Resolved")


class MaintenanceStatus(Enum):
    SCHEDULED = ("scheduled", "<:ystatus:1424029739496112200>", "Scheduled")
    IN_PROGRESS = ("in_progress", "<:rstatus:1424029736048267317>", "In Progress")
    EXTENDED = ("extended", "<:ystatus:1424029739496112200>", "Extended")
    PARTIALLY_COMPLETE = ("partially_complete", "<:ystatus:1424029739496112200>", "Partially Complete")
    COMPLETED = ("completed", "<:gstatus:1424029737977778206>", "Completed")
    CANCELLED = ("cancelled", "<:gstatus:1424029737977778206>", "Cancelled")


# Severity levels for incidents
class Severity(Enum):
    CRITICAL = "Critical"
    MAJOR = "Major"
    MINOR = "Minor"
    LOW = "Low"


def get_status_emoji_and_text(status_value: str, is_maintenance: bool = False) -> tuple:
    """Get the appropriate emoji and text for a status"""
    if is_maintenance:
        for status in MaintenanceStatus:
            if status.value[0] == status_value.lower():
                return status.value[1], status.value[2]
        return MaintenanceStatus.SCHEDULED.value[1], "Unknown"
    else:
        for status in IncidentStatus:
            if status.value[0] == status_value.lower():
                return status.value[1], status.value[2]
        return IncidentStatus.ONGOING.value[1], "Unknown"


def format_duration(start_timestamp: int, end_timestamp: Optional[int] = None) -> str:
    """Format duration between two timestamps"""
    if end_timestamp is None:
        end_timestamp = int(datetime.now().timestamp())

    duration = end_timestamp - start_timestamp
    hours = duration // 3600
    minutes = (duration % 3600) // 60

    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


class IncidentModal(ui.Modal):
    def __init__(self):
        super().__init__(title="Create Incident Report")

        self.title_input = ui.TextInput(
            label="Incident Title",
            placeholder="e.g., Moddy Offline / Not working",
            required=True,
            max_length=100
        )

        self.issue = ui.TextInput(
            label="Issue Description",
            placeholder="Detailed description of the issue...",
            style=discord.TextStyle.long,
            required=True,
            max_length=1000
        )

        self.services = ui.TextInput(
            label="Affected Services",
            placeholder="e.g., Moddy Bot, Dashboard, API",
            required=True,
            max_length=200
        )

        self.severity = ui.TextInput(
            label="Severity (Critical/Major/Minor/Low)",
            placeholder="Critical",
            required=True,
            max_length=20,
            default="Major"
        )

        self.eta = ui.TextInput(
            label="ETA (Estimated Time to Resolution)",
            placeholder="e.g., 2 hours, 30 minutes, TBD",
            required=True,
            max_length=100,
            default="TBD"
        )

        self.add_item(self.title_input)
        self.add_item(self.issue)
        self.add_item(self.services)
        self.add_item(self.severity)
        self.add_item(self.eta)

    async def on_submit(self, interaction: discord.Interaction):
        # Defer the response as we need to show another view
        await interaction.response.defer(ephemeral=True)

        # Store the incident data temporarily
        self.incident_data = {
            'title': self.title_input.value,
            'issue': self.issue.value,
            'services': self.services.value,
            'severity': self.severity.value.capitalize(),
            'eta': self.eta.value,
            'status': 'investigating',
            'start_time': int(datetime.now().timestamp())
        }

        # Show the mentions selection view
        view = MentionsView(self.incident_data, 'incident')
        await interaction.followup.send(
            "**Select mentions for this incident:**",
            view=view,
            ephemeral=True
        )


class MaintenanceModal(ui.Modal):
    def __init__(self):
        super().__init__(title="Schedule Maintenance")

        self.title_input = ui.TextInput(
            label="Maintenance Title",
            placeholder="e.g., Database Optimization",
            required=True,
            max_length=100
        )

        self.description = ui.TextInput(
            label="Description",
            placeholder="Detailed description of the maintenance...",
            style=discord.TextStyle.long,
            required=True,
            max_length=1000
        )

        self.services = ui.TextInput(
            label="Affected Services",
            placeholder="e.g., Moddy Bot, Dashboard, API",
            required=True,
            max_length=200
        )

        self.scheduled_time = ui.TextInput(
            label="Scheduled Time (Unix Timestamp)",
            placeholder=str(int((datetime.now() + timedelta(days=1)).timestamp())),
            required=True,
            max_length=20,
            default=str(int((datetime.now() + timedelta(days=1)).timestamp()))
        )

        self.duration = ui.TextInput(
            label="Expected Duration",
            placeholder="e.g., 2 hours, 30 minutes",
            required=True,
            max_length=50
        )

        self.add_item(self.title_input)
        self.add_item(self.description)
        self.add_item(self.services)
        self.add_item(self.scheduled_time)
        self.add_item(self.duration)

    async def on_submit(self, interaction: discord.Interaction):
        # Defer the response
        await interaction.response.defer(ephemeral=True)

        # Store the maintenance data
        self.maintenance_data = {
            'title': self.title_input.value,
            'description': self.description.value,
            'services': self.services.value,
            'scheduled_time': self.scheduled_time.value,
            'duration': self.duration.value,
            'status': 'scheduled',
            'type': 'maintenance'
        }

        # Show the mentions selection view
        view = MentionsView(self.maintenance_data, 'maintenance')
        await interaction.followup.send(
            "**Select mentions for this maintenance:**",
            view=view,
            ephemeral=True
        )


class MentionsView(discord.ui.View):
    def __init__(self, data: dict, report_type: str):
        super().__init__(timeout=60)
        self.data = data
        self.report_type = report_type
        self.mentions = []
        self.status_link = None

    @discord.ui.button(label="@everyone", style=discord.ButtonStyle.danger, emoji="📢")
    async def everyone_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if "@everyone" in self.mentions:
            self.mentions.remove("@everyone")
            button.style = discord.ButtonStyle.secondary
        else:
            self.mentions.append("@everyone")
            button.style = discord.ButtonStyle.danger
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="@here", style=discord.ButtonStyle.primary, emoji="📍")
    async def here_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if "@here" in self.mentions:
            self.mentions.remove("@here")
            button.style = discord.ButtonStyle.secondary
        else:
            self.mentions.append("@here")
            button.style = discord.ButtonStyle.primary
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Add Status Link", style=discord.ButtonStyle.secondary, emoji="🔗")
    async def status_link_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = StatusLinkModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Add Role Mention", style=discord.ButtonStyle.secondary, emoji="👥")
    async def role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RoleMentionModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Send Report", style=discord.ButtonStyle.success, emoji="✅", row=1)
    async def send_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.send_report(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌", row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Report cancelled.", view=None)
        self.stop()

    async def send_report(self, interaction: discord.Interaction):
        # Get the status channel
        channel = interaction.client.get_channel(STATUS_CHANNEL_ID)
        if not channel:
            await interaction.response.edit_message(
                content="❌ Status channel not found!",
                view=None
            )
            return

        # Create the V2 components view
        view = ui.LayoutView()
        container = ui.Container()

        if self.report_type == 'incident':
            # Get status emoji and text
            emoji, status_text = get_status_emoji_and_text(self.data['status'])

            # Title with status
            title_text = f"{emoji} **{self.data['title']} — {status_text}**"

            # Build the main content
            content_parts = [
                title_text,
                f"* **Issue:** {self.data['issue']}",
                f"* **Type:** `Incident`",
                f"* **Severity:** `{self.data['severity']}`",
                f"* **Affected services:** `{self.data['services']}`",
                f"* **Status:** `{status_text}`",
                f"* **ETA:** `{self.data['eta']}`",
                f"* **Started:** <t:{self.data['start_time']}:F>"
            ]
        else:
            # Maintenance
            emoji, status_text = get_status_emoji_and_text(self.data['status'], True)

            title_text = f"{emoji} **Scheduled Maintenance: {self.data['title']}**"

            content_parts = [
                title_text,
                f"* **Description:** {self.data['description']}",
                f"* **Type:** `Maintenance`",
                f"* **Affected services:** `{self.data['services']}`",
                f"* **Status:** `{status_text}`",
                f"* **Scheduled time:** <t:{self.data['scheduled_time']}:F> (<t:{self.data['scheduled_time']}:R>)",
                f"* **Expected duration:** `{self.data['duration']}`"
            ]

        if self.status_link:
            content_parts.append(f"* **Status link:** {self.status_link}")

        # Add status ID
        status_id = f"{datetime.now().strftime('%Y%m%d')}{int(datetime.now().timestamp()) % 10000:04d}"
        content_parts.append(f"* **Status ID:** `#{status_id}`")

        container.add_item(ui.TextDisplay('\n'.join(content_parts)))

        # Separator
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        # Updates section
        container.add_item(ui.TextDisplay("*Updates will be edited in this message*"))

        # Build mention string for actual pings
        mention_string = " ".join(self.mentions) if self.mentions else ""

        # Footer with mentions
        if self.mentions:
            # To support V2 components, mentions must be in the view content, not the message content field.
            # We add the raw mention string to the view for the ping to work.
            container.add_item(ui.TextDisplay(mention_string))

            mentions_text = " / ".join(self.mentions)
            container.add_item(ui.TextDisplay(f"-# {mentions_text}"))
        else:
            container.add_item(ui.TextDisplay("-# Status updates"))

        view.add_item(container)

        # Prepare allowed mentions
        allowed_mentions = discord.AllowedMentions(
            everyone="@everyone" in self.mentions,
            roles=True if any("<@&" in m for m in self.mentions) else False
        )

        # Send the message
        try:
            message = await channel.send(
                view=view,
                allowed_mentions=allowed_mentions
            )

            # Store incident data
            self.data['updates'] = []
            self.data['type'] = self.report_type
            self.data['status_link'] = self.status_link
            self.data['mentions'] = self.mentions
            self.data['status_id'] = status_id

            # Save to JSON
            incidents = {}
            if os.path.exists('incidents.json'):
                with open('incidents.json', 'r') as f:
                    incidents = json.load(f)

            incidents[str(message.id)] = self.data

            with open('incidents.json', 'w') as f:
                json.dump(incidents, f, indent=2)

            await interaction.response.edit_message(
                content=f"✅ {self.report_type.capitalize()} created successfully!\n"
                        f"**Message ID:** `{message.id}`\n"
                        f"**Status ID:** `#{status_id}`\n"
                        f"**Channel:** {channel.mention}",
                view=None
            )

            # Pin the message if it's an active incident
            if self.report_type == 'incident':
                await message.pin()
                print(f"Pinned new incident {message.id}")

        except Exception as e:
            await interaction.response.edit_message(
                content=f"❌ Error: {e}",
                view=None
            )


class StatusLinkModal(ui.Modal):
    def __init__(self, parent_view: MentionsView):
        super().__init__(title="Add Status Link")
        self.parent_view = parent_view

        self.link = ui.TextInput(
            label="Status Page Link",
            placeholder="e.g., moddy.app/status/989009",
            required=True,
            max_length=200
        )

        self.add_item(self.link)

    async def on_submit(self, interaction: discord.Interaction):
        self.parent_view.status_link = self.link.value

        # Update the button to show it's been added
        for item in self.parent_view.children:
            if hasattr(item, 'label') and item.label == "Add Status Link":
                item.label = "✅ Status Link Added"
                item.style = discord.ButtonStyle.success
                break

        await interaction.response.edit_message(view=self.parent_view)


class RoleMentionModal(ui.Modal):
    def __init__(self, parent_view: MentionsView):
        super().__init__(title="Add Role Mention")
        self.parent_view = parent_view

        self.role_id = ui.TextInput(
            label="Role ID",
            placeholder="e.g., 1424466344832925847",
            required=True,
            max_length=30
        )

        self.add_item(self.role_id)

    async def on_submit(self, interaction: discord.Interaction):
        role_mention = f"<@&{self.role_id.value}>"
        if role_mention not in self.parent_view.mentions:
            self.parent_view.mentions.append(role_mention)

        await interaction.response.edit_message(view=self.parent_view)


class UpdateModal(ui.Modal):
    def __init__(self, message_id: str):
        super().__init__(title="Add Update")
        self.message_id = message_id

        self.description = ui.TextInput(
            label="Update Description",
            placeholder="Describe the update...",
            style=discord.TextStyle.long,
            required=True,
            max_length=500
        )

        # Load current incident to show status options
        incident = {}
        if os.path.exists('incidents.json'):
            with open('incidents.json', 'r') as f:
                incidents = json.load(f)
                incident = incidents.get(message_id, {})

        status_placeholder = "investigating/monitoring/resolved" if incident.get(
            'type') == 'incident' else "in_progress/completed"

        self.new_status = ui.TextInput(
            label="New Status (optional)",
            placeholder=status_placeholder,
            required=False,
            max_length=50
        )

        self.eta = ui.TextInput(
            label="Updated ETA (optional)",
            placeholder="e.g., 1 hour, Resolved, TBD",
            required=False,
            max_length=100
        )

        self.timestamp = ui.TextInput(
            label="Timestamp (Unix)",
            placeholder="Leave empty for now",
            default=str(int(datetime.now().timestamp())),
            required=False,
            max_length=20
        )

        self.add_item(self.description)
        self.add_item(self.new_status)
        self.add_item(self.eta)
        self.add_item(self.timestamp)

    async def on_submit(self, interaction: discord.Interaction):
        # Load incident data
        incidents = {}
        if os.path.exists('incidents.json'):
            with open('incidents.json', 'r') as f:
                incidents = json.load(f)

        if self.message_id not in incidents:
            await interaction.response.send_message("❌ Report not found!", ephemeral=True)
            return

        incident = incidents[self.message_id]

        # Update status if provided
        if self.new_status.value:
            incident['status'] = self.new_status.value.lower().replace(" ", "_")

        # Add the update
        timestamp = self.timestamp.value or str(int(datetime.now().timestamp()))
        update = {
            'description': self.description.value,
            'timestamp': timestamp,
            'number': len(incident['updates']) + 1,
            'status': incident['status']
        }

        # Update ETA if provided
        if self.eta.value:
            incident['eta'] = self.eta.value

        incident['updates'].append(update)

        # Sort updates by timestamp
        incident['updates'].sort(key=lambda x: int(x['timestamp']))

        # Re-number updates after sorting
        for i, upd in enumerate(incident['updates'], 1):
            upd['number'] = i

        # Save data
        incidents[self.message_id] = incident
        with open('incidents.json', 'w') as f:
            json.dump(incidents, f, indent=2)

        # Update the message
        await self.update_message(interaction, incident)

    async def update_message(self, interaction: discord.Interaction, incident: dict):
        # Get the message
        channel = interaction.client.get_channel(STATUS_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
            return

        try:
            message = await channel.fetch_message(int(self.message_id))
        except:
            await interaction.response.send_message("❌ Message not found!", ephemeral=True)
            return

        # Recreate the view with updates
        view = ui.LayoutView()
        container = ui.Container()

        is_maintenance = incident.get('type') == 'maintenance'

        # Get status emoji and text
        emoji, status_text = get_status_emoji_and_text(incident['status'], is_maintenance)

        if not is_maintenance:
            # Calculate duration if resolved
            duration_text = ""
            if incident['status'] == 'resolved' and incident.get('start_time'):
                duration = format_duration(incident['start_time'])
                duration_text = f" (Duration: {duration})"

            # Title with status
            title_text = f"{emoji} **{incident['title']} — {status_text}**{duration_text}"

            content_parts = [
                title_text,
                f"* **Issue:** {incident['issue']}",
                f"* **Type:** `Incident`",
                f"* **Severity:** `{incident.get('severity', 'Major')}`",
                f"* **Affected services:** `{incident['services']}`",
                f"* **Status:** `{status_text}`",
                f"* **ETA:** `{incident.get('eta', 'TBD')}`",
                f"* **Started:** <t:{incident['start_time']}:F>"
            ]
        else:
            # Maintenance
            title_text = f"{emoji} **Maintenance: {incident['title']}**"
            if incident['status'] == 'completed':
                title_text = f"{emoji} **Maintenance: {incident['title']} — Completed**"

            content_parts = [
                title_text,
                f"* **Description:** {incident['description']}",
                f"* **Type:** `Maintenance`",
                f"* **Affected services:** `{incident['services']}`",
                f"* **Status:** `{status_text}`"
            ]

            if incident.get('scheduled_time'):
                content_parts.append(f"* **Scheduled time:** <t:{incident['scheduled_time']}:F>")
            if incident.get('duration'):
                content_parts.append(f"* **Expected duration:** `{incident['duration']}`")

        if incident.get('status_link'):
            content_parts.append(f"* **Status link:** {incident['status_link']}")

        if incident.get('status_id'):
            content_parts.append(f"* **Status ID:** `#{incident['status_id']}`")

        container.add_item(ui.TextDisplay('\n'.join(content_parts)))

        # Separator
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        # Add updates
        if incident['updates']:
            update_texts = []
            for upd in incident['updates']:
                upd_status = upd.get('status', incident['status'])
                upd_emoji, upd_status_text = get_status_emoji_and_text(upd_status, is_maintenance)
                update_texts.append(
                    f"> {upd_emoji} **Update {upd['number']} — {upd_status_text}, <t:{upd['timestamp']}:R>:**\n"
                    f"> {upd['description']}"
                )
            container.add_item(ui.TextDisplay('\n'.join(update_texts)))

            # Add separator before footer
            container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        # Footer
        container.add_item(ui.TextDisplay("*Updates will be edited in this message*"))

        if incident.get('mentions'):
            mentions_text = " / ".join(incident['mentions'])
            container.add_item(ui.TextDisplay(f"-# {mentions_text}"))

        view.add_item(container)

        # Edit the message
        await message.edit(view=view)

        # Manage pin status based on incident status
        cog = interaction.client.get_cog('Status')
        if cog:
            await cog.pin_incident_message(message, incident)

        # Send confirmation with update summary
        embed = discord.Embed(
            title="✅ Update Added Successfully",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="Update #", value=str(len(incident['updates'])), inline=True)
        embed.add_field(name="New Status", value=status_text, inline=True)
        embed.add_field(name="Message ID", value=f"`{self.message_id}`", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


class Status(commands.Cog):
    """Professional status management for incidents and maintenance"""

    def __init__(self, bot):
        self.bot = bot
        self.auto_update.start()
        # Load and sync incidents on startup
        self.bot.loop.create_task(self.sync_incidents_on_startup())

    def cog_unload(self):
        self.auto_update.cancel()

    async def sync_incidents_on_startup(self):
        """Sync all incidents from the status channel on bot startup"""
        await self.bot.wait_until_ready()

        channel = self.bot.get_channel(STATUS_CHANNEL_ID)
        if not channel:
            print(f"Warning: Status channel {STATUS_CHANNEL_ID} not found")
            return

        print(f"Syncing incidents from channel {channel.name}...")

        # Load existing incidents file
        incidents = {}
        if os.path.exists('incidents.json'):
            with open('incidents.json', 'r') as f:
                incidents = json.load(f)

        # Get all pinned messages to track active incidents
        try:
            pinned_messages = await channel.pins()
            pinned_ids = {str(msg.id) for msg in pinned_messages}

            # Update status of incidents based on pin status
            for msg_id in list(incidents.keys()):
                if msg_id in pinned_ids:
                    # Message is pinned, ensure it's not marked as resolved
                    if incidents[msg_id].get('status') == 'resolved':
                        print(f"Warning: Incident {msg_id} is pinned but marked as resolved")
                else:
                    # Message is not pinned, check if it should be
                    if incidents[msg_id].get('status') not in ['resolved', 'completed', 'cancelled']:
                        try:
                            message = await channel.fetch_message(int(msg_id))
                            if message:
                                await message.pin()
                                print(f"Re-pinned active incident {msg_id}")
                        except:
                            print(f"Could not find or pin message {msg_id}")

            # Scan recent messages for any incidents not in our database
            async for message in channel.history(limit=100):
                msg_id = str(message.id)

                # Check if this is an incident/maintenance message by looking for our format
                if message.author == self.bot.user and msg_id not in incidents:
                    # Check if message contains incident markers
                    content = message.content if message.content else ""

                    # Try to parse the message view
                    if hasattr(message, 'components') and message.components:
                        # This is likely one of our status messages
                        print(f"Found orphaned status message {msg_id}, adding to database")

                        # Create a basic incident record
                        is_pinned = message.pinned
                        incident_data = {
                            'title': 'Recovered Incident',
                            'status': 'ongoing' if is_pinned else 'resolved',
                            'type': 'incident',
                            'services': 'Unknown',
                            'updates': [],
                            'recovered': True,
                            'message_id': msg_id
                        }
                        incidents[msg_id] = incident_data

            # Save updated incidents
            with open('incidents.json', 'w') as f:
                json.dump(incidents, f, indent=2)

            print(f"Incident sync complete. Tracking {len(incidents)} incidents/maintenances")

        except Exception as e:
            print(f"Error during incident sync: {e}")

    async def pin_incident_message(self, message: discord.Message, incident: dict):
        """Pin or unpin a message based on incident status"""
        try:
            is_active = incident['status'] not in ['resolved', 'completed', 'cancelled']

            if is_active and not message.pinned:
                await message.pin()
                print(f"Pinned incident message {message.id}")
            elif not is_active and message.pinned:
                await message.unpin()
                print(f"Unpinned resolved incident message {message.id}")
        except discord.HTTPException as e:
            print(f"Could not manage pin for message {message.id}: {e}")

    @tasks.loop(minutes=5)
    async def auto_update(self):
        """Auto-update incident durations"""
        if not os.path.exists('incidents.json'):
            return

        with open('incidents.json', 'r') as f:
            incidents = json.load(f)

        channel = self.bot.get_channel(STATUS_CHANNEL_ID)
        if not channel:
            return

        for message_id, incident in incidents.items():
            # Only update ongoing incidents
            if incident.get('type') == 'incident' and incident['status'] not in ['resolved', 'closed']:
                try:
                    message = await channel.fetch_message(int(message_id))
                    # Re-render the message to update relative times
                    modal = UpdateModal(message_id)
                    # This will update the relative timestamps
                except:
                    continue

    @auto_update.before_loop
    async def before_auto_update(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="sync_incidents", description="Manually sync all incidents from the status channel")
    @app_commands.default_permissions(administrator=True)
    async def sync_incidents(self, interaction: discord.Interaction):
        """Manually trigger incident synchronization"""
        await interaction.response.defer(ephemeral=True)

        channel = self.bot.get_channel(STATUS_CHANNEL_ID)
        if not channel:
            await interaction.followup.send("❌ Status channel not found!", ephemeral=True)
            return

        # Load existing incidents
        incidents = {}
        if os.path.exists('incidents.json'):
            with open('incidents.json', 'r') as f:
                incidents = json.load(f)

        synced = 0
        errors = 0

        # Check all messages in incidents.json
        for msg_id in list(incidents.keys()):
            try:
                message = await channel.fetch_message(int(msg_id))
                incident = incidents[msg_id]

                # Update pin status
                is_active = incident['status'] not in ['resolved', 'completed', 'cancelled']

                if is_active and not message.pinned:
                    await message.pin()
                    synced += 1
                elif not is_active and message.pinned:
                    await message.unpin()
                    synced += 1

            except discord.NotFound:
                print(f"Message {msg_id} not found, removing from database")
                del incidents[msg_id]
                errors += 1
            except Exception as e:
                print(f"Error syncing {msg_id}: {e}")
                errors += 1

        # Save updated incidents
        with open('incidents.json', 'w') as f:
            json.dump(incidents, f, indent=2)

        embed = discord.Embed(
            title="✅ Sync Complete",
            description=f"**Synced:** {synced} messages\n**Errors:** {errors}\n**Total tracked:** {len(incidents)}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    incident_group = app_commands.Group(name="incident", description="Incident management commands")
    maintenance_group = app_commands.Group(name="maintenance", description="Maintenance management commands")

    @incident_group.command(name="create", description="Create a new incident report")
    async def incident_create(self, interaction: discord.Interaction):
        """Create a new incident with professional formatting"""
        modal = IncidentModal()
        await interaction.response.send_modal(modal)

    @incident_group.command(name="update", description="Add an update to an incident")
    @app_commands.describe(message_id="The message ID of the incident to update")
    async def incident_update(self, interaction: discord.Interaction, message_id: str):
        """Add an update to an existing incident"""
        modal = UpdateModal(message_id)
        await interaction.response.send_modal(modal)

    @incident_group.command(name="status", description="Quick status change")
    @app_commands.describe(
        message_id="The message ID of the incident",
        status="New status for the incident"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="🔴 Ongoing", value="ongoing"),
        app_commands.Choice(name="🟡 Investigating", value="investigating"),
        app_commands.Choice(name="🟡 Identified", value="identified"),
        app_commands.Choice(name="🟡 Monitoring", value="monitoring"),
        app_commands.Choice(name="🟡 Partially Resolved", value="partially_resolved"),
        app_commands.Choice(name="🟡 Remains Unstable", value="remains_unstable"),
        app_commands.Choice(name="🟡 Known Issues", value="known_issues"),
        app_commands.Choice(name="🟢 Resolved", value="resolved"),
    ])
    async def incident_status(self, interaction: discord.Interaction, message_id: str, status: str):
        """Quick status update without adding an update entry"""
        # Load incident data
        incidents = {}
        if os.path.exists('incidents.json'):
            with open('incidents.json', 'r') as f:
                incidents = json.load(f)

        if message_id not in incidents:
            await interaction.response.send_message("❌ Incident not found!", ephemeral=True)
            return

        incident = incidents[message_id]
        old_status = incident['status']
        incident['status'] = status

        # If resolving, update ETA
        if status == 'resolved':
            incident['eta'] = 'Resolved'

        # Save data
        incidents[message_id] = incident
        with open('incidents.json', 'w') as f:
            json.dump(incidents, f, indent=2)

        # Update the message
        modal = UpdateModal(message_id)
        await modal.update_message(interaction, incident)

    @incident_group.command(name="delete_update", description="Delete an update from an incident")
    @app_commands.describe(
        message_id="The message ID of the incident",
        update_number="The update number to delete"
    )
    async def incident_delete_update(self, interaction: discord.Interaction, message_id: str, update_number: int):
        """Delete a specific update from an incident"""
        # Load incident data
        incidents = {}
        if os.path.exists('incidents.json'):
            with open('incidents.json', 'r') as f:
                incidents = json.load(f)

        if message_id not in incidents:
            await interaction.response.send_message("❌ Incident not found!", ephemeral=True)
            return

        incident = incidents[message_id]

        # Find and remove the update
        if update_number <= 0 or update_number > len(incident['updates']):
            await interaction.response.send_message("❌ Invalid update number!", ephemeral=True)
            return

        # Remove the update
        incident['updates'] = [u for u in incident['updates'] if u['number'] != update_number]

        # Re-number remaining updates
        for i, upd in enumerate(incident['updates'], 1):
            upd['number'] = i

        # Save data
        incidents[message_id] = incident
        with open('incidents.json', 'w') as f:
            json.dump(incidents, f, indent=2)

        # Update the message
        modal = UpdateModal(message_id)
        await modal.update_message(interaction, incident)

    @incident_group.command(name="list", description="List all active incidents")
    async def incident_list(self, interaction: discord.Interaction):
        """List all active incidents with their status"""
        if not os.path.exists('incidents.json'):
            await interaction.response.send_message("📊 No incidents recorded.", ephemeral=True)
            return

        with open('incidents.json', 'r') as f:
            incidents = json.load(f)

        if not incidents:
            await interaction.response.send_message("📊 No incidents recorded.", ephemeral=True)
            return

        # Filter and categorize incidents
        active_incidents = []
        resolved_incidents = []

        for msg_id, incident in incidents.items():
            if incident.get('type') != 'incident':
                continue

            emoji, status_text = get_status_emoji_and_text(incident['status'])
            entry = {
                'id': incident.get('status_id', 'N/A'),
                'title': incident['title'],
                'status': status_text,
                'emoji': emoji,
                'message_id': msg_id,
                'start_time': incident.get('start_time', 0)
            }

            if incident['status'] == 'resolved':
                resolved_incidents.append(entry)
            else:
                active_incidents.append(entry)

        # Sort by start time (newest first)
        active_incidents.sort(key=lambda x: x['start_time'], reverse=True)
        resolved_incidents.sort(key=lambda x: x['start_time'], reverse=True)

        # Create embed
        embed = discord.Embed(
            title="📊 Incident Status Dashboard",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        # Add active incidents
        if active_incidents:
            active_text = []
            for inc in active_incidents[:10]:  # Show max 10
                active_text.append(
                    f"{inc['emoji']} **{inc['title'][:30]}**\n"
                    f"└ ID: `{inc['id']}` | Status: `{inc['status']}`"
                )
            embed.add_field(
                name="🔴 Active Incidents",
                value="\n".join(active_text),
                inline=False
            )
        else:
            embed.add_field(
                name="✅ System Status",
                value="All systems operational",
                inline=False
            )

        # Add recent resolved
        if resolved_incidents:
            resolved_text = []
            for inc in resolved_incidents[:5]:  # Show max 5
                resolved_text.append(f"{inc['emoji']} {inc['title'][:40]}")
            embed.add_field(
                name="📝 Recently Resolved",
                value="\n".join(resolved_text),
                inline=False
            )

        # Add statistics
        total_incidents = len(active_incidents) + len(resolved_incidents)
        embed.set_footer(
            text=f"Total: {total_incidents} | Active: {len(active_incidents)} | Resolved: {len(resolved_incidents)}"
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @maintenance_group.command(name="schedule", description="Schedule a new maintenance")
    async def maintenance_schedule(self, interaction: discord.Interaction):
        """Schedule a new maintenance with professional formatting"""
        modal = MaintenanceModal()
        await interaction.response.send_modal(modal)

    @maintenance_group.command(name="update", description="Add an update to a maintenance")
    @app_commands.describe(message_id="The message ID of the maintenance to update")
    async def maintenance_update(self, interaction: discord.Interaction, message_id: str):
        """Add an update to an existing maintenance"""
        modal = UpdateModal(message_id)
        await interaction.response.send_modal(modal)

    @maintenance_group.command(name="status", description="Quick maintenance status change")
    @app_commands.describe(
        message_id="The message ID of the maintenance",
        status="New status for the maintenance"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="🟡 Scheduled", value="scheduled"),
        app_commands.Choice(name="🔴 In Progress", value="in_progress"),
        app_commands.Choice(name="🟡 Extended", value="extended"),
        app_commands.Choice(name="🟡 Partially Complete", value="partially_complete"),
        app_commands.Choice(name="🟢 Completed", value="completed"),
        app_commands.Choice(name="🟢 Cancelled", value="cancelled"),
    ])
    async def maintenance_status(self, interaction: discord.Interaction, message_id: str, status: str):
        """Quick status update for maintenance"""
        # Load data
        incidents = {}
        if os.path.exists('incidents.json'):
            with open('incidents.json', 'r') as f:
                incidents = json.load(f)

        if message_id not in incidents:
            await interaction.response.send_message("❌ Maintenance not found!", ephemeral=True)
            return

        incident = incidents[message_id]
        incident['status'] = status

        # Save data
        incidents[message_id] = incident
        with open('incidents.json', 'w') as f:
            json.dump(incidents, f, indent=2)

        # Update the message
        modal = UpdateModal(message_id)
        await modal.update_message(interaction, incident)

    @maintenance_group.command(name="complete", description="Mark maintenance as completed")
    @app_commands.describe(
        message_id="The message ID of the maintenance",
        notes="Completion notes"
    )
    async def maintenance_complete(self, interaction: discord.Interaction, message_id: str,
                                   notes: Optional[str] = None):
        """Mark a maintenance as completed with notes"""
        # Load data
        incidents = {}
        if os.path.exists('incidents.json'):
            with open('incidents.json', 'r') as f:
                incidents = json.load(f)

        if message_id not in incidents:
            await interaction.response.send_message("❌ Maintenance not found!", ephemeral=True)
            return

        incident = incidents[message_id]
        incident['status'] = 'completed'

        # Add completion update
        timestamp = str(int(datetime.now().timestamp()))
        completion_text = "**COMPLETED:** Maintenance completed successfully."
        if notes:
            completion_text += f" {notes}"

        update = {
            'description': completion_text,
            'timestamp': timestamp,
            'number': len(incident['updates']) + 1,
            'status': 'completed'
        }
        incident['updates'].append(update)

        # Save data
        incidents[message_id] = incident
        with open('incidents.json', 'w') as f:
            json.dump(incidents, f, indent=2)

        # Update the message
        modal = UpdateModal(message_id)
        await modal.update_message(interaction, incident)

    @maintenance_group.command(name="list", description="List all scheduled maintenances")
    async def maintenance_list(self, interaction: discord.Interaction):
        """List all scheduled and recent maintenances"""
        if not os.path.exists('incidents.json'):
            await interaction.response.send_message("📊 No maintenances recorded.", ephemeral=True)
            return

        with open('incidents.json', 'r') as f:
            incidents = json.load(f)

        if not incidents:
            await interaction.response.send_message("📊 No maintenances recorded.", ephemeral=True)
            return

        # Filter maintenances
        scheduled = []
        completed = []

        for msg_id, incident in incidents.items():
            if incident.get('type') != 'maintenance':
                continue

            emoji, status_text = get_status_emoji_and_text(incident['status'], True)
            entry = {
                'title': incident['title'],
                'status': status_text,
                'emoji': emoji,
                'message_id': msg_id,
                'scheduled_time': int(incident.get('scheduled_time', 0))
            }

            if incident['status'] in ['completed', 'cancelled']:
                completed.append(entry)
            else:
                scheduled.append(entry)

        # Sort by scheduled time
        scheduled.sort(key=lambda x: x['scheduled_time'])
        completed.sort(key=lambda x: x['scheduled_time'], reverse=True)

        # Create embed
        embed = discord.Embed(
            title="🔧 Maintenance Schedule",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )

        # Add scheduled maintenances
        if scheduled:
            sched_text = []
            for maint in scheduled[:10]:
                sched_text.append(
                    f"{maint['emoji']} **{maint['title'][:40]}**\n"
                    f"└ <t:{maint['scheduled_time']}:F>"
                )
            embed.add_field(
                name="📅 Scheduled Maintenances",
                value="\n".join(sched_text),
                inline=False
            )
        else:
            embed.add_field(
                name="📅 Scheduled Maintenances",
                value="No scheduled maintenances",
                inline=False
            )

        # Add recent completed
        if completed:
            comp_text = []
            for maint in completed[:5]:
                comp_text.append(f"{maint['emoji']} {maint['title'][:40]}")
            embed.add_field(
                name="✅ Recently Completed",
                value="\n".join(comp_text),
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Admin command to export incident data
    @app_commands.command(name="export_incidents", description="Export all incident data")
    @app_commands.default_permissions(administrator=True)
    async def export_incidents(self, interaction: discord.Interaction):
        """Export all incident data as a file"""
        if not os.path.exists('incidents.json'):
            await interaction.response.send_message("❌ No data to export.", ephemeral=True)
            return

        with open('incidents.json', 'rb') as f:
            file = discord.File(f, filename=f"incidents_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

        await interaction.response.send_message(
            "📊 **Incident Data Export**\nHere's the complete incident database:",
            file=file,
            ephemeral=True
        )

    # Statistics command
    @app_commands.command(name="incident_stats", description="View incident statistics")
    async def incident_stats(self, interaction: discord.Interaction):
        """Display incident statistics"""
        if not os.path.exists('incidents.json'):
            await interaction.response.send_message("📊 No statistics available.", ephemeral=True)
            return

        with open('incidents.json', 'r') as f:
            incidents = json.load(f)

        # Calculate statistics
        total_incidents = 0
        total_maintenances = 0
        avg_resolution_time = []
        severity_count = {'Critical': 0, 'Major': 0, 'Minor': 0, 'Low': 0}

        for incident in incidents.values():
            if incident.get('type') == 'incident':
                total_incidents += 1
                if incident.get('severity'):
                    severity_count[incident['severity']] = severity_count.get(incident['severity'], 0) + 1

                # Calculate resolution time if resolved
                if incident.get('status') == 'resolved' and incident.get('start_time'):
                    if incident.get('resolution_time'):
                        resolution_time = incident['resolution_time'] - incident['start_time']
                        avg_resolution_time.append(resolution_time)
            elif incident.get('type') == 'maintenance':
                total_maintenances += 1

        # Create statistics embed
        embed = discord.Embed(
            title="📊 Incident & Maintenance Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        # Overall stats
        embed.add_field(
            name="📈 Overall",
            value=f"**Total Incidents:** {total_incidents}\n**Total Maintenances:** {total_maintenances}",
            inline=True
        )

        # Severity breakdown
        severity_text = "\n".join([f"**{sev}:** {count}" for sev, count in severity_count.items() if count > 0])
        embed.add_field(
            name="⚠️ Severity Breakdown",
            value=severity_text or "No data",
            inline=True
        )

        # Average resolution time
        if avg_resolution_time:
            avg_time = sum(avg_resolution_time) / len(avg_resolution_time)
            hours = int(avg_time // 3600)
            minutes = int((avg_time % 3600) // 60)
            embed.add_field(
                name="⏱️ Avg Resolution Time",
                value=f"{hours}h {minutes}m",
                inline=True
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @incident_group.command(name="resolve", description="Mark an incident as resolved")
    @app_commands.describe(
        message_id="The message ID of the incident to resolve",
        resolution="Resolution description"
    )
    async def incident_resolve(self, interaction: discord.Interaction, message_id: str, resolution: str):
        """Mark an incident as resolved with a resolution message"""
        # Load incident data
        incidents = {}
        if os.path.exists('incidents.json'):
            with open('incidents.json', 'r') as f:
                incidents = json.load(f)

        if message_id not in incidents:
            await interaction.response.send_message("❌ Incident not found!", ephemeral=True)
            return

        incident = incidents[message_id]
        incident['status'] = 'resolved'
        incident['eta'] = 'Resolved'

        # Add resolution update
        timestamp = str(int(datetime.now().timestamp()))
        update = {
            'description': f"**RESOLVED:** {resolution}",
            'timestamp': timestamp,
            'number': len(incident['updates']) + 1,
            'status': 'resolved'
        }
        incident['updates'].append(update)

        # Calculate and add duration
        if incident.get('start_time'):
            duration = format_duration(incident['start_time'])
            incident['resolution_time'] = int(datetime.now().timestamp())
            incident['total_duration'] = duration

        # Save data
        incidents[message_id] = incident
        with open('incidents.json', 'w') as f:
            json.dump(incidents, f, indent=2)

        # Update the message
        modal = UpdateModal(message_id)
        await modal.update_message(interaction, incident)


async def setup(bot):
    """Setup function to load the cog"""
    await bot.add_cog(Status(bot))