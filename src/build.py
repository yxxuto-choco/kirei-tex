from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KTEX_ENVS = "kfold|kbox|kadvanced|kproof|kexercise|khint|kanswer"
SUPPORTED_ENVS = set(KTEX_ENVS.split("|"))
THEME_MODES = {"rich", "mono"}
BEGIN_RE = re.compile(rf"\\begin\{{({KTEX_ENVS})\}}(?:\[([^\]]*)\])?", re.DOTALL)
ANY_BEGIN_RE = re.compile(r"\\begin\{([^}]+)\}")
KREF_RE = re.compile(r"\\kref\{([^{}]+)\}")
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
EXERCISE_LEVELS = {"basic", "standard", "advanced"}
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
class BuildMessage:
    kind: str
    message: str
    path: Path | None = None
    line: int | None = None
    column: int | None = None
    snippet: str | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class BuildOptions:
    strict: bool = False
    allow_output_on_error: bool = False
    quiet: bool = False
    check: bool = False
    mathjax_mode: str = "cdn"
    mathjax_path: Path = Path("vendor/mathjax/tex-svg.js")
    assets_mode: str = "inline"
    offline: bool = False
    theme: str = "rich"


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
        if not self.number:
            return self.kind
        return f"{self.kind} {self.number}"

    @property
    def label_text(self) -> str:
        if not self.number:
            return self.title or self.kind
        if self.title:
            return f"{self.kind} {self.number}（{self.title}）"
        return self.ref_text


@dataclass
class SourceLocation:
    path: Path
    line: int
    column: int
    snippet: str


@dataclass
class RefUse:
    label: str
    location: SourceLocation


@dataclass
class ChapterRecord:
    number: int
    title: str
    anchor: str


@dataclass
class BookChapter:
    path: Path
    title: str


@dataclass
class BookManifest:
    title: str
    subtitle: str
    chapters: list[BookChapter]


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


def normalize_options(options: BuildOptions) -> BuildOptions:
    if options.offline:
        options.mathjax_mode = "local"
        options.assets_mode = "inline"
    if options.theme not in THEME_MODES:
        options.theme = "rich"
    return options


def html_relpath(target: Path, start: Path) -> str:
    return os.path.relpath(target.resolve(), start.resolve()).replace(os.sep, "/")


def render_mathjax_config() -> str:
    return """<script>
    window.MathJax = {
      tex: {
        inlineMath: [["$", "$"], ["\\\\(", "\\\\)"]],
        displayMath: [["\\\\[", "\\\\]"], ["$$", "$$"]],
        processEscapes: true
      },
      svg: {
        fontCache: "global"
      }
    };
  </script>"""


def render_mathjax_blocks(renderer: "Renderer", output_path: Path, options: BuildOptions) -> tuple[str, str]:
    if options.mathjax_mode == "none":
        return "", ""

    config = render_mathjax_config()
    if options.mathjax_mode == "cdn":
        return config, '<script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>'

    mathjax_path = options.mathjax_path
    resolved = mathjax_path if mathjax_path.is_absolute() else (ROOT / mathjax_path)
    resolved = resolved.resolve()
    if not resolved.exists():
        renderer.add_message("warning", f"local MathJax file not found: {mathjax_path.as_posix()}")
    src = html_relpath(resolved, output_path.parent)
    return config, f'<script defer src="{html.escape(src)}"></script>'


def render_asset_blocks(output_path: Path, options: BuildOptions) -> tuple[str, str]:
    css = read_text(ROOT / "assets" / "kirei.css")
    js = read_text(ROOT / "assets" / "kirei.js")
    if options.assets_mode == "inline":
        return f"<style>\n{css}\n  </style>", f"<script>\n{js}\n  </script>"

    asset_dir = output_path.parent / "assets"
    css_output = asset_dir / "kirei.css"
    js_output = asset_dir / "kirei.js"
    css_href = html_relpath(css_output, output_path.parent)
    js_src = html_relpath(js_output, output_path.parent)
    return (
        f'<link rel="stylesheet" href="{html.escape(css_href)}">',
        f'<script src="{html.escape(js_src)}"></script>',
    )


def copy_external_assets(output_path: Path) -> None:
    asset_dir = output_path.parent / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "assets" / "kirei.css", asset_dir / "kirei.css")
    shutil.copyfile(ROOT / "assets" / "kirei.js", asset_dir / "kirei.js")


class Renderer:
    def __init__(self, source_path: Path, options: BuildOptions | None = None) -> None:
        self.source_path = source_path
        self.options = options or BuildOptions()
        self.source = ""
        self.source_lines: list[str] = []
        self.errors: list[BuildMessage] = []
        self.warnings: list[BuildMessage] = []
        self.gap_index = 0
        self.section_counts = [0, 0, 0]
        self.block_count = 0
        self.book_block_counts: dict[str, int] = {}
        self.heading_records: list[HeadingRecord] = []
        self.chapter_records: list[ChapterRecord] = []
        self.numbered_records: list[NumberedRecord] = []
        self.labels: dict[str, NumberedRecord] = {}
        self.label_locations: dict[str, SourceLocation] = {}
        self.ref_uses: list[RefUse] = []
        self.book_mode = False
        self.current_chapter = 0
        self._heading_cursor = 0
        self._chapter_cursor = 0
        self._numbered_cursor = 0

    def render_document(self, source: str) -> tuple[str, str, str, str]:
        self.set_source_context(self.source_path, source)
        title = self.extract_command(source, "title") or "Kirei Book"
        subtitle = self.extract_command(source, "subtitle") or ""
        body = self.remove_metadata(source)
        body_offset = source.find(body) if body else 0

        self.collect_metadata(body, body_offset)
        toc = self.render_toc()
        self.reset_render_state()
        return title, subtitle, toc, self.render_blocks(body)

    def render_book(self, manifest: BookManifest) -> tuple[str, str, str, str]:
        self.heading_records = []
        self.chapter_records = []
        self.numbered_records = []
        self.labels = {}
        self.label_locations = {}
        self.ref_uses = []
        self.book_mode = True

        chapter_sources: list[tuple[int, BookChapter, str, str, int]] = []
        for chapter_number, chapter in enumerate(manifest.chapters, start=1):
            try:
                chapter_source = read_text(chapter.path)
            except OSError as exc:
                self.set_source_context(chapter.path, "")
                self.add_message("error", f"cannot read chapter '{chapter.path}': {exc}")
                continue

            self.set_source_context(chapter.path, chapter_source)
            body = self.remove_metadata(chapter_source)
            body_offset = chapter_source.find(body) if body else 0
            chapter_sources.append((chapter_number, chapter, chapter_source, body, body_offset))

            self.current_chapter = chapter_number
            self.section_counts = [0, 0, 0]
            self.block_count = 0
            self.book_block_counts = {}
            self.chapter_records.append(
                ChapterRecord(number=chapter_number, title=chapter.title, anchor=f"chapter-{chapter_number}")
            )
            self.validate_unknown_envs(body, body_offset)
            self.collect_blocks(body, body_offset)
            self.collect_ref_uses(body, body_offset)

        self.validate_ref_uses()
        toc = self.render_toc()
        self.reset_render_state()

        rendered_chapters: list[str] = []
        for chapter_number, _chapter, chapter_source, body, _body_offset in chapter_sources:
            self.set_source_context(_chapter.path, chapter_source)
            self.current_chapter = chapter_number
            rendered_chapters.append(self.render_chapter_heading())
            rendered_chapters.append(self.render_blocks(body))

        return manifest.title, manifest.subtitle, toc, "\n\n".join(
            chunk for chunk in rendered_chapters if chunk.strip()
        )

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def set_source_context(self, source_path: Path, source: str) -> None:
        self.source_path = source_path
        self.source = source
        self.source_lines = source.splitlines()

    def add_message(
        self,
        kind: str,
        message: str,
        index: int | None = None,
        notes: list[str] | None = None,
    ) -> None:
        if kind == "warning" and self.options.strict:
            kind = "error"

        location = self.location_from_index(index) if index is not None else None
        build_message = BuildMessage(
            kind=kind,
            message=message,
            path=location.path if location else self.source_path,
            line=location.line if location else None,
            column=location.column if location else None,
            snippet=location.snippet if location else None,
            notes=notes or [],
        )
        if kind == "error":
            self.errors.append(build_message)
        else:
            self.warnings.append(build_message)

    def location_from_index(self, index: int) -> SourceLocation:
        line = self.source.count("\n", 0, index) + 1
        last_newline = self.source.rfind("\n", 0, index)
        column = index + 1 if last_newline == -1 else index - last_newline
        snippet = self.source_lines[line - 1] if 0 <= line - 1 < len(self.source_lines) else ""
        return SourceLocation(path=self.source_path, line=line, column=column, snippet=snippet)

    def extract_command(self, source: str, name: str) -> str | None:
        match = re.search(rf"\\{name}\{{([^{{}}]*)\}}", source)
        return match.group(1).strip() if match else None

    def remove_metadata(self, source: str) -> str:
        source = re.sub(r"\\title\{[^{}]*\}\s*", "", source)
        source = re.sub(r"\\subtitle\{[^{}]*\}\s*", "", source)
        return source.strip()

    def collect_metadata(self, source: str, base_offset: int = 0) -> None:
        self.section_counts = [0, 0, 0]
        self.block_count = 0
        self.book_block_counts = {}
        self.heading_records = []
        self.chapter_records = []
        self.numbered_records = []
        self.labels = {}
        self.label_locations = {}
        self.ref_uses = []
        self.book_mode = False
        self.current_chapter = 0
        self.validate_unknown_envs(source, base_offset)
        self.collect_blocks(source, base_offset)
        self.collect_ref_uses(source, base_offset)
        self.validate_ref_uses()

    def mask_math(self, source: str) -> str:
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
                    output.append("".join("\n" if char == "\n" else " " for char in math_source))
                    i = end + len(closer)
                    continue

            output.append(source[i])
            i += 1
        return "".join(output)

    def validate_unknown_envs(self, source: str, base_offset: int) -> None:
        masked = self.mask_math(source)
        for match in ANY_BEGIN_RE.finditer(masked):
            env = match.group(1)
            if env not in SUPPORTED_ENVS:
                self.add_message(
                    "warning",
                    f"unsupported environment '{env}'",
                    base_offset + match.start(),
                )

    def collect_ref_uses(self, source: str, base_offset: int) -> None:
        masked = self.mask_math(source)
        for match in KREF_RE.finditer(masked):
            label = match.group(1).strip()
            location = self.location_from_index(base_offset + match.start())
            self.ref_uses.append(RefUse(label=label, location=location))

    def validate_ref_uses(self) -> None:
        for ref_use in self.ref_uses:
            if ref_use.label in self.labels:
                continue
            kind = "error" if self.options.strict else "warning"
            build_message = BuildMessage(
                kind=kind,
                message=f"unresolved reference '{ref_use.label}'",
                path=ref_use.location.path,
                line=ref_use.location.line,
                column=ref_use.location.column,
                snippet=ref_use.location.snippet,
            )
            if kind == "error":
                self.errors.append(build_message)
            else:
                self.warnings.append(build_message)

    def collect_blocks(self, source: str, base_offset: int = 0) -> None:
        pos = 0
        while True:
            match = BEGIN_RE.search(source, pos)
            if not match:
                self.collect_plain(source[pos:], base_offset + pos)
                break

            self.collect_plain(source[pos : match.start()], base_offset + pos)
            env = match.group(1)
            options = parse_options(match.group(2))
            end_span = self.find_env_end(source, env, match.end())

            if end_span is None:
                self.add_message(
                    "error",
                    f"unclosed environment '{env}'",
                    base_offset + match.start(),
                )
                break

            self.collect_env(env, options, base_offset + match.start())
            self.collect_blocks(source[match.end() : end_span[0]], base_offset + match.end())
            pos = end_span[1]

    def collect_plain(self, source: str, base_offset: int) -> None:
        source = source.strip()
        if not source:
            return

        search_pos = 0
        for block in re.split(r"\n\s*\n", source):
            block_start = source.find(block, search_pos)
            if block_start == -1:
                block_start = search_pos
            heading = self.parse_heading(block.strip())
            if heading:
                self.register_heading(*heading)
            search_pos = block_start + len(block)

    def collect_env(self, env: str, options: dict[str, str], start_index: int) -> None:
        if env == "kbox":
            box_type = slug_class(options.get("type", "plain"))
            if box_type in NUMBERED_BOX_TYPES:
                self.register_numbered(
                    kind=NUMBERED_BOX_TYPES[box_type],
                    title=options.get("title", ""),
                    label=options.get("label"),
                    fallback_id=f"{box_type}-{len(self.numbered_records) + 1}",
                    start_index=start_index,
                )
            elif options.get("label"):
                label = options["label"]
                self.register_label(
                    label=label,
                    record=NumberedRecord(
                        kind=self.default_box_title(box_type),
                        number="",
                        title=options.get("title", ""),
                        anchor=safe_html_id(label, fallback=f"{box_type}-box"),
                    ),
                    start_index=start_index,
                )
        elif env == "kexercise":
            level = options.get("level", "standard").strip()
            if level and level not in EXERCISE_LEVELS:
                self.add_message(
                    "warning",
                    f"unknown exercise level '{level}'; fallback to 'standard'",
                    start_index,
                )
            self.register_numbered(
                kind="演習",
                title=options.get("title", ""),
                label=options.get("label"),
                fallback_id=f"exercise-{len(self.numbered_records) + 1}",
                start_index=start_index,
            )

    def register_heading(self, command: str, title: str) -> None:
        level = HEADING_LEVELS[command]
        self.section_counts[level - 1] += 1
        for index in range(level, len(self.section_counts)):
            self.section_counts[index] = 0
        if level == 1 and not self.book_mode:
            self.block_count = 0

        number_parts = [str(value) for value in self.section_counts[:level] if value > 0]
        if self.book_mode:
            number_parts = [str(self.current_chapter), *number_parts]
        number = ".".join(number_parts)
        anchor = "section-" + "-".join(number_parts)
        self.heading_records.append(HeadingRecord(level=level, number=number, title=title, anchor=anchor))

    def register_numbered(
        self,
        kind: str,
        title: str,
        label: str | None,
        fallback_id: str,
        start_index: int,
    ) -> None:
        section_number = self.current_chapter if self.book_mode else (self.section_counts[0] or 0)
        if self.book_mode:
            self.book_block_counts[kind] = self.book_block_counts.get(kind, 0) + 1
            number = f"{section_number}.{self.book_block_counts[kind]}"
        else:
            self.block_count += 1
            number = f"{section_number}.{self.block_count}"
        anchor = safe_html_id(label, fallback=fallback_id) if label else None
        record = NumberedRecord(kind=kind, number=number, title=title, anchor=anchor)
        self.numbered_records.append(record)
        if not label:
            return
        self.register_label(label, record, start_index)

    def register_label(self, label: str, record: NumberedRecord, start_index: int) -> None:
        current_location = self.location_from_index(start_index)
        if label in self.labels:
            first_location = self.label_locations[label]
            self.add_message(
                "error",
                f"duplicate label '{label}'",
                start_index,
                notes=[
                    f"first defined at {first_location.path}:{first_location.line}:{first_location.column}",
                    f"duplicated at {current_location.path}:{current_location.line}:{current_location.column}",
                ],
            )
            return

        self.labels[label] = record
        self.label_locations[label] = current_location

    def reset_render_state(self) -> None:
        self.gap_index = 0
        self._heading_cursor = 0
        self._chapter_cursor = 0
        self._numbered_cursor = 0

    def render_toc(self) -> str:
        if not self.heading_records and not self.chapter_records:
            return ""

        items = []
        if self.book_mode:
            heading_index = 0
            for chapter in self.chapter_records:
                chapter_label = html.escape(f"Chapter {chapter.number}: {chapter.title}")
                items.append(
                    f'    <li class="ktoc-chapter"><a href="#{html.escape(chapter.anchor)}">{chapter_label}</a></li>'
                )
                while heading_index < len(self.heading_records):
                    record = self.heading_records[heading_index]
                    if not record.number.startswith(f"{chapter.number}."):
                        break
                    label = html.escape(f"{record.number} {record.title}")
                    items.append(
                        f'    <li class="ktoc-level-{record.level} ktoc-in-chapter">'
                        f'<a href="#{html.escape(record.anchor)}">{label}</a></li>'
                    )
                    heading_index += 1
        else:
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

    def next_chapter_record(self) -> ChapterRecord:
        record = self.chapter_records[self._chapter_cursor]
        self._chapter_cursor += 1
        return record

    def render_chapter_heading(self) -> str:
        record = self.next_chapter_record()
        return (
            f'<section class="kchapter" id="{html.escape(record.anchor)}">\n'
            f'  <div class="kchapter-kicker">Chapter {record.number}</div>\n'
            f'  <h1>{html.escape(record.title)}</h1>\n'
            "</section>"
        )

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
        level = options.get("level", "standard").strip()
        if level not in EXERCISE_LEVELS:
            level = "standard"
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
        heading_prefix = f"{record.number} " if self.book_mode or record.level > 1 else f"{record.number}. "
        return f'<{tag} id="{html.escape(record.anchor)}">{html.escape(heading_prefix)}{title}</{tag}>'

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


def parse_manifest_value(line: str) -> str:
    value = line.split(":", 1)[1].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def line_start_index(lines: list[str], line_number: int) -> int:
    return sum(len(line) + 1 for line in lines[: max(0, line_number - 1)])


def parse_book_manifest(manifest_path: Path, renderer: Renderer) -> BookManifest:
    try:
        source = read_text(manifest_path)
    except OSError as exc:
        renderer.set_source_context(manifest_path, "")
        renderer.add_message("error", f"cannot read manifest '{manifest_path}': {exc}")
        return BookManifest(title="", subtitle="", chapters=[])

    renderer.set_source_context(manifest_path, source)
    lines = source.splitlines()
    title = ""
    subtitle = ""
    chapters: list[BookChapter] = []
    in_chapters = False
    current: dict[str, str] | None = None
    current_line = 1

    def finish_chapter() -> None:
        nonlocal current, current_line
        if current is None:
            return
        path_value = current.get("path", "").strip()
        title_value = current.get("title", "").strip()
        if not path_value:
            renderer.add_message(
                "error",
                "invalid manifest chapter: missing path",
                line_start_index(lines, current_line),
            )
        if not title_value:
            renderer.add_message(
                "error",
                "invalid manifest chapter: missing title",
                line_start_index(lines, current_line),
            )
        if path_value and title_value:
            chapters.append(BookChapter(path=(manifest_path.parent / path_value).resolve(), title=title_value))
        current = None

    for line_number, raw_line in enumerate(lines, start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped == "chapters:":
            in_chapters = True
            continue

        if not in_chapters:
            if stripped.startswith("title:"):
                title = parse_manifest_value(stripped)
            elif stripped.startswith("subtitle:"):
                subtitle = parse_manifest_value(stripped)
            else:
                renderer.add_message(
                    "error",
                    f"invalid manifest line: {stripped}",
                    line_start_index(lines, line_number),
                )
            continue

        if stripped.startswith("- "):
            finish_chapter()
            current = {}
            current_line = line_number
            stripped = stripped[2:].strip()
            if stripped:
                if ":" not in stripped:
                    renderer.add_message(
                        "error",
                        f"invalid chapter entry: {stripped}",
                        line_start_index(lines, line_number),
                    )
                else:
                    key, _sep, _value = stripped.partition(":")
                    current[key.strip()] = parse_manifest_value(stripped)
            continue

        if current is None:
            renderer.add_message(
                "error",
                f"invalid manifest chapter line: {stripped}",
                line_start_index(lines, line_number),
            )
            continue

        if ":" not in stripped:
            renderer.add_message(
                "error",
                f"invalid manifest chapter line: {stripped}",
                line_start_index(lines, line_number),
            )
            continue
        key, _sep, _value = stripped.partition(":")
        current[key.strip()] = parse_manifest_value(stripped)

    finish_chapter()

    if not title:
        renderer.add_message("error", "invalid manifest: missing title", 0)
    if not chapters:
        renderer.add_message("error", "invalid manifest: missing chapters", 0)

    return BookManifest(title=title or "Kirei Book", subtitle=subtitle, chapters=chapters)


def render_html_output(
    renderer: Renderer,
    title: str,
    subtitle: str,
    toc: str,
    content: str,
    output_path: Path,
    options: BuildOptions,
) -> str:
    template = read_text(ROOT / "templates" / "book.html")
    css_block, js_block = render_asset_blocks(output_path, options)
    mathjax_config, mathjax_script = render_mathjax_blocks(renderer, output_path, options)
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    scroll_class = "scroll-vertical"

    return (
        template.replace("{{ title }}", html.escape(title))
        .replace("{{ subtitle }}", html.escape(subtitle))
        .replace("{{ toc }}", toc)
        .replace("{{ content }}", content)
        .replace("{{ css_block }}", css_block)
        .replace("{{ mathjax_config }}", mathjax_config)
        .replace("{{ mathjax_script }}", mathjax_script)
        .replace("{{ js_block }}", js_block)
        .replace("{{ generated_at }}", generated_at)
        .replace("{{ theme_class }}", f"theme-{html.escape(options.theme)}")
        .replace("{{ scroll_class }}", scroll_class)
    )


def build(input_path: Path, output_path: Path, options: BuildOptions | None = None) -> Renderer:
    options = normalize_options(options or BuildOptions())
    renderer = Renderer(input_path, options)
    title, subtitle, toc, content = renderer.render_document(read_text(input_path))
    html_output = render_html_output(renderer, title, subtitle, toc, content, output_path, options)

    if not options.check and (not renderer.has_errors or options.allow_output_on_error):
        if options.assets_mode == "external":
            copy_external_assets(output_path)
        write_text(output_path, html_output)

    return renderer


def build_book(manifest_path: Path, output_path: Path, options: BuildOptions | None = None) -> Renderer:
    options = normalize_options(options or BuildOptions())
    renderer = Renderer(manifest_path, options)
    manifest = parse_book_manifest(manifest_path, renderer)
    title, subtitle, toc, content = renderer.render_book(manifest) if manifest.chapters else (
        manifest.title,
        manifest.subtitle,
        "",
        "",
    )
    html_output = render_html_output(renderer, title, subtitle, toc, content, output_path, options)

    if not options.check and (not renderer.has_errors or options.allow_output_on_error):
        if options.assets_mode == "external":
            copy_external_assets(output_path)
        write_text(output_path, html_output)

    return renderer


def pluralize(count: int, singular: str, plural: str) -> str:
    return singular if count == 1 else plural


def format_summary(renderer: Renderer) -> str:
    error_count = len(renderer.errors)
    warning_count = len(renderer.warnings)
    error_word = pluralize(error_count, "error", "errors")
    warning_word = pluralize(warning_count, "warning", "warnings")
    if error_count:
        return f"Kirei TeX build failed with {error_count} {error_word}, {warning_count} {warning_word}."
    if warning_count:
        return f"Kirei TeX build completed with {warning_count} {warning_word}."
    return "Kirei TeX build completed successfully."


def format_message(message: BuildMessage) -> str:
    lines = [f"{message.kind}: {message.message}"]
    if message.path and message.line is not None and message.column is not None:
        lines.append(f"  at {message.path}:{message.line}:{message.column}")
    if message.line is not None and message.snippet:
        lines.append(f"  {message.line} | {message.snippet}")
    lines.extend(f"  {note}" for note in message.notes)
    return "\n".join(lines)


def print_report(renderer: Renderer, quiet: bool = False) -> None:
    print(format_summary(renderer), file=sys.stderr)
    messages: list[BuildMessage] = list(renderer.errors)
    if not quiet:
        messages.extend(renderer.warnings)
    for message in messages:
        print(file=sys.stderr)
        print(format_message(message), file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a single-file interactive math book from .ktex.")
    parser.add_argument("input", type=Path, help="Input .ktex file")
    parser.add_argument("output", type=Path, help="Output HTML file")
    parser.add_argument("--book", action="store_true", help="Treat input as a book manifest")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--allow-output-on-error", action="store_true", help="Write HTML even if errors are found")
    parser.add_argument("--quiet", action="store_true", help="Suppress warning details")
    parser.add_argument("--check", action="store_true", help="Check syntax without writing HTML")
    parser.add_argument("--mathjax", choices=["cdn", "local", "none"], default="cdn", help="MathJax loading mode")
    parser.add_argument(
        "--mathjax-path",
        type=Path,
        default=Path("vendor/mathjax/tex-svg.js"),
        help="Local MathJax path used with --mathjax local",
    )
    parser.add_argument("--assets", choices=["inline", "external"], default="inline", help="CSS/JS output mode")
    parser.add_argument("--theme", choices=["rich", "mono"], default="rich", help="Initial display theme")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Shortcut for --mathjax local --assets inline",
    )
    args = parser.parse_args()

    options = BuildOptions(
        strict=args.strict,
        allow_output_on_error=args.allow_output_on_error,
        quiet=args.quiet,
        check=args.check,
        mathjax_mode=args.mathjax,
        mathjax_path=args.mathjax_path,
        assets_mode=args.assets,
        offline=args.offline,
        theme=args.theme,
    )
    renderer = build_book(args.input, args.output, options) if args.book else build(args.input, args.output, options)
    print_report(renderer, quiet=args.quiet)

    if renderer.has_errors:
        return 1

    if not args.check:
        print(f"built {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
