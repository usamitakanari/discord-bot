import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import pytz
import csv
import requests
from io import StringIO
import re
import json

SERVER_ID = 1293764328255656118　#1101493830915719273
ALERT_CHANNEL_ID = 1313729303145353276　#1110021867768664105
SENT_LOG_PATH = "sent_entries.json"
CHECK_FROM_TIME_STR = "2025/04/05 15:30:00"
CHECK_FROM_TIME = datetime.strptime(CHECK_FROM_TIME_STR, "%Y/%m/%d %H:%M:%S")

class FormWatcherCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tz = pytz.timezone("Asia/Tokyo")
        self.notified_entries = self.load_sent_entries()
        print("✅ FormWatcherCog 起動完了！チェック有効化！")
        self.check_form_responses.start()
        self.alert_unchecked_attendance.start()

    def cog_unload(self):
        self.check_form_responses.cancel()
        self.alert_unchecked_attendance.cancel()

    def load_sent_entries(self):
        try:
            with open(SENT_LOG_PATH, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except FileNotFoundError:
            return set()

    def save_sent_entry(self, entry_key):
        self.notified_entries.add(entry_key)
        with open(SENT_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(list(self.notified_entries), f, ensure_ascii=False, indent=2)

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

                timestamp_str = row[timestamp_col].strip()
                try:
                    timestamp_obj = datetime.strptime(timestamp_str, "%Y/%m/%d %H:%M:%S")
                    if timestamp_obj < CHECK_FROM_TIME:
                        continue
                except:
                    continue

                entry_key = f"{row[name_col].strip()}|{row[status_col].strip()}"
                if entry_key in self.notified_entries:
                    continue

                # ここにEmbed作成＆送信処理（省略）

                self.save_sent_entry(entry_key)

        except Exception as e:
            print(f"フォーム通知処理でエラーが発生しました: {e}")

    @tasks.loop(time=datetime.strptime("09:00:00", "%H:%M:%S").time())
    async def alert_unchecked_attendance(self):
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

            yesterday = (datetime.now(self.tz) - timedelta(days=1)).strftime("%Y/%m/%d")
            new_rows = rows[header_row_index + 1:]

            attended = set()
            left = set()

            for row in new_rows:
                if len(row) <= max(name_col, timestamp_col, status_col):
                    continue
                if row[name_col].strip() == "" or yesterday not in row[timestamp_col]:
                    continue

                name = row[name_col].strip()
                status = row[status_col].strip()

                if status == "出勤":
                    attended.add(name)
                elif status == "退勤":
                    left.add(name)

            not_left = attended - left
            if not_left:
                message = "\n".join(f"- {name} さん" for name in sorted(not_left))
                channel = self.bot.get_channel(ALERT_CHANNEL_ID)
                if channel:
                    await channel.send(f"⚠️ 昨日出勤して退勤していない方のリストです：\n{message}")

        except Exception as e:
            print(f"未退勤チェックでエラーが発生しました: {e}")

    @check_form_responses.before_loop
    @alert_unchecked_attendance.before_loop
    async def before_loops(self):
        await self.bot.wait_until_ready()

    def normalize_name(self, name):
        name = re.sub(r"[\s　]", "", name.strip())
        variants = {
            "髙": "高",
            "𠮷": "吉",
        }
        for old, new in variants.items():
            name = name.replace(old, new)
        return name
