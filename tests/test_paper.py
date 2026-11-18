"""Published PDFs link to both Quarto spellings of the source notebook."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_published_notebook_alias_survives_a_clean_render():
    alias = "index.qmd.html"
    paper = ROOT / "paper"
    docs = ROOT / "docs"
    resources = yaml.safe_load((paper / "_quarto.yml").read_text())["project"]["resources"]
    assert alias in resources
    assert (docs / alias).read_bytes() == (paper / alias).read_bytes()
    assert 'http-equiv="refresh" content="0; url=index-preview.html"' in (docs / alias).read_text()
    assert (docs / "index-preview.html").is_file()
