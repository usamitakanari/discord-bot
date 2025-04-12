import discord
from discord.ext import commands
from discord import app_commands
import os
from PIL import Image
import tempfile

class BlogUploaderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="画像圧縮", description="画像を1MB未満に圧縮して送信します")
    @app_commands.describe(
        画像="投稿画像（JPEG/PNG）"
    )
    async def post_image(self, interaction: discord.Interaction, 画像: discord.Attachment):
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            # 一時保存先（元画像）
            temp_dir = tempfile.gettempdir()
            original_path = os.path.join(temp_dir, 画像.filename)
            await 画像.save(original_path)

            # 圧縮画像の保存先
            compressed_path = os.path.join(temp_dir, f"compressed_{画像.filename}")

            # 画像を開く
            img = Image.open(original_path)
            format = img.format  # JPEG, PNG など

            if format == "JPEG":
                quality = 95
                while quality > 10:
                    img.save(compressed_path, format="JPEG", quality=quality, optimize=True)
                    if os.path.getsize(compressed_path) <= 1048576:
                        break
                    quality -= 5
                else:
                    raise Exception("JPEG画像を1MB未満に圧縮できませんでした")

            elif format == "PNG":
                img.save(compressed_path, format="PNG", optimize=True, compress_level=9)
                if os.path.getsize(compressed_path) > 1048576:
                    # PNGでは1MB未満にならなかった → JPEG変換
                    rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)

                    quality = 90
                    while quality > 10:
                        rgb_img.save(compressed_path, format="JPEG", quality=quality, optimize=True)
                        if os.path.getsize(compressed_path) <= 1048576:
                            break
                        quality -= 5
                    else:
                        raise Exception("PNG→JPEG変換でも1MB未満に圧縮できませんでした")
            else:
                raise Exception(f"{format}形式は現在未対応です")

            # 成功メッセージ
            size_kb = round(os.path.getsize(compressed_path) / 1024, 2)
            await interaction.followup.send(
                content=(
                    f"✅ 圧縮画像が完成しました！ `{os.path.basename(compressed_path)}`\n"
                    f"サイズ：{size_kb}KB/1024KB\n`1MB=1024KB`"
                ),
                file=discord.File(compressed_path),
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(f"❌ エラーが発生しました: {str(e)}", ephemeral=True)
