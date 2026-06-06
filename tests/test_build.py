from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.build import BuildOptions, build


ROOT = Path(__file__).resolve().parents[1]


class BuildTests(unittest.TestCase):
    def test_sample_builds_successfully(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "sample.html"
            renderer = build(ROOT / "examples" / "sample.ktex", output, BuildOptions())

            self.assertFalse(renderer.errors)
            self.assertFalse(renderer.warnings)
            self.assertTrue(output.exists())

    def test_broken_detects_errors_in_check_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "broken.html"
            renderer = build(
                ROOT / "examples" / "broken.ktex",
                output,
                BuildOptions(check=True),
            )

            error_text = "\n".join(message.message for message in renderer.errors)
            warning_text = "\n".join(message.message for message in renderer.warnings)
            self.assertIn("unclosed environment 'kbox'", error_text)
            self.assertIn("duplicate label 'thm:duplicate'", error_text)
            self.assertIn("unresolved reference 'thm:missing'", warning_text)
            self.assertIn("unknown exercise level 'hard'", warning_text)
            self.assertFalse(output.exists())

    def test_unresolved_reference_is_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "unresolved.ktex"
            output = Path(temp_dir) / "unresolved.html"
            source.write_text(
                "\\title{未解決参照}\n\\section{本文}\n未解決 \\kref{missing:label}\n",
                encoding="utf-8",
            )
            renderer = build(source, output, BuildOptions(check=True))

            self.assertFalse(renderer.errors)
            self.assertEqual(len(renderer.warnings), 1)
            self.assertIn("unresolved reference 'missing:label'", renderer.warnings[0].message)

    def test_strict_treats_warning_as_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "strict.ktex"
            output = Path(temp_dir) / "strict.html"
            source.write_text(
                "\\title{Strict}\n\\section{本文}\n未解決 \\kref{missing:label}\n",
                encoding="utf-8",
            )
            renderer = build(source, output, BuildOptions(check=True, strict=True))

            self.assertFalse(renderer.warnings)
            self.assertEqual(len(renderer.errors), 1)
            self.assertIn("unresolved reference 'missing:label'", renderer.errors[0].message)

    def test_duplicate_label_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "duplicate.ktex"
            output = Path(temp_dir) / "duplicate.html"
            source.write_text(
                "\\title{重複}\n"
                "\\section{本文}\n"
                "\\begin{kbox}[type=theorem,title=A,label=thm:a]\nA\n\\end{kbox}\n\n"
                "\\begin{kexercise}[title=B,label=thm:a,level=basic]\nB\n\\end{kexercise}\n",
                encoding="utf-8",
            )
            renderer = build(source, output, BuildOptions(check=True))

            self.assertEqual(len(renderer.errors), 1)
            self.assertIn("duplicate label 'thm:a'", renderer.errors[0].message)

    def test_default_build_includes_mathjax_cdn(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "sample.html"
            renderer = build(ROOT / "examples" / "sample.ktex", output, BuildOptions())
            html = output.read_text(encoding="utf-8")

            self.assertFalse(renderer.errors)
            self.assertIn("cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js", html)

    def test_mathjax_none_omits_mathjax_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "sample-none.html"
            renderer = build(
                ROOT / "examples" / "sample.ktex",
                output,
                BuildOptions(mathjax_mode="none"),
            )
            html = output.read_text(encoding="utf-8")

            self.assertFalse(renderer.errors)
            self.assertNotIn("window.MathJax = {", html)
            self.assertNotIn("tex-svg.js", html)

    def test_mathjax_local_uses_local_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "sample-local.html"
            renderer = build(
                ROOT / "examples" / "sample.ktex",
                output,
                BuildOptions(mathjax_mode="local", mathjax_path=Path("vendor/mathjax/tex-svg.js")),
            )
            html = output.read_text(encoding="utf-8")

            self.assertFalse(renderer.errors)
            self.assertIn("vendor/mathjax/tex-svg.js", html)
            self.assertFalse(renderer.warnings)

    def test_mathjax_local_missing_file_warns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "sample-local-missing.html"
            renderer = build(
                ROOT / "examples" / "sample.ktex",
                output,
                BuildOptions(mathjax_mode="local", mathjax_path=Path("vendor/mathjax/missing-tex-svg.js")),
            )

            self.assertFalse(renderer.errors)
            self.assertIn("local MathJax file not found", renderer.warnings[0].message)

    def test_offline_sets_local_mathjax_and_inline_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "sample-offline.html"
            renderer = build(ROOT / "examples" / "sample.ktex", output, BuildOptions(offline=True))
            html = output.read_text(encoding="utf-8")

            self.assertFalse(renderer.errors)
            self.assertIn("vendor/mathjax/tex-svg.js", html)
            self.assertIn("<style>", html)
            self.assertIn("const ADVANCED_KEY", html)
            self.assertFalse((Path(temp_dir) / "assets" / "kirei.css").exists())

    def test_external_assets_are_copied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "sample-external.html"
            renderer = build(
                ROOT / "examples" / "sample.ktex",
                output,
                BuildOptions(assets_mode="external"),
            )
            html = output.read_text(encoding="utf-8")

            self.assertFalse(renderer.errors)
            self.assertIn('href="assets/kirei.css"', html)
            self.assertIn('src="assets/kirei.js"', html)
            self.assertTrue((Path(temp_dir) / "assets" / "kirei.css").exists())
            self.assertTrue((Path(temp_dir) / "assets" / "kirei.js").exists())


if __name__ == "__main__":
    unittest.main()
