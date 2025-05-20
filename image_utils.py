from PIL import Image
import os

def compress_image(input_path: str, output_path: str, max_size_bytes: int = 1048576):
    """
    入力画像をWebP形式で1MB以下に圧縮し、出力パスに保存する。
    透過PNGにも対応（透過情報がある場合はRGBAとして保存）。
    """
    img = Image.open(input_path)

    # 透過があるかを判定し、RGBまたはRGBAに変換
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    quality = 95

    while quality > 10:
        img.save(output_path, format="WEBP", quality=quality, method=6)
        if os.path.getsize(output_path) <= max_size_bytes:
            return output_path
        quality -= 5

    raise Exception("WebP画像の圧縮に失敗しました（1MB以下にできませんでした）")

# 使用例
# compress_image("original.png", "compressed.webp")
