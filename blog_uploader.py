import discord
from discord.ext import commands
from discord import app_commands
import os
from PIL import Image
import tempfile

class BlogUploaderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="画像圧縮", description="画像を1MB未満に圧縮します")
    @app_commands.describe(
        画像="画像（JPEG/PNG）"
    )
    async def post_image(self, interaction: discord.Interaction, 画像: discord.Attachment):
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            # 一時保存先（元画像）
            temp_dir = tempfile.gettempdir()
            original_path = os.path.join(temp_dir, 画像.filename)
            await 画像.save(original_path)

            # 圧縮画像の保存先
            os.makedirs("/app/downloads", exist_ok=True)
            compressed_path = os.path.join("/app/downloads", f"compressed_{画像.filename}")

            # 圧縮処理
            img = Image.open(original_path)
            format = img.format

            if format == "JPEG":
                quality = 95
                while quality > 10:
                    img.save(compressed_path, format="JPEG", quality=quality, optimize=True)
                    if os.path.getsize(compressed_path) <= 1048576:
                        break
                    quality -= 5
                else:
                    raise Exception("1MB未満に圧縮できませんでした")
            elif format == "PNG":
                img.save(compressed_path, format="PNG", optimize=True, compress_level=9)
                if os.path.getsize(compressed_path) > 1048576:
                    raise Exception("PNG画像の圧縮に失敗しました（1MB未満になりません）")
            else:
                raise Exception(f"{format}形式は現在未対応です")

            # 成功メッセージ
            size_kb = round(os.path.getsize(compressed_path) / 1024, 2)
            await interaction.followup.send(
                content=f"✅ 圧縮画像が完成しました！ `{os.path.basename(compressed_path)}`",
                file=discord.File(compressed_path),
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(f"❌ エラーが発生しました: {str(e)}", ephemeral=True)
