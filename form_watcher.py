import discord
from discord.ext import commands, tasks
from datetime import datetime
import pytz
import csv
import requests
from io import StringIO
import re
import json

SERVER_ID = #1101493830915719273
SENT_LOG_PATH = "sent_entries.json"

CHECK_FROM_TIME_STR = "2025/03/25 16:00:00"
CHECK_FROM_TIME = datetime.strptime(CHECK_FROM_TIME_STR, "%Y/%m/%d %H:%M:%S")

class FormWatcherCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tz = pytz.timezone("Asia/Tokyo")
        self.notified_entries = self.load_sent_entries()
        print("✅ FormWatcherCog 起動完了！チェック有効化！")
        self.check_form_responses.start()

    def cog_unload(self):
        self.check_form_responses.cancel()

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

                entry_key = f"{row[name_col].strip()}|{timestamp_str}|{row[status_col].strip()}"
                if entry_key in self.notified_entries:
                    continue

                raw_name = row[name_col].strip()
                normalized_name = self.normalize_name(raw_name)
                status = row[status_col].strip()

                embed = discord.Embed(color=0x00BFFF)
                embed.set_footer(text=timestamp_str)

                if status == "出勤":
                    embed.title = f"🔵 {raw_name} さん 出勤連絡"
                    temp = row[headers.index("体温")].strip() if "体温" in headers else ""
                    cond = row[headers.index("体調")].strip() if "体調" in headers else ""
                    note = row[headers.index("体調備考")].strip() if "体調備考" in headers else ""
                    schedule = row[headers.index("本日の作業予定")].strip() if "本日の作業予定" in headers else ""
                    goal = row[headers.index("本日の目標")].strip() if "本日の目標" in headers else ""

                    if temp or cond:
                        status_line = []
                        if temp:
                            status_line.append(f"体温: {temp}")
                        if cond:
                            status_line.append(f"体調: {cond}")
                        embed.add_field(name="体調情報", value=" | ".join(status_line), inline=False)
                    if note:
                        embed.add_field(name="体調備考", value=note, inline=False)
                    if schedule:
                        embed.add_field(name="本日の作業予定", value=schedule, inline=False)
                    if goal:
                        embed.add_field(name="本日の目標", value=goal, inline=False)

                elif status == "退勤":
                    embed.title = f"🟢 {raw_name} さん 退勤報告"
                    work = row[headers.index("本日の作業内容")].strip() if "本日の作業内容" in headers else ""
                    feedback = row[headers.index("感想")].strip() if "感想" in headers else ""
                    special = row[headers.index("特記事項")].strip() if "特記事項" in headers else ""

                    if work:
                        embed.add_field(name="本日の作業内容", value=work, inline=False)
                    if feedback:
                        embed.add_field(name="感想", value=feedback, inline=False)
                    if special:
                        embed.add_field(name="特記事項", value=special, inline=False)

                    table_keys = [
                        "目標通りの作業ができた",
                        "手順を覚えることができた",
                        "間違いに気づき、直すことができた",
                        "オンライン（公式LINEやDiscord）での挨拶等",
                        "作業準備・整理整頓",
                        "必要に応じた報告・連絡・相談",
                        "集中して取り組むことが出来た",
                        "楽しい時間を過ごすことができた"
                    ]
                    rating_lines = []
                    for key in table_keys:
                        if key in headers:
                            val = row[headers.index(key)].strip()
                            if val:
                                rating_lines.append((key, val))

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
                                await text_channel.send(embed=embed)
                                if status == "退勤" and rating_lines:
                                    rating_embed = discord.Embed(title="📝 評価項目", color=0x87CEFA)
                                    for key, val in rating_lines:
                                        rating_embed.add_field(name=key, value=val, inline=True)
                                    await text_channel.send(embed=rating_embed)
                                found = True
                                break
                    if found:
                        break

                    for channel in guild.channels:
                        if isinstance(channel, discord.ForumChannel) and self.normalize_name(channel.name) == normalized_name:
                            for thread in channel.threads:
                                if thread.name == "今日のお仕事":
                                    await thread.send(embed=embed)
                                    if status == "退勤" and rating_lines:
                                        rating_embed = discord.Embed(title="📝 評価項目", color=0x87CEFA)
                                        for key, val in rating_lines:
                                            rating_embed.add_field(name=key, value=val, inline=True)
                                        await thread.send(embed=rating_embed)
                                    found = True
                                    break
                        if found:
                            break

                if found:
                    self.save_sent_entry(entry_key)

        except Exception as e:
            print(f"フォーム通知処理でエラーが発生しました: {e}")

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
