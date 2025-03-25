import discord
from discord.ext import commands, tasks
from datetime import datetime
import pytz
import csv
import requests
from io import StringIO
import re

SERVER_ID = 1293764328255656118  # ← サーバーID

class FormWatcherCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tz = pytz.timezone("Asia/Tokyo")
        self.last_checked_rows = 0
        self.check_form_responses.start()

    def cog_unload(self):
        self.check_form_responses.cancel()

    @tasks.loop(minutes=1)
    async def check_form_responses(self):
        try:
            url = "https://docs.google.com/spreadsheets/d/1jFGvfXK6musgzn97lkQwJyXPLAiXIIwHBHbLScKgEzQ/export?format=csv&gid=1784560896"
            response = requests.get(url)
            response.raise_for_status()

            content = response.content.decode("utf-8-sig")
            reader = csv.reader(StringIO(content))
            rows = list(reader)

             # ✅ ここにログを追加！
            for i, row in enumerate(rows[:5]):
                print(f"Row {i}: {row}")

            headers = rows[0]
            name_col = headers.index("お名前")
            new_rows = rows[self.last_checked_rows + 1:]

            for row in new_rows:
                if len(row) <= name_col:
                    continue
                raw_name = row[name_col].strip()
                category_name = self.normalize_name(raw_name)

                for guild in self.bot.guilds:
                    if guild.id != SERVER_ID:
                        continue

                    for category in guild.categories:
                        if category.name == category_name:
                            # テキストチャンネル or フォーラム探す
                            target_channel = discord.utils.get(category.channels, name="今日のお仕事")

                            if target_channel:
                                content_lines = [
                                    f"【{headers[i]}】{cell}" for i, cell in enumerate(row) if cell.strip() != ""
                                ]
                                message = "\n".join(content_lines)

                                # フォーラムなら投稿、チャンネルならsend
                                if isinstance(target_channel, discord.ForumChannel):
                                    await target_channel.create_thread(name=f"{raw_name}の報告", content=message)
                                else:
                                    await target_channel.send(message)
                            break

            self.last_checked_rows = len(rows) - 1

        except Exception as e:
            print(f"フォーム通知処理でエラーが発生しました: {e}")

    @check_form_responses.before_loop
    async def before_check_form_responses(self):
        await self.bot.wait_until_ready()

    def normalize_name(self, name):
        # 全角・半角スペースを1つのスペースにして整える
        name = re.sub(r"[\u3000\s]+", " ", name.strip())
        return name

