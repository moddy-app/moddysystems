import discord
from discord import app_commands, ui
from discord.ext import commands
import re
from typing import List, Tuple


class OfficialNewsModal(ui.Modal):
    """Modal for creating official news announcements"""

    def __init__(self):
        super().__init__(title="Official News Announcement")

        self.content = ui.TextInput(
            label="Message Content",
            placeholder="Enter your official announcement message here...",
            style=discord.TextStyle.long,
            required=True,
            max_length=2000
        )

        self.links = ui.TextInput(
            label="Additional Links (Optional)",
            placeholder="[Link Title](https://example.com), [Another Link](https://example2.com)",
            style=discord.TextStyle.long,
            required=False,
            max_length=1000
        )

        self.add_item(self.content)
        self.add_item(self.links)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Get the official news channel
            OFFICIAL_NEWS_CHANNEL_ID = 1410338969107042515
            channel = interaction.client.get_channel(OFFICIAL_NEWS_CHANNEL_ID)

            if not channel:
                await interaction.response.send_message(
                    "❌ Official news channel not found!",
                    ephemeral=True
                )
                return

            # Check bot permissions
            if not channel.permissions_for(channel.guild.me).send_messages:
                await interaction.response.send_message(
                    "❌ No permission to send messages in the official news channel!",
                    ephemeral=True
                )
                return

            # Parse links
            parsed_links = self.parse_links(self.links.value) if self.links.value.strip() else []

            # Create the V2 view
            view = self.create_official_news_view(self.content.value, parsed_links)

            # Send the message
            message = await channel.send(view=view)

            # Send confirmation
            embed = discord.Embed(
                title="✅ Official News Sent",
                color=discord.Color.green(),
                description=f"Official announcement sent successfully!"
            )
            embed.add_field(name="Channel", value=channel.mention, inline=True)
            embed.add_field(name="Message ID", value=f"`{message.id}`", inline=True)
            embed.add_field(name="Jump to Message", value=f"[Click here]({message.jump_url})", inline=True)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error sending official news: {e}",
                ephemeral=True
            )

    def parse_links(self, links_text: str) -> List[Tuple[str, str]]:
        """
        Parse links in the format [Title](url), [Title2](url2)
        Returns list of tuples: [(title, url), (title, url)]
        """
        # Regex pattern to match [text](url)
        pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        matches = re.findall(pattern, links_text)
        return matches

    def create_official_news_view(self, content: str, additional_links: List[Tuple[str, str]]) -> ui.LayoutView:
        """Create a V2 components view for official news"""
        view = ui.LayoutView()
        container = ui.Container()

        # Add the main content
        container.add_item(ui.TextDisplay(content))

        # Add separator
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))

        # Add official message footer
        footer_text = (
            "-# This is an official message issued by the Moddy team. "
            "For more information or updates, please consult Moddy's official communication channels. "
            "[Learn more](https://moddy.app/official_messages)"
        )
        container.add_item(ui.TextDisplay(footer_text))

        view.add_item(container)

        # Create buttons outside the container
        # Support Server button is always present
        button_row = ui.ActionRow()

        support_button = ui.Button(
            label="Support Server",
            url="https://moddy.app/support"
        )
        button_row.add_item(support_button)

        # Add additional link buttons (max 4 more buttons to not exceed Discord's 5 button limit per row)
        for title, url in additional_links[:4]:
            link_button = ui.Button(
                label=title[:80],  # Discord button label max length
                url=url
            )
            button_row.add_item(link_button)

        view.add_item(button_row)

        return view


class OfficialNews(commands.Cog):
    """Official news announcements with V2 components"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="official-news",
        description="Send an official news announcement to the official channel"
    )
    async def official_news(self, interaction: discord.Interaction):
        """Send an official news announcement with V2 components"""
        modal = OfficialNewsModal()
        await interaction.response.send_modal(modal)


async def setup(bot):
    """Setup function to load the cog"""
    await bot.add_cog(OfficialNews(bot))
