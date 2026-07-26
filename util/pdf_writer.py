from html import escape
from pathlib import Path
from typing import Any

from agents import function_tool
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
)


def add_page_number(canvas, doc):
    """Add page number at the bottom of every page."""
    canvas.saveState()

    page_number = canvas.getPageNumber()

    canvas.setFont("Helvetica", 9)
    canvas.drawCentredString(
        A4[0] / 2,
        0.4 * inch,
        f"Page {page_number}",
    )

    canvas.restoreState()


@function_tool
def create_pdf(
    research_directory: str,
    markdown_files: list[str],
    output_file: str,
) -> dict[str, Any]:
    """Render ordered Markdown files into a single PDF."""
    try:
        research_path = Path(research_directory).expanduser().resolve(strict=True)
        if not research_path.is_dir():
            return {
                "success": False,
                "pdf_path": None,
                "error": f"Research directory does not exist: {research_directory}",
            }

        if not markdown_files:
            return {
                "success": False,
                "pdf_path": None,
                "error": "No Markdown files were supplied.",
            }

        resolved_markdown_files: list[Path] = []
        for supplied_file in markdown_files:
            candidate = Path(supplied_file).expanduser()
            if not candidate.is_absolute():
                possible_paths = [
                    research_path / candidate,
                    research_path.parent / candidate,
                    Path.cwd() / candidate,
                ]
                candidate = next(
                    (
                        possible_path
                        for possible_path in possible_paths
                        if possible_path.exists()
                    ),
                    possible_paths[0],
                )

            candidate = candidate.resolve(strict=True)
            if not candidate.is_relative_to(research_path):
                return {
                    "success": False,
                    "pdf_path": None,
                    "error": (
                        "Markdown file is outside the research directory: "
                        f"{supplied_file}"
                    ),
                }

            if not candidate.is_file() or candidate.suffix.lower() != ".md":
                return {
                    "success": False,
                    "pdf_path": None,
                    "error": f"Invalid Markdown file: {supplied_file}",
                }

            if candidate.stat().st_size == 0:
                return {
                    "success": False,
                    "pdf_path": None,
                    "error": f"Markdown file is empty: {supplied_file}",
                }

            resolved_markdown_files.append(candidate)

        pdf_directory = research_path.parent / "pdf"
        pdf_directory.mkdir(parents=True, exist_ok=True)

        output_path = Path(output_file).expanduser()
        if not output_path.is_absolute():
            if output_path.parent == Path("."):
                output_path = pdf_directory / output_path
            else:
                output_path = Path.cwd() / output_path

        output_path = output_path.resolve()
        if output_path.parent != pdf_directory.resolve():
            return {
                "success": False,
                "pdf_path": None,
                "error": (
                    "The PDF must be created inside the research/pdf directory."
                ),
            }

        if output_path.suffix.lower() != ".pdf":
            return {
                "success": False,
                "pdf_path": None,
                "error": "output_file must have a .pdf extension.",
            }

        document = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=0.8 * inch,
            leftMargin=0.8 * inch,
            topMargin=0.8 * inch,
            bottomMargin=0.8 * inch,
            title="Research Thesis",
            author="Research Agent",
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            name="CustomTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=30,
            alignment=TA_CENTER,
            spaceAfter=30,
        )
        heading1_style = ParagraphStyle(
            name="CustomHeading1",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            spaceBefore=16,
            spaceAfter=10,
            textColor=colors.HexColor("#1F3A5F"),
        )
        heading2_style = ParagraphStyle(
            name="CustomHeading2",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            spaceBefore=12,
            spaceAfter=8,
            textColor=colors.HexColor("#345B7E"),
        )
        body_style = ParagraphStyle(
            name="CustomBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=17,
            alignment=TA_JUSTIFY,
            spaceAfter=10,
        )
        quote_style = ParagraphStyle(
            name="Quote",
            parent=body_style,
            leftIndent=25,
            rightIndent=25,
            fontName="Helvetica-Oblique",
            textColor=colors.darkgrey,
        )

        story = []

        def flush_paragraph(paragraph_lines: list[str]) -> None:
            if paragraph_lines:
                story.append(
                    Paragraph(escape(" ".join(paragraph_lines)), body_style)
                )
                paragraph_lines.clear()

        for file_index, markdown_path in enumerate(resolved_markdown_files):
            if file_index > 0:
                story.append(PageBreak())

            markdown_text = markdown_path.read_text(encoding="utf-8")
            paragraph_lines: list[str] = []

            for raw_line in markdown_text.splitlines():
                line = raw_line.strip()
                if not line:
                    flush_paragraph(paragraph_lines)
                    story.append(Spacer(1, 6))
                    continue

                if line.startswith("# "):
                    flush_paragraph(paragraph_lines)
                    story.append(Paragraph(escape(line[2:].strip()), title_style))
                elif line.startswith("## "):
                    flush_paragraph(paragraph_lines)
                    story.append(Paragraph(escape(line[3:].strip()), heading1_style))
                elif line.startswith("### "):
                    flush_paragraph(paragraph_lines)
                    story.append(Paragraph(escape(line[4:].strip()), heading2_style))
                elif line.startswith("> "):
                    flush_paragraph(paragraph_lines)
                    story.append(Paragraph(escape(line[2:].strip()), quote_style))
                elif line.startswith(("- ", "* ")):
                    flush_paragraph(paragraph_lines)
                    story.append(
                        Paragraph(f"• {escape(line[2:].strip())}", body_style)
                    )
                else:
                    paragraph_lines.append(line)

            flush_paragraph(paragraph_lines)

        if not story:
            return {
                "success": False,
                "pdf_path": None,
                "error": "No renderable Markdown content was found.",
            }

        document.build(
            story,
            onFirstPage=add_page_number,
            onLaterPages=add_page_number,
        )

        if not output_path.is_file() or output_path.stat().st_size == 0:
            return {
                "success": False,
                "pdf_path": None,
                "error": "PDF generation completed without creating a valid file.",
            }

        return {
            "success": True,
            "pdf_path": str(output_path),
            "error": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "pdf_path": None,
            "error": str(exc),
        }
