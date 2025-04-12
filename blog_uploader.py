import discord
from discord.ext import commands
from discord import app_commands
import os
from utils.image_utils import compress_image

class BlogUploaderCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="投稿", description="ブログ記事の投稿情報を登録します")
    @app_commands.describe(
        タイトル="記事のタイトル",
        本文="記事の本文",
        画像="投稿画像（JPEG/PNG）"
    )
    async def post_article(
        self,
        interaction: discord.Interaction,
        タイトル: str,
        本文: str,
        画像: discord.Attachment
    ):
        await interaction.response.defer(thinking=True, ephemeral=True)

        # 保存先フォルダ
        os.makedirs("compressed_images", exist_ok=True)

        # ファイル保存パス
        original_path = f"compressed_images/{画像.filename}"
        await 画像.save(original_path)

        compressed_path = f"compressed_images/compressed_{画像.filename}"

        try:
            # 画像圧縮
            result_path = compress_image(original_path, compressed_path)
            size_kb = round(os.path.getsize(result_path) / 1024, 2)

            # 成功メッセージ
            await interaction.followup.send(
                f"✅ 記事投稿データを受け取りました！\n\n"
                f"**タイトル**: {タイトル}\n"
                f"**本文（先頭30文字）**: {本文[:30]}...\n"
                f"**画像**: `{os.path.basename(result_path)}`（{size_kb}KB）\n\n"
                f"※このあと拡張機能または自動投稿処理で反映されます。",
                ephemeral=True
            )

            # 🔜 ここでbase64化して JSON 書き出しも可能！

        except Exception as e:
            await interaction.followup.send(f"❌ 圧縮失敗: {str(e)}", ephemeral=True)
