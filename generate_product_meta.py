# -*- coding: utf-8 -*-
"""
商品メタデータ生成スクリプト
00_list_xlsx/ 内の Excel（品番コピー用シート）を読み、
  商品ID -> { name: 商品名, vendor: 事業者名, url: 楽天URL }
の対応表を gallery_data/products.js (var PRODUCT_META = {...};) として出力する。

特徴:
  - 追加インストール不要（Python標準ライブラリのみ）で .xlsx を読む
  - 月によって列順がバラバラ・メモ行混在でも、行スキャン＋ヒューリスティックで抽出
  - 品番セルの値（＝画像ファイル名のコード）を優先キーにする。1行に複数コードがある行も分解。
  - URL末尾の品番は「別名(alias)」として補完（画像が数字IDで命名されていても拾えるように）
  - 品番は数字/英字・大小ゆれを normalize_id() で吸収
  - gallery_data/section_*.js と突き合わせ、未マッチ（画像にあるが名前が無いID等）を表示

使い方:
  python generate_product_meta.py
  （Excelを差し替えたら再実行して gallery_data/products.js をコミット）
"""

import glob
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_DIR = Path(__file__).parent
XLSX_DIR = BASE_DIR / "00_list_xlsx"
GALLERY_DIR = BASE_DIR / "gallery_data"
OUT_FILE = GALLERY_DIR / "products.js"

# 事業者名 -> 並び替え用の読み（ひらがな）。漢字とカナが混ざっても五十音順で並べるための辞書。
# 読みが不明・新規の事業者はここに追記してください（無ければHTML側で屋号フォールバック）。
VENDOR_READINGS = {
    "オーイーシー株式会社": "おーいーしー",
    "株式会社カネカイチ": "かねかいち",
    "有限会社カネカイチ鈴木商店": "かねかいちすずきしょうてん",
    "株式会社カネマ浜屋商店": "かねまはまやしょうてん",
    "株式会社セイブ": "せいぶ",
    "泰匠物産": "たいしょうぶっさん",
    "株式会社トラスト": "とらすと",
    "ナカウロコ中西水産": "なかうろこなかにしすいさん",
    "株式会社マルダイ水産": "まるだいすいさん",
    "株式会社マルチュウ福原商店": "まるちゅうふくはらしょうてん",
    "有限会社マルイ井上水産": "まるいいのうえすいさん",
    "株式会社マルユウ": "まるゆう",
    "有限会社ヤマリ利琴水産": "やまりりことすいさん",
    "海の幸イースト": "うみのさちいーすと",
    "株式会社海匠": "かいしょう",
    "株式会社兼由": "かねよし",
    "根室かに鮮株式会社": "ねむろかにせん",
    "株式会社根室海鮮市場": "ねむろかいせんいちば",
    "株式会社根室海鮮市場 北": "ねむろかいせんいちばきた",
    "根室海宝": "ねむろかいほう",
    "根室海宝(宝田　進)": "ねむろかいほうたからだすすむ",
    "根室海宝(宝田 進)": "ねむろかいほうたからだすすむ",
    "根室北のグルメ市場": "ねむろきたのぐるめいちば",
    "株式会社藤井水産": "ふじいすいさん",
    "根室　藤井水産　創業1902": "ふじいすいさん",
    "落石漁業協同組合": "おちいしぎょぎょうきょうどうくみあい",
}

# Windowsコンソールの文字化け対策
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 品番トークン（ASCII数字4桁以上 もしくは 英字-数字）。全角の連番(１２３４)は拾わない。
ID_TOKEN_RE = re.compile(r"[A-Za-z]{0,2}-?[0-9]{4,}")

# 事業者名に出る「会社・屋号」を示す強い手がかり
VENDOR_STRONG = re.compile(
    r"株式会社|有限会社|合同会社|（株）|\(株\)|（有）|\(有\)|"
    r"水産|物産|商店|商會|商会|商事|市場|フーズ|ファーム|イースト|トラスト|"
    r"グルメ|本舗|製作所|協同組合|組合|海宝"
)
# 商品名・規格に出やすい語（これを含むセルは事業者ではないと判定）
PRODUCT_HINT = re.compile(
    r"セット|詰め合わせ|詰合せ|お刺身|刺身|切り身|切身|味付|醤油漬|焼き|"
    r"煮|貝柱|選べる|×|✕|応援品|[0-9０-９]+\s*[gｇkｋ]|[0-9０-９]+\s*[Pp]"
)

# 容量・規格っぽいセル（商品名候補から除外）: 70×２ / 200×１ / 80〜90g２P など
CAP_RE = re.compile(r"^[\d０-９.,，、\sgkｇｋGKPpＰ×x✕＊*〜~ｇ()（）\-－]+$")

# 商品名の頭に紛れる重複した品番プレフィックス（"A-46001 商品名" 等）を除去
LEAD_ID_RE = re.compile(r"^[A-Za-z]{0,2}-?[0-9]{3,}\s+")

# 楽天URL末尾の品番（/10000954/ 形式。?variantId= 付きは末尾一致しないので拾わない）
URL_ID_RE = re.compile(r"/([A-Za-z]{0,2}-?[0-9]{4,})/?\s*$")

RELNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def jp_count(s):
    """ひらがな・カタカナ・漢字の数（商品名らしさの指標）。"""
    return len(re.findall(r"[぀-ヿ一-鿿]", s))


def normalize_id(raw):
    """品番/ファイル名を共通キーに正規化。
    例: 'A-09002' -> 'A-09002' / '10000185_01.webp' -> '10000185'
        '02_10001217_01' -> '10001217' / 'a-30059' -> 'A-30059'
    """
    s = str(raw).strip()
    s = re.sub(r"\.[A-Za-z0-9]+$", "", s)     # 拡張子除去
    s = re.sub(r"^\d{1,2}\s*_", "", s)        # 先頭の序数 "N_"/"NN_" 除去（2_10004967 等）
    s = s.split("_")[0]                          # 最初の下線より前
    s = re.sub(r"-\d{1,2}$", "", s)            # 末尾のハイフン連番除去（d-09039-01 -> d-09039）
    return s.strip().upper()


def localname(tag):
    return tag.split("}")[-1]


def col_index(ref):
    m = re.match(r"([A-Z]+)", ref or "A1")
    s = m.group(1)
    idx = 0
    for ch in s:
        idx = idx * 26 + (ord(ch) - 64)
    return idx - 1


def read_xlsx_rows(path):
    """xlsx の全シートを (sheet_name, [行(セル文字列のリスト)]) で返す。"""
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")):
            shared.append("".join(t.text or "" for t in si.iter() if localname(t.tag) == "t"))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    sheets = [(s.get("name"), s.get(RELNS)) for s in wb.iter() if localname(s.tag) == "sheet"]
    rels = {}
    if "xl/_rels/workbook.xml.rels" in z.namelist():
        for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")):
            rels[r.get("Id")] = r.get("Target")

    result = []
    for name, rid in sheets:
        target = rels.get(rid, "")
        spath = "xl/" + target.lstrip("/") if target else None
        if not spath or spath not in z.namelist():
            continue
        sx = ET.fromstring(z.read(spath))
        rows = []
        for row in (r for r in sx.iter() if localname(r.tag) == "row"):
            cells = {}
            maxc = -1
            for c in row:
                if localname(c.tag) != "c":
                    continue
                ci = col_index(c.get("r"))
                vtext = "".join(v.text or "" for v in c.iter() if localname(v.tag) in ("v", "t"))
                if c.get("t") == "s" and vtext.isdigit() and int(vtext) < len(shared):
                    val = shared[int(vtext)]
                else:
                    val = vtext
                cells[ci] = val
                if ci > maxc:
                    maxc = ci
            rows.append([str(cells.get(i, "")) for i in range(maxc + 1)])
        result.append((name, rows))
    z.close()
    return result


def clean_name(s):
    s = s.strip()
    s = LEAD_ID_RE.sub("", s)            # 先頭の重複品番を除去
    s = re.sub(r"[　\s]+", " ", s)    # 全角/連続スペースを1個に
    s = s.strip()
    # 作業メモ等は商品名として採用しない
    if s.startswith("※") or s.startswith("メモ") or s.startswith("注意") or s.startswith("●"):
        return ""
    return s


def is_url(s):
    return s.strip().lower().startswith("http")


def split_vendors(cell):
    """事業者セルを ・/、/, で複数事業者に分割し、各要素が会社名らしいものだけ返す。"""
    if not cell:
        return []
    parts = [p.strip() for p in re.split(r"[・、,]", str(cell)) if p.strip()]
    return [p for p in parts if is_vendor_like(p)]


def is_vendor_like(cell):
    """セルが事業者名（会社・屋号）らしいか。商品名・品番・規格は除外する。"""
    c = str(cell).strip()
    if not c or is_url(c):
        return False
    if not VENDOR_STRONG.search(c):       # 会社・屋号の語が無ければ事業者ではない
        return False
    if re.match(r"^\s*[A-Za-z]{0,2}-?[0-9]{4,}", c):  # 先頭が品番 → 商品名
        return False
    if PRODUCT_HINT.search(c):             # 商品名・規格の語を含む → 事業者ではない
        return False
    return True


def find_id_cell(row):
    """品番らしいトークンを含む最初のセル（URLは除く）の列番号を返す。無ければ None。"""
    for i, c in enumerate(row):
        cs = c.strip()
        if not cs or is_url(cs):
            continue
        if ID_TOKEN_RE.search(cs):
            return i
    return None


def find_vendor(row, start):
    for c in row[start:]:
        if is_vendor_like(c):
            return c.strip()
    return ""


def find_url(row):
    for c in row:
        if is_url(c):
            return c.strip()
    return ""


def extract_records(row):
    """行から (records, url_id) を返す。records は {id,name,vendor,url} のリスト。"""
    idc = find_id_cell(row)
    if idc is None:
        return [], ""
    codes = ID_TOKEN_RE.findall(row[idc])
    if not codes:
        return [], ""

    url = find_url(row)
    url_id = ""
    if url:
        m = URL_ID_RE.search(url)
        if m:
            url_id = normalize_id(m.group(1))
    vendor_cell = find_vendor(row, idc + 1)

    if len(codes) == 1:
        cands = [c.strip() for c in row[idc + 1:] if c.strip()]
        # 商品名候補: URL・事業者らしいセル・規格セルを除く
        texts = [c for c in cands if not is_url(c) and not is_vendor_like(c) and not CAP_RE.match(c)]
        name = ""
        text_jp = [c for c in texts if jp_count(c) > 0]
        if text_jp:
            name = clean_name(max(text_jp, key=lambda c: (jp_count(c), len(c))))
        vendor = vendor_cell if is_vendor_like(vendor_cell) else ""
        vendors = split_vendors(vendor)
        rec = {"id": normalize_id(codes[0]), "name": name, "vendor": (vendors[0] if vendors else vendor), "url": url}
        if len(vendors) > 1:
            rec["vendors"] = vendors
        return [rec], url_id

    # 複数コード（カンマ区切り）行: 品番の次セルを商品名、事業者を 、/・ で分割し対応づけ
    name_cell = row[idc + 1].strip() if idc + 1 < len(row) else ""
    if is_url(name_cell) or name_cell == vendor_cell:
        name_cell = ""
    name_parts = [clean_name(x) for x in re.split(r"[、,]", name_cell) if x.strip()]
    v_parts = [x.strip() for x in re.split(r"[、,・]", vendor_cell) if x.strip()]
    recs = []
    for k, code in enumerate(codes):
        if len(name_parts) == len(codes):
            nm = name_parts[k]
        elif len(name_parts) == 1:
            nm = name_parts[0]
        else:
            nm = clean_name(name_cell)
        if len(v_parts) == len(codes):
            vd = v_parts[k]
        elif len(v_parts) == 1:
            vd = v_parts[0]
        else:
            vd = vendor_cell
        if not is_vendor_like(vd):
            vd = ""
        vds = split_vendors(vd)
        rec2 = {"id": normalize_id(code), "name": nm, "vendor": (vds[0] if vds else vd), "url": url}
        if len(vds) > 1:
            rec2["vendors"] = vds
        recs.append(rec2)
    return recs, ""  # 複数行は alias を付けない（URLは親listingのため曖昧）


def merge(meta, pid, rec):
    if not pid:
        return
    cur = meta.get(pid)
    if cur is None:
        out = {"name": rec.get("name", ""), "vendor": rec.get("vendor", ""), "url": rec.get("url", "")}
        if rec.get("vendors"):
            out["vendors"] = rec["vendors"]
        meta[pid] = out
    else:
        if not cur.get("name") and rec.get("name"):
            cur["name"] = rec["name"]
        if not cur.get("vendor") and rec.get("vendor"):
            cur["vendor"] = rec["vendor"]
        if not cur.get("vendors") and rec.get("vendors"):
            cur["vendors"] = rec["vendors"]
        if not cur.get("url") and rec.get("url"):
            cur["url"] = rec["url"]


def build_meta():
    meta = {}
    aliases = []  # (url_id, rec) 後で本キーに無いものだけ補完
    files = sorted(glob.glob(str(XLSX_DIR / "*.xlsx")))
    if not files:
        print("エラー: 00_list_xlsx に .xlsx が見つかりません。")
        return meta

    for f in files:
        if Path(f).name.startswith("~$"):
            continue
        print("読み込み:", Path(f).name)
        for sheet_name, rows in read_xlsx_rows(f):
            count = 0
            for row in rows:
                recs, url_id = extract_records(row)
                for rec in recs:
                    if not rec["name"] and not rec["url"]:
                        continue
                    merge(meta, rec["id"], rec)
                    count += 1
                if url_id and len(recs) == 1:
                    aliases.append((url_id, recs[0]))
            print("  - %s: %d 件" % (sheet_name, count))

    # URL末尾IDを別名として補完（本キーに無いものだけ）
    added = 0
    for url_id, rec in aliases:
        if url_id and url_id not in meta:
            meta[url_id] = {"name": rec.get("name", ""), "vendor": rec.get("vendor", ""), "url": rec.get("url", "")}
            added += 1
    if added:
        print("URL別名で補完: %d 件" % added)
    return meta


def load_gallery_ids():
    """gallery_data/section_*.js から画像の正規化IDを集める。"""
    ids = {}
    for p in sorted(glob.glob(str(GALLERY_DIR / "section_*.js"))):
        txt = Path(p).read_text(encoding="utf-8")
        m = re.search(r"=\s*(\{.*\})\s*;?\s*$", txt, re.S)
        if not m:
            continue
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        for prod in data.get("products", []):
            for img in prod.get("images", []):
                ids.setdefault(normalize_id(Path(img).name), img)
    return ids


def write_products_js(meta):
    GALLERY_DIR.mkdir(exist_ok=True)
    lines = [
        "// 自動生成ファイル: generate_product_meta.py が出力します。手で編集しないでください。",
        "// 商品ID -> { name: 商品名, vendor: 事業者名, url: 楽天商品URL }",
        "var PRODUCT_META = {",
    ]
    keys = sorted(meta.keys())
    for i, k in enumerate(keys):
        comma = "," if i < len(keys) - 1 else ""
        lines.append("  %s: %s%s" % (
            json.dumps(k, ensure_ascii=False),
            json.dumps(meta[k], ensure_ascii=False),
            comma,
        ))
    lines.append("};")
    # 事業者の読み（五十音順ソート用）。HTMLが VENDOR_READINGS[display名] で参照する。
    lines.append("")
    lines.append("// 事業者名 -> 読み（ひらがな）。五十音順ソート用。")
    lines.append("var VENDOR_READINGS = {")
    rkeys = sorted(VENDOR_READINGS.keys())
    for i, vk in enumerate(rkeys):
        comma = "," if i < len(rkeys) - 1 else ""
        lines.append("  %s: %s%s" % (
            json.dumps(vk, ensure_ascii=False),
            json.dumps(VENDOR_READINGS[vk], ensure_ascii=False),
            comma,
        ))
    lines.append("};")
    OUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    meta = build_meta()
    if not meta:
        return
    write_products_js(meta)

    with_name = sum(1 for v in meta.values() if v["name"])
    with_vendor = sum(1 for v in meta.values() if v["vendor"])
    with_url = sum(1 for v in meta.values() if v["url"])

    print("\n==== 生成結果 ====")
    print("出力:", OUT_FILE)
    print("商品ID数: %d（商品名あり %d / 事業者あり %d / URLあり %d）"
          % (len(meta), with_name, with_vendor, with_url))

    gallery = load_gallery_ids()
    if gallery:
        g_ids = set(gallery.keys())
        m_ids = set(meta.keys())
        matched = g_ids & m_ids
        no_name = sorted(gallery[i] for i in (g_ids - m_ids))
        no_image = sorted(m_ids - g_ids)
        print("\n==== 突き合わせ（画像 ⇔ 対応表）====")
        print("画像の商品ID数: %d / 対応表とマッチ: %d (%.0f%%)"
              % (len(g_ids), len(matched), 100.0 * len(matched) / max(1, len(g_ids))))
        print("画像はあるが名前が付かないID: %d 件" % len(no_name))
        for s in no_name[:40]:
            print("    -", s)
        if len(no_name) > 40:
            print("    ... 他 %d 件" % (len(no_name) - 40))
        print("対応表にあるが画像が無いID: %d 件（参考）" % len(no_image))
    print("\n完了。HTMLを再読み込みしてください。")


if __name__ == "__main__":
    main()
