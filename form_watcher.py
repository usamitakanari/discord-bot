import discord
from discord.ext import commands, tasks
from datetime import datetime
import pytz
import csv
import requests
from io import StringIO
import re

TEST_SERVER_ID = 1293764328255656118  # ← テストサーバーID

class FormWatcherCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tz = pytz.timezone("Asia/Tokyo")
        print("✅ FormWatcherCog 起動完了！ループ開始！")
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

            header_row_index = next(i for i, row in enumerate(rows) if "お名前" in row)
            headers = rows[header_row_index]
            name_col = headers.index("お名前")
            timestamp_col = headers.index("タイムスタンプ")

            today_str = datetime.now(self.tz).strftime("%Y/%m/%d")

            new_rows = rows[header_row_index + 1:]

            for row in new_rows:
                if len(row) <= max(name_col, timestamp_col):
                    continue
                if row[name_col].strip() == "" or today_str not in row[timestamp_col]:
                    continue

                raw_name = row[name_col].strip()
                category_name = self.normalize_name(raw_name)

                print(f"▶️ チェック中: raw_name = '{raw_name}' → category_name = '{category_name}'")

                for guild in self.bot.guilds:
                    if guild.id != TEST_SERVER_ID:
                        continue

                    found = False

                    # パターンA: カテゴリ内のテキストチャンネル
                    for category in guild.categories:
                        if category.name == category_name:
                            text_channel = discord.utils.get(category.channels, name="今日のお仕事")
                            if isinstance(text_channel, discord.TextChannel):
                                content_lines = [
                                    f"【{headers[i]}】{cell}" for i, cell in enumerate(row) if cell.strip() != ""
                                ]
                                message = "\n".join(content_lines)
                                print(f"📤 テキストチャンネル送信先: {category_name}/今日のお仕事")
                                print(f"📨 メッセージ:\n{message}")
                                await text_channel.send(message)
                                found = True
                                break
                    if found:
                        break

                    # パターンB: フォーラムチャンネル内の投稿
                    for channel in guild.channels:
                        if isinstance(channel, discord.ForumChannel) and channel.name == category_name:
                            for thread in channel.threads:
                                if thread.name == "今日のお仕事":
                                    content_lines = [
                                        f"【{headers[i]}】{cell}" for i, cell in enumerate(row) if cell.strip() != ""
                                    ]
                                    message = "\n".join(content_lines)
                                    print(f"📤 フォーラムスレッド送信先: {category_name}/今日のお仕事")
                                    print(f"📨 メッセージ:\n{message}")
                                    await thread.send(message)
                                    found = True
                                    break
                        if found:
                            break

        except Exception as e:
            print(f"フォーム通知処理でエラーが発生しました: {e}")

    @check_form_responses.before_loop
    async def before_check_form_responses(self):
        await self.bot.wait_until_ready()

    def normalize_name(self, name):
        name = re.sub(r"[\u3000\s]+", " ", name.strip())
        return name
