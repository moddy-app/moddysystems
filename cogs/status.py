import discord
from discord import app_commands, ui
from discord.ext import commands
from typing import Optional, List, Dict
from datetime import datetime
import re
import json
import os

# Channel ID for status updates
STATUS_CHANNEL_ID = 1398625686301704323

# Status emojis
STATUS_EMOJIS = {
    'resolved': '<:gstatus:1424029737977778206>',  # Green
    'monitoring': '<:ystatus:1424029739496112200>',  # Orange
    'investigating': '<:ystatus:1424029739496112200>',  # Orange
    'identified': '<:ystatus:1424029739496112200>',  # Orange
    'ongoing': '<:rstatus:1424029736048267317>',  # Red
    'scheduled': '<:ystatus:1424029739496112200>',  # Orange for maintenance
    'in_progress': '<:rstatus:1424029736048267317>',  # Red for maintenance
    'completed': '<:gstatus:1424029737977778206>',  # Green for maintenance
}


class IncidentModal(ui.Modal):
    def __init__(self):
        super().__init__(title="Create Incident")

        self.title_input = ui.TextInput(
            label="Incident Title",
            placeholder="e.g., Moddy Offline / Not working",
            required=True,
            max_length=100
        )

        self.issue = ui.TextInput(
            label="Issue Description",
            placeholder="Describe the issue...",
            style=discord.TextStyle.long,
            required=True,
            max_length=1000
        )

        self.services = ui.TextInput(
            label="Affected Services",
            placeholder="e.g., Moddy Bot, Dashboard",
            required=True,
            max_length=200
        )

        self.status = ui.TextInput(
            label="Status",
            placeholder="ongoing/investigating/identified/monitoring/resolved",
            required=True,
            max_length=50,
            default="investigating"
        )

        self.status_link = ui.TextInput(
            label="Status Link (optional)",
            placeholder="e.g., moddy.app/status/989009",
            required=False,
            max_length=200
        )

        self.add_item(self.title_input)
        self.add_item(self.issue)
        self.add_item(self.services)
        self.add_item(self.status)
        self.add_item(self.status_link)

    async def on_submit(self, interaction: discord.Interaction):
        # Get the status channel
        channel = interaction.client.get_channel(STATUS_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("❌ Status channel not found!", ephemeral=True)
            return

        # Get the appropriate emoji based on status
        status_lower = self.status.value.lower()
        emoji = STATUS_EMOJIS.get(status_lower, STATUS_EMOJIS['ongoing'])

        # Determine ETA based on status
        eta = "TBD" if status_lower in ['ongoing', 'investigating'] else status_lower.title()

        # Create the V2 components view
        view = ui.LayoutView()
        container = ui.Container()

        # Title with status emoji
        title_text = f"{emoji} **{self.title_input.value}**"
        if status_lower == 'resolved':
            title_text = f"{emoji} **{self.title_input.value} — Resolved**"

        # Build the main content
        content_parts = [
            title_text,
            f"* **Issue:** {self.issue.value}",
            f"* **Type:** `Incident`",
            f"* **Affected services:** `{self.services.value}`",
            f"* **Status:** `{self.status.value.title()}`",
            f"* **ETA:** `{eta}`"
        ]

        if self.status_link.value:
            content_parts.append(f"* **Status link:** {self.status_link.value}")

        container.add_item(ui.TextDisplay('\n'.join(content_parts)))

        # Separator
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        # Updates section (initially empty)
        container.add_item(ui.TextDisplay("*Updates will be edited in this message*"))

        # Footer with mentions placeholder
        container.add_item(ui.TextDisplay("-# Updates will be posted here"))

        view.add_item(container)

        # Send the message
        try:
            message = await channel.send(view=view)

            # Store incident data for updates
            incident_data = {
                'title': self.title_input.value,
                'issue': self.issue.value,
                'services': self.services.value,
                'status': self.status.value,
                'status_link': self.status_link.value,
                'updates': [],
                'type': 'incident'
            }

            # Save to a simple JSON file (you might want to use a database instead)
            incidents = {}
            if os.path.exists('incidents.json'):
                with open('incidents.json', 'r') as f:
                    incidents = json.load(f)

            incidents[str(message.id)] = incident_data

            with open('incidents.json', 'w') as f:
                json.dump(incidents, f, indent=2)

            await interaction.response.send_message(
                f"✅ Incident created successfully!\nMessage ID: `{message.id}`",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)


class MaintenanceModal(ui.Modal):
    def __init__(self):
        super().__init__(title="Schedule Maintenance")

        self.title_input = ui.TextInput(
            label="Maintenance Title",
            placeholder="e.g., Database Maintenance",
            required=True,
            max_length=100
        )

        self.description = ui.TextInput(
            label="Description",
            placeholder="Describe the maintenance...",
            style=discord.TextStyle.long,
            required=True,
            max_length=1000
        )

        self.services = ui.TextInput(
            label="Affected Services",
            placeholder="e.g., Moddy Bot, Dashboard",
            required=True,
            max_length=200
        )

        self.scheduled_time = ui.TextInput(
            label="Scheduled Time (Unix Timestamp)",
            placeholder=str(int(datetime.now().timestamp())),
            required=True,
            max_length=20
        )

        self.duration = ui.TextInput(
            label="Expected Duration",
            placeholder="e.g., 2 hours",
            required=True,
            max_length=50
        )

        self.add_item(self.title_input)
        self.add_item(self.description)
        self.add_item(self.services)
        self.add_item(self.scheduled_time)
        self.add_item(self.duration)

    async def on_submit(self, interaction: discord.Interaction):
        # Get the status channel
        channel = interaction.client.get_channel(STATUS_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("❌ Status channel not found!", ephemeral=True)
            return

        # Get the appropriate emoji
        emoji = STATUS_EMOJIS['scheduled']

        # Create the V2 components view
        view = ui.LayoutView()
        container = ui.Container()

        # Title with status emoji
        title_text = f"{emoji} **Scheduled Maintenance: {self.title_input.value}**"

        # Build the main content
        content_parts = [
            title_text,
            f"* **Description:** {self.description.value}",
            f"* **Type:** `Maintenance`",
            f"* **Affected services:** `{self.services.value}`",
            f"* **Scheduled time:** <t:{self.scheduled_time.value}:F>",
            f"* **Expected duration:** `{self.duration.value}`",
            f"* **Status:** `Scheduled`"
        ]

        container.add_item(ui.TextDisplay('\n'.join(content_parts)))

        # Separator
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        # Updates section
        container.add_item(ui.TextDisplay("*Updates will be edited in this message*"))

        # Footer
        container.add_item(ui.TextDisplay("-# Updates will be posted here"))

        view.add_item(container)

        # Send the message
        try:
            message = await channel.send(view=view)

            # Store maintenance data
            maintenance_data = {
                'title': self.title_input.value,
                'description': self.description.value,
                'services': self.services.value,
                'scheduled_time': self.scheduled_time.value,
                'duration': self.duration.value,
                'status': 'scheduled',
                'updates': [],
                'type': 'maintenance'
            }

            # Save to JSON
            incidents = {}
            if os.path.exists('incidents.json'):
                with open('incidents.json', 'r') as f:
                    incidents = json.load(f)

            incidents[str(message.id)] = maintenance_data

            with open('incidents.json', 'w') as f:
                json.dump(incidents, f, indent=2)

            await interaction.response.send_message(
                f"✅ Maintenance scheduled successfully!\nMessage ID: `{message.id}`",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)


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

        self.new_status = ui.TextInput(
            label="New Status (leave empty to keep current)",
            placeholder="e.g., monitoring, resolved",
            required=False,
            max_length=50
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
        self.add_item(self.timestamp)

    async def on_submit(self, interaction: discord.Interaction):
        # Load incident data
        incidents = {}
        if os.path.exists('incidents.json'):
            with open('incidents.json', 'r') as f:
                incidents = json.load(f)

        if self.message_id not in incidents:
            await interaction.response.send_message("❌ Incident not found!", ephemeral=True)
            return

        incident = incidents[self.message_id]

        # Add the update
        timestamp = self.timestamp.value or str(int(datetime.now().timestamp()))
        update = {
            'description': self.description.value,
            'timestamp': timestamp,
            'number': len(incident['updates']) + 1
        }

        # Update status if provided
        if self.new_status.value:
            incident['status'] = self.new_status.value.lower()

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

        # Get the appropriate emoji based on status
        status_lower = incident['status'].lower()
        emoji = STATUS_EMOJIS.get(status_lower, STATUS_EMOJIS['ongoing'])

        # Build the content based on type
        if incident['type'] == 'incident':
            # Title with status
            title_text = f"{emoji} **{incident['title']}**"
            if status_lower == 'resolved':
                title_text = f"{emoji} **{incident['title']} — Resolved**"

            eta = "Resolved" if status_lower == 'resolved' else (
                "Monitoring" if status_lower == 'monitoring' else "TBD"
            )

            content_parts = [
                title_text,
                f"* **Issue:** {incident['issue']}",
                f"* **Type:** `Incident`",
                f"* **Affected services:** `{incident['services']}`",
                f"* **Status:** `{incident['status'].title()}`",
                f"* **ETA:** `{eta}`"
            ]

            if incident.get('status_link'):
                content_parts.append(f"* **Status link:** {incident['status_link']}")
        else:
            # Maintenance
            title_text = f"{emoji} **Scheduled Maintenance: {incident['title']}**"
            if status_lower == 'completed':
                title_text = f"{emoji} **Maintenance: {incident['title']} — Completed**"

            content_parts = [
                title_text,
                f"* **Description:** {incident['description']}",
                f"* **Type:** `Maintenance`",
                f"* **Affected services:** `{incident['services']}`",
                f"* **Status:** `{incident['status'].title()}`"
            ]

            if incident.get('scheduled_time'):
                content_parts.append(f"* **Scheduled time:** <t:{incident['scheduled_time']}:F>")
            if incident.get('duration'):
                content_parts.append(f"* **Expected duration:** `{incident['duration']}`")

        container.add_item(ui.TextDisplay('\n'.join(content_parts)))

        # Separator
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        # Add updates
        if incident['updates']:
            update_texts = []
            for upd in incident['updates']:
                update_texts.append(
                    f"> **Update {upd['number']}, <t:{upd['timestamp']}:R>:**\n"
                    f"> {upd['description']}"
                )
            container.add_item(ui.TextDisplay('\n'.join(update_texts)))
        else:
            container.add_item(ui.TextDisplay("*No updates yet*"))

        # Another separator
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        # Footer
        container.add_item(ui.TextDisplay("*Updates will be edited in this message*"))
        container.add_item(ui.TextDisplay("-# Status updates"))

        view.add_item(container)

        # Edit the message
        await message.edit(view=view)
        await interaction.response.send_message("✅ Update added successfully!", ephemeral=True)


class Status(commands.Cog):
    """Status management for incidents and maintenance"""

    def __init__(self, bot):
        self.bot = bot

    incident_group = app_commands.Group(name="incident", description="Incident management commands")
    maintenance_group = app_commands.Group(name="maintenance", description="Maintenance management commands")

    @incident_group.command(name="create", description="Create a new incident")
    async def incident_create(self, interaction: discord.Interaction):
        """Create a new incident"""
        modal = IncidentModal()
        await interaction.response.send_modal(modal)

    @incident_group.command(name="update", description="Add an update to an incident")
    @app_commands.describe(message_id="The message ID of the incident to update")
    async def incident_update(self, interaction: discord.Interaction, message_id: str):
        """Add an update to an existing incident"""
        modal = UpdateModal(message_id)
        await interaction.response.send_modal(modal)

    @incident_group.command(name="resolve", description="Mark an incident as resolved")
    @app_commands.describe(message_id="The message ID of the incident to resolve")
    async def incident_resolve(self, interaction: discord.Interaction, message_id: str):
        """Mark an incident as resolved"""
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

        # Add automatic resolution update
        timestamp = str(int(datetime.now().timestamp()))
        update = {
            'description': 'The incident has been resolved.',
            'timestamp': timestamp,
            'number': len(incident['updates']) + 1
        }
        incident['updates'].append(update)

        # Save data
        incidents[message_id] = incident
        with open('incidents.json', 'w') as f:
            json.dump(incidents, f, indent=2)

        # Update the message using the modal's update method
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

    @maintenance_group.command(name="schedule", description="Schedule a new maintenance")
    async def maintenance_schedule(self, interaction: discord.Interaction):
        """Schedule a new maintenance"""
        modal = MaintenanceModal()
        await interaction.response.send_modal(modal)

    @maintenance_group.command(name="update", description="Add an update to a maintenance")
    @app_commands.describe(message_id="The message ID of the maintenance to update")
    async def maintenance_update(self, interaction: discord.Interaction, message_id: str):
        """Add an update to an existing maintenance"""
        modal = UpdateModal(message_id)
        await interaction.response.send_modal(modal)

    @maintenance_group.command(name="complete", description="Mark a maintenance as completed")
    @app_commands.describe(message_id="The message ID of the maintenance to complete")
    async def maintenance_complete(self, interaction: discord.Interaction, message_id: str):
        """Mark a maintenance as completed"""
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

        # Add automatic completion update
        timestamp = str(int(datetime.now().timestamp()))
        update = {
            'description': 'The maintenance has been completed successfully.',
            'timestamp': timestamp,
            'number': len(incident['updates']) + 1
        }
        incident['updates'].append(update)

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