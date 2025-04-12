from discord.ext import commands
from discord import app_commands
import discord

class BlogUploaderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ブログ投稿", description="ブログ記事を投稿します（タイトル・本文・画像）")
    async def post_article(self, interaction: discord.Interaction):
        await interaction.response.send_message("ブログ投稿機能は準備中です！", ephemeral=True)
