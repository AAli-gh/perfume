"""مستندات با کد هماهنگ می‌مانند: پیوندها، تصاویر و مسیرهای فایل نام‌برده در اسناد باید وجود داشته باشند."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOCS = [ROOT / "README.md", ROOT / "DEPLOY.md", ROOT / "themes" / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)|<img src=\"([^\"]+)\"")
PATH = re.compile(r"`((?:apps|themes|deploy|tests|config|static|docs|scripts)/[^`\s]*)`")
# فایل‌هایی که در git نیستند: خروجی build و مثال‌های عمدی (فایل‌هایی که کاربر خودش می‌سازد)
NOT_IN_GIT = {"static/css/app.css", "deploy/certs/fullchain.pem", "deploy/certs/privkey.pem",
              "themes/minimal/templates/components/product_card.html", "themes/minimal/templates/sections/hero.html"}


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: str(p.relative_to(ROOT)))
def test_links_and_paths_exist(doc):
    text = doc.read_text()
    links = [md or img for md, img in LINK.findall(text)]
    missing = [link for link in links
               if not link.startswith(("http://", "https://")) and not (doc.parent / link).exists()]
    missing += [p for p in PATH.findall(text)
                if "<" not in p and "*" not in p and p not in NOT_IN_GIT and not (ROOT / p.rstrip("/")).exists()]
    assert not missing, f"{doc.name}: {missing}"


def test_adr_index_lists_every_adr():
    index = (ROOT / "docs" / "adr" / "README.md").read_text()
    for adr in (ROOT / "docs" / "adr").glob("0*.md"):
        assert f"({adr.name})" in index, adr.name
