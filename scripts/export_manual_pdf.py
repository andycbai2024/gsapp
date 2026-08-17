from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "平台端与LM700离线办案操作手册.md"
OUTPUT = ROOT / "平台端与LM700离线办案操作手册.pdf"
FONT = Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf")


def inline(text: str) -> str:
    value = html.escape(text)
    value = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    return value


def build_styles() -> dict[str, ParagraphStyle]:
    pdfmetrics.registerFont(TTFont("NotoSansSC", str(FONT)))
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ManualTitle", parent=base["Title"], fontName="NotoSansSC", fontSize=21, leading=29, textColor=colors.HexColor("#153b5a"), alignment=TA_CENTER, spaceAfter=14),
        "h1": ParagraphStyle("ManualH1", parent=base["Heading1"], fontName="NotoSansSC", fontSize=15, leading=23, textColor=colors.HexColor("#153b5a"), spaceBefore=14, spaceAfter=8),
        "h2": ParagraphStyle("ManualH2", parent=base["Heading2"], fontName="NotoSansSC", fontSize=12, leading=19, textColor=colors.HexColor("#1d668f"), spaceBefore=10, spaceAfter=6),
        "body": ParagraphStyle("ManualBody", parent=base["BodyText"], fontName="NotoSansSC", fontSize=9.2, leading=15, spaceAfter=4),
        "bullet": ParagraphStyle("ManualBullet", parent=base["BodyText"], fontName="NotoSansSC", fontSize=9.2, leading=15, leftIndent=14, firstLineIndent=-10, spaceAfter=3),
        "note": ParagraphStyle("ManualNote", parent=base["BodyText"], fontName="NotoSansSC", fontSize=8.8, leading=14, backColor=colors.HexColor("#f3f8fc"), borderColor=colors.HexColor("#a8c9df"), borderWidth=0.5, borderPadding=7, spaceBefore=5, spaceAfter=7),
        "code": ParagraphStyle("ManualCode", parent=base["Code"], fontName="NotoSansSC", fontSize=8, leading=12, backColor=colors.HexColor("#f4f5f6"), borderPadding=6, spaceAfter=6),
        "caption": ParagraphStyle("ManualCaption", parent=base["BodyText"], fontName="NotoSansSC", fontSize=8, leading=12, textColor=colors.HexColor("#596a73"), alignment=TA_CENTER, spaceBefore=2, spaceAfter=10),
    }


def table_from_rows(rows: list[list[str]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[Paragraph(inline(cell.strip()), styles["body"]) for cell in row] for row in rows]
    width = 17.2 * cm
    col_width = width / max(len(row) for row in rows)
    table = Table(data, colWidths=[col_width] * len(rows[0]), repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d9eaf5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#153b5a")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#a8c9df")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def parse_markdown() -> list:
    styles = build_styles()
    story: list = []
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("# "):
            story.append(Paragraph(inline(line[2:]), styles["title"]))
        elif line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), styles["h1"]))
        elif line.startswith("### "):
            story.append(Paragraph(inline(line[4:]), styles["h2"]))
        elif line.startswith("!["):
            match = re.search(r"!\[([^]]*)\]\(([^)]+)\)", line)
            if match:
                path = ROOT / match.group(2)
                if path.exists():
                    image = Image(str(path))
                    max_width, max_height = 16.8 * cm, 20.5 * cm
                    ratio = min(max_width / image.imageWidth, max_height / image.imageHeight)
                    image.drawWidth = image.imageWidth * ratio
                    image.drawHeight = image.imageHeight * ratio
                    story.extend([image, Paragraph(inline(match.group(1)), styles["caption"])])
        elif line.startswith("```"):
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                code_lines.append(lines[index])
                index += 1
            story.append(Paragraph("<br/>".join(inline(item) for item in code_lines), styles["code"]))
        elif line.startswith("| "):
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].startswith("|"):
                cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                    rows.append(cells)
                index += 1
            if rows:
                story.extend([table_from_rows(rows, styles), Spacer(1, 0.25 * cm)])
            continue
        elif line.startswith("> "):
            story.append(Paragraph(inline(line[2:]), styles["note"]))
        elif re.match(r"^[-*] ", line):
            story.append(Paragraph("• " + inline(line[2:]), styles["bullet"]))
        elif re.match(r"^\d+\. ", line):
            story.append(Paragraph(inline(line), styles["bullet"]))
        else:
            story.append(Paragraph(inline(line), styles["body"]))
        index += 1
    return story


def page_number(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("NotoSansSC", 8)
    canvas.setFillColor(colors.HexColor("#61737d"))
    canvas.drawRightString(A4[0] - 1.5 * cm, 1.1 * cm, f"第 {document.page} 页")
    canvas.drawString(1.5 * cm, 1.1 * cm, "GS8000 / LM700 离线办案操作手册")
    canvas.restoreState()


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)
    if not FONT.exists():
        raise FileNotFoundError(FONT)
    document = SimpleDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm, topMargin=1.35 * cm, bottomMargin=1.65 * cm, title="平台端与LM700离线办案操作手册")
    document.build(parse_markdown(), onFirstPage=page_number, onLaterPages=page_number)
    print(OUTPUT)


if __name__ == "__main__":
    main()