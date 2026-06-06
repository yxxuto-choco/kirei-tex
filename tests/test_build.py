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


if __name__ == "__main__":
    unittest.main()
