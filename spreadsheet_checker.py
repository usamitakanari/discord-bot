import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import pytz
import csv
import requests
from io import StringIO
import random
import json

class SpreadsheetCheckerCog(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.tz = pytz.timezone("Asia/Tokyo")
        self.check_daily.start()

    def cog_unload(self):
        self.check_daily.cancel()

    @tasks.loop(minutes=1)
    async def check_daily(self):
        now = datetime.now(self.tz)
        if now.hour == 16 and now.minute == 30:
            await self.send_notification()

    @check_daily.before_loop
    async def before_check_daily(self):
        await self.bot.wait_until_ready()

    async def send_notification(self):
        for guild in self.bot.guilds:
            config = self.config.get(str(guild.id))
            if not config:
                continue

            try:
                jisseki_url = config["jisseki_url"]
                response = requests.get(jisseki_url)
                response.raise_for_status()

                content = response.content.decode("utf-8")
                reader = csv.reader(StringIO(content))
                rows = list(reader)

                today = str(datetime.now(self.tz).day)
                date_row = rows[3]  # 4行目（日付行）

                for col_index, date in enumerate(date_row):
                    if date.strip() == today:
                        col_values = [
                            rows[row_index][col_index] if col_index < len(rows[row_index]) else ""
                            for row_index in range(6, 18)
                        ]
                        if any(cell.strip() == "" for cell in col_values):
                            channel = discord.utils.get(guild.text_channels, name=config["ALERT_CHANNEL_NAME"])
                            role = discord.utils.get(guild.roles, name=config["role_name"])
                            if channel:
                                messages = [
                                    f"{role.mention if role else '@here'} 本日の実績報告がまだ入力されてないです！",
                                    f"{role.mention if role else '@here'} 実績報告の入力忘れてるかも...？ ",
                                    f"{role.mention if role else '@here'} 実績報告まだみたいです〜！お願いします！",
                                    f"{role.mention if role else '@here'} 今日の実績入力、16:30過ぎましたよ〜！",
                                    f"{role.mention if role else '@here'} 本日の報告お忘れなく！入力チェックしてます！"
                                ]
                                await channel.send(random.choice(messages))
                            return
            except Exception as e:
                print(f"通知処理でエラーが発生しました: {e}")
