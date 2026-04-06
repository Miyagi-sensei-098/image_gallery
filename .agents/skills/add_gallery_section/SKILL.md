---
name: add_gallery_section
description: 新しい画像フォルダのアコーディオンセクションを 00_image_gallery.html に追加する
---

# 画像ギャラリーセクション追加スキル

新規に画像フォルダが追加された際、`00_image_gallery.html` の末尾にアコーディオンセクションを自動追加するためのスキルです。

## 前提条件

- 追加対象の画像フォルダがワークスペース直下に存在すること（例: `13_03月データ/`）
- フォルダ内に `.webp` 形式の画像ファイルが格納されていること
- `00_image_gallery.html` がワークスペース直下に存在すること

## 実行手順

### ステップ1: Pythonスクリプトの作成

以下の内容で `add_gallery_section.py` をワークスペース直下に作成する。
**`FOLDER_NAME` 変数をユーザーが指定したフォルダ名に書き換えること。**

```python
import os
import re
from collections import defaultdict

# ============================================================
# 設定 - ここをユーザー指定のフォルダ名に変更する
# ============================================================
FOLDER_NAME = '<<フォルダ名>>'  # 例: '13_03月データ', '14_04月データ'

IMG_DIR = FOLDER_NAME
TARGET_HTML = '00_image_gallery.html'
ACCORDION_NAME = FOLDER_NAME


def generate_html_block():
    all_files = os.listdir(IMG_DIR)
    webp_files = [f for f in all_files if f.lower().endswith('.webp')]

    groups = defaultdict(list)
    for f in webp_files:
        first_underscore = f.index('_') if '_' in f else len(f)
        prefix = f[:first_underscore]
        groups[prefix].append(f)

    html_output = []
    html_output.append(f'<button class="accordion">{ACCORDION_NAME}</button>')
    html_output.append('<div class="panel">')

    for prefix in sorted(groups.keys(), key=lambda x: x.lower()):
        files = groups[prefix]

        priority = []
        others = []
        for f in files:
            suffix = f[len(prefix):]
            if re.match(r'^_0[1-5]\.webp$', suffix, re.IGNORECASE):
                priority.append(f)
            else:
                others.append(f)

        priority.sort(key=lambda x: x.lower())
        others.sort(key=lambda x: x.lower())
        sorted_files = priority + others

        for i in range(0, len(sorted_files), 5):
            chunk = sorted_files[i:i+5]
            html_output.append('  <div class="image-row">')
            for file in chunk:
                html_output.append(f'    <img src="{IMG_DIR}/{file}" alt="{file}" onclick="openModal(this)" loading="lazy" />')
            html_output.append('  </div>')

    html_output.append('</div>')

    return "\n".join(html_output)


def main():
    with open(TARGET_HTML, 'r', encoding='utf-8') as f:
        original_html = f.read()

    # 既存の同名セクションを削除（冪等性のため）
    pattern = rf'<button class="accordion">{re.escape(ACCORDION_NAME)}</button>.*?<div class="panel">.*?</div>\s*'
    cleaned_html = re.sub(pattern, '', original_html, flags=re.DOTALL)

    cleaned_html = cleaned_html.replace('</body>', '').replace('</html>', '')
    cleaned_html = cleaned_html.rstrip()

    new_block = generate_html_block()

    final_html = cleaned_html + "\n" + new_block + "\n  </body>\n</html>"

    with open(TARGET_HTML, 'w', encoding='utf-8') as f:
        f.write(final_html)

    print(f"{ACCORDION_NAME}の追加作業が正常に完了しました。")


if __name__ == '__main__':
    main()
```

### ステップ2: スクリプトの実行

```bash
python add_gallery_section.py
```

### ステップ3: 結果の確認

- `00_image_gallery.html` の末尾に新しいアコーディオンセクションが追加されていることを確認
- `</body>` と `</html>` が正しく閉じられていることを確認

### ステップ4: クリーンアップ

スクリプトファイルを削除する。

```bash
Remove-Item add_gallery_section.py
```

## 厳守ルール

1. **フォルダ直接スキャン:** `00_file_list.txt` は無視し、`os.listdir()` で画像ファイルを直接取得する
2. **余計なテキスト出力の禁止:** HTML内には `<img>` タグと `<div>` 等の構造タグのみを含め、グループ名やファイル名をテキストとして表示しない
3. **確実なクリーンアップ:** 追記前に、正規表現で既存の同名セクションと末尾の `</body>` `</html>` を削除する
4. **正しいソート順:** 各グループ内で `_01`〜`_05.webp` を優先して番号順に、それ以外をアルファベット順に並べる
5. **画像タグの形式:** `<img src="{フォルダ名}/{ファイル名}" alt="{ファイル名}" onclick="openModal(this)" loading="lazy" />`
6. **1行5画像:** `<div class="image-row">` 内に最大5つの `<img>` タグを配置する

## ファイル名のグループ化ルール

- ファイル名の最初の `_` より前の部分をプレフィックス（グループキー）とする
- 例: `10000850_01.webp` → プレフィックス `10000850`
- 例: `A-09018_0318_01.webp` → プレフィックス `A-09018`
- グループはプレフィックスのアルファベット順（大文字小文字無視）でソートされる

## HTML構造の例

```html
<button class="accordion">13_03月データ</button>
<div class="panel">
  <div class="image-row">
    <img src="13_03月データ/10000850_01.webp" alt="10000850_01.webp" onclick="openModal(this)" loading="lazy" />
    <img src="13_03月データ/10000850_02.webp" alt="10000850_02.webp" onclick="openModal(this)" loading="lazy" />
    <img src="13_03月データ/10000850_03.webp" alt="10000850_03.webp" onclick="openModal(this)" loading="lazy" />
    <img src="13_03月データ/10000850_04.webp" alt="10000850_04.webp" onclick="openModal(this)" loading="lazy" />
    <img src="13_03月データ/10000850_05.webp" alt="10000850_05.webp" onclick="openModal(this)" loading="lazy" />
  </div>
  <div class="image-row">
    <img src="13_03月データ/10000850_06.webp" alt="10000850_06.webp" onclick="openModal(this)" loading="lazy" />
    <img src="13_03月データ/10000850_10000850.webp" alt="10000850_10000850.webp" onclick="openModal(this)" loading="lazy" />
  </div>
</div>
