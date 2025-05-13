import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime
import json
import pytz
import os
from typing import Optional, Union
from enum import Enum

REMIND_PATH = "remind_config.json"
CONFIG_PATH = "config.json"  # configからチャンネル名参照

class VisibilityOption(Enum):
    全員 = "true"
    自分 = "false"

class RepeatOption(Enum):
    一回のみ = "once"
    毎日 = "daily"
    毎週 = "weekly"

class RemindCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tz = pytz.timezone("Asia/Tokyo")
        self.reminders = self.load_reminders()
        self.config = self.load_config()
        self.remind_loop.change_interval(seconds=1)
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

    @app_commands.command(name="リマインド", description="リマインドを設定します（改行入力可能）")
    @app_commands.describe(
        日付="通知する日付（例: 20250515）",
        時間="通知する時間（例: 16:30）",
        ロール="メンションするロール名または@ユーザー（空欄でメンションなし）",
        チャンネル="送信するチャンネル（テキストまたはスレッド）",
        公開="通知の公開範囲",
        繰り返し="送信間隔（1回・毎日・毎週）"
    )
    async def set_reminder(
        self,
        interaction: discord.Interaction,
        日付: str,
        時間: str,
        ロール: Optional[str] = None,
        チャンネル: Optional[Union[discord.TextChannel, discord.Thread]] = None,
        公開: VisibilityOption = VisibilityOption.自分,
        繰り返し: RepeatOption = RepeatOption.一回のみ
    ):
        try:
            datetime.strptime(f"{日付} {時間}", "%Y%m%d %H:%M")
        except ValueError:
            await interaction.response.send_message("📅 日付または時間の形式が正しくありません。例: `20250515` `16:30`", ephemeral=True)
            return

        await interaction.response.send_modal(RemindModal(
            日付=日付,
            時間=時間,
            ロール=ロール,
            チャンネル=チャンネル,
            公開=(公開.value == "true"),
            repeat_mode=繰り返し.value,
            cog=self
        ))

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

        await interaction.response.send_message(f"🗑 リマインド削除済み：{deleted['date']} {deleted['time']} {deleted['mention_target']} → {deleted['message']}", ephemeral=True)

    @app_commands.command(name="リマインド一覧", description="設定されているリマインドを表示します")
    async def list_reminders(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        items = self.reminders.get(guild_id, [])

        if not items:
            await interaction.response.send_message("🔕 設定されているリマインドはありません。", ephemeral=True)
            return

        lines = []
        for idx, item in enumerate(items, 1):
            channel_part = f" → <#{item['channel_id']}>" if item.get("channel_id") else ""
            repeat_label = {
                "once": "一回のみ",
                "daily": "毎日",
                "weekly": "毎週"
            }.get(item.get("repeat"), "不明")
            visibility = "全員" if item.get("公開") else "自分"
            formatted_date = datetime.strptime(item['date'], "%Y%m%d").strftime("%Y-%m-%d")
            line = f"{idx}. 📅 {formatted_date} 🕒 {item['time']} | {item['mention_target'] or 'なし'} | {item['message']}{channel_part} [{repeat_label} / {visibility}]"
            lines.append(line)

        msg = "\n".join(lines)
        await interaction.response.send_message(f"📋 リマインド一覧：\n{msg}", ephemeral=True)

    @tasks.loop(seconds=1)
    async def remind_loop(self):
        now = datetime.now(self.tz)
        now_str = now.strftime("%Y%m%d %H:%M")
        weekday = now.strftime("%A")
        print(f"[DEBUG] remind_loop checking at {now_str}")
        for guild in self.bot.guilds:
            guild_id = str(guild.id)
            settings = self.reminders.get(guild_id, [])
            default_channel_name = self.config.get(guild_id, {}).get("default_remind_channel", "スタッフ連絡")
            new_settings = []

            for item in settings:
                remind_at = f"{item['date']} {item['time']}"
                if now_str == remind_at:
                    channel = self.bot.get_channel(item.get("channel_id")) if item.get("channel_id") else discord.utils.get(guild.text_channels, name=default_channel_name)
                    if channel:
                        content = f"{item['mention_target']}\n{item['message']}" if item.get("mention_target") else item['message']
                        try:
                            await channel.send(content, silent=not item.get("公開", False))
                            print(f"[送信] {remind_at} に {item['message'][:20]}... を送信しました")
                        except Exception as e:
                            print(f"⚠️ チャンネル送信エラー: {e}")
                            await channel.send(content)

                    # 再設定条件
                    if item.get("repeat") == "daily":
                        next_date = (now + timedelta(days=1)).strftime("%Y%m%d")
                        item['date'] = next_date
                        new_settings.append(item)
                    elif item.get("repeat") == "weekly":
                        next_date = (now + timedelta(days=7)).strftime("%Y%m%d")
                        item['date'] = next_date
                        new_settings.append(item)
                else:
                    new_settings.append(item)

            self.reminders[guild_id] = new_settings
            self.save_reminders()

    @remind_loop.before_loop
    async def before_remind_loop(self):
        await self.bot.wait_until_ready()

class RemindModal(discord.ui.Modal, title="リマインド内容入力"):
    内容 = discord.ui.TextInput(label="通知メッセージ（複数行可）", style=discord.TextStyle.paragraph)

    def __init__(self, 日付, 時間, ロール, チャンネル, 公開, repeat_mode, cog):
        super().__init__()
        self.日付 = 日付
        self.時間 = 時間
        self.ロール = ロール
        self.チャンネル = チャンネル
        self.公開 = 公開
        self.repeat_mode = repeat_mode
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        if guild_id not in self.cog.reminders:
            self.cog.reminders[guild_id] = []

        self.cog.reminders[guild_id].append({
            "message": self.内容.value,
            "date": self.日付,
            "time": self.時間,
            "mention_target": self.ロール or "",
            "channel_id": self.チャンネル.id if self.チャンネル else None,
            "公開": self.公開,
            "repeat": self.repeat_mode
        })
        self.cog.save_reminders()

        repeat_label = {
            "once": "一回のみ",
            "daily": "毎日",
            "weekly": "毎週"
        }.get(self.repeat_mode, "不明")
        visibility = "全員" if self.公開 else "自分"
        formatted_date = datetime.strptime(self.日付, "%Y%m%d").strftime("%Y-%m-%d")

        await interaction.response.send_message(
            f"⏰ リマインド設定完了：{formatted_date} {self.時間} に送信予定\n"
            f"宛先: {self.ロール or 'なし'}\n"
            f"種類: {repeat_label} / {visibility}",
            ephemeral=not self.公開
        )
