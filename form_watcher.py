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
        self.notified_entries = set()
        self.check_start_time = datetime.now(self.tz)  # 起動時刻を記録
        print("✅ FormWatcherCog 起動完了！チェック有効化！")
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

                timestamp_str = row[timestamp_col].strip()
                try:
                    timestamp_obj = datetime.strptime(timestamp_str, "%Y/%m/%d %H:%M:%S")
                    if timestamp_obj < self.check_start_time:
                        continue  # 起動前のデータはスキップ
                except:
                    pass

                entry_key = f"{row[name_col].strip()}|{timestamp_str}|{row[status_col].strip()}"
                if entry_key in self.notified_entries:
                    continue

                raw_name = row[name_col].strip()
                normalized_name = self.normalize_name(raw_name)

                print(f"▶️ チェック中: raw_name = '{raw_name}' → normalized_name = '{normalized_name}'")

                greeting = ""
                status = row[status_col].strip()
                try:
                    hour = int(timestamp_str.split()[1].split(":")[0])
                except:
                    hour = 12

                if status == "出勤":
                    greeting = (
                        f"> {raw_name} さん！{'おはようございます' if hour <= 11 else 'こんにちは'} :sunny:\n"
                        f"> 本日もよろしくお願いします:blush:\n\n"
                        f"{timestamp_str}\n"
                        f"## 出勤\n"
                    )
                    temp = row[headers.index("体温")].strip() if "体温" in headers else ""
                    cond = row[headers.index("体調")].strip() if "体調" in headers else ""
                    note = row[headers.index("体調備考")].strip() if "体調備考" in headers else ""
                    schedule = row[headers.index("本日の作業予定")].strip() if "本日の作業予定" in headers else ""
                    goal = row[headers.index("本日の目標")].strip() if "本日の目標" in headers else ""

                    status_line = []
                    if temp:
                        status_line.append(f"**体温 : ** {temp}")
                    if cond:
                        status_line.append(f"**体調 : ** {cond}")
                    if note:
                        status_line.append(f"**体調備考 : ** {note}")
                    if status_line:
                        greeting += "> " + " | ".join(status_line) + "\n"
                    if schedule:
                        greeting += f"> **本日の作業予定 : ** {schedule}\n"
                    if goal:
                        greeting += f"> **本日の目標 : ** {goal}\n"

                elif status == "退勤":
                    greeting = (
                        f"> {raw_name} さん！本日もお疲れ様でした:sparkles:\n"
                        f"> 次回もよろしくお願いします:person_bowing:\n\n"
                        f"{timestamp_str}\n"
                        f"## 退勤\n"
                    )
                    work = row[headers.index("本日の作業内容")].strip() if "本日の作業内容" in headers else ""
                    feedback = row[headers.index("感想")].strip() if "感想" in headers else ""
                    special = row[headers.index("特記事項")].strip() if "特記事項" in headers else ""

                    if work:
                        greeting += f"> **本日の作業内容 : ** {work}\n"
                    if feedback:
                        greeting += f"> **感想 : ** {feedback}\n"

                    # 表形式評価項目
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
                    table = []
                    for key in table_keys:
                        if key in headers:
                            val = row[headers.index(key)].strip()
                            if val:
                                table.append(f"- **{key}**：{val}")
                    if table:
                        greeting += "\n" + "\n".join(table) + "\n"

                    if special:
                        greeting += f"> **特記事項 : ** {special}\n"

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

                if found:
                    self.notified_entries.add(entry_key)

        except Exception as e:
            print(f"フォーム通知処理でエラーが発生しました: {e}")

    @check_form_responses.before_loop
    async def before_check_form_responses(self):
        await self.bot.wait_until_ready()

    def normalize_name(self, name):
        return re.sub(r"[\s　]", "", name.strip())
