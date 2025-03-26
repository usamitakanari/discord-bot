import discord
from discord.ext import commands, tasks
from datetime import datetime
import pytz
import csv
import requests
from io import StringIO
import re

SERVER_ID = 1101493830915719273  # ← サーバーID

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
            status_col = headers.index("出退勤")

            today_str = datetime.now(self.tz).strftime("%Y/%m/%d")

            new_rows = rows[header_row_index + 1:]

            for row in new_rows:
                if len(row) <= max(name_col, timestamp_col, status_col):
                    continue
                if row[name_col].strip() == "" or today_str not in row[timestamp_col]:
                    continue

                raw_name = row[name_col].strip()
                normalized_name = self.normalize_name(raw_name)

                print(f"▶️ チェック中: raw_name = '{raw_name}' → normalized_name = '{normalized_name}'")

                greeting = ""
                status = row[status_col].strip()
                timestamp = row[timestamp_col].strip()
                try:
                    hour = int(timestamp.split()[1].split(":")[0])
                except:
                    hour = 12

                if status == "出勤":
                    greeting = (
                        f"> {raw_name} さん！{'おはようございます' if hour <= 11 else 'こんにちは'} :sunny:\n"
                        f"> 出勤報告確認しました:thumbsup:\n"
                        f"> 本日もよろしくお願いします:blush:\n\n"
                        f"{timestamp}\n"
                        f"## :house: 出退勤\n{status}\n"
                    )
                    for key in ["体温", "体調", "体調備考", "本日の作業予定", "本日の目標"]:
                        if key in headers:
                            val = row[headers.index(key)].strip()
                            if val:
                                greeting += f"## {key}\n{val}\n"

                elif status == "退勤":
                    greeting = (
                        f"> {raw_name} さん！本日もお疲れ様でした:sparkles:\n"
                        f"> 退勤報告確認しました:thumbsup:\n"
                        f"> 次回もよろしくお願いします:person_bowing:\n\n"
                        f"{timestamp}\n"
                        f"## :house: 出退勤\n{status}\n"
                    )
                    for key, emoji in zip(["本日の作業内容", "感想"], [":pencil:", ":triangular_flag_on_post:"]):
                        if key in headers:
                            val = row[headers.index(key)].strip()
                            if val:
                                greeting += f"## {emoji} {key}\n{val}\n"

                else:
                    continue

                for guild in self.bot.guilds:
                    if guild.id != SERVER_ID:
                        continue

                    found = False

                    for category in guild.categories:
                        if self.normalize_name(category.name) == normalized_name:
                            text_channel = discord.utils.get(category.channels, name="今日のお仕事")
                            if isinstance(text_channel, discord.TextChannel):
                                print(f"📤 テキストチャンネル送信先: {category.name}/今日のお仕事")
                                print(f"📨 メッセージ:\n{greeting}")
                                await text_channel.send(greeting)
                                found = True
                                break
                    if found:
                        break

                    for channel in guild.channels:
                        if isinstance(channel, discord.ForumChannel) and self.normalize_name(channel.name) == normalized_name:
                            for thread in channel.threads:
                                if thread.name == "今日のお仕事":
                                    print(f"📤 フォーラムスレッド送信先: {channel.name}/今日のお仕事")
                                    print(f"📨 メッセージ:\n{greeting}")
                                    await thread.send(greeting)
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
        return re.sub(r"[\s　]", "", name.strip())
