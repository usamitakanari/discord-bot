import discord
from discord.ext import commands
from discord import app_commands
import os
from PIL import Image
import tempfile

class BlogUploaderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="画像圧縮", description="画像を1MB未満に圧縮して送信します（WebP形式）")
    @app_commands.describe(
        画像="投稿画像（JPEG/PNGなど）"
    )
    async def post_image(self, interaction: discord.Interaction, 画像: discord.Attachment):
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            temp_dir = tempfile.gettempdir()
            original_path = os.path.join(temp_dir, 画像.filename)
            await 画像.save(original_path)

            # 拡張子だけwebpに変更したファイル名を作成
            original_name, _ = os.path.splitext(画像.filename)
            compressed_path = os.path.join(temp_dir, f"{original_name}.webp")

            img = Image.open(original_path)

            # 透過対応
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                img = img.convert("RGBA")
            else:
                img = img.convert("RGB")

            # WebP圧縮処理
            quality = 95
            while quality > 10:
                img.save(compressed_path, format="WEBP", quality=quality, method=6)
                if os.path.getsize(compressed_path) <= 1048576:
                    break
                quality -= 5
            else:
                raise Exception("画像を1MB未満に圧縮できませんでした")

            size_kb = round(os.path.getsize(compressed_path) / 1024, 2)
            await interaction.followup.send(
                content=(
                    f"✅ 圧縮画像が完成しました！（WebP形式） `{os.path.basename(compressed_path)}`\n"
                    f"サイズ：{size_kb}KB / 1024KB `1MB=1024KB`"
                ),
                file=discord.File(compressed_path),
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(f"❌ エラーが発生しました: {str(e)}", ephemeral=True)
