import discord
from discord import app_commands
from discord.ext import commands
import time


class Ping(commands.Cog):
    """Cog to check bot latency and status"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        """Ping command to check latency"""

        # Calculate API latency
        start_time = time.monotonic()
        await interaction.response.defer(ephemeral=True)
        end_time = time.monotonic()

        # API latency in ms
        api_latency = (end_time - start_time) * 1000

        # WebSocket latency in ms
        ws_latency = self.bot.latency * 1000

        # Create response embed
        embed = discord.Embed(
            title="PONG",
            description="Connection statistics",
            color=self._get_color_from_latency(ws_latency)
        )

        # Add latency fields with clean formatting
        embed.add_field(
            name="WebSocket",
            value=f"```{ws_latency:.0f} ms```",
            inline=True
        )

        embed.add_field(
            name="API Response",
            value=f"```{api_latency:.0f} ms```",
            inline=True
        )

        embed.add_field(
            name="Status",
            value=f"```{self._get_status(ws_latency)}```",
            inline=True
        )

        # Minimal footer
        embed.set_footer(text=f"Moddy Systems | Shard {self.bot.shard_id or 0}")

        await interaction.followup.send(embed=embed, ephemeral=True)

    def _get_color_from_latency(self, latency: float) -> int:
        """Return a color based on latency"""
        if latency < 100:
            return 0x2ECC71  # Green
        elif latency < 200:
            return 0xF39C12  # Orange
        else:
            return 0xE74C3C  # Red

    def _get_status(self, latency: float) -> str:
        """Return status text based on latency"""
        if latency < 100:
            return "Excellent"
        elif latency < 200:
            return "Good"
        elif latency < 300:
            return "Fair"
        else:
            return "Poor"


async def setup(bot):
    """Setup function to load the cog"""
    await bot.add_cog(Ping(bot))