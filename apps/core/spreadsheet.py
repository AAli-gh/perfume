"""خواندن و نوشتن جدول ساده با Excel (xlsx) یا CSV — بدون وابستگی خارجی.

- write_xlsx(rows) ← bytes: یک برگه راست‌به‌چپ؛ متن به‌صورت inline string و عدد به‌صورت عدد.
- read_table(filename, data) ← list[list[str]]: اولین برگه xlsx یا CSV (UTF-8 با/بدون BOM؛ ویندوز-۱۲۵۶).

فایل‌ها را فقط کارکنان آپلود می‌کنند، با این حال اندازه، تعداد ردیف، حجم باز‌شده zip و DOCTYPE (حمله
گسترش entity در XML) محدود می‌شوند.
"""

import csv
import io
import re
import zipfile
from xml.etree import ElementTree
from xml.sax.saxutils import escape

MAX_UPLOAD = 5 * 1024 * 1024
MAX_UNZIPPED = 40 * 1024 * 1024
MAX_ROWS = 5000
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "pr": "http://schemas.openxmlformats.org/package/2006/relationships"}
_CELL_REF = re.compile(r"([A-Z]+)(\d+)")
_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class SpreadsheetError(ValueError):
    pass


# ---------- نوشتن ----------

def _col(index):
    name = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def _cell(ref, value):
    if isinstance(value, bool):
        value = "بله" if value else "خیر"
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"><v>{value}</v></c>'
    text = escape(_ILLEGAL_XML.sub("", "" if value is None else str(value)))
    if text[:1] in ("=", "+", "-", "@"):  # جلوگیری از اجرای فرمول (CSV/Excel injection)
        text = "'" + text
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def write_xlsx(rows, sheet_name="Sheet1"):
    rows = list(rows)
    body = "".join(
        f'<row r="{r + 1}">' + "".join(_cell(f"{_col(c)}{r + 1}", v) for c, v in enumerate(row)) + "</row>"
        for r, row in enumerate(rows)
    )
    widths = "".join(f'<col min="{i + 1}" max="{i + 1}" width="18" customWidth="1"/>'
                     for i in range(max((len(r) for r in rows), default=0)))
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0" rightToLeft="1"><pane ySplit="1" topLeftCell="A2" state="frozen"/>'
        '</sheetView></sheetViews>'
        f'{"<cols>" + widths + "</cols>" if widths else ""}<sheetData>{body}</sheetData></worksheet>'
    )
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>'),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'officeDocument" Target="xl/workbook.xml"/></Relationships>'),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets><sheet name="{escape(sheet_name[:31])}" sheetId="1" r:id="rId1"/></sheets></workbook>'),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'worksheet" Target="worksheets/sheet1.xml"/></Relationships>'),
        "xl/worksheets/sheet1.xml": sheet,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def write_csv(rows):
    buffer = io.StringIO()
    buffer.write("﻿")  # BOM تا Excel متن فارسی را درست نشان دهد
    writer = csv.writer(buffer)
    for row in rows:
        writer.writerow([("'" + v) if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v for v in row])
    return buffer.getvalue().encode("utf-8")


# ---------- خواندن ----------

def _xml(archive, name):
    with archive.open(name) as handle:
        data = handle.read(MAX_UNZIPPED + 1)
    if len(data) > MAX_UNZIPPED:
        raise SpreadsheetError("فایل بیش از حد بزرگ است.")
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise SpreadsheetError("فایل Excel نامعتبر است.")
    return ElementTree.fromstring(data)


def read_xlsx(data):
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise SpreadsheetError("فایل Excel (xlsx) معتبر نیست.") from exc
    with archive:
        if sum(info.file_size for info in archive.infolist()) > MAX_UNZIPPED:
            raise SpreadsheetError("فایل بیش از حد بزرگ است.")
        names = set(archive.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            for item in _xml(archive, "xl/sharedStrings.xml").findall("m:si", NS):
                shared.append("".join(t.text or "" for t in item.iter(f"{{{NS['m']}}}t")))
        sheet_path = "xl/worksheets/sheet1.xml"
        if "xl/workbook.xml" in names and "xl/_rels/workbook.xml.rels" in names:
            first = _xml(archive, "xl/workbook.xml").find("m:sheets/m:sheet", NS)
            rels = {r.get("Id"): r.get("Target") for r in _xml(archive, "xl/_rels/workbook.xml.rels")}
            target = rels.get(first.get(f"{{{NS['r']}}}id")) if first is not None else None
            if target:
                sheet_path = target.lstrip("/") if target.startswith("/") else "xl/" + target
        if sheet_path not in names:
            raise SpreadsheetError("برگه‌ای در فایل Excel پیدا نشد.")
        rows = []
        for row in _xml(archive, sheet_path).iter(f"{{{NS['m']}}}row"):
            values = {}
            for cell in row.findall("m:c", NS):
                match = _CELL_REF.match(cell.get("r", ""))
                col = 0
                if match:
                    for ch in match.group(1):
                        col = col * 26 + ord(ch) - 64
                    col -= 1
                else:
                    col = len(values)
                kind = cell.get("t")
                if kind == "inlineStr":
                    text = "".join(t.text or "" for t in cell.iter(f"{{{NS['m']}}}t"))
                else:
                    v = cell.find("m:v", NS)
                    text = v.text if v is not None and v.text is not None else ""
                    if kind == "s" and text.isdigit():
                        text = shared[int(text)] if int(text) < len(shared) else ""
                    elif kind == "b":
                        text = "بله" if text == "1" else "خیر"
                    elif kind is None and re.fullmatch(r"-?\d+\.0+", text):
                        text = text.split(".")[0]  # 1500000.0 ← 1500000
                values[col] = text
            if values:
                rows.append([values.get(i, "") for i in range(max(values) + 1)])
            if len(rows) > MAX_ROWS:
                raise SpreadsheetError(f"حداکثر {MAX_ROWS} ردیف در هر فایل.")
        return rows


def read_csv(data):
    for encoding in ("utf-8-sig", "cp1256"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SpreadsheetError("رمزگذاری فایل CSV شناخته نشد؛ آن را با UTF-8 ذخیره کنید.")
    sample = text[:2048]
    delimiter = ";" if sample.count(";") > sample.count(",") else ("\t" if "\t" in sample else ",")
    rows = [row for row in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in row)]
    if len(rows) > MAX_ROWS:
        raise SpreadsheetError(f"حداکثر {MAX_ROWS} ردیف در هر فایل.")
    return rows


def read_table(filename, data):
    if len(data) > MAX_UPLOAD:
        raise SpreadsheetError("حجم فایل حداکثر ۵ مگابایت است.")
    name = (filename or "").lower()
    if name.endswith(".xlsx") or data[:2] == b"PK":
        rows = read_xlsx(data)
    elif name.endswith((".csv", ".txt")):
        rows = read_csv(data)
    else:
        raise SpreadsheetError("فقط فایل Excel (.xlsx) یا CSV پذیرفته می‌شود.")
    return [[(c or "").strip().lstrip("'") if isinstance(c, str) else c for c in row] for row in rows]
