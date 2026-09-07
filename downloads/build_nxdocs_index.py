#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Siemens Help Server Documentation -> Standalone Offline Documentation

Usage:

    python build_index.py SOURCE_DIR OUTPUT_DIR

Example:

    python build_index.py ./siemens_help ./dist

Optional:

    python build_index.py ./siemens_help ./dist --clean
    python build_index.py ./siemens_help ./dist --page-size 20
    python build_index.py ./siemens_help ./dist --base-url http://localhost:8080/help/

Required:

    pip install beautifulsoup4 lxml

Features:

1. Scans HTML / XHTML / XML documentation.
2. Builds a topic/file manifest.
3. Copies documentation/assets to the output directory.
4. Rewrites local HTML links.
5. Preserves URL fragments.
6. Tries to resolve Siemens Help Server query-based topic URLs.
7. Detects unresolved internal Help Server links.
8. Converts unresolved internal <a> links into GET searches
   using the visible anchor text.
9. Adds data-shc-search-fallback="true" to search fallback links.
10. Injects a global search bar into every HTML document.
11. Search supports GET and POST forms.
12. Search URLs support:
        search.html?q=PLC
        search.html?q=PLC&page=2
13. Search results are paginated.
14. Default page size is 20.
15. Every page has a Documentation Home link.
16. Generates search-documents.json.
17. Generates standalone JavaScript search UI.
18. Generates validation-report.json.
19. Generates manifest.json.
20. No Node.js required.
21. No JDK required at runtime.
22. Generated documentation can be used offline.

Important:

For a link such as:

    <a href="http://help-server/...">Configure PLC</a>

where the original Siemens Help Server URL cannot be mapped to a local
HTML file, the converter generates:

    <a href="../search.html?q=Configure%20PLC"
       data-shc-search-fallback="true">
        Configure PLC
    </a>

This means the link remains useful after the Help Server is removed.
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import os
import re
import shutil
import sys
import unicodedata
import warnings

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
from urllib.parse import (
    parse_qs,
    quote,
    unquote,
    urlsplit,
)

from bs4 import (
    BeautifulSoup,
    XMLParsedAsHTMLWarning,
)


# ============================================================
# Suppress XMLParsedAsHTMLWarning
# ============================================================

warnings.filterwarnings(
    "ignore",
    category=XMLParsedAsHTMLWarning,
)


# ============================================================
# Constants
# ============================================================

HTML_EXTENSIONS = {
    ".html",
    ".htm",
    ".xhtml",
}

XML_EXTENSIONS = {
    ".xml",
}

TEXT_EXTENSIONS = {
    ".txt",
    ".xml",
    ".xhtml",
    ".html",
    ".htm",
}

URL_ATTRIBUTES = {
    "a": ("href",),
    "area": ("href",),
    "img": ("src", "srcset"),
    "script": ("src",),
    "link": ("href",),
    "iframe": ("src",),
    "frame": ("src",),
    "object": ("data",),
    "embed": ("src",),
    "video": ("src", "poster"),
    "audio": ("src",),
    "source": ("src", "srcset"),
    "track": ("src",),
    "input": ("src",),
    "form": ("action",),
}

IGNORED_URL_SCHEMES = {
    "http",
    "https",
    "mailto",
    "tel",
    "javascript",
    "data",
    "blob",
    "ftp",
    "file",
}

QUERY_TOPIC_KEYS = (
    "id",
    "topic",
    "topicid",
    "topicId",
    "topic_id",
    "node",
    "nodeid",
    "nodeId",
    "doc",
    "docid",
    "docId",
    "page",
    "pageid",
    "pageId",
    "article",
    "articleid",
    "articleId",
)

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
    "you",
    "your",
}


# ============================================================
# Dataclasses
# ============================================================

@dataclass
class Topic:
    topic_id: str
    source: str
    output: str
    title: str
    original_url: str = ""


@dataclass
class BrokenLink:
    source: str
    url: str
    reason: str


@dataclass
class SearchFallback:
    source: str
    original_url: str
    anchor_text: str
    generated_url: str
    reason: str


# ============================================================
# Utility Functions
# ============================================================

def normalize_slashes(value: str) -> str:
    return value.replace("\\", "/")


def normalize_relpath(path: Path) -> str:
    return normalize_slashes(str(path))


def sha1_text(value: str) -> str:
    return hashlib.sha1(
        value.encode("utf-8")
    ).hexdigest()


def is_html(path: Path) -> bool:
    return path.suffix.lower() in HTML_EXTENSIONS


def is_xml(path: Path) -> bool:
    return path.suffix.lower() in XML_EXTENSIONS


def is_markup(path: Path) -> bool:
    return is_html(path) or is_xml(path)


def is_external_url(value: str) -> bool:

    value = value.strip()

    if not value:
        return False

    parts = urlsplit(value)

    if parts.scheme:
        return parts.scheme.lower() in IGNORED_URL_SCHEMES

    if value.startswith("//"):
        return True

    return False


def is_http_url(value: str) -> bool:

    value = value.strip()

    parts = urlsplit(value)

    return parts.scheme.lower() in {
        "http",
        "https",
    }


def clean_text(text: str) -> str:

    text = unicodedata.normalize(
        "NFKC",
        text,
    )

    text = text.replace(
        "\xa0",
        " ",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def safe_json_dump(
    data,
    path: Path,
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def relative_url(
    from_file: Path,
    to_file: Path,
) -> str:

    rel = os.path.relpath(
        to_file,
        start=from_file.parent,
    )

    rel = normalize_slashes(rel)

    if rel == ".":
        return "./"

    return quote(
        rel,
        safe="/:@-._~!$&'()*+,;=",
    )


def normalize_path_for_lookup(
    path: str,
) -> str:

    path = unquote(path)

    path = normalize_slashes(path)

    while "//" in path:
        path = path.replace(
            "//",
            "/",
        )

    if path.startswith("./"):
        path = path[2:]

    return path.lstrip("/")


def split_srcset(value: str):

    result = []

    for item in value.split(","):

        item = item.strip()

        if not item:
            continue

        parts = item.split()

        if not parts:
            continue

        url = parts[0]

        descriptor = " ".join(
            parts[1:]
        )

        result.append(
            (
                url,
                descriptor,
            )
        )

    return result


def build_srcset(items):

    return ", ".join(
        f"{url} {descriptor}".strip()
        for url, descriptor in items
    )


def parser_for(path: Path) -> str:

    if is_xml(path):
        return "xml"

    return "lxml"


def parse_document(
    text: str,
    path: Path,
) -> BeautifulSoup:

    return BeautifulSoup(
        text,
        parser_for(path),
    )


def parse_html_fragment(
    text: str,
) -> BeautifulSoup:

    return BeautifulSoup(
        text,
        "lxml",
    )


# ============================================================
# Documentation Scanner
# ============================================================

class DocumentationScanner:

    def __init__(
        self,
        source_root: Path,
    ):
        self.source_root = source_root

    def scan(self) -> list[Path]:

        files = []

        ignored_directories = {
            ".git",
            ".svn",
            "__pycache__",
            "node_modules",
            ".cache",
        }

        for path in self.source_root.rglob("*"):

            if not path.is_file():
                continue

            if any(
                part in ignored_directories
                for part in path.parts
            ):
                continue

            files.append(path)

        files.sort()

        return files


# ============================================================
# Manifest Builder
# ============================================================

class ManifestBuilder:

    def __init__(
        self,
        source_root: Path,
    ):

        self.source_root = source_root

        self.file_to_topic: dict[str, Topic] = {}

        self.topic_id_to_topic: dict[str, Topic] = {}

        self.url_to_topic: dict[str, Topic] = {}

        self.anchor_to_topic: dict[str, Topic] = {}

    def relative_source(
        self,
        path: Path,
    ) -> str:

        return normalize_relpath(
            path.relative_to(
                self.source_root
            )
        )

    def read_html(
        self,
        path: Path,
    ) -> BeautifulSoup:

        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        return parse_document(
            text,
            path,
        )

    def extract_title(
        self,
        soup: BeautifulSoup,
        path: Path,
    ) -> str:

        title = soup.find("title")

        if title:

            value = clean_text(
                title.get_text(
                    " ",
                    strip=True,
                )
            )

            if value:
                return value

        heading = soup.find(
            [
                "h1",
                "h2",
                "h3",
            ]
        )

        if heading:

            value = clean_text(
                heading.get_text(
                    " ",
                    strip=True,
                )
            )

            if value:
                return value

        return path.stem

    def extract_topic_ids(
        self,
        soup: BeautifulSoup,
    ) -> list[str]:

        ids = []

        for tag in soup.find_all(
            attrs={
                "id": True,
            }
        ):

            value = str(
                tag.get("id")
            ).strip()

            if value:
                ids.append(value)

        for tag in soup.find_all(
            attrs={
                "name": True,
            }
        ):

            value = str(
                tag.get("name")
            ).strip()

            if value:
                ids.append(value)

        return ids

    def create_file_topic(
        self,
        path: Path,
        output_path: str,
    ) -> Topic:

        relative = self.relative_source(
            path
        )

        soup = self.read_html(
            path
        )

        title = self.extract_title(
            soup,
            path,
        )

        topic_id = sha1_text(
            relative
        )[:16]

        topic = Topic(
            topic_id=topic_id,
            source=relative,
            output=output_path,
            title=title,
        )

        self.file_to_topic[
            relative
        ] = topic

        return topic

    def build(
        self,
        files: list[Path],
    ):

        html_files = [
            p
            for p in files
            if is_html(p)
        ]

        # ----------------------------------------------------
        # Pass 1: File mappings
        # ----------------------------------------------------

        for source in html_files:

            relative = self.relative_source(
                source
            )

            output = normalize_slashes(
                str(
                    Path(relative)
                )
            )

            topic = self.create_file_topic(
                source,
                output,
            )

            aliases = {
                relative,
                relative.lstrip("./"),
                "/" + relative.lstrip("./"),
            }

            if Path(relative).suffix:

                no_ext = normalize_slashes(
                    str(
                        Path(relative).with_suffix("")
                    )
                )

                aliases.add(no_ext)

                aliases.add(
                    "/" + no_ext
                )

            for alias in aliases:

                self.url_to_topic[
                    normalize_path_for_lookup(
                        alias
                    )
                ] = topic

        # ----------------------------------------------------
        # Pass 2: IDs / anchors
        # ----------------------------------------------------

        for source in html_files:

            relative = self.relative_source(
                source
            )

            topic = self.file_to_topic[
                relative
            ]

            soup = self.read_html(
                source
            )

            ids = self.extract_topic_ids(
                soup
            )

            for anchor_id in ids:

                key = anchor_id.strip()

                if not key:
                    continue

                if (
                    key
                    not in self.anchor_to_topic
                ):

                    self.anchor_to_topic[
                        key
                    ] = topic

        # ----------------------------------------------------
        # Pass 3: topic IDs from filename
        # ----------------------------------------------------

        for topic in self.file_to_topic.values():

            stem = Path(
                topic.source
            ).stem

            candidates = {
                stem,
                topic.topic_id,
            }

            for value in candidates:

                if value:

                    self.topic_id_to_topic.setdefault(
                        value,
                        topic,
                    )

        return self


# ============================================================
# Topic Resolver
# ============================================================

class TopicResolver:

    def __init__(
        self,
        source_root: Path,
        output_root: Path,
        manifest: ManifestBuilder,
        base_url: str = "",
    ):

        self.source_root = source_root
        self.output_root = output_root
        self.manifest = manifest

        self.base_url = (
            base_url.rstrip("/")
            if base_url
            else ""
        )

    def find_file_by_relative_path(
        self,
        current_source: Path,
        target_path: str,
    ) -> Optional[Path]:

        target_path = unquote(
            target_path
        )

        if not target_path:
            return None

        if target_path.startswith("/"):

            candidate = (
                self.source_root /
                target_path.lstrip("/")
            ).resolve()

        else:

            candidate = (
                current_source.parent /
                target_path
            ).resolve()

        try:

            candidate.relative_to(
                self.source_root.resolve()
            )

        except ValueError:

            return None

        if candidate.is_file():
            return candidate

        if not candidate.suffix:

            for ext in HTML_EXTENSIONS:

                alternative = (
                    candidate.with_suffix(ext)
                )

                if alternative.is_file():
                    return alternative

        return None

    def lookup_manifest_path(
        self,
        path_value: str,
    ) -> Optional[Topic]:

        normalized = normalize_path_for_lookup(
            path_value
        )

        if normalized in self.manifest.url_to_topic:

            return self.manifest.url_to_topic[
                normalized
            ]

        normalized = normalized.lstrip("/")

        if normalized in self.manifest.url_to_topic:

            return self.manifest.url_to_topic[
                normalized
            ]

        return None

    def lookup_query_topic(
        self,
        query: str,
    ) -> Optional[Topic]:

        if not query:
            return None

        params = parse_qs(
            query,
            keep_blank_values=True,
        )

        # ----------------------------------------------------
        # Known topic parameter names
        # ----------------------------------------------------

        for key in QUERY_TOPIC_KEYS:

            values = params.get(key)

            if not values:
                continue

            for value in values:

                value = unquote(
                    value.strip()
                )

                if not value:
                    continue

                if (
                    value
                    in self.manifest.topic_id_to_topic
                ):

                    return self.manifest.topic_id_to_topic[
                        value
                    ]

                if (
                    value
                    in self.manifest.anchor_to_topic
                ):

                    return self.manifest.anchor_to_topic[
                        value
                    ]

                topic = self.lookup_manifest_path(
                    value
                )

                if topic:
                    return topic

        # ----------------------------------------------------
        # Generic fallback
        # ----------------------------------------------------

        for values in params.values():

            for value in values:

                value = unquote(
                    value.strip()
                )

                if (
                    value
                    in self.manifest.topic_id_to_topic
                ):

                    return self.manifest.topic_id_to_topic[
                        value
                    ]

                if (
                    value
                    in self.manifest.anchor_to_topic
                ):

                    return self.manifest.anchor_to_topic[
                        value
                    ]

        return None

    def build_relative_topic_url(
        self,
        current_source: Path,
        topic: Topic,
        fragment: str = "",
    ) -> str:

        current_output = (
            self.output_root /
            normalize_relpath(
                current_source.relative_to(
                    self.source_root
                )
            )
        )

        target_output = (
            self.output_root /
            topic.output
        )

        result = relative_url(
            current_output,
            target_output,
        )

        if fragment:

            result += "#" + quote(
                fragment,
                safe="!$&'()*+,;=:@/?",
            )

        return result

    def resolve(
        self,
        current_source: Path,
        url: str,
    ) -> Optional[str]:

        url = url.strip()

        if not url:
            return url

        if url.startswith("#"):
            return url

        if is_external_url(url):
            return None

        parts = urlsplit(url)

        path = parts.path
        query = parts.query
        fragment = parts.fragment

        # ----------------------------------------------------
        # 1. Query-based virtual topic
        # ----------------------------------------------------

        query_topic = self.lookup_query_topic(
            query
        )

        if query_topic:

            return self.build_relative_topic_url(
                current_source,
                query_topic,
                fragment,
            )

        # ----------------------------------------------------
        # 2. Manifest path mapping
        # ----------------------------------------------------

        topic = self.lookup_manifest_path(
            path
        )

        if topic:

            return self.build_relative_topic_url(
                current_source,
                topic,
                fragment,
            )

        # ----------------------------------------------------
        # 3. Normal local filesystem path
        # ----------------------------------------------------

        target_source = (
            self.find_file_by_relative_path(
                current_source,
                path,
            )
        )

        if target_source:

            relative_target = normalize_relpath(
                target_source.relative_to(
                    self.source_root
                )
            )

            topic = (
                self.manifest.file_to_topic.get(
                    relative_target
                )
            )

            if topic:

                return self.build_relative_topic_url(
                    current_source,
                    topic,
                    fragment,
                )

            current_output = (
                self.output_root /
                normalize_relpath(
                    current_source.relative_to(
                        self.source_root
                    )
                )
            )

            target_output = (
                self.output_root /
                relative_target
            )

            result = relative_url(
                current_output,
                target_output,
            )

            if fragment:

                result += "#" + quote(
                    fragment,
                    safe="!$&'()*+,;=:@/?",
                )

            return result

        # ----------------------------------------------------
        # 4. Empty path + query
        # ----------------------------------------------------

        if not path and query:

            topic = self.lookup_query_topic(
                query
            )

            if topic:

                return self.build_relative_topic_url(
                    current_source,
                    topic,
                    fragment,
                )

        return None


# ============================================================
# Search Fallback Builder
# ============================================================

class SearchFallbackBuilder:

    def __init__(
        self,
        source_root: Path,
        output_root: Path,
    ):

        self.source_root = source_root
        self.output_root = output_root

        self.fallbacks: list[
            SearchFallback
        ] = []

    def get_anchor_text(
        self,
        tag,
    ) -> str:

        # Remove irrelevant accessibility/generated
        # elements from text extraction.
        cloned = BeautifulSoup(
            str(tag),
            "lxml",
        )

        for child in cloned(
            [
                "script",
                "style",
                "noscript",
                "svg",
            ]
        ):
            child.decompose()

        text = cloned.get_text(
            " ",
            strip=True,
        )

        return clean_text(
            text
        )

    def make_search_url(
        self,
        current_source: Path,
        anchor_text: str,
    ) -> str:

        current_output = (
            self.output_root /
            normalize_relpath(
                current_source.relative_to(
                    self.source_root
                )
            )
        )

        search_output = (
            self.output_root /
            "search.html"
        )

        base = relative_url(
            current_output,
            search_output,
        )

        return (
            base
            + "?q="
            + quote(
                anchor_text,
                safe="",
            )
        )

    def convert(
        self,
        source: Path,
        tag,
        original_url: str,
        reason: str,
    ) -> str:

        anchor_text = self.get_anchor_text(
            tag
        )

        # If an anchor has no visible text, do not
        # generate a meaningless search URL.
        if not anchor_text:

            anchor_text = clean_text(
                tag.get(
                    "title",
                    "",
                )
            )

        if not anchor_text:

            anchor_text = clean_text(
                tag.get(
                    "aria-label",
                    "",
                )
            )

        if not anchor_text:

            return original_url

        search_url = self.make_search_url(
            source,
            anchor_text,
        )

        tag["href"] = search_url

        tag[
            "data-shc-search-fallback"
        ] = "true"

        tag[
            "data-shc-original-href"
        ] = original_url

        self.fallbacks.append(
            SearchFallback(
                source=normalize_relpath(
                    source.relative_to(
                        self.source_root
                    )
                ),
                original_url=original_url,
                anchor_text=anchor_text,
                generated_url=search_url,
                reason=reason,
            )
        )

        return search_url


# ============================================================
# HTML Rewriter
# ============================================================

class HTMLRewriter:

    def __init__(
        self,
        source_root: Path,
        output_root: Path,
        resolver: TopicResolver,
        page_size: int,
    ):

        self.source_root = source_root
        self.output_root = output_root
        self.resolver = resolver
        self.page_size = page_size

        self.unresolved_links: list[
            BrokenLink
        ] = []

        self.search_fallback_builder = (
            SearchFallbackBuilder(
                source_root,
                output_root,
            )
        )

    def output_path(
        self,
        source: Path,
    ) -> Path:

        relative = source.relative_to(
            self.source_root
        )

        return self.output_root / relative

    def rewrite_srcset(
        self,
        source: Path,
        value: str,
    ) -> str:

        items = split_srcset(
            value
        )

        rewritten = []

        for url, descriptor in items:

            resolved = self.resolver.resolve(
                source,
                url,
            )

            if resolved is None:

                resolved = url

            rewritten.append(
                (
                    resolved,
                    descriptor,
                )
            )

        return build_srcset(
            rewritten
        )

    def should_skip_url(
        self,
        value: str,
    ) -> bool:

        value = value.strip()

        if not value:
            return True

        if value.startswith("#"):
            return True

        return is_external_url(
            value
        )

    def is_anchor_tag(
        self,
        tag,
    ) -> bool:

        return (
            getattr(
                tag,
                "name",
                "",
            ).lower()
            == "a"
        )

    def is_probably_internal_help_url(
        self,
        value: str,
    ) -> bool:

        value = value.strip()

        if not value:
            return False

        if value.startswith("#"):
            return False

        if is_http_url(value):
            return True

        parts = urlsplit(
            value
        )

        if parts.query:
            return True

        if parts.path:
            return True

        return False

    def rewrite_url(
        self,
        source: Path,
        tag,
        attr: str,
        value: str,
    ) -> str:

        value = value.strip()

        if self.should_skip_url(
            value
        ):

            return value

        resolved = self.resolver.resolve(
            source,
            value,
        )

        if resolved is not None:

            return resolved

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # <a> links that cannot be resolved are converted to
        # GET searches using the visible anchor text.
        #
        # Other resources such as IMG/SCRIPT/CSS are NOT
        # converted into searches.
        # ----------------------------------------------------

        if (
            self.is_anchor_tag(tag)
            and attr == "href"
            and self.is_probably_internal_help_url(
                value
            )
        ):

            fallback_url = (
                self.search_fallback_builder.convert(
                    source,
                    tag,
                    value,
                    "unresolved-internal-anchor",
                )
            )

            if fallback_url != value:

                return fallback_url

        # Record unresolved local links.
        self.unresolved_links.append(
            BrokenLink(
                source=normalize_relpath(
                    source.relative_to(
                        self.source_root
                    )
                ),
                url=value,
                reason="unresolved",
            )
        )

        return value

    def rewrite_html(
        self,
        source: Path,
    ) -> str:

        text = source.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        soup = parse_document(
            text,
            source,
        )

        # ----------------------------------------------------
        # Remove generated header from previous conversion.
        # ----------------------------------------------------

        for tag in soup.select(
            '[data-generated="siemens-help-converter"]'
        ):
            tag.decompose()

        # ----------------------------------------------------
        # Rewrite URL attributes.
        # ----------------------------------------------------

        for tag_name, attributes in URL_ATTRIBUTES.items():

            for tag in soup.find_all(
                tag_name
            ):

                for attr in attributes:

                    if not tag.has_attr(
                        attr
                    ):
                        continue

                    value = tag.get(
                        attr
                    )

                    if not value:
                        continue

                    if attr == "srcset":

                        tag[attr] = (
                            self.rewrite_srcset(
                                source,
                                str(value),
                            )
                        )

                        continue

                    tag[attr] = (
                        self.rewrite_url(
                            source,
                            tag,
                            attr,
                            str(value),
                        )
                    )

        # ----------------------------------------------------
        # Inject navigation.
        # ----------------------------------------------------

        self.inject_navigation(
            soup,
            source,
        )

        # ----------------------------------------------------
        # Inject CSS / JS.
        # ----------------------------------------------------

        self.inject_assets(
            soup,
            source,
        )

        return str(
            soup
        )

    def inject_assets(
        self,
        soup: BeautifulSoup,
        source: Path,
    ):

        output_html = self.output_path(
            source
        )

        search_dir = (
            self.output_root /
            "_search"
        )

        css_path = relative_url(
            output_html,
            search_dir /
            "style.css",
        )

        js_path = relative_url(
            output_html,
            search_dir /
            "app.js",
        )

        head = soup.head

        if head is None:

            if soup.html is None:
                return

            head = soup.new_tag(
                "head"
            )

            soup.html.insert(
                0,
                head,
            )

        if not soup.find(
            "link",
            attrs={
                "data-generated":
                    "siemens-help-converter-css"
            },
        ):

            link = soup.new_tag(
                "link",
                rel="stylesheet",
                href=css_path,
            )

            link[
                "data-generated"
            ] = (
                "siemens-help-converter-css"
            )

            head.append(
                link
            )

        if not soup.find(
            "script",
            attrs={
                "data-generated":
                    "siemens-help-converter-js"
            },
        ):

            script = soup.new_tag(
                "script",
                src=js_path,
                defer=True,
            )

            script[
                "data-generated"
            ] = (
                "siemens-help-converter-js"
            )

            head.append(
                script
            )

    def inject_navigation(
        self,
        soup: BeautifulSoup,
        source: Path,
    ):

        if soup.body is None:
            return

        output_html = self.output_path(
            source
        )

        home_path = relative_url(
            output_html,
            self.output_root /
            "index.html",
        )

        search_path = relative_url(
            output_html,
            self.output_root /
            "search.html",
        )

        nav_html = f"""
<header
    class="shc-global-header"
    data-generated="siemens-help-converter"
>
    <div class="shc-header-inner">

        <div class="shc-brand">
            <a href="{html_lib.escape(home_path)}">
                Documentation Home
            </a>
        </div>

        <form
            class="shc-search-form"
            data-search-form="true"
            action="{html_lib.escape(search_path)}"
            method="get"
        >
            <input
                type="search"
                name="q"
                data-search-input="true"
                placeholder="Search documentation..."
                autocomplete="off"
                spellcheck="false"
            />

            <button type="submit">
                Search
            </button>
        </form>

    </div>
</header>
"""

        header = parse_html_fragment(
            nav_html
        ).find(
            "header"
        )

        soup.body.insert(
            0,
            header,
        )

    def write_all(
        self,
        html_files: list[Path],
    ) -> int:

        count = 0

        for source in html_files:

            destination = self.output_path(
                source
            )

            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            rewritten = self.rewrite_html(
                source
            )

            destination.write_text(
                rewritten,
                encoding="utf-8",
            )

            count += 1

        return count


# ============================================================
# Search Document Builder
# ============================================================

class SearchDocumentBuilder:

    def __init__(
        self,
        source_root: Path,
        manifest: ManifestBuilder,
    ):

        self.source_root = source_root
        self.manifest = manifest

    def extract_search_text(
        self,
        soup: BeautifulSoup,
    ) -> str:

        for tag in soup(
            [
                "script",
                "style",
                "noscript",
                "template",
                "svg",
            ]
        ):
            tag.decompose()

        for tag in soup.select(
            '[data-generated="siemens-help-converter"]'
        ):
            tag.decompose()

        main = soup.find(
            "main"
        )

        if main:

            text = main.get_text(
                " ",
                strip=True,
            )

        else:

            body = (
                soup.body
                or soup
            )

            text = body.get_text(
                " ",
                strip=True,
            )

        return clean_text(
            text
        )

    def create_documents(
        self,
    ) -> list[dict]:

        documents = []

        topics = sorted(
            self.manifest.file_to_topic.values(),
            key=lambda t: t.output.lower(),
        )

        for topic in topics:

            source = (
                self.source_root /
                topic.source
            )

            try:

                text = source.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )

            except Exception as exc:

                print(
                    f"WARNING: cannot read "
                    f"{source}: {exc}"
                )

                continue

            soup = parse_document(
                text,
                source,
            )

            body_text = (
                self.extract_search_text(
                    soup
                )
            )

            if not body_text:
                continue

            documents.append(
                {
                    "id": topic.topic_id,
                    "title": topic.title,
                    "url": topic.output,
                    "text": body_text,
                }
            )

        return documents


# ============================================================
# Generated Search JavaScript
# ============================================================

SEARCH_APP_JS = r"""
(() => {
    "use strict";

    const DEFAULT_PAGE_SIZE = 20;

    let documents = [];
    let loaded = false;

    const $ = (
        selector,
        root = document
    ) =>
        root.querySelector(selector);

    const $$ = (
        selector,
        root = document
    ) =>
        Array.from(
            root.querySelectorAll(selector)
        );

    function normalizeText(value) {

        return (value || "")
            .normalize("NFKC")
            .toLowerCase()
            .replace(/\s+/g, " ")
            .trim();
    }

    function tokenize(value) {

        return normalizeText(value)
            .split(
                /[^a-z0-9_\-\u0080-\uffff]+/i
            )
            .map(
                x => x.trim()
            )
            .filter(Boolean);
    }

    function escapeHtml(value) {

        return String(
            value ?? ""
        )
            .replaceAll(
                "&",
                "&amp;"
            )
            .replaceAll(
                "<",
                "&lt;"
            )
            .replaceAll(
                ">",
                "&gt;"
            )
            .replaceAll(
                '"',
                "&quot;"
            )
            .replaceAll(
                "'",
                "&#039;"
            );
    }

    function escapeRegExp(value) {

        return String(value)
            .replace(
                /[.*+?^${}()|[\]\\]/g,
                "\\$&"
            );
    }

    function makeSnippet(
        text,
        query
    ) {

        const normalizedText =
            normalizeText(text);

        const normalizedQuery =
            normalizeText(query);

        if (!normalizedText) {
            return "";
        }

        let index =
            normalizedText.indexOf(
                normalizedQuery
            );

        if (index < 0) {

            const tokens =
                tokenize(query);

            for (
                const token of tokens
            ) {

                index =
                    normalizedText.indexOf(
                        token
                    );

                if (index >= 0) {
                    break;
                }
            }
        }

        if (index < 0) {
            index = 0;
        }

        const start =
            Math.max(
                0,
                index - 140
            );

        const end =
            Math.min(
                text.length,
                start + 320
            );

        let snippet =
            text.slice(
                start,
                end
            );

        if (start > 0) {
            snippet =
                "..." + snippet;
        }

        if (end < text.length) {
            snippet += "...";
        }

        return snippet;
    }

    function highlight(
        text,
        query
    ) {

        let result =
            escapeHtml(text);

        const tokens =
            tokenize(query)
                .sort(
                    (a, b) =>
                        b.length -
                        a.length
                );

        for (
            const token of tokens
        ) {

            if (token.length < 2) {
                continue;
            }

            const regex =
                new RegExp(
                    "(" +
                    escapeRegExp(token) +
                    ")",
                    "gi"
                );

            result =
                result.replace(
                    regex,
                    "<mark>$1</mark>"
                );
        }

        return result;
    }

    function scoreDocument(
        doc,
        query
    ) {

        const q =
            normalizeText(query);

        if (!q) {
            return 0;
        }

        const title =
            normalizeText(
                doc.title
            );

        const text =
            normalizeText(
                doc.text
            );

        let score = 0;

        if (title.includes(q)) {
            score += 1000;
        }

        if (text.includes(q)) {
            score += 300;
        }

        const tokens =
            tokenize(query);

        for (
            const token of tokens
        ) {

            if (!token) {
                continue;
            }

            if (
                title.includes(token)
            ) {
                score += 100;
            }

            let count = 0;
            let pos = 0;

            while (count < 20) {

                const found =
                    text.indexOf(
                        token,
                        pos
                    );

                if (found < 0) {
                    break;
                }

                count++;

                pos =
                    found +
                    token.length;
            }

            score += Math.min(
                count * 5,
                100
            );
        }

        return score;
    }

    function search(
        query
    ) {

        const q =
            normalizeText(query);

        if (!q) {
            return [];
        }

        return documents
            .map(
                doc => ({
                    doc,
                    score:
                        scoreDocument(
                            doc,
                            q
                        )
                })
            )
            .filter(
                item =>
                    item.score > 0
            )
            .sort(
                (a, b) => {

                    if (
                        b.score !==
                        a.score
                    ) {

                        return (
                            b.score -
                            a.score
                        );
                    }

                    return a.doc.title.localeCompare(
                        b.doc.title
                    );
                }
            );
    }

    function getPageSize() {

        const value =
            Number(
                document.body
                    .dataset
                    .pageSize ||
                DEFAULT_PAGE_SIZE
            );

        if (
            !Number.isFinite(value) ||
            value <= 0
        ) {
            return DEFAULT_PAGE_SIZE;
        }

        return Math.floor(value);
    }

    function getQueryState() {

        const params =
            new URLSearchParams(
                window.location.search
            );

        const q =
            params.get("q") || "";

        let page =
            Number(
                params.get("page") ||
                "1"
            );

        if (
            !Number.isFinite(page) ||
            page < 1
        ) {
            page = 1;
        }

        return {
            q,
            page: Math.floor(page)
        };
    }

    function setQueryState(
        q,
        page = 1
    ) {

        const params =
            new URLSearchParams();

        q =
            String(q || "").trim();

        if (q) {
            params.set(
                "q",
                q
            );
        }

        if (page > 1) {

            params.set(
                "page",
                String(page)
            );
        }

        const queryString =
            params.toString();

        const url =
            window.location.pathname +
            (
                queryString
                    ? "?" + queryString
                    : ""
            );

        window.history.pushState(
            {},
            "",
            url
        );

        render();
    }

    function navigateSearch(
        form
    ) {

        const input =
            form.querySelector(
                '[data-search-input="true"]'
            );

        const q =
            input
                ? input.value.trim()
                : "";

        const action =
            form.getAttribute(
                "action"
            ) ||
            "search.html";

        const method =
            (
                form.getAttribute(
                    "method"
                ) ||
                "get"
            ).toLowerCase();

        /*
         * GET and POST are both supported.
         *
         * For offline static documentation, POST
         * cannot be processed by a static HTML file.
         * Therefore POST is intentionally converted
         * to the same GET URL.
         */

        const url =
            new URL(
                action,
                window.location.href
            );

        if (q) {

            url.searchParams.set(
                "q",
                q
            );

        } else {

            url.searchParams.delete(
                "q"
            );
        }

        url.searchParams.delete(
            "page"
        );

        if (
            window.location.pathname
                .toLowerCase()
                .endsWith(
                    "search.html"
                )
        ) {

            window.history.pushState(
                {},
                "",
                url.pathname +
                (
                    url.search
                    ? url.search
                    : ""
                )
            );

            render();

        } else {

            window.location.href =
                url.toString();
        }
    }

    function wireSearchForms() {

        $$(
            '[data-search-form="true"]'
        ).forEach(
            form => {

                if (
                    form.dataset
                        .shcBound === "true"
                ) {
                    return;
                }

                form.dataset
                    .shcBound = "true";

                form.addEventListener(
                    "submit",
                    event => {

                        event.preventDefault();

                        navigateSearch(
                            form
                        );
                    }
                );
            }
        );
    }

    function renderPagination(
        container,
        q,
        page,
        totalPages
    ) {

        container.innerHTML = "";

        if (
            totalPages <= 1
        ) {
            return;
        }

        const nav =
            document.createElement(
                "nav"
            );

        nav.className =
            "shc-pagination";

        nav.setAttribute(
            "aria-label",
            "Search result pages"
        );

        function addButton(
            label,
            targetPage,
            disabled = false
        ) {

            const button =
                document.createElement(
                    "button"
                );

            button.type =
                "button";

            button.textContent =
                label;

            button.disabled =
                disabled;

            button.addEventListener(
                "click",
                () => {

                    if (!disabled) {

                        setQueryState(
                            q,
                            targetPage
                        );
                    }
                }
            );

            nav.appendChild(
                button
            );
        }

        addButton(
            "Previous",
            page - 1,
            page <= 1
        );

        let start =
            Math.max(
                1,
                page - 3
            );

        let end =
            Math.min(
                totalPages,
                page + 3
            );

        if (start > 1) {

            addButton(
                "1",
                1
            );

            if (start > 2) {

                const span =
                    document.createElement(
                        "span"
                    );

                span.textContent =
                    "...";

                span.className =
                    "shc-page-gap";

                nav.appendChild(
                    span
                );
            }
        }

        for (
            let p = start;
            p <= end;
            p++
        ) {

            const button =
                document.createElement(
                    "button"
                );

            button.type =
                "button";

            button.textContent =
                String(p);

            if (p === page) {

                button.classList.add(
                    "active"
                );

                button.setAttribute(
                    "aria-current",
                    "page"
                );
            }

            button.addEventListener(
                "click",
                () => {

                    setQueryState(
                        q,
                        p
                    );
                }
            );

            nav.appendChild(
                button
            );
        }

        if (
            end < totalPages
        ) {

            if (
                end <
                totalPages - 1
            ) {

                const span =
                    document.createElement(
                        "span"
                    );

                span.textContent =
                    "...";

                span.className =
                    "shc-page-gap";

                nav.appendChild(
                    span
                );
            }

            addButton(
                String(totalPages),
                totalPages
            );
        }

        addButton(
            "Next",
            page + 1,
            page >= totalPages
        );

        container.appendChild(
            nav
        );
    }

    function renderResults(
        container,
        results,
        query,
        page
    ) {

        container.innerHTML = "";

        const pageSize =
            getPageSize();

        const total =
            results.length;

        const totalPages =
            Math.max(
                1,
                Math.ceil(
                    total /
                    pageSize
                )
            );

        if (
            page > totalPages
        ) {
            page = totalPages;
        }

        const start =
            (page - 1) *
            pageSize;

        const end =
            Math.min(
                start + pageSize,
                total
            );

        const current =
            results.slice(
                start,
                end
            );

        const summary =
            document.createElement(
                "div"
            );

        summary.className =
            "shc-result-summary";

        if (!query) {

            summary.textContent =
                "Enter a keyword to search the documentation.";

        } else if (
            total === 0
        ) {

            summary.innerHTML =
                "No results found for <strong>" +
                escapeHtml(query) +
                "</strong>.";

        } else {

            summary.innerHTML =
                "Found <strong>" +
                total.toLocaleString() +
                "</strong> results. " +
                "Showing <strong>" +
                (start + 1) +
                "</strong>–<strong>" +
                end +
                "</strong>.";
        }

        container.appendChild(
            summary
        );

        if (
            current.length > 0
        ) {

            const list =
                document.createElement(
                    "ol"
                );

            list.className =
                "shc-results";

            current.forEach(
                item => {

                    const li =
                        document.createElement(
                            "li"
                        );

                    li.className =
                        "shc-result";

                    const title =
                        document.createElement(
                            "a"
                        );

                    title.href =
                        item.doc.url;

                    title.innerHTML =
                        highlight(
                            item.doc.title,
                            query
                        );

                    title.className =
                        "shc-result-title";

                    const snippet =
                        document.createElement(
                            "div"
                        );

                    snippet.className =
                        "shc-result-snippet";

                    const rawSnippet =
                        makeSnippet(
                            item.doc.text,
                            query
                        );

                    snippet.innerHTML =
                        highlight(
                            rawSnippet,
                            query
                        );

                    const url =
                        document.createElement(
                            "div"
                        );

                    url.className =
                        "shc-result-url";

                    url.textContent =
                        item.doc.url;

                    li.appendChild(
                        title
                    );

                    li.appendChild(
                        snippet
                    );

                    li.appendChild(
                        url
                    );

                    list.appendChild(
                        li
                    );
                }
            );

            container.appendChild(
                list
            );
        }

        const pagination =
            document.createElement(
                "div"
            );

        pagination.className =
            "shc-pagination-container";

        container.appendChild(
            pagination
        );

        renderPagination(
            pagination,
            query,
            page,
            totalPages
        );
    }

    async function loadDocuments() {

        if (loaded) {
            return;
        }

        /*
         * app.js is stored at:
         *
         *     _search/app.js
         *
         * therefore:
         *
         *     ../search-documents.json
         *
         * points to the output root.
         */

        const script =
            document.currentScript;

        let indexUrl;

        if (script) {

            indexUrl =
                new URL(
                    "../search-documents.json",
                    script.src
                );

        } else {

            indexUrl =
                new URL(
                    "../search-documents.json",
                    window.location.href
                );
        }

        const response =
            await fetch(
                indexUrl.href,
                {
                    cache: "no-cache"
                }
            );

        if (!response.ok) {

            throw new Error(
                "Cannot load search-documents.json"
            );
        }

        documents =
            await response.json();

        loaded = true;
    }

    function setInputValue(
        q
    ) {

        $$(
            '[data-search-input="true"]'
        ).forEach(
            input => {

                input.value = q;
            }
        );
    }

    async function render() {

        wireSearchForms();

        const searchContainer =
            $(
                '[data-search-results="true"]'
            );

        if (!searchContainer) {
            return;
        }

        try {

            await loadDocuments();

            const state =
                getQueryState();

            setInputValue(
                state.q
            );

            const results =
                search(
                    state.q
                );

            renderResults(
                searchContainer,
                results,
                state.q,
                state.page
            );

            document.title =
                state.q
                    ? (
                        "Search: " +
                        state.q +
                        " - Documentation"
                    )
                    : "Documentation Search";

        } catch (error) {

            console.error(
                error
            );

            searchContainer.innerHTML =
                '<div class="shc-error">' +
                'Unable to load the search index.' +
                '</div>';
        }
    }

    window.addEventListener(
        "popstate",
        render
    );

    document.addEventListener(
        "DOMContentLoaded",
        render
    );

})();
"""


# ============================================================
# Generated CSS
# ============================================================

SEARCH_STYLE_CSS = r"""
:root {
    --shc-blue: #0066a1;
    --shc-blue-dark: #004b78;
    --shc-border: #d5dbe0;
    --shc-bg: #f5f7f9;
    --shc-text: #20262b;
    --shc-muted: #68737d;
    --shc-mark: #fff19a;
}

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    color: var(--shc-text);
}

.shc-global-header {
    width: 100%;
    background: #ffffff;
    border-bottom: 1px solid var(--shc-border);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
    position: relative;
    z-index: 9999;
}

.shc-header-inner {
    max-width: 1400px;
    margin: 0 auto;
    padding: 10px 18px;
    display: flex;
    gap: 20px;
    align-items: center;
}

.shc-brand {
    white-space: nowrap;
    font-weight: 600;
}

.shc-brand a {
    color: var(--shc-blue);
    text-decoration: none;
}

.shc-brand a:hover {
    text-decoration: underline;
}

.shc-search-form {
    display: flex;
    flex: 1;
    max-width: 900px;
    gap: 8px;
}

.shc-search-form input[type="search"] {
    flex: 1;
    min-width: 100px;
    height: 38px;
    padding: 7px 11px;
    border: 1px solid #aeb8c0;
    border-radius: 4px;
    font-size: 15px;
    background: #ffffff;
    color: #111111;
}

.shc-search-form input[type="search"]:focus {
    outline: none;
    border-color: var(--shc-blue);
    box-shadow: 0 0 0 2px rgba(0, 102, 161, 0.15);
}

.shc-search-form button {
    height: 38px;
    padding: 0 18px;
    border: 1px solid var(--shc-blue);
    border-radius: 4px;
    background: var(--shc-blue);
    color: white;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
}

.shc-search-form button:hover {
    background: var(--shc-blue-dark);
}

.shc-search-page {
    max-width: 1200px;
    margin: 0 auto;
    padding: 25px 20px 60px;
}

.shc-search-page h1 {
    margin: 0 0 20px;
}

.shc-result-summary {
    margin: 18px 0;
    color: var(--shc-muted);
}

.shc-results {
    padding-left: 32px;
}

.shc-result {
    margin-bottom: 24px;
    padding-bottom: 18px;
    border-bottom: 1px solid #e4e8eb;
}

.shc-result-title {
    color: var(--shc-blue);
    font-size: 18px;
    font-weight: 600;
    text-decoration: none;
}

.shc-result-title:hover {
    text-decoration: underline;
}

.shc-result-snippet {
    margin-top: 7px;
    line-height: 1.55;
    color: #3c454c;
}

.shc-result-snippet mark {
    background: var(--shc-mark);
    color: inherit;
    padding: 0 2px;
}

.shc-result-url {
    margin-top: 7px;
    color: var(--shc-muted);
    font-size: 12px;
    word-break: break-all;
}

.shc-pagination-container {
    margin-top: 25px;
}

.shc-pagination {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
}

.shc-pagination button {
    min-width: 38px;
    height: 36px;
    padding: 0 10px;
    border: 1px solid var(--shc-border);
    background: white;
    color: #333;
    border-radius: 4px;
    cursor: pointer;
}

.shc-pagination button:hover:not(:disabled) {
    border-color: var(--shc-blue);
    color: var(--shc-blue);
}

.shc-pagination button.active {
    background: var(--shc-blue);
    border-color: var(--shc-blue);
    color: white;
    font-weight: 600;
}

.shc-pagination button:disabled {
    opacity: 0.45;
    cursor: default;
}

.shc-page-gap {
    padding: 0 3px;
    color: var(--shc-muted);
}

.shc-home-button {
    display: inline-block;
    margin-top: 30px;
    padding: 8px 14px;
    border: 1px solid var(--shc-border);
    border-radius: 4px;
    text-decoration: none;
    color: var(--shc-blue);
    background: #fff;
}

.shc-home-button:hover {
    border-color: var(--shc-blue);
}

.shc-error {
    padding: 16px;
    border: 1px solid #e0a0a0;
    background: #fff4f4;
    color: #8a2020;
}

@media (max-width: 700px) {

    .shc-header-inner {
        flex-direction: column;
        align-items: stretch;
        gap: 9px;
    }

    .shc-search-form {
        max-width: none;
    }

    .shc-search-page {
        padding-left: 12px;
        padding-right: 12px;
    }
}
"""


# ============================================================
# Search HTML
# ============================================================

SEARCH_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>Documentation Search</title>

    <link
        rel="stylesheet"
        href="_search/style.css"
    >

    <script
        src="_search/app.js"
        defer
    ></script>
</head>

<body data-page-size="20">

<header
    class="shc-global-header"
    data-generated="siemens-help-converter"
>
    <div class="shc-header-inner">

        <div class="shc-brand">
            <a href="index.html">
                Documentation Home
            </a>
        </div>

        <form
            class="shc-search-form"
            data-search-form="true"
            action="search.html"
            method="get"
        >
            <input
                type="search"
                name="q"
                data-search-input="true"
                placeholder="Search documentation..."
                autocomplete="off"
                spellcheck="false"
            />

            <button type="submit">
                Search
            </button>
        </form>

    </div>
</header>

<main class="shc-search-page">

    <h1>Documentation Search</h1>

    <div data-search-results="true">
        Loading search index...
    </div>

    <a
        href="index.html"
        class="shc-home-button"
    >
        Documentation Home
    </a>

</main>

</body>
</html>
"""


# ============================================================
# Index HTML
# ============================================================

INDEX_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>Documentation</title>

    <link
        rel="stylesheet"
        href="_search/style.css"
    >

    <script
        src="_search/app.js"
        defer
    ></script>
</head>

<body data-page-size="20">

<header
    class="shc-global-header"
    data-generated="siemens-help-converter"
>
    <div class="shc-header-inner">

        <div class="shc-brand">
            <a href="index.html">
                Documentation Home
            </a>
        </div>

        <form
            class="shc-search-form"
            data-search-form="true"
            action="search.html"
            method="get"
        >
            <input
                type="search"
                name="q"
                data-search-input="true"
                placeholder="Search documentation..."
                autocomplete="off"
                spellcheck="false"
            />

            <button type="submit">
                Search
            </button>
        </form>

    </div>
</header>

<main class="shc-search-page">

    <h1>Documentation</h1>

    <p>
        Use the search field above to search the
        complete documentation.
    </p>

    <p>
        <a
            href="search.html"
            class="shc-home-button"
        >
            Open Documentation Search
        </a>
    </p>

</main>

</body>
</html>
"""


# ============================================================
# Output Builder
# ============================================================

class OutputBuilder:

    def __init__(
        self,
        source_root: Path,
        output_root: Path,
        page_size: int,
    ):

        self.source_root = source_root
        self.output_root = output_root
        self.page_size = page_size

    def clean_output(self):

        if not self.output_root.exists():
            return

        for child in self.output_root.iterdir():

            if child.is_dir():

                shutil.rmtree(
                    child
                )

            else:

                child.unlink()

    def copy_non_html_files(
        self,
        files: list[Path],
    ) -> int:

        count = 0

        for source in files:

            if is_html(source):
                continue

            relative = source.relative_to(
                self.source_root
            )

            destination = (
                self.output_root /
                relative
            )

            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copy2(
                source,
                destination,
            )

            count += 1

        return count

    def write_search_assets(
        self,
    ):

        search_dir = (
            self.output_root /
            "_search"
        )

        search_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        (
            search_dir /
            "app.js"
        ).write_text(
            SEARCH_APP_JS,
            encoding="utf-8",
        )

        (
            search_dir /
            "style.css"
        ).write_text(
            SEARCH_STYLE_CSS,
            encoding="utf-8",
        )

    def write_search_html(
        self,
    ):

        content = (
            SEARCH_HTML_TEMPLATE
            .replace(
                'data-page-size="20"',
                f'data-page-size="{self.page_size}"',
            )
        )

        (
            self.output_root /
            "search.html"
        ).write_text(
            content,
            encoding="utf-8",
        )

    def write_index_html(
        self,
    ):

        content = (
            INDEX_HTML_TEMPLATE
            .replace(
                'data-page-size="20"',
                f'data-page-size="{self.page_size}"',
            )
        )

        (
            self.output_root /
            "index.html"
        ).write_text(
            content,
            encoding="utf-8",
        )


# ============================================================
# Link Validator
# ============================================================

class LinkValidator:

    def __init__(
        self,
        output_root: Path,
    ):

        self.output_root = output_root

        self.broken: list[
            BrokenLink
        ] = []

    def validate_url(
        self,
        html_file: Path,
        url: str,
    ):

        if not url:
            return

        if url.startswith("#"):

            self.validate_fragment(
                html_file,
                url[1:],
            )

            return

        if is_external_url(url):
            return

        parts = urlsplit(
            url
        )

        path = unquote(
            parts.path
        )

        fragment = parts.fragment

        if not path:

            if fragment:

                self.validate_fragment(
                    html_file,
                    fragment,
                )

            return

        target = (
            html_file.parent /
            path
        ).resolve()

        try:

            target.relative_to(
                self.output_root.resolve()
            )

        except ValueError:

            self.broken.append(
                BrokenLink(
                    source=normalize_relpath(
                        html_file.relative_to(
                            self.output_root
                        )
                    ),
                    url=url,
                    reason="outside-output",
                )
            )

            return

        if not target.exists():

            self.broken.append(
                BrokenLink(
                    source=normalize_relpath(
                        html_file.relative_to(
                            self.output_root
                        )
                    ),
                    url=url,
                    reason="file-not-found",
                )
            )

            return

        if fragment:

            self.validate_fragment(
                target,
                fragment,
            )

    def validate_fragment(
        self,
        html_file: Path,
        fragment: str,
    ):

        if not fragment:
            return

        if not html_file.is_file():
            return

        try:

            text = html_file.read_text(
                encoding="utf-8",
                errors="ignore",
            )

            soup = parse_document(
                text,
                html_file,
            )

        except Exception:
            return

        fragment = unquote(
            fragment
        )

        found = soup.find(
            id=fragment
        )

        if not found:

            found = soup.find(
                attrs={
                    "name": fragment
                }
            )

        if not found:

            self.broken.append(
                BrokenLink(
                    source=normalize_relpath(
                        html_file.relative_to(
                            self.output_root
                        )
                    ),
                    url="#" + fragment,
                    reason="fragment-not-found",
                )
            )

    def validate(
        self,
    ):

        html_files = list(
            self.output_root.rglob(
                "*.html"
            )
        )

        for html_file in html_files:

            try:

                text = html_file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )

                soup = parse_document(
                    text,
                    html_file,
                )

            except Exception:
                continue

            for tag_name, attributes in URL_ATTRIBUTES.items():

                for tag in soup.find_all(
                    tag_name
                ):

                    for attr in attributes:

                        if not tag.has_attr(
                            attr
                        ):
                            continue

                        value = tag.get(
                            attr
                        )

                        if not value:
                            continue

                        if attr == "srcset":

                            for url, _ in split_srcset(
                                str(value)
                            ):

                                self.validate_url(
                                    html_file,
                                    url,
                                )

                        else:

                            self.validate_url(
                                html_file,
                                str(value),
                            )

        return self.broken


# ============================================================
# Manifest JSON
# ============================================================

def create_manifest_json(
    output_root: Path,
    manifest: ManifestBuilder,
    unresolved_links: list[BrokenLink],
    search_fallbacks: list[SearchFallback],
    page_size: int,
):

    topics = []

    for topic in sorted(
        manifest.file_to_topic.values(),
        key=lambda t: t.output.lower(),
    ):

        topics.append(
            asdict(topic)
        )

    data = {
        "version": 2,
        "home": "index.html",
        "search": "search.html",
        "search_method": "GET",
        "page_size": page_size,
        "topics": topics,
        "unresolved_links": [
            asdict(x)
            for x in unresolved_links
        ],
        "search_fallback_links": [
            asdict(x)
            for x in search_fallbacks
        ],
    }

    safe_json_dump(
        data,
        output_root /
        "manifest.json",
    )


# ============================================================
# Report
# ============================================================

def write_validation_report(
    output_root: Path,
    broken: list[BrokenLink],
    unresolved: list[BrokenLink],
    search_fallbacks: list[SearchFallback],
):

    report = {
        "broken_links": [
            asdict(x)
            for x in broken
        ],
        "unresolved_during_rewrite": [
            asdict(x)
            for x in unresolved
        ],
        "search_fallback_links": [
            asdict(x)
            for x in search_fallbacks
        ],
        "broken_count": len(
            broken
        ),
        "unresolved_count": len(
            unresolved
        ),
        "search_fallback_count": len(
            search_fallbacks
        ),
    }

    safe_json_dump(
        report,
        output_root /
        "validation-report.json",
    )


# ============================================================
# CLI
# ============================================================

def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "Convert Siemens Help documentation "
            "into standalone offline HTML + JavaScript search."
        )
    )

    parser.add_argument(
        "source",
        type=Path,
        help=(
            "Source Siemens Help documentation directory."
        ),
    )

    parser.add_argument(
        "output",
        type=Path,
        help=(
            "Output directory."
        ),
    )

    parser.add_argument(
        "--clean",
        action="store_true",
        help=(
            "Delete output directory contents "
            "before build."
        ),
    )

    parser.add_argument(
        "--page-size",
        type=int,
        default=20,
        help=(
            "Search result page size. "
            "Default: 20."
        ),
    )

    parser.add_argument(
        "--base-url",
        default="",
        help=(
            "Original Siemens Help Server base URL. "
            "Used for documentation analysis."
        ),
    )

    return parser.parse_args()


# ============================================================
# Main Build
# ============================================================

def main():

    args = parse_args()

    source_root = (
        args.source.resolve()
    )

    output_root = (
        args.output.resolve()
    )

    if not source_root.exists():

        print(
            f"ERROR: source does not exist: "
            f"{source_root}"
        )

        return 1

    if not source_root.is_dir():

        print(
            f"ERROR: source is not a directory: "
            f"{source_root}"
        )

        return 1

    if source_root == output_root:

        print(
            "ERROR: source and output directories "
            "must be different."
        )

        return 1

    if args.page_size <= 0:

        print(
            "ERROR: page size must be > 0."
        )

        return 1

    print()

    print(
        "=" * 70
    )

    print(
        " Siemens Help Documentation Builder"
    )

    print(
        "=" * 70
    )

    print()

    print(
        f"Source : {source_root}"
    )

    print(
        f"Output : {output_root}"
    )

    print(
        f"Page   : {args.page_size}"
    )

    print()

    # --------------------------------------------------------
    # Output
    # --------------------------------------------------------

    output_builder = OutputBuilder(
        source_root,
        output_root,
        args.page_size,
    )

    if args.clean:

        print(
            "[1/10] Cleaning output..."
        )

        if output_root.exists():

            output_builder.clean_output()

    else:

        print(
            "[1/10] Preparing output..."
        )

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # Scan
    # --------------------------------------------------------

    print(
        "[2/10] Scanning documentation..."
    )

    scanner = DocumentationScanner(
        source_root
    )

    files = scanner.scan()

    html_files = [
        p
        for p in files
        if is_html(p)
    ]

    print(
        f"      Files       : "
        f"{len(files):,}"
    )

    print(
        f"      HTML topics : "
        f"{len(html_files):,}"
    )

    # --------------------------------------------------------
    # Manifest
    # --------------------------------------------------------

    print(
        "[3/10] Building topic manifest..."
    )

    manifest = ManifestBuilder(
        source_root
    )

    manifest.build(
        files
    )

    print(
        f"      Topics : "
        f"{len(manifest.file_to_topic):,}"
    )

    print(
        f"      Anchors: "
        f"{len(manifest.anchor_to_topic):,}"
    )

    # --------------------------------------------------------
    # Copy assets
    # --------------------------------------------------------

    print(
        "[4/10] Copying non-HTML files..."
    )

    copied = (
        output_builder.copy_non_html_files(
            files
        )
    )

    print(
        f"      Copied: "
        f"{copied:,}"
    )

    # --------------------------------------------------------
    # Resolver
    # --------------------------------------------------------

    print(
        "[5/10] Rewriting HTML links..."
    )

    resolver = TopicResolver(
        source_root=source_root,
        output_root=output_root,
        manifest=manifest,
        base_url=args.base_url,
    )

    rewriter = HTMLRewriter(
        source_root=source_root,
        output_root=output_root,
        resolver=resolver,
        page_size=args.page_size,
    )

    rewritten_count = (
        rewriter.write_all(
            html_files
        )
    )

    print(
        f"      Rewritten HTML : "
        f"{rewritten_count:,}"
    )

    print(
        f"      Unresolved URLs: "
        f"{len(rewriter.unresolved_links):,}"
    )

    print(
        f"      Search fallback links: "
        f"{len(rewriter.search_fallback_builder.fallbacks):,}"
    )

    # --------------------------------------------------------
    # Search index
    # --------------------------------------------------------

    print(
        "[6/10] Building search documents..."
    )

    search_builder = (
        SearchDocumentBuilder(
            source_root,
            manifest,
        )
    )

    search_documents = (
        search_builder.create_documents()
    )

    safe_json_dump(
        search_documents,
        output_root /
        "search-documents.json",
    )

    print(
        f"      Search documents: "
        f"{len(search_documents):,}"
    )

    # --------------------------------------------------------
    # Search UI
    # --------------------------------------------------------

    print(
        "[7/10] Generating search UI..."
    )

    output_builder.write_search_assets()

    output_builder.write_search_html()

    output_builder.write_index_html()

    # --------------------------------------------------------
    # Manifest
    # --------------------------------------------------------

    print(
        "[8/10] Writing manifest..."
    )

    create_manifest_json(
        output_root,
        manifest,
        rewriter.unresolved_links,
        rewriter.search_fallback_builder.fallbacks,
        args.page_size,
    )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    print(
        "[9/10] Validating links..."
    )

    validator = LinkValidator(
        output_root
    )

    broken = validator.validate()

    write_validation_report(
        output_root,
        broken,
        rewriter.unresolved_links,
        rewriter.search_fallback_builder.fallbacks,
    )

    # --------------------------------------------------------
    # Final report
    # --------------------------------------------------------

    print(
        "[10/10] Finalizing..."
    )

    print()

    print(
        "=" * 70
    )

    print(
        " Build Complete"
    )

    print(
        "=" * 70
    )

    print()

    print(
        f"HTML topics              : "
        f"{len(html_files):,}"
    )

    print(
        f"Search documents         : "
        f"{len(search_documents):,}"
    )

    print(
        f"Non-HTML files           : "
        f"{copied:,}"
    )

    print(
        f"Rewritten HTML           : "
        f"{rewritten_count:,}"
    )

    print(
        f"Unresolved URLs          : "
        f"{len(rewriter.unresolved_links):,}"
    )

    print(
        f"Search fallback links    : "
        f"{len(rewriter.search_fallback_builder.fallbacks):,}"
    )

    print(
        f"Validation broken        : "
        f"{len(broken):,}"
    )

    print()

    print(
        "Documentation home:"
    )

    print(
        f"    {output_root / 'index.html'}"
    )

    print()

    print(
        "Search:"
    )

    print(
        f"    {output_root / 'search.html'}"
    )

    print()

    print(
        "Search URL example:"
    )

    print(
        "    search.html?q=PLC"
    )

    print()

    print(
        "Search page example:"
    )

    print(
        "    search.html?q=PLC&page=2"
    )

    print()

    if (
        rewriter.search_fallback_builder.fallbacks
    ):

        print(
            "INFO:"
        )

        print(
            f"{len(rewriter.search_fallback_builder.fallbacks):,} "
            "unresolved internal anchor links "
            "were converted to GET searches."
        )

        print(
            "See:"
        )

        print(
            f"    {output_root / 'validation-report.json'}"
        )

        print()

    if rewriter.unresolved_links:

        print(
            "WARNING:"
        )

        print(
            "Some local URLs could not be resolved."
        )

        print(
            "See:"
        )

        print(
            f"    {output_root / 'validation-report.json'}"
        )

        print()

    if broken:

        print(
            "WARNING:"
        )

        print(
            f"{len(broken):,} broken local links/fragments "
            "were detected."
        )

        print(
            f"See: "
            f"{output_root / 'validation-report.json'}"
        )

        print()

    print(
        "The generated documentation can now be opened "
        "without JDK / Help Server."
    )

    print()

    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
