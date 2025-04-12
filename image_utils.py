from PIL import Image
import os

def compress_image(input_path: str, output_path: str, max_size_bytes: int = 1048576):
    """
    入力画像を形式を維持したまま1MB以下に圧縮し、出力パスに保存する
    """
    img = Image.open(input_path)
    format = img.format  # JPEG, PNG, etc.

    if format == "JPEG":
        quality = 95
        while quality > 10:
            img.save(output_path, format="JPEG", quality=quality, optimize=True)
            if os.path.getsize(output_path) <= max_size_bytes:
                return output_path
            quality -= 5
        raise Exception("JPEG画像の圧縮に失敗しました（1MB以下にできませんでした）")

    elif format == "PNG":
        compress_level = 9
        img.save(output_path, format="PNG", optimize=True, compress_level=compress_level)
        if os.path.getsize(output_path) <= max_size_bytes:
            return output_path
        else:
            raise Exception("PNG画像の圧縮に失敗しました（1MB以下にできませんでした）")

    else:
        raise Exception(f"{format}形式の圧縮は現在未対応です")

# 使用例
# compress_image("original.jpg", "compressed.jpg")
