# pip install pymupdf
from pathlib import Path
import pymupdf

import html
import re
import shutil
import sys
import time
import zipfile
import hashlib


# ============================================================
# 基本設定
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# PDF 檔案放在 Python 程式同一目錄
PDF_DIR = BASE_DIR

# EPUB 輸出目錄
OUTPUT_DIR = BASE_DIR / "epub"

# 是否保留 PDF 中的圖片
KEEP_IMAGES = True

# ============================================================
#
# 將 pdf 轉為 epub 過程不嵌入中文字型
#
# 在 Kindle 使用內建的中文字型。
#
# ============================================================

EMBED_FONT = False

# ============================================================
# HTML escape
# ============================================================

def html_escape(text):

    if not text:
        return ""

    return html.escape(
        str(text),
        quote=False
    )


def xml_escape(text):

    if not text:
        return ""

    return html.escape(
        str(text),
        quote=True
    )


# ============================================================
# 判斷中文
# ============================================================

def contains_chinese(text):

    if not text:
        return False

    for ch in text:

        code = ord(ch)

        if 0x3400 <= code <= 0x4DBF:
            return True

        if 0x4E00 <= code <= 0x9FFF:
            return True

        if 0xF900 <= code <= 0xFAFF:
            return True

    return False


# ============================================================
# 清理文字
# ============================================================

def clean_text(text):

    if not text:
        return ""

    text = text.replace(
        "\r",
        ""
    )

    # 移除控制字元
    text = re.sub(
        r"[\x00-\x08\x0b\x0c\x0e-\x1f]",
        "",
        text
    )

    # 保留換行
    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    # 過多空白行
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text
    )

    return text.strip()


# ============================================================
# 取得文字 blocks
# ============================================================

def get_text_blocks(page):

    blocks = []

    try:

        data = page.get_text(
            "dict",
            flags=11
        )

    except Exception as e:

        print(
            f"文字讀取失敗：{e}"
        )

        return blocks

    for block in data.get(
        "blocks",
        []
    ):

        if "lines" not in block:
            continue

        lines = []

        font_sizes = []

        for line in block.get(
            "lines",
            []
        ):

            line_text = ""

            for span in line.get(
                "spans",
                []
            ):

                text = span.get(
                    "text",
                    ""
                )

                if not text:
                    continue

                line_text += text

                try:

                    font_sizes.append(
                        float(
                            span.get(
                                "size",
                                10
                            )
                        )
                    )

                except Exception:
                    pass

            if line_text.strip():

                lines.append(
                    line_text.rstrip()
                )

        if not lines:
            continue

        text = "\n".join(
            lines
        )

        text = clean_text(
            text
        )

        if not text:
            continue

        bbox = block.get(
            "bbox"
        )

        if not bbox:
            continue

        rect = pymupdf.Rect(
            bbox
        )

        if font_sizes:

            average_size = (
                sum(font_sizes)
                /
                len(font_sizes)
            )

        else:

            average_size = 10.0

        blocks.append(
            {
                "text": text,
                "rect": rect,
                "size": average_size
            }
        )

    # --------------------------------------------------------
    # 依照閱讀順序：
    # 上 → 下
    # 左 → 右
    # --------------------------------------------------------

    blocks.sort(
        key=lambda item: (
            round(
                item["rect"].y0,
                1
            ),
            round(
                item["rect"].x0,
                1
            )
        )
    )

    return blocks


# ============================================================
# 判斷是否可能是標題
# ============================================================

def looks_like_heading(
    text,
    font_size,
    page_height
):

    text = text.strip()

    if not text:
        return False

    if len(text) < 2:
        return False

    if len(text) > 80:
        return False

    # 明顯大字
    if font_size >= 18:
        return True

    # 相對頁面高度
    if page_height > 0:

        ratio = (
            font_size /
            page_height
        )

        if ratio > 0.018:
            return True

    return False


# ============================================================
# 抽取圖片
# ============================================================

def extract_images(
    page,
    document,
    image_dir,
    page_number
):

    results = []

    if not KEEP_IMAGES:
        return results

    try:

        image_list = page.get_images(
            full=True
        )

    except Exception:

        return results

    image_number = 0

    for image in image_list:

        if not image:
            continue

        xref = image[0]

        try:

            info = (
                document.extract_image(
                    xref
                )
            )

            if not info:
                continue

            image_data = info.get(
                "image"
            )

            extension = info.get(
                "ext",
                "png"
            ).lower()

            if not image_data:
                continue

            # ------------------------------------------------
            # 不重新壓縮圖片。
            #
            # PDF 原本是 JPEG，就直接保留 JPEG。
            # PDF 原本是 PNG，就直接保留 PNG。
            #
            # 這樣不會增加額外圖片品質損失。
            # ------------------------------------------------

            image_number += 1

            filename = (
                f"p{page_number:05d}_"
                f"i{image_number:03d}."
                f"{extension}"
            )

            image_path = (
                image_dir /
                filename
            )

            image_path.write_bytes(
                image_data
            )

            rects = page.get_image_rects(
                xref
            )

            for rect in rects:

                results.append(
                    {
                        "path": image_path,
                        "rect": rect
                    }
                )

        except Exception as e:

            print(
                f"圖片 {xref} "
                f"處理失敗：{e}"
            )

    return results


# ============================================================
# 取得圖片 MIME
# ============================================================

def get_media_type(
    extension
):

    extension = extension.lower()

    mapping = {

        ".jpg":
            "image/jpeg",

        ".jpeg":
            "image/jpeg",

        ".png":
            "image/png",

        ".gif":
            "image/gif",

        ".webp":
            "image/webp",

        ".svg":
            "image/svg+xml"

    }

    return mapping.get(
        extension,
        "application/octet-stream"
    )


# ============================================================
# 將 block 轉 XHTML
# ============================================================

def block_to_xhtml(
    block,
    page_height
):

    text = block["text"]

    size = block["size"]

    lines = text.split(
        "\n"
    )

    escaped_lines = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        escaped_lines.append(
            html_escape(line)
        )

    if not escaped_lines:
        return ""

    content = (
        "<br/>".join(
            escaped_lines
        )
    )

    # --------------------------------------------------------
    # 標題
    # --------------------------------------------------------

    if looks_like_heading(
        text,
        size,
        page_height
    ):

        if size >= 22:

            return (
                '<h2 class="heading">'
                + content
                + "</h2>"
            )

        return (
            '<h3 class="heading">'
            + content
            + "</h3>"
        )

    # --------------------------------------------------------
    # 正文
    # --------------------------------------------------------

    return (
        '<p class="paragraph">'
        + content
        + "</p>"
    )


# ============================================================
# CSS
#
# 注意：
#
# 沒有 @font-face
#
# 因為不嵌入字型。
# ============================================================

def create_css():

    return """@charset "UTF-8";

html {
    margin: 0;
    padding: 0;
}

body {
    margin: 0;
    padding: 0;

    font-family:
        serif;

    font-size: 1em;

    line-height: 1.65;

    text-align: left;

    widows: 2;
    orphans: 2;
}

.paragraph {
    margin-top: 0;
    margin-bottom: 0.75em;

    text-indent: 2em;

    line-height: 1.65;
}

.heading {
    margin-top: 1.4em;
    margin-bottom: 0.7em;

    font-weight: bold;

    line-height: 1.35;

    page-break-after: avoid;
}

h2.heading {
    font-size: 1.5em;
}

h3.heading {
    font-size: 1.25em;
}

.image-container {
    text-align: center;

    margin-top: 1em;
    margin-bottom: 1em;

    page-break-inside: avoid;
}

.pdf-image {
    max-width: 100%;
    height: auto;
}

img {
    max-width: 100%;
    height: auto;
}
"""


# ============================================================
# 建立 XHTML
# ============================================================

def create_xhtml(
    title,
    page_number,
    blocks,
    images,
    page_height
):

    parts = []

    parts.append(
        '<?xml version="1.0" '
        'encoding="utf-8"?>'
    )

    parts.append(
        '<!DOCTYPE html>'
    )

    parts.append(
        '<html '
        'xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops" '
        'lang="zh-TW" '
        'xml:lang="zh-TW">'
    )

    parts.append(
        "<head>"
    )

    parts.append(
        '<meta charset="utf-8"/>'
    )

    parts.append(
        "<title>"
        + xml_escape(
            f"{title} - 第 {page_number} 頁"
        )
        + "</title>"
    )

    parts.append(
        '<link rel="stylesheet" '
        'type="text/css" '
        'href="../Styles/style.css"/>'
    )

    parts.append(
        "</head>"
    )

    parts.append(
        "<body>"
    )

    # --------------------------------------------------------
    # 文字
    # --------------------------------------------------------

    for block in blocks:

        content = block_to_xhtml(
            block,
            page_height
        )

        if content:

            parts.append(
                content
            )

    # --------------------------------------------------------
    # 圖片
    # --------------------------------------------------------

    images.sort(
        key=lambda item: (
            round(
                item["rect"].y0,
                1
            ),
            round(
                item["rect"].x0,
                1
            )
        )
    )

    for image in images:

        filename = image[
            "path"
        ].name

        parts.append(
            '<div class="image-container">'
            '<img '
            f'src="../Images/'
            f'{xml_escape(filename)}" '
            'class="pdf-image" '
            'alt="PDF image"/>'
            '</div>'
        )

    # --------------------------------------------------------
    # 絕對不要建立空 XHTML
    # --------------------------------------------------------

    if not blocks and not images:

        parts.append(
            "<p>"
            f"第 {page_number} 頁"
            "</p>"
        )

    parts.append(
        "</body>"
    )

    parts.append(
        "</html>"
    )

    return "\n".join(
        parts
    )


# ============================================================
# OPF
# ============================================================

def create_opf(
    title,
    identifier,
    chapter_count,
    image_files
):

    manifest = []

    # NCX
    manifest.append(
        '<item '
        'id="ncx" '
        'href="toc.ncx" '
        'media-type="application/x-dtbncx+xml"/>'
    )

    # EPUB Navigation
    manifest.append(
        '<item '
        'id="nav" '
        'href="nav.xhtml" '
        'media-type="application/xhtml+xml" '
        'properties="nav"/>'
    )

    # CSS
    manifest.append(
        '<item '
        'id="css" '
        'href="Styles/style.css" '
        'media-type="text/css"/>'
    )

    # XHTML
    for page_number in range(
        1,
        chapter_count + 1
    ):

        manifest.append(
            '<item '
            f'id="page{page_number}" '
            f'href="Text/page_{page_number:05d}.xhtml" '
            'media-type="application/xhtml+xml"/>'
        )

    # Images
    for index, image in enumerate(
        image_files,
        start=1
    ):

        manifest.append(
            '<item '
            f'id="image{index}" '
            f'href="Images/'
            f'{xml_escape(image["name"])}" '
            f'media-type="{image["media_type"]}"/>'
        )

    # Spine
    spine = []

    for page_number in range(
        1,
        chapter_count + 1
    ):

        spine.append(
            f'<itemref idref="page{page_number}"/>'
        )

    return f"""<?xml version="1.0" encoding="utf-8"?>

<package
    xmlns="http://www.idpf.org/2007/opf"
    version="3.0"
    unique-identifier="BookID">

    <metadata
        xmlns:dc="http://purl.org/dc/elements/1.1/"
        xmlns:dcterms="http://purl.org/dc/terms/">

        <dc:identifier id="BookID">
            {xml_escape(identifier)}
        </dc:identifier>

        <dc:title>
            {xml_escape(title)}
        </dc:title>

        <dc:language>
            zh-TW
        </dc:language>

        <dc:creator>
            著作者
        </dc:creator>

        <meta
            property="dcterms:modified">
            2026-09-15T00:00:00Z
        </meta>

    </metadata>

    <manifest>

        {"".join(manifest)}

    </manifest>

    <spine toc="ncx">

        {"".join(spine)}

    </spine>

</package>
"""


# ============================================================
# EPUB Navigation
# ============================================================

def create_nav(
    title,
    chapters
):

    links = []

    for chapter in chapters:

        page = chapter[
            "page"
        ]

        chapter_title = chapter[
            "title"
        ]

        filename = (
            f"Text/page_{page:05d}.xhtml"
        )

        links.append(
            "<li>"
            f'<a href="{filename}">'
            f"{xml_escape(chapter_title)}"
            "</a>"
            "</li>"
        )

    return f"""<?xml version="1.0" encoding="utf-8"?>

<!DOCTYPE html>

<html
    xmlns="http://www.w3.org/1999/xhtml"
    xmlns:epub="http://www.idpf.org/2007/ops"
    lang="zh-TW"
    xml:lang="zh-TW">

<head>

    <meta charset="utf-8"/>

    <title>
        {xml_escape(title)}
    </title>

</head>

<body>

<nav
    epub:type="toc"
    id="toc">

    <h1>目錄</h1>

    <ol>

        {"".join(links)}

    </ol>

</nav>

</body>

</html>
"""


# ============================================================
# NCX
# ============================================================

def create_ncx(
    title,
    identifier,
    chapters
):

    nav_points = []

    for index, chapter in enumerate(
        chapters,
        start=1
    ):

        page = chapter[
            "page"
        ]

        chapter_title = chapter[
            "title"
        ]

        filename = (
            f"Text/page_{page:05d}.xhtml"
        )

        nav_points.append(
            f"""
<navPoint
    id="navPoint-{index}"
    playOrder="{index}">

    <navLabel>
        <text>
            {xml_escape(chapter_title)}
        </text>
    </navLabel>

    <content
        src="{filename}"/>

</navPoint>
"""
        )

    return f"""<?xml version="1.0" encoding="utf-8"?>

<!DOCTYPE ncx
    PUBLIC "-//NISO//DTD ncx 2005-1//EN"
    "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">

<ncx
    xmlns="http://www.daisy.org/z3986/2005/ncx/"
    version="2005-1">

<head>

    <meta
        name="dtb:uid"
        content="{xml_escape(identifier)}"/>

</head>

<docTitle>

    <text>
        {xml_escape(title)}
    </text>

</docTitle>

<navMap>

    {"".join(nav_points)}

</navMap>

</ncx>
"""


# ============================================================
# 安全刪除
# ============================================================

def safe_remove(
    path,
    retries=10
):

    path = Path(path)

    if not path.exists():

        return True

    for attempt in range(
        retries
    ):

        try:

            if path.is_dir():

                shutil.rmtree(
                    path
                )

            else:

                path.unlink()

            return True

        except (
            PermissionError,
            OSError
        ):

            if attempt >= retries - 1:

                return False

            time.sleep(
                0.3
            )

    return False


# ============================================================
# 建立 EPUB
# ============================================================

def build_epub(
    output_file,
    title,
    identifier,
    chapters,
    xhtml_files,
    css_data,
    image_files
):

    # --------------------------------------------------------
    # 產生 OPF
    # --------------------------------------------------------

    opf = create_opf(
        title,
        identifier,
        len(chapters),
        image_files
    )

    nav = create_nav(
        title,
        chapters
    )

    ncx = create_ncx(
        title,
        identifier,
        chapters
    )

    container = """<?xml version="1.0" encoding="UTF-8"?>

<container
    version="1.0"
    xmlns="urn:oasis:names:tc:opendocument:xmlns:container">

    <rootfiles>

        <rootfile
            full-path="OEBPS/content.opf"
            media-type="application/oebps-package+xml"/>

    </rootfiles>

</container>
"""

    # --------------------------------------------------------
    # EPUB mimetype
    #
    # 必須：
    #   1. 第一個
    #   2. 不壓縮
    # --------------------------------------------------------

    with zipfile.ZipFile(
        output_file,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9
    ) as archive:

        info = zipfile.ZipInfo(
            "mimetype"
        )

        info.compress_type = (
            zipfile.ZIP_STORED
        )

        archive.writestr(
            info,
            b"application/epub+zip"
        )

        # ----------------------------------------------------
        # container
        # ----------------------------------------------------

        archive.writestr(
            "META-INF/container.xml",
            container.encode(
                "utf-8"
            )
        )

        # ----------------------------------------------------
        # OPF
        # ----------------------------------------------------

        archive.writestr(
            "OEBPS/content.opf",
            opf.encode(
                "utf-8"
            )
        )

        # ----------------------------------------------------
        # CSS
        # ----------------------------------------------------

        archive.writestr(
            "OEBPS/Styles/style.css",
            css_data
        )

        # ----------------------------------------------------
        # Navigation
        # ----------------------------------------------------

        archive.writestr(
            "OEBPS/nav.xhtml",
            nav.encode(
                "utf-8"
            )
        )

        # ----------------------------------------------------
        # NCX
        # ----------------------------------------------------

        archive.writestr(
            "OEBPS/toc.ncx",
            ncx.encode(
                "utf-8"
            )
        )

        # ----------------------------------------------------
        # XHTML
        # ----------------------------------------------------

        for filename, data in xhtml_files:

            archive.writestr(
                "OEBPS/" + filename,
                data
            )

        # ----------------------------------------------------
        # Images
        # ----------------------------------------------------

        for image in image_files:

            archive.writestr(
                "OEBPS/Images/"
                + image["name"],
                image["data"]
            )


# ============================================================
# EPUB 驗證
# ============================================================

def validate_epub(
    epub_file
):

    print(
        "  驗證 EPUB..."
    )

    try:

        with zipfile.ZipFile(
            epub_file,
            "r"
        ) as archive:

            names = archive.namelist()

            # ------------------------------------------------
            # mimetype
            # ------------------------------------------------

            if not names:

                print(
                    "EPUB 是空的"
                )

                return False

            if names[0] != "mimetype":

                print(
                    "mimetype "
                    "不是第一個檔案"
                )

                return False

            mimetype = (
                archive
                .read("mimetype")
                .decode("ascii")
            )

            if (
                mimetype
                !=
                "application/epub+zip"
            ):

                print(
                    "mimetype 錯誤"
                )

                return False

            # ------------------------------------------------
            # 必要檔案
            # ------------------------------------------------

            required = [

                "META-INF/container.xml",

                "OEBPS/content.opf",

                "OEBPS/nav.xhtml",

                "OEBPS/toc.ncx",

                "OEBPS/Styles/style.css"

            ]

            for filename in required:

                if filename not in names:

                    print(
                        "缺少："
                        + filename
                    )

                    return False

            # ------------------------------------------------
            # XHTML
            # ------------------------------------------------

            xhtml_files = [

                name
                for name in names

                if (
                    name.startswith(
                        "OEBPS/Text/"
                    )
                    and
                    name.endswith(
                        ".xhtml"
                    )
                )

            ]

            if not xhtml_files:

                print(
                    "沒有 XHTML"
                )

                return False

            # ------------------------------------------------
            # 中文
            # ------------------------------------------------

            chinese_found = False

            for filename in xhtml_files:

                data = archive.read(
                    filename
                )

                text = data.decode(
                    "utf-8",
                    errors="ignore"
                )

                if contains_chinese(
                    text
                ):

                    chinese_found = True

                    break

            if not chinese_found:

                print(
                    "EPUB 中"
                    "沒有找到中文文字"
                )

                return False

            print(
                "EPUB 結構正常"
            )

            print(
                f"XHTML："
                f"{len(xhtml_files)}"
            )

            print(
                "中文文字：OK"
            )

            print(
                "未嵌入大型中文字型"
            )

            return True

    except Exception as e:

        print(
            f"驗證失敗：{e}"
        )

        return False


# ============================================================
# PDF → EPUB
# ============================================================

def convert_pdf(
    input_pdf
):

    print()
    print("=" * 70)

    print(
        f"處理：{input_pdf.name}"
    )

    print("=" * 70)

    output_file = (
        OUTPUT_DIR
        /
        (
            input_pdf.stem
            + ".epub"
        )
    )

    temp_file = (
        OUTPUT_DIR
        /
        (
            "."
            + input_pdf.stem
            + ".tmp.epub"
        )
    )

    image_dir = (
        OUTPUT_DIR
        /
        (
            ".images_"
            + input_pdf.stem
        )
    )

    # --------------------------------------------------------
    # 清理暫存
    # --------------------------------------------------------

    safe_remove(
        temp_file
    )

    safe_remove(
        image_dir
    )

    document = None

    try:

        # ----------------------------------------------------
        # 開啟 PDF
        # ----------------------------------------------------

        document = pymupdf.open(
            str(input_pdf)
        )

        if document.is_encrypted:

            print(
                "PDF 有密碼保護。"
            )

            return False

        page_count = len(
            document
        )

        if page_count == 0:

            print(
                "PDF 沒有頁面。"
            )

            return False

        print(
            f"PDF 頁數：{page_count}"
        )

        # ----------------------------------------------------
        # 檢查文字
        # ----------------------------------------------------

        total_chars = 0

        chinese_chars = 0

        pages_with_text = 0

        for page in document:

            text = page.get_text(
                "text"
            )

            if text.strip():

                pages_with_text += 1

                total_chars += len(
                    text
                )

                chinese_chars += sum(
                    1
                    for ch in text
                    if (
                        0x3400
                        <= ord(ch)
                        <= 0x9FFF
                    )
                )

        print(
            f"文字字元：{total_chars}"
        )

        print(
            f"中文字元：{chinese_chars}"
        )

        print(
            f"有文字頁面："
            f"{pages_with_text}"
        )

        # ----------------------------------------------------
        # 如果完全沒有文字
        # ----------------------------------------------------

        if total_chars == 0:

            print()
            print(
                "這個 PDF 沒有文字層。"
            )

            print(
                "可能是掃描 PDF，"
                "需要 OCR 才能轉成可重新排版 EPUB。"
            )

            return False

        # ----------------------------------------------------
        # CSS
        # ----------------------------------------------------

        css_data = (
            create_css()
            .encode(
                "utf-8"
            )
        )

        # ----------------------------------------------------
        # 圖片暫存
        # ----------------------------------------------------

        if KEEP_IMAGES:

            image_dir.mkdir(
                parents=True,
                exist_ok=True
            )

        # ----------------------------------------------------
        # XHTML
        # ----------------------------------------------------

        xhtml_files = []

        chapters = []

        all_images = []

        total_blocks = 0

        chinese_blocks = 0

        # ====================================================
        # 逐頁處理
        # ====================================================

        for page_index in range(
            page_count
        ):

            page_number = (
                page_index + 1
            )

            page = document[
                page_index
            ]

            print(
                f"  處理第 "
                f"{page_number}/"
                f"{page_count} 頁...",
                end="\r"
            )

            # ------------------------------------------------
            # 文字
            # ------------------------------------------------

            blocks = get_text_blocks(
                page
            )

            total_blocks += len(
                blocks
            )

            for block in blocks:

                if contains_chinese(
                    block["text"]
                ):

                    chinese_blocks += 1

            # ------------------------------------------------
            # 圖片
            # ------------------------------------------------

            images = extract_images(
                page,
                document,
                image_dir,
                page_number
            )

            all_images.extend(
                images
            )

            # ------------------------------------------------
            # XHTML
            # ------------------------------------------------

            xhtml = create_xhtml(
                input_pdf.stem,
                page_number,
                blocks,
                images,
                page.rect.height
            )

            filename = (
                f"Text/page_"
                f"{page_number:05d}.xhtml"
            )

            xhtml_files.append(
                (
                    filename,
                    xhtml.encode(
                        "utf-8"
                    )
                )
            )

            # ------------------------------------------------
            # 找一個適合作為目錄的標題
            # ------------------------------------------------

            chapter_title = (
                f"第 {page_number} 頁"
            )

            for block in blocks:

                if looks_like_heading(
                    block["text"],
                    block["size"],
                    page.rect.height
                ):

                    heading = (
                        block["text"]
                        .split("\n")[0]
                        .strip()
                    )

                    if (
                        heading
                        and
                        len(heading)
                        <= 80
                    ):

                        chapter_title = (
                            heading
                        )

                        break

            chapters.append(
                {
                    "page": page_number,
                    "title": chapter_title
                }
            )

        print()

        # ----------------------------------------------------
        # 將圖片讀入記憶體
        # ----------------------------------------------------

        image_files = []

        if KEEP_IMAGES:

            # 去除同一圖片的重複項目
            #
            # PDF 中同一 xref 可能被多次引用。
            # 用檔名去重。
            # ------------------------------------------------

            seen = set()

            for image in all_images:

                path = image[
                    "path"
                ]

                if not path.exists():
                    continue

                filename = path.name

                if filename in seen:
                    continue

                seen.add(
                    filename
                )

                try:

                    data = (
                        path.read_bytes()
                    )

                    image_files.append(
                        {
                            "name":
                                filename,

                            "data":
                                data,

                            "media_type":
                                get_media_type(
                                    path.suffix
                                )
                        }
                    )

                except Exception as e:

                    print(
                        f"圖片讀取失敗："
                        f"{filename}"
                    )

                    print(
                        f"     {e}"
                    )

        # ----------------------------------------------------
        # 關閉 PDF
        # ----------------------------------------------------

        document.close()

        document = None

        # ----------------------------------------------------
        # 建立 EPUB
        # ----------------------------------------------------

        print()
        print(
            "  建立 EPUB..."
        )

        identifier = (
            "urn:pdf-to-epub:"
            +
            hashlib.sha1(
                input_pdf.name.encode(
                    "utf-8"
                )
            ).hexdigest()
        )

        build_epub(
            temp_file,
            input_pdf.stem,
            identifier,
            chapters,
            xhtml_files,
            css_data,
            image_files
        )

        # ----------------------------------------------------
        # 驗證
        # ----------------------------------------------------

        if not temp_file.exists():

            print(
                "EPUB 沒有建立。"
            )

            return False

        if not validate_epub(
            temp_file
        ):

            print(
                "EPUB 驗證失敗。"
            )

            return False

        # ----------------------------------------------------
        # 取得大小
        # ----------------------------------------------------

        size_mb = (
            temp_file.stat().st_size
            /
            1024
            /
            1024
        )

        print(
            f"  EPUB 暫存大小："
            f"{size_mb:.2f} MB"
        )

        # ----------------------------------------------------
        # 移除舊檔
        # ----------------------------------------------------

        if output_file.exists():

            print(
                "  移除舊 EPUB..."
            )

            if not safe_remove(
                output_file
            ):

                print(
                    "無法刪除舊 EPUB："
                )

                print(
                    output_file
                )

                print()
                print(
                    "請關閉可能正在使用"
                    "此檔案的程式，例如："
                )

                print(
                    "  • Calibre"
                )

                print(
                    "  • EPUB 閱讀器"
                )

                print(
                    "  • Windows 預覽窗格"
                )

                return False

        # ----------------------------------------------------
        # 移動
        # ----------------------------------------------------

        shutil.move(
            str(temp_file),
            str(output_file)
        )

        # ----------------------------------------------------
        # 清除圖片暫存
        # ----------------------------------------------------

        safe_remove(
            image_dir
        )

        # ----------------------------------------------------
        # 完成
        # ----------------------------------------------------

        final_size = (
            output_file.stat().st_size
            /
            1024
            /
            1024
        )

        print()
        print(
            "完成"
        )

        print(
            f"   檔案："
            f"{output_file.name}"
        )

        print(
            f"   頁數："
            f"{page_count}"
        )

        print(
            f"   文字區塊："
            f"{total_blocks}"
        )

        print(
            f"   中文區塊："
            f"{chinese_blocks}"
        )

        print(
            f"   圖片："
            f"{len(image_files)}"
        )

        print(
            f"   EPUB 大小："
            f"{final_size:.2f} MB"
        )

        print(
            f"   輸出："
            f"{output_file}"
        )

        return True

    except Exception as e:

        print()
        print(
            f"{input_pdf.name}"
            " 發生錯誤："
        )

        print(
            repr(e)
        )

        return False

    finally:

        if document is not None:

            try:

                document.close()

            except Exception:

                pass


# ============================================================
# 主程式
# ============================================================

def main():

    print()
    print("=" * 70)

    print(
        "PDF → 小型 Kindle EPUB"
    )

    print(
        "繁體中文 / Unicode / Reflowable"
    )

    print(
        "不嵌入大型中文字型"
    )

    print(
        "ZIP DEFLATED level 9"
    )

    print("=" * 70)

    # --------------------------------------------------------
    # PyMuPDF
    # --------------------------------------------------------

    try:

        print(
            "PyMuPDF："
            +
            pymupdf.VersionBind
        )

    except Exception:
        pass

    # --------------------------------------------------------
    # 輸出目錄
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    pdf_files = sorted(
        [
            p
            for p in PDF_DIR.glob(
                "*.pdf"
            )
            if p.is_file()
        ]
    )

    if not pdf_files:

        print()
        print(
            "找不到 PDF。"
        )

        print(
            PDF_DIR
        )

        return

    print()
    print(
        f"找到 {len(pdf_files)} 個 PDF。"
    )

    print()
    print(
        "輸出目錄："
    )

    print(
        OUTPUT_DIR
    )

    print()
    print(
        "字型嵌入：否"
    )

    print(
        "EPUB 壓縮：ZIP_DEFLATED level 9"
    )

    success = 0

    failed = 0

    # ========================================================
    # 批次
    # ========================================================

    for pdf_file in pdf_files:

        try:

            result = convert_pdf(
                pdf_file
            )

            if result:

                success += 1

            else:

                failed += 1

        except KeyboardInterrupt:

            print()
            print(
                "使用者中止。"
            )

            break

        except Exception as e:

            print()
            print(
                f"{pdf_file.name}"
                " 發生未預期錯誤："
            )

            print(
                repr(e)
            )

            failed += 1

    # ========================================================
    # 結果
    # ========================================================

    print()
    print("=" * 70)

    print(
        "全部處理完成"
    )

    print("=" * 70)

    print(
        f"成功：{success}"
    )

    print(
        f"失敗：{failed}"
    )

    print()

    print(
        "EPUB 位置："
    )

    print(
        OUTPUT_DIR
    )

    print()


# ============================================================
# 執行
# ============================================================

if __name__ == "__main__":

    main()

