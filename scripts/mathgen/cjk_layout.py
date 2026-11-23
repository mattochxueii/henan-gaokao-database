"""Chinese question paragraphs with nonbreaking punctuation and answer spaces."""

import re

from reportlab.platypus import Paragraph
from reportlab.platypus.paragraph import ParaLines, cjkU, makeCJKParaLine

from .export import formatted_plain


OPEN = "（(［[【〔《〈“‘"
CLOSE = "，。；：、？！）》〉】〕”’］％%）)]"
LATIN_RUN = re.compile(r"[A-Za-z0-9./+\-_=·]+\Z")


def plain_markup(text):
    """Draw one continuous rule with base-font spaces, independent of underscore glyphs."""
    chunks = re.split(r"(_{3,})", text)
    return "".join(
        '<nobr><u width="0.65" offset="-1.8">' + "&nbsp;" * len(chunk)
        + '</u><font size="1">&nbsp;</font></nobr>'
        if i % 2 else formatted_plain(chunk)
        for i, chunk in enumerate(chunks)
    )


def breakable_space(unit):
    return bool(unit and unit != "\xa0" and unit.isspace())


def is_blank(unit):
    return unit == "\xa0" and getattr(unit.frag, "nobr", False)


def inline_groups(frags):
    groups = []
    for frag in frags:
        for glyph in frag.text or ("",):
            unit = cjkU(glyph, frag, "utf8")
            previous = groups[-1][-1] if groups else None
            if previous is None or hasattr(previous.frag, "lineBreak") or hasattr(frag, "lineBreak"):
                groups.append([unit])
                continue
            if breakable_space(previous) and ((glyph and glyph in CLOSE) or is_blank(unit)):
                groups[-1].pop()
                if not groups[-1]:
                    groups.pop()
                previous = groups[-1][-1] if groups else None
            joined = previous is not None and (
                bool(glyph and glyph in CLOSE)
                or bool(previous and previous in OPEN)
                or (getattr(previous.frag, "nobr", False) and getattr(frag, "nobr", False))
                or (LATIN_RUN.fullmatch(previous) and LATIN_RUN.fullmatch(glyph))
                or is_blank(unit)
                or (is_blank(previous) and not breakable_space(unit))
            )
            if joined:
                groups[-1].append(unit)
            else:
                groups.append([unit])
    return groups


class ExamParagraph(Paragraph):
    """Use ReportLab's drawing and splitting with line breaks chosen at fragment boundaries."""

    def breakLinesCJK(self, maxWidths):
        if getattr(self, "_splitpara", 0) and hasattr(self, "blPara"):
            return self.blPara
        if not isinstance(maxWidths, (list, tuple)):
            maxWidths = [maxWidths]
        lines, row = [], []
        width = 0
        limit = maxWidths[0]
        auto_leading = getattr(self, "autoLeading", getattr(self.style, "autoLeading", ""))

        def finish(hard_break=False):
            nonlocal row, width, limit
            while row and breakable_space(row[-1]):
                width -= row.pop().width
            if row:
                lines.append(makeCJKParaLine(
                    row, limit, width, limit-width, hard_break, auto_leading not in ("", "off")
                ))
            row, width = [], 0
            limit = maxWidths[min(len(lines), len(maxWidths)-1)]

        for group in inline_groups(self.frags):
            if hasattr(group[0].frag, "lineBreak"):
                finish(hard_break=True)
                continue
            size = sum(unit.width for unit in group)
            if row and width + size > limit + 1e-8:
                finish()
            if not row and breakable_space(group[0]):
                continue
            row.extend(group)
            width += size
        finish()
        return ParaLines(kind=1, lines=lines)
