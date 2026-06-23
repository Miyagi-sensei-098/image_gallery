---
name: monthly-folder-add
description: 新規月別画像フォルダ（例：15_05月データ）を追加した際の一連の処理を行う。jpg→webp変換、ギャラリーデータ更新、商品メタ（Excel→products.js）更新、OCR実行までを順に実施する。トリガー：「新しい月のフォルダを追加した」「月別データを追加」「webp変換してギャラリー更新してOCRかけて」「新規フォルダの処理」など。
version: 1.1.1
---

# 月別フォルダ追加ワークフロー

`99_sample一覧` プロジェクトに新しい月別画像フォルダ（例：`15_05月データ`）を追加したときに実施する標準処理。

## 前提

- 作業ディレクトリ：`D:/OneDrive/40_Puzzle/99_sample一覧`
- Python仮想環境：`.venv/Scripts/python.exe`（torch CUDA版、easyocr、manga_ocr、PIL インストール済み）
- フォルダ命名：`{2桁番号}_{月}月データ`（例：`15_05月データ`）
- 画像サイズ：1000×1000、メイン6枚／商品

## 全体フロー

```
新規フォルダ追加 (jpg) + Excelリスト追加 (00_list_xlsx/*.xlsx)
  ↓
1. jpg → webp 変換（quality=80）
  ↓
2. 元jpg削除（確認後）
  ↓
3. ギャラリーデータ再生成
  ↓
4. 商品メタ（Excel → products.js）再生成
  ↓
5. OCR実行（バックグラウンド、GPU使用）  ※ステップ4と並行可
  ↓
6. 動作確認 → コミット&プッシュ
```

> 📝 ユーザーは新規月の画像フォルダと一緒に `00_list_xlsx/` にExcelリストを追加する運用。Excelのファイル名は決まっておらず、`00_list_xlsx/*.xlsx` を全て読む（`generate_product_meta.py` がフォルダ内全xlsxを自動検出する）。

---

## ステップ 1：jpg → webp 変換

`quality=80` で他月（14_04月：~200KB/枚）と同水準に圧縮する。

```bash
.venv/Scripts/python.exe -c "
from PIL import Image
import glob, os
folder = '15_05月データ'  # ← 対象フォルダを書き換える
files = sorted(glob.glob(f'{folder}/*.jpg'))
print(f'Total: {len(files)}')
for i, f in enumerate(files, 1):
    out = f[:-4] + '.webp'
    if os.path.exists(out):
        continue
    Image.open(f).save(out, 'webp', quality=80)
    if i % 50 == 0:
        print(f'{i}/{len(files)}')
print('Done')
"
```

### 品質指針
- `quality=80` → 1000×1000 jpg ~1MB が webp ~190KB（約80%圧縮）
- 14_04月の実測：67MB / 367枚 ≒ 180KB/枚
- 大きく外れた場合のみ q=75〜85 で再調整

---

## ステップ 2：元 jpg 削除

変換完了とサイズを確認してから削除する。**ユーザー確認を取ること**。

```bash
# 確認
ls 15_05月データ/*.webp | wc -l
ls 15_05月データ/*.jpg | wc -l
du -sh 15_05月データ

# 削除（ユーザー OK 後）
rm 15_05月データ/*.jpg
```

---

## ステップ 3：ギャラリーデータ再生成

`generate_gallery_data.py` はプロジェクト直下の `\d{2}_*` フォルダを自動検出する。新規フォルダ追加後に1回実行すれば `gallery_data/section_NN.js` と `index.js` が更新される。

```bash
.venv/Scripts/python.exe generate_gallery_data.py
```

出力例：
```
  スキャン中: 15_05月データ ... 76商品, 460枚
Done! 15 sections -> gallery_data/
```

ブラウザで `00_image_gallery.html` を再読み込みすると新フォルダが表示される。

---

## ステップ 4：商品メタ（Excel → products.js）再生成

新しい月のExcelリストが `00_list_xlsx/` に追加されたら実行する。`generate_product_meta.py` がフォルダ内の全 `.xlsx` を自動検出し、品番→商品名・事業者・楽天URLを抽出して `gallery_data/products.js` に出力する。

```bash
.venv/Scripts/python.exe generate_product_meta.py
```

出力例：
```
読み込み: ★★チームまさ★★楽天制作関連_共有_2026年度4月-3月.xlsx
  - 【4月】品番コピー用: 60 件
  - 【5月】品番コピー用: 79 件
URL別名で補完: 40 件

==== 生成結果 ====
出力: gallery_data/products.js
商品ID数: 932（商品名あり 926 / 事業者あり 843 / URLあり 878）

==== 突き合わせ（画像 ⇔ 対応表）====
画像の商品ID数: 816 / 対応表とマッチ: 801 (98%)
画像はあるが名前が付かないID: 15 件
    - 06_8月データ/22_new/...
対応表にあるが画像が無いID: 131 件（参考）
```

### 確認ポイント
- **マッチ率**：通常95%以上が目安。大きく下がる場合は新しいExcelの列構成が変わった可能性。
- **「画像はあるが名前が付かないID」**：プレースホルダ（`new`, `uni_new` 等）は無視してOK。普通の品番がここに出る場合はExcel側のID表記揺れ（大小・空白・序数付き）の可能性 → 抽出スクリプトの `normalize_id` で吸収しているはずだが、新パターンが出たら報告。
- **新しい事業者**：ドロワーの五十音ソート用に読みを `generate_product_meta.py` の `VENDOR_READINGS` 辞書に追記する。読みが分からない場合は **公式サイト・楽天ページ・WebSearchで確認**。読みを追記したら再実行で `products.js` に反映される。
- **事業者の表記揺れを統合したい場合**：同じ事業者が支店名・担当者名付きなど別表記で出てくる場合（例：「株式会社根室海鮮市場 北」と「株式会社根室海鮮市場」、「根室海宝(宝田 進)」と「根室海宝」）は、`generate_product_meta.py` の `VENDOR_ALIASES` 辞書に「左→右」のマッピングを追加する。再実行時に `事業者エイリアスを適用: N 件` と出れば反映成功。

> ⚠️ `products.js` は機械生成物。手で編集しないこと。修正は `generate_product_meta.py`（`VENDOR_READINGS`、`VENDOR_ALIASES`、`VENDOR_STRONG`、`PRODUCT_HINT` など）を直して再生成する。
> 📝 Excel側に新しい列構成・記法が出てきた場合（例：複数事業者のカンマ連結、新しい品番フォーマット等）は `extract_records()` を拡張する。

---

## ステップ 5：OCR 実行（GPU・バックグラウンド）

`generate_ocr_data.py` は `ocr_data.js` に未登録の webp のみを差分処理する。

### 実行

```bash
.venv/Scripts/python.exe generate_ocr_data.py
```

Claude Code から起動する場合は **必ず `run_in_background: true`**。初期化（EasyOCR + MangaOCR）に5〜10分、処理速度は GTX 1650 Ti で約3.3枚/分（≒1枚18秒）。460枚で約2時間50分。

### GPU 使用確認

```bash
.venv/Scripts/python.exe -c "import torch; print('CUDA:', torch.cuda.is_available(), torch.cuda.get_device_name(0))"
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
```

GPU 100% 稼働、メモリ約4GB 使用が正常。

### 進捗確認

stdout はバッファリングされてログに即時反映されないため、`ocr_data.js`（10件ごとに自動保存）のエントリ数で確認する：

```bash
.venv/Scripts/python.exe -c "
import json, glob
folder_prefix = '15_'  # ← 対象フォルダの先頭を書き換える
with open('ocr_data.js', 'r', encoding='utf-8') as f:
    content = f.read()
data = json.loads(content[len('const OCR_DATA = '):].strip().rstrip(';'))
done = [k for k in data if k.startswith(folder_prefix)]
actual = glob.glob(f'{folder_prefix}*/*.webp')
print(f'処理済み: {len(done)} / {len(actual)} ({len(done)*100//len(actual)}%)')
"
```

> ⚠️ 部分一致 `'15_' in k` は NG。`10001505_01.webp` のようにファイル名にも `15_` が含まれることがある。必ず `k.startswith('15_')` を使う。

### 完了確認

- 残り0件 / ログに `Done.` 出力
- `ocr_data.js` 最終保存時刻が処理終了時刻

### 再処理が必要な場合

`ocr_data.js` から該当フォルダのエントリを削除してから再実行：

```bash
.venv/Scripts/python.exe -c "
import json
folder_prefix = '15_'
with open('ocr_data.js', 'r', encoding='utf-8') as f:
    content = f.read()
data = json.loads(content[len('const OCR_DATA = '):].strip().rstrip(';'))
before = len(data)
data = {k: v for k, v in data.items() if not k.startswith(folder_prefix)}
print(f'削除: {before - len(data)}件')
with open('ocr_data.js', 'w', encoding='utf-8') as f:
    f.write('const OCR_DATA = ' + json.dumps(data, ensure_ascii=False, indent=2) + ';')
"
```

---

## ステップ 6：動作確認 → コミット&プッシュ

ユーザーがブラウザ（`00_image_gallery.html`）で動作確認 → OKの指示を受けてから：

```bash
git add "15_05月データ" ocr_data.js gallery_data/index.js gallery_data/section_NN.js gallery_data/products.js
# generate_product_meta.py を編集した場合のみ追加
# git add generate_product_meta.py
git commit -m "26MMDD_Nmonth_OCR"   # 例：260604_5gatu_OCR
git push
```

コミットメッセージ形式の前例：
- `260520_search_update`
- `260604_5gatu_OCR`
- `260604_search_company`（商品名・事業者検索の追加時）

> ⚠️ **`00_list_xlsx/` はリポジトリに含めない**。Excelには社内人名・進捗が含まれるため非公開（`products.js` だけ公開すればフロントは動く）。
> ⚠️ `.claude/settings.local.json`、`.claude/launch.json`、`.claude/worktrees/`、`00_image_gallery_BLUR.html` も無関係なので含めない。フォルダ・データファイルのみを明示的に `git add` する。
> ⚠️ コミット&プッシュは **ユーザーの明示的な指示があるまで実行しない**。

---

## トラブルシュート

| 症状 | 対処 |
|---|---|
| `torch.cuda.OutOfMemoryError` | `generate_ocr_data.py` は自動で `mag_ratio=1.5, canvas=2000` にフォールバック済み |
| OCR が0%のまま | 初期化に5〜10分かかる。GPU使用率と `ocr_data.js` 保存時刻で確認 |
| 進捗ログが出ない | stdout バッファリング。`ocr_data.js` のエントリ数で見る |
| webp 変換後にサイズが大きすぎ／小さすぎ | quality を 75〜85 で再調整 |

## 処理時間目安（GTX 1650 Ti）

| 処理 | 460枚あたり |
|---|---|
| jpg→webp 変換 | 約1〜2分 |
| ギャラリーデータ生成 | 数秒 |
| OCR 初期化 | 5〜10分 |
| OCR 本処理 | 約2時間40分 |
