import os
from dotenv import load_dotenv  # type: ignore
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import json

from spreadsheet_checker import SpreadsheetCheckerCog
from blog_uploader import BlogUploaderCog
from form_watcher import FormWatcherCog

# 環境変数を読み込む
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# 設定ファイル読み込み
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

# ボットの設定
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # メンバー情報取得のため
bot = commands.Bot(command_prefix="!", intents=intents)

class ArchiveCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="archive_ch_th", description="チャンネルの内容をフォーラム投稿にコピーします")
    @app_commands.describe(
        保存元="保存元のチャンネル", 
        保存先="保存先のフォーラム投稿（スレッド）"
    )
    async def archive_ch_th(self, interaction: discord.Interaction, 保存元: discord.TextChannel, 保存先: discord.Thread):
        await self._archive_messages(interaction, 保存元, 保存先)

    @app_commands.command(name="archive_th_th", description="フォーラム投稿の内容を別のフォーラム投稿にコピーします")
    @app_commands.describe(
        保存元="保存元のフォーラム投稿（スレッド）",
        保存先="保存先のフォーラム投稿（スレッド）"
    )
    async def archive_th_th(self, interaction: discord.Interaction, 保存元: discord.Thread, 保存先: discord.Thread):
        await self._archive_messages(interaction, 保存元, 保存先)

    async def _archive_messages(self, interaction: discord.Interaction, 保存元: discord.abc.Messageable, 保存先: discord.Thread):
        await interaction.response.defer(thinking=True, ephemeral=True)
        messages = [msg async for msg in 保存元.history(limit=100)]

        if not messages:
            await interaction.followup.send("保存元にメッセージがありません。", ephemeral=True)
            return

        for message in reversed(messages):
            try:
                if not message.content and not message.attachments:
                    continue
                avatar_url = message.author.display_avatar.url
                embed = discord.Embed(description=message.content or "", timestamp=message.created_at)
                embed.set_author(name=message.author.display_name, icon_url=avatar_url)
                if message.attachments:
                    for attachment in message.attachments:
                        await 保存先.send(embed=embed, file=await attachment.to_file())
                else:
                    await 保存先.send(embed=embed)
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"メッセージ送信中にエラーが発生しました: {e}")

        await interaction.followup.send(f"保存元: {保存元.mention} のメッセージをスレッド: {保存先.mention} に保存しました！", ephemeral=True)

    @app_commands.command(name="server", description="サーバーの情報を表示します")
    async def server_info(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("このコマンドはサーバー内でのみ使用できます。", ephemeral=True)
            return

        total_members = guild.member_count
        bot_count = sum(1 for member in guild.members if member.bot)
        human_count = total_members - bot_count
        role_count = len(guild.roles)
        channel_count = len(guild.channels)

        embed = discord.Embed(title="📊 サーバー情報", color=0x00AE86)
        embed.add_field(name="メンバー数", value=f"{human_count}人+{bot_count}Bot", inline=True)
        embed.add_field(name="ロール数", value=f"{role_count}/250個", inline=True)
        embed.add_field(name="チャンネル数", value=f"{channel_count}/500個", inline=True)
        embed.timestamp = discord.utils.utcnow()

        await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def setup_hook():
    await bot.add_cog(ArchiveCog(bot))
    await bot.add_cog(SpreadsheetCheckerCog(bot, CONFIG))
    await bot.add_cog(FormWatcherCog(bot, CONFIG))
    await bot.add_cog(BlogUploaderCog(bot))
    try:
        await bot.tree.sync()
        print("スラッシュコマンドをグローバルに同期しました。")
    except Exception as e:
        print(f"コマンド同期中にエラーが発生しました: {str(e)}")

@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user}")
    for command in bot.tree.get_commands():
        print(f"登録されたコマンド: {command.name}")

if TOKEN is None:
    print("トークンが見つかりません！.envファイルを確認してください。")
else:
    bot.run(TOKEN)
