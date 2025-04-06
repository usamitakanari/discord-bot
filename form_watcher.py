import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import pytz
import csv
import requests
from io import StringIO
import re
import json

SERVER_ID = 1293764328255656118 #1101493830915719273
ALERT_CHANNEL_ID = 1313729303145353276 #1110021867768664105
SENT_LOG_PATH = "sent_entries.json"
CHECK_FROM_TIME_STR = "2025/04/05 09:00:00"
CHECK_FROM_TIME = datetime.strptime(CHECK_FROM_TIME_STR, "%Y/%m/%d %H:%M:%S")
SNS_LINK = "https://discord.com/channels/1101493830915719273/1336506529314115664"

class FormWatcherCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tz = pytz.timezone("Asia/Tokyo")
        self.notified_entries = self.load_sent_entries()
        self.missing_retire_alert_sent = False
        print("✅ FormWatcherCog 起動完了！チェック有効化！")
        self.check_form_responses.start()
        self.check_missing_retire.start()

    def cog_unload(self):
        self.check_form_responses.cancel()
        self.check_missing_retire.cancel()

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
            new_rows = rows[header_row_index + 1:]
            today_str = datetime.now(self.tz).strftime("%Y/%m/%d")

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

                raw_name = row[name_col].strip()
                normalized_name = self.normalize_name(raw_name)
                status = row[status_col].strip()
                entry_key = f"{raw_name}|{status}"

                if entry_key in self.notified_entries:
                    continue

                embed = self.create_embed(raw_name, status, timestamp_str, headers, row)
                if embed is None:
                    continue

                sent = await self.send_to_discord(normalized_name, embed, status)
                if sent:
                    self.save_sent_entry(entry_key)

        except Exception as e:
            print(f"フォーム通知処理でエラーが発生しました: {e}")
            
    @tasks.loop(time=datetime.strptime("09:00:00", "%H:%M:%S").time())
    async def check_missing_retire(self):
        try:
            if self.missing_retire_alert_sent:
                return

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
            data = rows[header_row_index + 1:]

            yesterday = (datetime.now(self.tz) - timedelta(days=1)).strftime("%Y/%m/%d")
            checked = {}

            for row in data:
                if len(row) <= max(name_col, timestamp_col, status_col):
                    continue
                if yesterday not in row[timestamp_col]:
                    continue
                name = self.normalize_name(row[name_col].strip())
                status = row[status_col].strip()
                checked.setdefault(name, set()).add(status)

            missing = [name for name, statuses in checked.items() if "出勤" in statuses and "退勤" not in statuses]

            if missing:
                channel = self.bot.get_channel(ALERT_CHANNEL_ID)
                if channel:
                    role_mention = "<@&1270600048878686259>"
                    names = "\n".join(f"・{name}" for name in missing)
                    message = f"{role_mention}\n昨日出勤して退勤していない可能性がある人のリスト:\n{names}"
                    await channel.send(message)
                    self.missing_retire_alert_sent = True

        except Exception as e:
            print(f"退勤漏れチェックエラー: {e}")

    async def send_to_discord(self, normalized_name, embed, status):
    for guild in self.bot.guilds:
        if guild.id != SERVER_ID:
            continue
        for category in guild.categories:
            if self.normalize_name(category.name) == normalized_name:
                text_channel = discord.utils.get(category.channels, name="今日のお仕事")
                if isinstance(text_channel, discord.TextChannel):
                    await text_channel.send(embed=embed)
                    if status == "出勤":
                        await text_channel.send(f"SNS広報\n{SNS_LINK}")
                    return True
        for channel in guild.channels:
            if isinstance(channel, discord.ForumChannel) and self.normalize_name(channel.name) == normalized_name:
                for thread in channel.threads:
                    if thread.name == "今日のお仕事":
                        await thread.send(embed=embed)
                        if status == "出勤":
                            await thread.send(f"SNS広報\n{SNS_LINK}")
                        return True
    return False



    def create_embed(self, raw_name, status, timestamp_str, headers, row):
        embed = discord.Embed(color=0x1E90FF if status == "出勤" else 0x32CD32)
        embed.title = f"{'🔵 出勤連絡' if status == '出勤' else '🟢 退勤報告'} - {raw_name}"
        embed.set_footer(text=timestamp_str)

        def get(col): return row[headers.index(col)].strip() if col in headers else ""

        if status == "出勤":
            temp, cond = get("体温"), get("体調")
            if temp or cond:
                embed.add_field(name="体調情報", value=" | ".join(filter(None, [f"体温: {temp}" if temp else "", f"体調: {cond}" if cond else ""])), inline=False)
            if get("体調備考"):
                embed.add_field(name="体調備考", value=get("体調備考"), inline=False)
            if get("本日の作業予定"):
                tasks = "\n".join(item.strip() for item in get("本日の作業予定").split(","))
                embed.add_field(name="本日の作業予定", value=tasks, inline=False)
            if get("本日の目標"):
                embed.add_field(name="本日の目標", value=get("本日の目標"), inline=False)

        elif status == "退勤":
            if get("本日の作業内容"):
                embed.add_field(name="本日の作業内容", value=get("本日の作業内容"), inline=False)
            if get("感想"):
                embed.add_field(name="感想", value=get("感想"), inline=False)
            if get("特記事項"):
                embed.add_field(name="特記事項", value=get("特記事項"), inline=False)

            label_map = {
                "目標通りの作業ができた": "目標通りの作業",
                "順調に作業がすすめられた": "順調に作業を進める",
                "間違いに気づき、直すことができた": "間違い発見と修正",
                "作業準備・整理整頓ができた": "作業準備・整理整頓",
                "必要に応じた報告・連絡・相談ができた": "報告・連絡・相談",
                "集中して取り組むことができた": "集中して作業",
                "楽しい時間を過ごすことができた": "楽しく過ごせた"
            }
            ratings = []
            for col, label in label_map.items():
                val = get(col)
                if val:
                    ratings.append(f"{val} | {label}")
            if ratings:
                embed.add_field(name="評価項目", value="```\n" + "\n".join(ratings) + "\n```", inline=False)

        return embed

    @check_form_responses.before_loop
    async def before_check_form_responses(self):
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

