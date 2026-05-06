"""
画像ギャラリーデータ自動生成スクリプト
フォルダ構造をスキャンして gallery_data/ にセクション別JSファイルを出力する。
使い方: python generate_gallery_data.py
        または generate_gallery_data.bat をダブルクリック
"""

import os
import re
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "gallery_data"

# 数字プレフィックスで始まるフォルダのみ対象
SECTION_PATTERN = re.compile(r"^(\d{2})_(.+)$")

# 画像拡張子
IMAGE_EXTENSIONS = {".webp", ".png", ".jpg", ".jpeg"}


def is_image(filename):
    return Path(filename).suffix.lower() in IMAGE_EXTENSIONS


def get_product_id(filename):
    """ファイル名から商品IDを抽出する。
    例: 'A-11001_01.webp' -> 'A-11001'
        '10000185_01.webp' -> '10000185'
        '02_10001217_01.webp' -> '02_10001217'
        '10000735_1_1.webp' -> '10000735'
    """
    stem = Path(filename).stem  # 拡張子なし

    # _XX (2桁数字) で終わるパターンを探す（_01, _02, ... _06 など）
    # 末尾から _数字 を除いた部分が商品ID
    match = re.match(r"^(.+)_(\d{2})$", stem)
    if match:
        return match.group(1)

    # それ以外はファイル名全体を商品IDとする（比較画像など）
    # 例: A-11001_A-11001, A-11001_G-11039
    # 最初のアンダースコアまでを商品IDとする
    parts = stem.split("_")
    if len(parts) >= 2:
        # 数字のみの短いプレフィックスがある場合（02_10001217_01 のようなパターン��
        # -> 既にmatchで処理済みのはず
        return parts[0]

    return stem


def get_sort_key(filename):
    """画像ファイルのソート用キー。番号順にする。"""
    stem = Path(filename).stem
    match = re.match(r"^(.+)_(\d{2})$", stem)
    if match:
        return (0, int(match.group(2)))  # メイン画像: 番号順
    return (1, stem)  # その他: 名前順（メイン画像の後）


def scan_section_with_subfolders(section_dir, section_name):
    """サブフォルダ構造のセクションをスキャン (06_8月データ形式)"""
    products = []

    subdirs = sorted([
        d for d in section_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ])

    for subdir in subdirs:
        images = sorted(
            [f.name for f in subdir.iterdir() if f.is_file() and is_image(f.name)],
            key=get_sort_key
        )
        if images:
            # パスは section_name/subdir_name/filename 形式
            image_paths = [f"{section_name}/{subdir.name}/{img}" for img in images]
            products.append({
                "id": subdir.name,
                "images": image_paths
            })

    return products


def scan_section_flat(section_dir, section_name):
    """フラット構造のセクションをスキャン (07以降の月別データ、01-05の商品カテゴリ)"""
    # 全画像ファイル取得
    all_images = sorted(
        [f.name for f in section_dir.iterdir() if f.is_file() and is_image(f.name)]
    )

    if not all_images:
        return []

    # 商品IDでグルーピング
    product_groups = {}
    for img in all_images:
        pid = get_product_id(img)
        if pid not in product_groups:
            product_groups[pid] = []
        product_groups[pid].append(img)

    # 各グループ内をソート
    products = []
    # 商品IDの出現順序を保持（最初の画像の位置でソート）
    seen_order = []
    for img in all_images:
        pid = get_product_id(img)
        if pid not in seen_order:
            seen_order.append(pid)

    for pid in seen_order:
        images = sorted(product_groups[pid], key=get_sort_key)
        image_paths = [f"{section_name}/{img}" for img in images]
        products.append({
            "id": pid,
            "images": image_paths
        })

    return products


def has_subfolders(section_dir):
    """セクションディレクトリがサブフォルダ構造かどうか判定"""
    for item in section_dir.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            return True
        if item.is_file() and is_image(item.name):
            return False
    return False


def generate_section_data(section_dir, section_name):
    """セクションデータを��成"""
    if has_subfolders(section_dir):
        products = scan_section_with_subfolders(section_dir, section_name)
    else:
        products = scan_section_flat(section_dir, section_name)

    return {
        "section": section_name,
        "productCount": len(products),
        "imageCount": sum(len(p["images"]) for p in products),
        "products": products
    }


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    # セクションフォルダを検出
    sections = []
    for item in sorted(BASE_DIR.iterdir()):
        if item.is_dir():
            match = SECTION_PATTERN.match(item.name)
            if match:
                num = match.group(1)
                sections.append((num, item.name, item))

    if not sections:
        print("エラー: セクションフォル���が見つかりません。")
        return

    print(f"検出されたセクション: {len(sections)}個")

    # セクション一覧 (index) を生成
    index_data = []

    for num, name, path in sections:
        print(f"  スキャン中: {name} ...", end=" ")
        data = generate_section_data(path, name)
        print(f"{data['productCount']}商品, {data['imageCount']}枚")

        # JSファイルとして出力
        js_var_name = f"GALLERY_{num}"
        js_content = f"var {js_var_name} = {json.dumps(data, ensure_ascii=False, indent=None)};\n"

        output_file = OUTPUT_DIR / f"section_{num}.js"
        output_file.write_text(js_content, encoding="utf-8")

        index_data.append({
            "num": num,
            "name": name,
            "file": f"gallery_data/section_{num}.js",
            "varName": js_var_name,
            "productCount": data["productCount"],
            "imageCount": data["imageCount"]
        })

    # インデックスファイル出力
    index_js = f"var GALLERY_INDEX = {json.dumps(index_data, ensure_ascii=False, indent=2)};\n"
    (OUTPUT_DIR / "index.js").write_text(index_js, encoding="utf-8")

    print(f"\nDone! {len(sections)} sections -> gallery_data/")
    print("Reload HTML in browser.")


if __name__ == "__main__":
    main()
