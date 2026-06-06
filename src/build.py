from __future__ import annotations

import argparse
import datetime as dt
import html
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KTEX_ENVS = "kfold|kbox|kadvanced|kproof|kexercise|khint|kanswer"
BEGIN_RE = re.compile(rf"\\begin\{{({KTEX_ENVS})\}}(?:\[([^\]]*)\])?", re.DOTALL)
NUMBERED_BOX_TYPES = {
    "theorem": "定理",
    "definition": "定義",
    "proposition": "命題",
    "lemma": "補題",
    "corollary": "系",
    "example": "例",
    "exercise": "演習",
}
UNNUMBERED_BOX_TYPES = {
    "note": "注意",
    "proof": "証明",
    "plain": "補足",
}
HEADING_LEVELS = {
    "section": 1,
    "subsection": 2,
    "subsubsection": 3,
}
HEADING_TAGS = {
    1: "h2",
    2: "h3",
    3: "h4",
}


@dataclass
class HeadingRecord:
    level: int
    number: str
    title: str
    anchor: str


@dataclass
class NumberedRecord:
    kind: str
    number: str
    title: str
    anchor: str | None

    @property
    def ref_text(self) -> str:
        return f"{self.kind} {self.number}"

    @property
    def label_text(self) -> str:
        if self.title:
            return f"{self.kind} {self.number}（{self.title}）"
        return self.ref_text


def split_options(source: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None

    for char in source:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
            current.append(char)
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)

    if current:
        parts.append("".join(current).strip())
    return [part for part in parts if part]


def parse_options(source: str | None) -> dict[str, str]:
    if not source:
        return {}

    options: dict[str, str] = {}
    for part in split_options(source):
        key, sep, value = part.partition("=")
        if not sep:
            options[key.strip()] = "true"
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        options[key.strip()] = value
    return options


def slug_class(value: str, fallback: str = "plain") -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug or fallback


def safe_html_id(value: str, fallback: str = "item") -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-")
    if not safe:
        safe = fallback
    if safe[0].isdigit():
        safe = f"{fallback}-{safe}"
    return safe


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class Renderer:
    def __init__(self) -> None:
        self.gap_index = 0
        self.section_counts = [0, 0, 0]
        self.block_count = 0
        self.heading_records: list[HeadingRecord] = []
        self.numbered_records: list[NumberedRecord] = []
        self.labels: dict[str, NumberedRecord] = {}
        self._heading_cursor = 0
        self._numbered_cursor = 0

    def render_document(self, source: str) -> tuple[str, str, str, str]:
        title = self.extract_command(source, "title") or "Kirei Book"
        subtitle = self.extract_command(source, "subtitle") or ""
        body = self.remove_metadata(source)

        self.collect_metadata(body)
        toc = self.render_toc()
        self.reset_render_state()
        return title, subtitle, toc, self.render_blocks(body)

    def extract_command(self, source: str, name: str) -> str | None:
        match = re.search(rf"\\{name}\{{([^{{}}]*)\}}", source)
        return match.group(1).strip() if match else None

    def remove_metadata(self, source: str) -> str:
        source = re.sub(r"\\title\{[^{}]*\}\s*", "", source)
        source = re.sub(r"\\subtitle\{[^{}]*\}\s*", "", source)
        return source.strip()

    def collect_metadata(self, source: str) -> None:
        self.section_counts = [0, 0, 0]
        self.block_count = 0
        self.heading_records = []
        self.numbered_records = []
        self.labels = {}
        self.collect_blocks(source)

    def collect_blocks(self, source: str) -> None:
        pos = 0
        while True:
            match = BEGIN_RE.search(source, pos)
            if not match:
                self.collect_plain(source[pos:])
                break

            self.collect_plain(source[pos : match.start()])
            env = match.group(1)
            options = parse_options(match.group(2))
            end_span = self.find_env_end(source, env, match.end())

            if end_span is None:
                self.collect_plain(source[match.start() :])
                break

            self.collect_env(env, options)
            self.collect_blocks(source[match.end() : end_span[0]])
            pos = end_span[1]

    def collect_plain(self, source: str) -> None:
        source = source.strip()
        if not source:
            return

        for block in re.split(r"\n\s*\n", source):
            heading = self.parse_heading(block.strip())
            if heading:
                self.register_heading(*heading)

    def collect_env(self, env: str, options: dict[str, str]) -> None:
        if env == "kbox":
            box_type = slug_class(options.get("type", "plain"))
            if box_type in NUMBERED_BOX_TYPES:
                self.register_numbered(
                    kind=NUMBERED_BOX_TYPES[box_type],
                    title=options.get("title", ""),
                    label=options.get("label"),
                    fallback_id=f"{box_type}-{len(self.numbered_records) + 1}",
                )
        elif env == "kexercise":
            self.register_numbered(
                kind="演習",
                title=options.get("title", ""),
                label=options.get("label"),
                fallback_id=f"exercise-{len(self.numbered_records) + 1}",
            )

    def register_heading(self, command: str, title: str) -> None:
        level = HEADING_LEVELS[command]
        self.section_counts[level - 1] += 1
        for index in range(level, len(self.section_counts)):
            self.section_counts[index] = 0
        if level == 1:
            self.block_count = 0

        number_parts = [str(value) for value in self.section_counts[:level] if value > 0]
        number = ".".join(number_parts)
        anchor = "section-" + "-".join(number_parts)
        self.heading_records.append(HeadingRecord(level=level, number=number, title=title, anchor=anchor))

    def register_numbered(self, kind: str, title: str, label: str | None, fallback_id: str) -> None:
        section_number = self.section_counts[0] or 0
        self.block_count += 1
        number = f"{section_number}.{self.block_count}"
        anchor = safe_html_id(label, fallback=fallback_id) if label else None
        record = NumberedRecord(kind=kind, number=number, title=title, anchor=anchor)
        self.numbered_records.append(record)
        if label:
            self.labels[label] = record

    def reset_render_state(self) -> None:
        self.gap_index = 0
        self._heading_cursor = 0
        self._numbered_cursor = 0

    def render_toc(self) -> str:
        if not self.heading_records:
            return ""

        items = []
        for record in self.heading_records:
            label = html.escape(f"{record.number} {record.title}")
            items.append(
                f'    <li class="ktoc-level-{record.level}">'
                f'<a href="#{html.escape(record.anchor)}">{label}</a></li>'
            )
        return (
            '<details class="ktoc" open>\n'
            "  <summary>目次</summary>\n"
            "  <ol>\n"
            + "\n".join(items)
            + "\n  </ol>\n"
            "</details>"
        )

    def next_heading_record(self) -> HeadingRecord:
        record = self.heading_records[self._heading_cursor]
        self._heading_cursor += 1
        return record

    def next_numbered_record(self) -> NumberedRecord:
        record = self.numbered_records[self._numbered_cursor]
        self._numbered_cursor += 1
        return record

    def render_blocks(self, source: str) -> str:
        chunks: list[str] = []
        pos = 0

        while True:
            match = BEGIN_RE.search(source, pos)
            if not match:
                chunks.append(self.render_plain(source[pos:]))
                break

            chunks.append(self.render_plain(source[pos : match.start()]))
            env = match.group(1)
            options = parse_options(match.group(2))
            end_span = self.find_env_end(source, env, match.end())

            if end_span is None:
                chunks.append(self.render_plain(source[match.start() :]))
                break

            inner_source = source[match.end() : end_span[0]]
            inner_html = self.render_blocks(inner_source)
            chunks.append(self.render_env(env, options, inner_html))
            pos = end_span[1]

        return "\n".join(chunk for chunk in chunks if chunk.strip())

    def find_env_end(self, source: str, env: str, start: int) -> tuple[int, int] | None:
        pattern = re.compile(rf"\\(?P<kind>begin|end)\{{{re.escape(env)}\}}(?:\[[^\]]*\])?")
        depth = 1
        for match in pattern.finditer(source, start):
            if match.group("kind") == "begin":
                depth += 1
            else:
                depth -= 1
                if depth == 0:
                    return match.start(), match.end()
        return None

    def render_env(self, env: str, options: dict[str, str], inner_html: str) -> str:
        if env == "kfold":
            title = options.get("title", "詳しく見る")
            return (
                '<details class="kfold">\n'
                f"  <summary>{self.render_inline(title)}</summary>\n"
                f'  <div class="kfold-body">\n{inner_html}\n  </div>\n'
                "</details>"
            )

        if env == "kbox":
            return self.render_kbox(options, inner_html)

        if env == "kproof":
            title = options.get("title", "証明")
            return (
                '<details class="kproof">\n'
                f"  <summary>{self.render_inline(title)}</summary>\n"
                f'  <div class="kproof-body">\n{inner_html}\n'
                '    <div class="qed" aria-label="証明終わり">□</div>\n'
                "  </div>\n"
                "</details>"
            )

        if env == "kexercise":
            return self.render_kexercise(options, inner_html)

        if env == "khint":
            title = options.get("title", "ヒント")
            return self.render_named_fold("khint", title, inner_html)

        if env == "kanswer":
            title = options.get("title", "解答")
            return self.render_named_fold("kanswer", title, inner_html)

        if env == "kadvanced":
            return (
                '<div class="kadvanced-notice" data-advanced-notice>\n'
                '  <span class="kadvanced-notice-label">発展内容があります</span>\n'
                '  <span class="kadvanced-notice-text">上の「発展を表示」をオンにすると読めます。</span>\n'
                "</div>\n"
                '<section class="kadvanced" data-advanced>\n'
                '  <div class="kadvanced-ribbon">発展</div>\n'
                f'  <div class="kadvanced-body">\n{inner_html}\n  </div>\n'
                "</section>"
            )

        return inner_html

    def render_kbox(self, options: dict[str, str], inner_html: str) -> str:
        box_type = slug_class(options.get("type", "plain"))
        title = options.get("title", "")
        label = options.get("label")
        attrs = ""

        if box_type in NUMBERED_BOX_TYPES:
            record = self.next_numbered_record()
            attrs = f' id="{html.escape(record.anchor)}"' if record.anchor else ""
            label_html = self.render_inline(record.label_text)
        else:
            display_title = title or self.default_box_title(box_type)
            anchor = safe_html_id(label, fallback=f"{box_type}-box") if label else None
            attrs = f' id="{html.escape(anchor)}"' if anchor else ""
            label_html = self.render_inline(display_title)

        return (
            f'<aside class="kbox kbox-{box_type}"{attrs}>\n'
            f'  <div class="kbox-label">{label_html}</div>\n'
            f'  <div class="kbox-body">\n{inner_html}\n  </div>\n'
            "</aside>"
        )

    def render_kexercise(self, options: dict[str, str], inner_html: str) -> str:
        level = slug_class(options.get("level", "standard"), fallback="standard")
        record = self.next_numbered_record()
        attrs = f' id="{html.escape(record.anchor)}"' if record.anchor else ""
        return (
            f'<aside class="kexercise kexercise-{level}" data-level="{level}"{attrs}>\n'
            '  <div class="kexercise-header">\n'
            f'    <div class="kexercise-label">{self.render_inline(record.label_text)}</div>\n'
            f'    <div class="kexercise-level">{self.render_inline(level)}</div>\n'
            "  </div>\n"
            f'  <div class="kexercise-body">\n{inner_html}\n  </div>\n'
            "</aside>"
        )

    def render_named_fold(self, class_name: str, title: str, inner_html: str) -> str:
        return (
            f'<details class="{class_name}">\n'
            f"  <summary>{self.render_inline(title)}</summary>\n"
            f'  <div class="{class_name}-body">\n{inner_html}\n  </div>\n'
            "</details>"
        )

    def default_box_title(self, box_type: str) -> str:
        return NUMBERED_BOX_TYPES.get(box_type) or UNNUMBERED_BOX_TYPES.get(box_type, "補足")

    def render_plain(self, source: str) -> str:
        source = source.strip()
        if not source:
            return ""

        blocks = re.split(r"\n\s*\n", source)
        rendered: list[str] = []
        for block in blocks:
            block = block.strip()
            if not block:
                continue

            heading = self.render_heading(block)
            if heading:
                rendered.append(heading)
                continue

            if block.startswith(r"\[") and block.endswith(r"\]"):
                rendered.append(f'<div class="math-display">\n{block}\n</div>')
                continue

            inline = self.render_inline(block, linebreaks=True)
            rendered.append(f"<p>{inline}</p>")

        return "\n".join(rendered)

    def parse_heading(self, block: str) -> tuple[str, str] | None:
        for command in HEADING_LEVELS:
            match = re.fullmatch(rf"\\{command}\{{([^{{}}]+)\}}", block, re.DOTALL)
            if match:
                return command, match.group(1).strip()
        return None

    def render_heading(self, block: str) -> str | None:
        parsed = self.parse_heading(block)
        if not parsed:
            return None

        record = self.next_heading_record()
        tag = HEADING_TAGS[record.level]
        title = self.render_inline(record.title)
        return f'<{tag} id="{html.escape(record.anchor)}">{html.escape(record.number)}. {title}</{tag}>'

    def render_inline(self, source: str, linebreaks: bool = False) -> str:
        protected, math_tokens = self.protect_math(source)
        rendered = self.render_text_macros(protected)
        if linebreaks:
            rendered = rendered.replace("\n", "<br>\n")
        for placeholder, math_source in math_tokens:
            rendered = rendered.replace(placeholder, math_source)
        return rendered

    def protect_math(self, source: str) -> tuple[str, list[tuple[str, str]]]:
        tokens: list[tuple[str, str]] = []
        output: list[str] = []
        i = 0

        while i < len(source):
            delimiter = None
            closer = None

            if source.startswith(r"\[", i):
                delimiter, closer = r"\[", r"\]"
            elif source.startswith(r"\(", i):
                delimiter, closer = r"\(", r"\)"
            elif source.startswith("$$", i):
                delimiter, closer = "$$", "$$"
            elif source[i] == "$":
                delimiter, closer = "$", "$"

            if delimiter and closer:
                end = self.find_math_end(source, i + len(delimiter), closer)
                if end != -1:
                    math_source = source[i : end + len(closer)]
                    placeholder = f"@@KIREI_MATH_{len(tokens)}@@"
                    tokens.append((placeholder, math_source))
                    output.append(placeholder)
                    i = end + len(closer)
                    continue

            output.append(source[i])
            i += 1

        return "".join(output), tokens

    def find_math_end(self, source: str, start: int, closer: str) -> int:
        pos = start
        while True:
            end = source.find(closer, pos)
            if end == -1:
                return -1
            if end == 0 or source[end - 1] != "\\":
                return end
            pos = end + len(closer)

    def render_text_macros(self, source: str) -> str:
        output: list[str] = []
        pos = 0

        while pos < len(source):
            gap_start = source.find(r"\kgap{", pos)
            ref_start = source.find(r"\kref{", pos)
            candidates = [index for index in (gap_start, ref_start) if index != -1]
            if not candidates:
                output.append(html.escape(source[pos:]))
                break

            start = min(candidates)
            output.append(html.escape(source[pos:start]))

            if source.startswith(r"\kgap{", start):
                content_start = start + len(r"\kgap{")
                content_end = self.find_matching_brace(source, content_start - 1)
                if content_end is None:
                    output.append(html.escape(source[start:]))
                    break
                output.append(self.render_gap(source[content_start:content_end]))
                pos = content_end + 1
            else:
                content_start = start + len(r"\kref{")
                content_end = self.find_matching_brace(source, content_start - 1)
                if content_end is None:
                    output.append(html.escape(source[start:]))
                    break
                output.append(self.render_ref(source[content_start:content_end].strip()))
                pos = content_end + 1

        return "".join(output)

    def find_matching_brace(self, source: str, open_index: int) -> int | None:
        depth = 0
        for index in range(open_index, len(source)):
            char = source[index]
            if char == "{" and (index == 0 or source[index - 1] != "\\"):
                depth += 1
            elif char == "}" and (index == 0 or source[index - 1] != "\\"):
                depth -= 1
                if depth == 0:
                    return index
        return None

    def render_gap(self, content: str) -> str:
        self.gap_index += 1
        gap_id = f"kgap-{self.gap_index}"
        body = self.render_inline(content, linebreaks=True)
        return (
            f'<span class="kgap" data-kgap>'
            f'<button class="kgap-trigger" type="button" aria-expanded="false" '
            f'aria-controls="{gap_id}" data-kgap-target="{gap_id}">?</button>'
            f'<span id="{gap_id}" class="kgap-popover" role="note" hidden>{body}</span>'
            f"</span>"
        )

    def render_ref(self, label: str) -> str:
        record = self.labels.get(label)
        if not record or not record.anchor:
            return '<span class="kref kref-missing">??</span>'
        href = html.escape(f"#{record.anchor}")
        text = html.escape(record.ref_text)
        return f'<a class="kref" href="{href}">{text}</a>'


def build(input_path: Path, output_path: Path) -> None:
    renderer = Renderer()
    title, subtitle, toc, content = renderer.render_document(read_text(input_path))
    template = read_text(ROOT / "templates" / "book.html")
    css = read_text(ROOT / "assets" / "kirei.css")
    js = read_text(ROOT / "assets" / "kirei.js")
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    html_output = (
        template.replace("{{ title }}", html.escape(title))
        .replace("{{ subtitle }}", html.escape(subtitle))
        .replace("{{ toc }}", toc)
        .replace("{{ content }}", content)
        .replace("{{ css }}", css)
        .replace("{{ js }}", js)
        .replace("{{ generated_at }}", generated_at)
    )
    write_text(output_path, html_output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a single-file interactive math book from .ktex.")
    parser.add_argument("input", type=Path, help="Input .ktex file")
    parser.add_argument("output", type=Path, help="Output HTML file")
    args = parser.parse_args()

    build(args.input, args.output)
    print(f"built {args.output}")


if __name__ == "__main__":
    main()
