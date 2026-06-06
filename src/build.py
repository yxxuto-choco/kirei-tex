from __future__ import annotations

import argparse
import datetime as dt
import html
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BEGIN_RE = re.compile(r"\\begin\{(kfold|kbox|kadvanced)\}(?:\[([^\]]*)\])?", re.DOTALL)


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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class Renderer:
    def __init__(self) -> None:
        self.gap_index = 0

    def render_document(self, source: str) -> tuple[str, str, str]:
        title = self.extract_command(source, "title") or "Kirei Book"
        subtitle = self.extract_command(source, "subtitle") or ""
        body = self.remove_metadata(source)
        return title, subtitle, self.render_blocks(body)

    def extract_command(self, source: str, name: str) -> str | None:
        match = re.search(rf"\\{name}\{{([^{{}}]*)\}}", source)
        return match.group(1).strip() if match else None

    def remove_metadata(self, source: str) -> str:
        source = re.sub(r"\\title\{[^{}]*\}\s*", "", source)
        source = re.sub(r"\\subtitle\{[^{}]*\}\s*", "", source)
        return source.strip()

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
            box_type = slug_class(options.get("type", "plain"))
            title = options.get("title") or self.default_box_title(box_type)
            return (
                f'<aside class="kbox kbox-{box_type}">\n'
                f'  <div class="kbox-label">{self.render_inline(title)}</div>\n'
                f'  <div class="kbox-body">\n{inner_html}\n  </div>\n'
                "</aside>"
            )

        if env == "kadvanced":
            return (
                '<section class="kadvanced" data-advanced>\n'
                '  <div class="kadvanced-ribbon">発展</div>\n'
                f'  <div class="kadvanced-body">\n{inner_html}\n  </div>\n'
                "</section>"
            )

        return inner_html

    def default_box_title(self, box_type: str) -> str:
        return {
            "theorem": "定理",
            "note": "注意",
            "example": "例",
            "proof": "証明",
        }.get(box_type, "補足")

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

    def render_heading(self, block: str) -> str | None:
        for command, tag in (("section", "h2"), ("subsection", "h3"), ("subsubsection", "h4")):
            match = re.fullmatch(rf"\\{command}\{{([^{{}}]+)\}}", block, re.DOTALL)
            if match:
                return f"<{tag}>{self.render_inline(match.group(1).strip())}</{tag}>"
        return None

    def render_inline(self, source: str, linebreaks: bool = False) -> str:
        protected, math_tokens = self.protect_math(source)
        rendered = self.render_gaps(protected)
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

    def render_gaps(self, source: str) -> str:
        output: list[str] = []
        pos = 0
        macro = r"\kgap{"

        while True:
            start = source.find(macro, pos)
            if start == -1:
                output.append(html.escape(source[pos:]))
                break

            output.append(html.escape(source[pos:start]))
            content_start = start + len(macro)
            content_end = self.find_matching_brace(source, content_start - 1)
            if content_end is None:
                output.append(html.escape(source[start:]))
                break

            content = source[content_start:content_end]
            output.append(self.render_gap(content))
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
        body = html.escape(content).replace("\n", "<br>\n")
        return (
            f'<span class="kgap" data-kgap>'
            f'<button class="kgap-trigger" type="button" aria-expanded="false" '
            f'aria-controls="{gap_id}" data-kgap-target="{gap_id}">?</button>'
            f'<span id="{gap_id}" class="kgap-popover" role="note" hidden>{body}</span>'
            f"</span>"
        )


def build(input_path: Path, output_path: Path) -> None:
    renderer = Renderer()
    title, subtitle, content = renderer.render_document(read_text(input_path))
    template = read_text(ROOT / "templates" / "book.html")
    css = read_text(ROOT / "assets" / "kirei.css")
    js = read_text(ROOT / "assets" / "kirei.js")
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    html_output = (
        template.replace("{{ title }}", html.escape(title))
        .replace("{{ subtitle }}", html.escape(subtitle))
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
