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

# 月次データフォルダ: "{YY}_{M}月{suffix}" (例: 25_08月データ -> 2025年8月データ)
MONTHLY_PATTERN = re.compile(r"^\d{2}_(\d{1,2})月(.*)$")
# カテゴリフォルダ: "{YY}_{NN}_{名前}" (例: 25_01_緑ラベル -> 緑ラベル)
CATEGORY_PATTERN = re.compile(r"^\d{2}_(\d{2})_(.+)$")


def get_section_label(name):
    """フォルダ名から表示用ラベル（年を明示した人間向け文字列）を生成する。
    例: '25_08月データ' -> '2025_08月データ'（月は2桁ゼロ埋め、年区切りは"_"）、'25_01_緑ラベル' -> '緑ラベル'
    """
    m = MONTHLY_PATTERN.match(name)
    if m:
        full_year = 2000 + int(name[:2])
        month = int(m.group(1))
        return f"{full_year}_{month:02d}月{m.group(2)}"
    m = CATEGORY_PATTERN.match(name)
    if m:
        return m.group(2)
    return re.sub(r"^\d+_", "", name)

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


def load_existing_drive_ids():
    """既存の index.js から googleDriveFolderId を読み取り、
    num（スキャン順の連番）-> ID の辞書で返す（再生成時に引き継ぐため）。
    フォルダ名ではなく位置（num）をキーにするのは、命名規則変更でフォルダ名が
    変わっても同じ位置の月には同じIDを引き継げるようにするため。"""
    index_file = OUTPUT_DIR / "index.js"
    if not index_file.exists():
        return {}
    try:
        content = index_file.read_text(encoding="utf-8").strip()
        # "var GALLERY_INDEX = [...];" から JSON 部分を取り出す
        json_str = content[content.index("["):content.rindex("]") + 1]
        entries = json.loads(json_str)
        return {
            e["num"]: e["googleDriveFolderId"]
            for e in entries if e.get("googleDriveFolderId")
        }
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"警告: 既存index.jsの読み取りに失敗（googleDriveFolderIdは引き継がれません）: {e}")
        return {}


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    # 手動付与された googleDriveFolderId を引き継ぐ
    drive_ids = load_existing_drive_ids()
    if drive_ids:
        print(f"googleDriveFolderId 引き継ぎ: {len(drive_ids)}件")

    # セクションフォルダを検出（ソート順=表示順。00_list_xlsx等の管理用フォルダは対象外）
    sections = []
    for item in sorted(BASE_DIR.iterdir()):
        if item.is_dir() and not item.name.startswith("00_"):
            if SECTION_PATTERN.match(item.name):
                sections.append((item.name, item))

    if not sections:
        print("エラー: セクションフォル���が見つかりません。")
        return

    print(f"検出されたセクション: {len(sections)}個")

    # セクション一覧 (index) を生成
    # num はフォルダ名の先頭数字ではなく、スキャン順（＝表示順）の連番として採番する。
    # これにより命名規則が変わっても num<=5 等の既存ロジック・googleDriveFolderId引き継ぎに影響しない。
    index_data = []

    for i, (name, path) in enumerate(sections, start=1):
        num = f"{i:02d}"
        print(f"  スキャン中: {name} ...", end=" ")
        data = generate_section_data(path, name)
        print(f"{data['productCount']}商品, {data['imageCount']}枚")

        # JSファイルとして出力
        js_var_name = f"GALLERY_{num}"
        js_content = f"var {js_var_name} = {json.dumps(data, ensure_ascii=False, indent=None)};\n"

        output_file = OUTPUT_DIR / f"section_{num}.js"
        output_file.write_text(js_content, encoding="utf-8")

        entry = {
            "num": num,
            "name": name,
            "label": get_section_label(name),
            "file": f"gallery_data/section_{num}.js",
            "varName": js_var_name,
            "productCount": data["productCount"],
            "imageCount": data["imageCount"]
        }
        if num in drive_ids:
            entry["googleDriveFolderId"] = drive_ids[num]
        index_data.append(entry)

    # インデックスファイル出力
    index_js = f"var GALLERY_INDEX = {json.dumps(index_data, ensure_ascii=False, indent=2)};\n"
    (OUTPUT_DIR / "index.js").write_text(index_js, encoding="utf-8")

    print(f"\nDone! {len(sections)} sections -> gallery_data/")
    print("Reload HTML in browser.")


if __name__ == "__main__":
    main()
