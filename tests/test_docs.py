import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_AUTOMODULE_RE = re.compile(r"^\.\.\s+automodule::\s+(\S+)\s*$", re.MULTILINE)


class TestEveryModuleHasExactlyOneAutomodulePage(unittest.TestCase):
    def test_every_module_is_documented_exactly_once(self):
        module_names = sorted(
            f"document2md.{path.stem}"
            for path in (ROOT / "document2md").glob("*.py")
            if path.stem != "__init__"
        )
        self.assertTrue(module_names, "expected at least one document2md/*.py module")

        rst_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "docs" / "source").rglob("*.rst")
        )
        documented = _AUTOMODULE_RE.findall(rst_text)

        for name in module_names:
            occurrences = documented.count(name)
            self.assertEqual(
                occurrences, 1,
                f"{name} is named by {occurrences} automodule directives under "
                "docs/source/, expected exactly 1",
            )


if __name__ == "__main__":
    unittest.main()
