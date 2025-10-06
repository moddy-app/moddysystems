import discord
from discord import app_commands, ui
from discord.ext import commands
from typing import Optional


class MessageModal(ui.Modal):
    def __init__(self, title: str = "Send Message"):
        super().__init__(title=title)

        self.content = ui.TextInput(
            label="Message Content",
            placeholder="Type your message...\nUse --- for separators",
            style=discord.TextStyle.long,
            required=True,
            max_length=2000
        )

        self.add_item(self.content)

    async def on_submit(self, interaction: discord.Interaction):
        # This will be overridden by subclasses
        pass


class SendMessageModal(MessageModal):
    def __init__(self):
        super().__init__(title="Send V2 Message")

        self.channel_id = ui.TextInput(
            label="Channel ID",
            placeholder="Enter the channel ID where to send the message",
            required=True,
            max_length=20
        )

        self.add_item(self.channel_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Get the channel
            channel = interaction.client.get_channel(int(self.channel_id.value))
            if not channel:
                await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
                return

            # Check permissions
            if not channel.permissions_for(channel.guild.me).send_messages:
                await interaction.response.send_message("❌ No permission to send messages in that channel!",
                                                        ephemeral=True)
                return

            # Parse and send the message
            view = self.create_v2_view(self.content.value)
            message = await channel.send(view=view)

            # Send confirmation
            embed = discord.Embed(
                title="✅ Message Sent",
                color=discord.Color.green(),
                description=f"Message sent successfully!"
            )
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.add_field(name="Message ID", value=f"`{message.id}`", inline=True)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except ValueError:
            await interaction.response.send_message("❌ Invalid channel ID!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    def create_v2_view(self, content: str) -> ui.LayoutView:
        """Create a V2 components view from the content"""
        view = ui.LayoutView()
        container = ui.Container()

        # Split content by lines
        lines = content.split('\n')
        current_section = []

        for line in lines:
            if line.strip() == '---':
                # Add current section if exists
                if current_section:
                    text_content = '\n'.join(current_section)
                    if text_content.strip():
                        container.add_item(ui.TextDisplay(text_content))
                    current_section = []

                # Add separator
                container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
            else:
                current_section.append(line)

        # Add the last section
        if current_section:
            text_content = '\n'.join(current_section)
            if text_content.strip():
                container.add_item(ui.TextDisplay(text_content))

        view.add_item(container)
        return view


class EditMessageModal(MessageModal):
    def __init__(self):
        super().__init__(title="Edit V2 Message")

        self.message_id = ui.TextInput(
            label="Message ID",
            placeholder="Enter the message ID to edit",
            required=True,
            max_length=20
        )

        self.channel_id = ui.TextInput(
            label="Channel ID",
            placeholder="Enter the channel ID where the message is",
            required=True,
            max_length=20
        )

        self.add_item(self.message_id)
        self.add_item(self.channel_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Get the channel
            channel = interaction.client.get_channel(int(self.channel_id.value))
            if not channel:
                await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
                return

            # Get the message
            message = await channel.fetch_message(int(self.message_id.value))

            # Check if the message was sent by the bot
            if message.author != interaction.client.user:
                await interaction.response.send_message("❌ Can only edit messages sent by the bot!", ephemeral=True)
                return

            # Parse and edit the message
            view = self.create_v2_view(self.content.value)
            await message.edit(view=view)

            # Send confirmation
            embed = discord.Embed(
                title="✅ Message Edited",
                color=discord.Color.green(),
                description=f"Message edited successfully!"
            )
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.add_field(name="Message ID", value=f"`{message.id}`", inline=True)
            embed.add_field(name="Jump to Message", value=f"[Click here]({message.jump_url})", inline=True)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except ValueError:
            await interaction.response.send_message("❌ Invalid ID format!", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("❌ Message not found!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    def create_v2_view(self, content: str) -> ui.LayoutView:
        """Create a V2 components view from the content"""
        view = ui.LayoutView()
        container = ui.Container()

        # Split content by lines
        lines = content.split('\n')
        current_section = []

        for line in lines:
            if line.strip() == '---':
                # Add current section if exists
                if current_section:
                    text_content = '\n'.join(current_section)
                    if text_content.strip():
                        container.add_item(ui.TextDisplay(text_content))
                    current_section = []

                # Add separator
                container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
            else:
                current_section.append(line)

        # Add the last section
        if current_section:
            text_content = '\n'.join(current_section)
            if text_content.strip():
                container.add_item(ui.TextDisplay(text_content))

        view.add_item(container)
        return view


class QuickMessageView(discord.ui.View):
    """Quick action buttons for message management"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Send Message", style=discord.ButtonStyle.primary, emoji="📤")
    async def send_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SendMessageModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Edit Message", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EditMessageModal()
        await interaction.response.send_modal(modal)


class V2Messages(commands.Cog):
    """Send and edit messages with V2 components"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="v2send", description="Send a message with V2 components")
    async def v2send(self, interaction: discord.Interaction):
        """Send a message with V2 components to a specific channel"""
        modal = SendMessageModal()
        await interaction.response.send_modal(modal)

    @app_commands.command(name="v2edit", description="Edit a message with V2 components")
    async def v2edit(self, interaction: discord.Interaction):
        """Edit an existing message with V2 components"""
        modal = EditMessageModal()
        await interaction.response.send_modal(modal)

    @app_commands.command(name="v2quick", description="Quick message panel with buttons")
    async def v2quick(self, interaction: discord.Interaction):
        """Show a quick panel with send/edit buttons"""
        embed = discord.Embed(
            title="📨 V2 Message Manager",
            description="Use the buttons below to send or edit messages with V2 components.",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="📝 Formatting",
            value="• Use `---` on its own line for separators\n"
                  "• Supports all Discord markdown\n"
                  "• Messages are sent with V2 layout components",
            inline=False
        )

        embed.add_field(
            name="💡 Tips",
            value="• You need the message ID and channel ID to edit\n"
                  "• Can only edit messages sent by the bot\n"
                  "• Check permissions before sending",
            inline=False
        )

        view = QuickMessageView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="v2channel", description="Send a V2 message to the current channel")
    @app_commands.describe(content="Message content (use --- for separators)")
    async def v2channel(self, interaction: discord.Interaction, content: str):
        """Quick command to send a V2 message to the current channel"""
        # Parse the content
        view = ui.LayoutView()
        container = ui.Container()

        # Split content by lines
        lines = content.split('\\n')  # Handle \n in slash command input
        current_section = []

        for line in lines:
            if line.strip() == '---':
                # Add current section if exists
                if current_section:
                    text_content = '\n'.join(current_section)
                    if text_content.strip():
                        container.add_item(ui.TextDisplay(text_content))
                    current_section = []

                # Add separator
                container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
            else:
                current_section.append(line)

        # Add the last section
        if current_section:
            text_content = '\n'.join(current_section)
            if text_content.strip():
                container.add_item(ui.TextDisplay(text_content))

        view.add_item(container)

        # Send the message
        try:
            message = await interaction.channel.send(view=view)

            embed = discord.Embed(
                title="✅ Message Sent",
                description=f"Message sent successfully!\n**ID:** `{message.id}`",
                color=discord.Color.green()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    @app_commands.command(name="v2delete", description="Delete a bot message")
    @app_commands.describe(
        message_id="ID of the message to delete",
        channel_id="ID of the channel (optional, uses current if not provided)"
    )
    async def v2delete(self, interaction: discord.Interaction, message_id: str, channel_id: Optional[str] = None):
        """Delete a message sent by the bot"""
        try:
            # Get the channel
            if channel_id:
                channel = self.bot.get_channel(int(channel_id))
                if not channel:
                    await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
                    return
            else:
                channel = interaction.channel

            # Get and delete the message
            message = await channel.fetch_message(int(message_id))

            # Check if the message was sent by the bot
            if message.author != self.bot.user:
                await interaction.response.send_message("❌ Can only delete messages sent by the bot!", ephemeral=True)
                return

            await message.delete()

            embed = discord.Embed(
                title="✅ Message Deleted",
                description=f"Message `{message_id}` has been deleted.",
                color=discord.Color.green()
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except ValueError:
            await interaction.response.send_message("❌ Invalid ID format!", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("❌ Message not found!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ No permission to delete this message!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)


async def setup(bot):
    """Setup function to load the cog"""
    await bot.add_cog(V2Messages(bot))