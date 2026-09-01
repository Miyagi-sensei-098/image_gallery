---
name: monthly-folder-add
description: 新規月別画像フォルダ（例：26_09月データ）を追加した際の一連の処理を行う。jpg→webp変換、ギャラリーデータ更新、商品メタ（Excel→products.js）更新、OCR実行までを順に実施する。トリガー：「新しい月のフォルダを追加した」「月別データを追加」「webp変換してギャラリー更新してOCRかけて」「新規フォルダの処理」など。
version: 1.4.0
---

# 月別フォルダ追加ワークフロー

`99_sample一覧` プロジェクトに新しい月別画像フォルダ（例：`26_09月データ`）を追加したときに実施する標準処理。

> 📝 v1.3.0でフォルダ命名規則を変更（2026-09-01）。プロジェクトが2027年3月まで続き、8〜12月・1〜3月が2回ずつ登場するため、旧方式（`{連番2桁}_{月}月データ`、例：`06_8月データ`）では同じ月名が複数回現れてサイドバー表示が曖昧になる問題があった。年を明示する新方式に統一済み（過去フォルダも含め全リネーム）。詳細は[[naming-convention]]参照。
> 📝 v1.4.0で表示・並び順を変更（2026-09-01同日）。①表示ラベルを `2026年8月データ` → `2026_08月データ`（月を2桁ゼロ埋め、年区切りを"_"に）に変更。②サイドバーの「商品カテゴリ」見出しを廃止し、緑ラベル等5フォルダも月別データと同じ単一リストで扱う（実質カテゴリとして機能していなかったため）。③サイドバーに「新しい順（デフォルト）／古い順」の並び替えを追加、緑ラベル等は2025年扱いの最古データとしてソートに組み込まれる。実装は `generate_gallery_data.py` の `get_section_label()` と `00_image_gallery.html` の `buildGallery()`。

## ユーザーから受け取る入力（作業開始前に3点そろえる）

| # | 入力 | 確認方法 |
|---|---|---|
| ① | 新規月フォルダ（jpg） | プロジェクト直下に `{YY}_{M}月データ` があるか |
| ② | その月の「○月データ_保管」GoogleドライブフォルダのURL | **未提供なら AskUserQuestion で確認してから進む**（ステップ3のgoogleDriveFolderIdに必要） |
| ③ | 品番Excel | `00_list_xlsx/` に当年度の xlsx が置かれているか（シート「【N月】品番コピー用」に新月分があるか） |

この3点がそろっていれば、以降のステップはユーザーへの削除確認（ステップ2）とコミット指示（ステップ6）以外、確認なしで完遂できる。

## 前提

- 作業ディレクトリ：`D:/GoogleDrive/40_Puzzle/99_sample一覧`
- Python仮想環境：`.venv/Scripts/python.exe`（torch CUDA版、easyocr、manga_ocr、PIL インストール済み）
- フォルダ命名：`{YY}_{M}月データ`（西暦下2桁_月、例：`26_09月データ`=2026年9月）。カテゴリフォルダ（緑ラベル等）は例外で `{YY}_{NN}_名前`（例：`25_01_緑ラベル`）
- `gallery_data/index.js` の `num` はフォルダ名の先頭2桁ではなく、`generate_gallery_data.py` がスキャン順（＝表示順）で採番する連番。フォルダ名の先頭2桁（YY）と一致しないので、OCR進捗確認などフォルダ名で絞り込む処理では**必ずフォルダ名全体**を使う（後述）
- 画像サイズ：1000×1000、メイン6枚／商品

## 全体フロー

```
新規フォルダ追加 (jpg) + Excelリスト追加 (00_list_xlsx/*.xlsx) + GoogleドライブURL受領
  ↓
1. jpg → webp 変換（quality=80）
  ↓
2. 元jpg削除（確認後）
  ↓
3. ギャラリーデータ再生成 ＋ 新月の googleDriveFolderId を index.js に追記
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
folder = '26_09月データ'  # ← 対象フォルダを書き換える
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
- 26_04月データ（旧14_04月）の実測：67MB / 367枚 ≒ 180KB/枚
- 大きく外れた場合のみ q=75〜85 で再調整

---

## ステップ 2：元 jpg 削除

変換完了とサイズを確認してから削除する。**ユーザー確認を取ること**。

```bash
# 確認
ls 26_09月データ/*.webp | wc -l
ls 26_09月データ/*.jpg | wc -l
du -sh 26_09月データ

# 削除（ユーザー OK 後）
rm 26_09月データ/*.jpg
```

---

## ステップ 3：ギャラリーデータ再生成

`generate_gallery_data.py` はプロジェクト直下の `\d{2}_*` フォルダを自動検出する。新規フォルダ追加後に1回実行すれば `gallery_data/section_NN.js` と `index.js` が更新される。

```bash
.venv/Scripts/python.exe generate_gallery_data.py
```

出力例：
```
googleDriveFolderId 引き継ぎ: 12件
  スキャン中: 26_09月データ ... 76商品, 460枚
Done! 19 sections -> gallery_data/
```

ブラウザで `00_image_gallery.html` を再読み込みすると新フォルダが表示される（`num` はフォルダ名の先頭桁ではなく、スキャン順の連番として自動採番される。`index.js` の `label` フィールドが実際の表示ラベル＝年を含む人間向けの文字列）。

### 新月の googleDriveFolderId を index.js に追記する

モーダルのGoogleドライブボタン（月の「○月データ_保管」フォルダを開く）用。

1. 既存月のIDは `generate_gallery_data.py` が既存 index.js から**自動で引き継ぐ**（`num`＝スキャン順の位置をキーに引き継ぐので、フォルダ名が変わっても同じ位置の月には同じIDが付く。ログの `googleDriveFolderId 引き継ぎ: N件` で確認）。
2. **新月分だけは手動追記**：ユーザーから受け取ったDrive URL（`https://drive.google.com/drive/folders/{ID}`）の `folders/` 以降がID。`gallery_data/index.js` の新月エントリに追記する：

```json
{
  "num": "19",
  "name": "26_09月データ",
  "label": "2026_09月データ",
  ...
  "imageCount": 460,
  "googleDriveFolderId": "1yj5LcVdRt2056rV4NAlKSzFbYAo8wkHS"
}
```

3. 追記後の検証：index.js をJSONパースして「セクション数」と「googleDriveFolderId数（月次フォルダ数と一致）」を確認する。
4. ブラウザでの反映確認は **Ctrl+F5**（index.js はバージョン文字列なしで読まれるためキャッシュされやすい）。

> ⚠️ index.js は機械生成物。手編集はこの googleDriveFolderId 追記だけに限定する。

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
    - 25_08月データ/22_new/...
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
folder = '26_09月データ'  # ← 対象フォルダ名を丸ごと書き換える（先頭2桁だけだと他の月と衝突する）
prefix = folder + '/'
with open('ocr_data.js', 'r', encoding='utf-8') as f:
    content = f.read()
data = json.loads(content[len('const OCR_DATA = '):].strip().rstrip(';'))
done = [k for k in data if k.startswith(prefix)]
actual = glob.glob(f'{folder}/*.webp')
print(f'処理済み: {len(done)} / {len(actual)} ({len(done)*100//len(actual)}%)')
"
```

> ⚠️ v1.3.0の命名規則変更で、フォルダ名の先頭2桁（YY）は年を表すだけで一意ではなくなった（例：`26_01月データ`〜`26_08月データ`は全て`26_`で始まる）。**必ずフォルダ名全体**（末尾に`/`を付けた文字列）で絞り込むこと。先頭2桁だけの `k.startswith('26_')` は他の月まで巻き込むのでNG。

### 完了確認

- 残り0件 / ログに `Done.` 出力
- `ocr_data.js` 最終保存時刻が処理終了時刻

### 再処理が必要な場合

`ocr_data.js` から該当フォルダのエントリを削除してから再実行：

```bash
.venv/Scripts/python.exe -c "
import json
folder = '26_09月データ'  # ← 対象フォルダ名を丸ごと書き換える
prefix = folder + '/'
with open('ocr_data.js', 'r', encoding='utf-8') as f:
    content = f.read()
data = json.loads(content[len('const OCR_DATA = '):].strip().rstrip(';'))
before = len(data)
data = {k: v for k, v in data.items() if not k.startswith(prefix)}
print(f'削除: {before - len(data)}件')
with open('ocr_data.js', 'w', encoding='utf-8') as f:
    f.write('const OCR_DATA = ' + json.dumps(data, ensure_ascii=False, indent=2) + ';')
"
```

---

## ステップ 6：動作確認 → コミット&プッシュ

ユーザーがブラウザ（`00_image_gallery.html`）で動作確認 → OKの指示を受けてから：

```bash
# gallery_data/index.js には新月の googleDriveFolderId 追記分が含まれる
git add "26_09月データ" ocr_data.js gallery_data/index.js gallery_data/section_NN.js gallery_data/products.js
# generate_product_meta.py（VENDOR_READINGS/VENDOR_ALIASES追記）・generate_gallery_data.py を編集した場合のみ追加
# git add generate_product_meta.py generate_gallery_data.py
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
| `did not find executable at 'C:\Python313\python.exe'` 等、venvが起動しない | venvの基底Python消失。`uv python install 3.13` でインストール後、`.venv/pyvenv.cfg` の `home`/`executable`/`command` をuvのPythonパス（例：`C:\Users\Sho Miyagi\AppData\Roaming\uv\python\cpython-3.13.x-windows-x86_64-none`）に書き換える。**パッケージ（torch等5.2GB）は`.venv`内に残っているので再インストール不要**。検証：`--version` が3.13.x、`torch.cuda.is_available()` がTrue（2026-07-06に実績あり） |
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
