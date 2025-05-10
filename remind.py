import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime
import json
import pytz
import os

REMIND_PATH = "remind_config.json"
CONFIG_PATH = "config.json"  # configからチャンネル名参照

class RemindCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tz = pytz.timezone("Asia/Tokyo")
        self.reminders = self.load_reminders()
        self.config = self.load_config()
        self.remind_loop.start()

    def cog_unload(self):
        self.remind_loop.cancel()

    def load_reminders(self):
        if os.path.exists(REMIND_PATH):
            with open(REMIND_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_reminders(self):
        with open(REMIND_PATH, "w", encoding="utf-8") as f:
            json.dump(self.reminders, f, ensure_ascii=False, indent=2)

    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    @app_commands.command(name="リマインド", description="リマインドを設定します")
    @app_commands.describe(
        内容="通知するメッセージの内容",
        時間="通知する時間（例: 16:30）",
        ロール="メンションするロール名",
        チャンネル="送信するチャンネル名（一覧から選択）",
        公開="リマインド通知を公開するか（True/False）"
    )
    async def set_reminder(self, interaction: discord.Interaction, 内容: str, 時間: str, ロール: str, チャンネル: str = None, 公開: bool = False):
        guild_id = str(interaction.guild_id)
        if guild_id not in self.reminders:
            self.reminders[guild_id] = []

        channel_names = [c.name for c in interaction.guild.text_channels]
        if チャンネル and チャンネル not in channel_names:
            await interaction.response.send_message(f"⚠️ チャンネル '{チャンネル}' は存在しません。以下から選んでください：\n" + ", ".join(channel_names), ephemeral=True)
            return

        self.reminders[guild_id].append({
            "message": 内容,
            "time": 時間,
            "role_name": ロール,
            "channel_name": チャンネル,
            "公開": 公開
        })
        self.save_reminders()

        await interaction.response.send_message(f"⏰ リマインド設定完了：{時間} に '{内容}' を @{ロール} に送信します。", ephemeral=not 公開)

    @app_commands.command(name="リマインド一覧", description="設定されているリマインドを表示します")
    async def list_reminders(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        items = self.reminders.get(guild_id, [])

        if not items:
            await interaction.response.send_message("🔕 設定されているリマインドはありません。", ephemeral=True)
            return

        lines = []
        for idx, item in enumerate(items, 1):
            line = f"{idx}. 🕒 {item['time']} | @{item['role_name']} | {item['message']}"
            if item.get("channel_name"):
                line += f" → #{item['channel_name']}"
            lines.append(line)

        msg = "\n".join(lines)
        await interaction.response.send_message(f"📋 リマインド一覧：\n{msg}", ephemeral=True)

    @app_commands.command(name="リマインド削除", description="リマインドを削除します")
    @app_commands.describe(番号="削除したいリマインドの番号（一覧で表示された番号）")
    async def delete_reminder(self, interaction: discord.Interaction, 番号: int):
        guild_id = str(interaction.guild_id)
        items = self.reminders.get(guild_id, [])

        if 番号 <= 0 or 番号 > len(items):
            await interaction.response.send_message("⚠️ 無効な番号です。", ephemeral=True)
            return

        deleted = items.pop(番号 - 1)
        self.reminders[guild_id] = items
        self.save_reminders()

        await interaction.response.send_message(f"🗑 リマインド削除済み：{deleted['time']} @{deleted['role_name']} → {deleted['message']}", ephemeral=True)

    @tasks.loop(minutes=1)
    async def remind_loop(self):
        now = datetime.now(self.tz).strftime("%H:%M")
        for guild in self.bot.guilds:
            guild_id = str(guild.id)
            settings = self.reminders.get(guild_id, [])
            default_channel_name = self.config.get(guild_id, {}).get("default_remind_channel", "スタッフ連絡")

            for item in settings:
                if item["time"] == now:
                    role = discord.utils.get(guild.roles, name=item["role_name"])
                    channel_name = item.get("channel_name") or default_channel_name
                    channel = discord.utils.get(guild.text_channels, name=channel_name)
                    if channel:
                        content = f"{role.mention if role else '@here'}\n{item['message']}"
                        try:
                            await channel.send(content, silent=not item.get("公開", False))
                        except:
                            await channel.send(content)

    @remind_loop.before_loop
    async def before_remind_loop(self):
        await self.bot.wait_until_ready()
