import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import pytz
import csv
import requests
from io import StringIO
import random

class SpreadsheetCheckerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tz = pytz.timezone("Asia/Tokyo")
        print("✅ FormWatcherCog 起動完了！ループ開始！")  # ← ここに追加！
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
        try:
            # 🔗 公開スプレッドシートのCSV URL
            sheet_id = "1jFGvfXK6musgzn97lkQwJyXPLAiXIIwHBHbLScKgEzQ"
            gid = "1236011318"  # 実績コピーシートのGID
            url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"

            response = requests.get(url)
            response.raise_for_status()

            content = response.content.decode("utf-8")
            reader = csv.reader(StringIO(content))
            rows = list(reader)

            today = str(datetime.now(self.tz).day)
            date_row = rows[3]  # 4行目（日付行）

            for col_index, date in enumerate(date_row):
                if date.strip() == today:
                    # 6〜14行目（インデックス5〜13）
                    col_values = [
                        rows[row_index][col_index] if col_index < len(rows[row_index]) else ""
                        for row_index in range(5, 14)
                    ]
                    if any(cell.strip() == "" for cell in col_values):
                        channel = self.bot.get_channel(1110021867768664105)
                        if channel:
                            messages = [
                                f"<@&{1270600048878686259}> 本日の実績報告がまだ入力されてないです！",
                                f"<@&{1270600048878686259}> 実績報告の入力忘れてるかも...？ ",
                                f"<@&{1270600048878686259}> 実績報告まだみたいです〜！お願いします！",
                                f"<@&{1270600048878686259}> 今日の実績入力、16:30過ぎましたよ〜！",
                                f"<@&{1270600048878686259}> 本日の報告お忘れなく！入力チェックしてます！"
                            ]
                            await channel.send(random.choice(messages))
                        return

        except Exception as e:
            print(f"通知処理でエラーが発生しました: {e}")
