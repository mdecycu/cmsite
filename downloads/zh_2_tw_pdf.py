# -*- coding: utf-8 -*-

"""
======================================================================
zh_2_tw_pdf.py
======================================================================

功能：

    1. 自動搜尋目前程式所在目錄。
    2. 遞迴搜尋所有子目錄、子目錄的子目錄……
    3. 找出所有 PDF 檔案。
    4. 將 PDF 中的簡體中文轉換成台灣繁體中文。
    5. 使用 OpenCC s2twp 進行「簡體 → 台灣繁體」及詞彙轉換。
    6. 使用 PyMuPDF 內建 CJK 字型 china-t。
    7. 保留圖片。
    8. 保留原有 PDF 超連結。
    9. 保留頁面尺寸。
   10. 保留文字位置。
   11. 保留文字大小。
   12. 保留文字顏色。
   13. 只有文字真正發生變化才處理。
   14. 輸出檔案放在原 PDF 相同目錄。
   15. 輸出檔名：
           1.pdf       → 1_tw.pdf
           test.pdf    → test_tw.pdf
           book.pdf    → book_tw.pdf
   16. 已經是 *_tw.pdf 的檔案自動跳過。
   17. 顯示整體及個別 PDF 的處理進度。
   18. 顯示預估剩餘時間。
   19. 最後顯示完整統計。

注意：

    本程式適合「文字型 PDF」。

    如果 PDF 裡面的中文字其實是「掃描圖片」，
    get_text() 無法取得文字，
    因此本程式不會轉換圖片中的文字。

安裝：

    python -m pip install --upgrade pymupdf opencc-python-reimplemented

執行：

    python zh_2_tw_pdf.py

======================================================================
"""

import os
import sys
import time
import traceback

import pymupdf
from opencc import OpenCC


# ====================================================================
# 使用者設定
# ====================================================================

# 輸入根目錄：
#
# 使用目前 Python 程式所在的目錄。
#
ROOT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

# 輸出檔名後綴
OUTPUT_SUFFIX = "_tw"

# OpenCC：
#
# s2twp：
#
#   Simplified Chinese
#       →
#   Traditional Chinese (Taiwan)
#
# 並包含台灣詞彙轉換。
#
# 例如：
#
#   软件     → 軟體
#   鼠标     → 滑鼠
#   信息     → 資訊
#   打印     → 列印
#   网络     → 網路
#   视频     → 影片
#   服务器   → 伺服器
#   数据库   → 資料庫
#
cc = OpenCC("s2twp")


# ====================================================================
# PyMuPDF 內建 CJK 字型
# ====================================================================

CJK_FONT = "china-t"


# ====================================================================
# 進度顯示
# ====================================================================

# 每處理多少頁顯示一次完整進度
PROGRESS_INTERVAL = 100


# ====================================================================
# 搜尋 PDF
# ====================================================================

def find_all_pdfs(root_dir):
    """
    遞迴搜尋 root_dir 以下所有 PDF。

    包含：

        root_dir/*.pdf
        root_dir/A/*.pdf
        root_dir/A/B/*.pdf
        root_dir/A/B/C/*.pdf
        ...

    自動跳過：

        *_tw.pdf
    """

    pdf_files = []

    for current_root, dirs, files in os.walk(root_dir):

        # ------------------------------------------------------------
        # 排序，讓處理順序固定
        # ------------------------------------------------------------

        dirs.sort()
        files.sort()

        for filename in files:

            # --------------------------------------------------------
            # 必須是 PDF
            # --------------------------------------------------------

            if not filename.lower().endswith(".pdf"):
                continue

            # --------------------------------------------------------
            # 已經轉換過的 *_tw.pdf 跳過
            # --------------------------------------------------------

            name_without_ext = os.path.splitext(
                filename
            )[0]

            if name_without_ext.lower().endswith(
                OUTPUT_SUFFIX.lower()
            ):
                continue

            full_path = os.path.join(
                current_root,
                filename
            )

            pdf_files.append(
                full_path
            )

    return pdf_files


# ====================================================================
# 判斷是否有中文字
# ====================================================================

def contains_chinese(text):

    if not text:
        return False

    for ch in text:

        code = ord(ch)

        if (
            0x3400 <= code <= 0x4DBF
            or
            0x4E00 <= code <= 0x9FFF
            or
            0xF900 <= code <= 0xFAFF
        ):
            return True

    return False


# ====================================================================
# 簡體 → 台灣繁體
# ====================================================================

def convert_text(text):

    if not text:
        return text

    if not contains_chinese(text):
        return text

    return cc.convert(text)


# ====================================================================
# 顏色轉 RGB
# ====================================================================

def get_rgb(color):

    r = (color >> 16) & 255
    g = (color >> 8) & 255
    b = color & 255

    return (
        r / 255.0,
        g / 255.0,
        b / 255.0
    )


# ====================================================================
# 取得文字旋轉角度
# ====================================================================

def get_rotation(line):

    direction = line.get(
        "dir",
        (1, 0)
    )

    dx = direction[0]
    dy = direction[1]

    # ------------------------------------------------------------
    # 0°
    # ------------------------------------------------------------

    if abs(dx) > 0.9 and abs(dy) < 0.1:

        if dx >= 0:
            return 0

        return 180

    # ------------------------------------------------------------
    # 90°
    # ------------------------------------------------------------

    if abs(dy) > 0.9 and abs(dx) < 0.1:

        if dy < 0:
            return 90

        return 270

    # ------------------------------------------------------------
    # 其他角度
    # ------------------------------------------------------------

    return 0


# ====================================================================
# 找出需要轉換的文字
# ====================================================================

def get_changed_spans(page):

    changed = []

    try:

        data = page.get_text(
            "dict"
        )

    except Exception:

        return changed

    # ------------------------------------------------------------
    # 逐個 block
    # ------------------------------------------------------------

    for block in data.get(
        "blocks",
        []
    ):

        # --------------------------------------------------------
        # type 0 = text
        #
        # type 1 = image
        #
        # 只處理文字 block。
        # --------------------------------------------------------

        if block.get("type") != 0:
            continue

        # --------------------------------------------------------
        # 逐個 line
        # --------------------------------------------------------

        for line in block.get(
            "lines",
            []
        ):

            rotation = get_rotation(
                line
            )

            # ----------------------------------------------------
            # 逐個 span
            # ----------------------------------------------------

            for span in line.get(
                "spans",
                []
            ):

                original = span.get(
                    "text",
                    ""
                )

                if not original:
                    continue

                converted = convert_text(
                    original
                )

                # ------------------------------------------------
                # 文字沒有變化
                # ------------------------------------------------

                if converted == original:
                    continue

                changed.append({

                    "bbox": span[
                        "bbox"
                    ],

                    "original": original,

                    "converted": converted,

                    "size": float(
                        span.get(
                            "size",
                            10
                        )
                    ),

                    "color": get_rgb(
                        span.get(
                            "color",
                            0
                        )
                    ),

                    "rotation": rotation
                })

    return changed


# ====================================================================
# 計算文字插入點
# ====================================================================

def get_insert_point(span):

    x0, y0, x1, y1 = span[
        "bbox"
    ]

    size = span[
        "size"
    ]

    rotation = span[
        "rotation"
    ]

    # ------------------------------------------------------------
    # 0°
    # ------------------------------------------------------------

    if rotation == 0:

        return (
            x0,
            y1 - size * 0.15
        )

    # ------------------------------------------------------------
    # 90°
    # ------------------------------------------------------------

    if rotation == 90:

        return (
            x0,
            y1
        )

    # ------------------------------------------------------------
    # 180°
    # ------------------------------------------------------------

    if rotation == 180:

        return (
            x1,
            y0
        )

    # ------------------------------------------------------------
    # 270°
    # ------------------------------------------------------------

    if rotation == 270:

        return (
            x1,
            y0
        )

    return (
        x0,
        y1 - size * 0.15
    )


# ====================================================================
# 備份頁面連結
# ====================================================================

def backup_links(page):

    try:

        links = page.get_links()

        result = []

        for link in links:

            result.append(
                dict(link)
            )

        return result

    except Exception:

        return []


# ====================================================================
# 還原頁面連結
# ====================================================================

def restore_links(
    page,
    links
):

    if not links:
        return

    for link in links:

        try:

            page.insert_link(
                link
            )

        except Exception:

            # 某些特殊 annotation
            # 可能無法重新加入。
            pass


# ====================================================================
# 處理單頁
# ====================================================================

def process_page(page):

    # ------------------------------------------------------------
    # 找出需要轉換的文字
    # ------------------------------------------------------------

    spans = get_changed_spans(
        page
    )

    if not spans:

        return 0

    # ------------------------------------------------------------
    # 備份超連結
    # ------------------------------------------------------------

    links = backup_links(
        page
    )

    # ------------------------------------------------------------
    # 遮蓋原來的簡體文字
    # ------------------------------------------------------------

    for span in spans:

        x0, y0, x1, y1 = span[
            "bbox"
        ]

        rect = pymupdf.Rect(
            x0 - 0.4,
            y0 - 0.4,
            x1 + 0.4,
            y1 + 0.4
        )

        page.add_redact_annot(
            rect,
            fill=(1, 1, 1)
        )

    # ------------------------------------------------------------
    # 套用 redaction
    #
    # images=0
    #     保留圖片
    #
    # graphics=0
    #     保留圖形
    #
    # text=0
    #     不讓 redaction 自己處理其他文字
    # ------------------------------------------------------------

    page.apply_redactions(
        images=0,
        graphics=0,
        text=0
    )

    # ------------------------------------------------------------
    # 寫入繁體中文
    # ------------------------------------------------------------

    count = 0

    for span in spans:

        text = span[
            "converted"
        ]

        fontsize = span[
            "size"
        ]

        color = span[
            "color"
        ]

        rotation = span[
            "rotation"
        ]

        point = get_insert_point(
            span
        )

        try:

            page.insert_text(

                point,

                text,

                fontsize=fontsize,

                fontname=CJK_FONT,

                color=color,

                rotate=rotation,

                overlay=True
            )

            count += 1

        except Exception as e:

            print()

            print(
                "    [文字寫入失敗]"
            )

            print(
                "    原文字：",
                repr(
                    span["original"][:100]
                )
            )

            print(
                "    轉換後：",
                repr(
                    text[:100]
                )
            )

            print(
                "    錯誤：",
                e
            )

    # ------------------------------------------------------------
    # 還原超連結
    # ------------------------------------------------------------

    restore_links(
        page,
        links
    )

    return count


# ====================================================================
# 格式化時間
# ====================================================================

def format_time(seconds):

    if seconds < 60:

        return (
            f"{seconds:.0f} 秒"
        )

    minutes = int(
        seconds // 60
    )

    seconds = int(
        seconds % 60
    )

    if minutes < 60:

        return (
            f"{minutes} 分 {seconds} 秒"
        )

    hours = int(
        minutes // 60
    )

    minutes = minutes % 60

    return (
        f"{hours} 小時 {minutes} 分"
    )


# ====================================================================
# 取得輸出檔名
# ====================================================================

def get_output_path(input_path):

    directory = os.path.dirname(
        input_path
    )

    filename = os.path.basename(
        input_path
    )

    name, ext = os.path.splitext(
        filename
    )

    output_filename = (
        name
        +
        OUTPUT_SUFFIX
        +
        ext
    )

    return os.path.join(
        directory,
        output_filename
    )


# ====================================================================
# 處理單一 PDF
# ====================================================================

def process_pdf(
    input_path,
    pdf_number,
    total_pdfs
):

    output_path = get_output_path(
        input_path
    )

    print()
    print()
    print(
        "=" * 70
    )

    print(
        f"[PDF {pdf_number}/{total_pdfs}]"
    )

    print(
        f"輸入：{input_path}"
    )

    print(
        f"輸出：{output_path}"
    )

    print(
        "=" * 70
    )

    # ------------------------------------------------------------
    # 開啟 PDF
    # ------------------------------------------------------------

    try:

        doc = pymupdf.open(
            input_path
        )

    except Exception as e:

        print(
            f"[錯誤] 無法開啟 PDF：{e}"
        )

        return {
            "success": False,
            "pages": 0,
            "changed": 0,
            "failed": 0,
            "time": 0
        }

    total_pages = len(doc)

    print(
        f"總頁數：{total_pages}"
    )

    # ------------------------------------------------------------
    # 計時
    # ------------------------------------------------------------

    start_time = time.time()

    total_changed = 0
    successful_pages = 0
    failed_pages = 0
    pages_without_changes = 0

    # ------------------------------------------------------------
    # 逐頁處理
    # ------------------------------------------------------------

    for page_index in range(
        total_pages
    ):

        page_number = (
            page_index + 1
        )

        changed = 0

        try:

            page = doc[
                page_index
            ]

            changed = process_page(
                page
            )

            total_changed += changed

            successful_pages += 1

            if changed == 0:

                pages_without_changes += 1

        except Exception as e:

            failed_pages += 1

            print()
            print(
                f"[錯誤] 第 {page_number} 頁"
            )

            print(
                e
            )

            traceback.print_exc()

        # --------------------------------------------------------
        # 顯示單行進度
        # --------------------------------------------------------

        if total_pages > 0:

            percent = (
                page_number
                /
                total_pages
                *
                100
            )

        else:

            percent = 100

        print(
            f"\r處理："
            f"{page_number}/{total_pages}"
            f" "
            f"({percent:.2f}%)"
            f" "
            f"本頁轉換：{changed}",
            end="",
            flush=True
        )

        # --------------------------------------------------------
        # 每 100 頁顯示詳細資訊
        # --------------------------------------------------------

        if (
            page_number % PROGRESS_INTERVAL == 0
            or
            page_number == total_pages
        ):

            elapsed = (
                time.time()
                -
                start_time
            )

            if page_number > 0:

                average = (
                    elapsed
                    /
                    page_number
                )

            else:

                average = 0

            remaining_pages = (
                total_pages
                -
                page_number
            )

            estimated_remaining = (
                average
                *
                remaining_pages
            )

            print()

            print(
                "-" * 70
            )

            print(
                f"進度："
                f"{page_number}/{total_pages}"
            )

            print(
                f"完成率："
                f"{percent:.2f}%"
            )

            print(
                f"轉換文字區塊："
                f"{total_changed}"
            )

            print(
                f"無需轉換頁面："
                f"{pages_without_changes}"
            )

            print(
                f"失敗頁面："
                f"{failed_pages}"
            )

            if elapsed > 0:

                print(
                    f"平均速度："
                    f"{page_number / elapsed:.2f}"
                    f" 頁/秒"
                )

            print(
                f"已耗時："
                f"{format_time(elapsed)}"
            )

            print(
                f"預估剩餘："
                f"{format_time(estimated_remaining)}"
            )

            print(
                "-" * 70
            )

    # ------------------------------------------------------------
    # 儲存
    # ------------------------------------------------------------

    print()
    print()

    print(
        "正在儲存轉換後 PDF..."
    )

    save_start = time.time()

    try:

        # --------------------------------------------------------
        # 如果輸出檔已經存在
        # --------------------------------------------------------

        if os.path.exists(
            output_path
        ):

            try:

                os.remove(
                    output_path
                )

            except PermissionError:

                print()

                print(
                    f"[錯誤] 無法覆蓋："
                    f"{output_path}"
                )

                print(
                    "請先關閉已開啟的輸出 PDF。"
                )

                doc.close()

                return {
                    "success": False,
                    "pages": total_pages,
                    "changed": total_changed,
                    "failed": failed_pages,
                    "time": (
                        time.time()
                        -
                        start_time
                    )
                }

        # --------------------------------------------------------
        # 儲存
        # --------------------------------------------------------

        doc.save(

            output_path,

            # 清理未使用物件
            garbage=4,

            # 壓縮內容
            deflate=True,

            # 清理內容串流
            clean=True
        )

    except Exception as e:

        print()
        print(
            "[錯誤] PDF 儲存失敗："
        )

        print(
            e
        )

        traceback.print_exc()

        doc.close()

        return {
            "success": False,
            "pages": total_pages,
            "changed": total_changed,
            "failed": failed_pages,
            "time": (
                time.time()
                -
                start_time
            )
        }

    save_time = (
        time.time()
        -
        save_start
    )

    # ------------------------------------------------------------
    # 關閉 PDF
    # ------------------------------------------------------------

    doc.close()

    total_time = (
        time.time()
        -
        start_time
    )

    # ------------------------------------------------------------
    # 輸出檔案大小
    # ------------------------------------------------------------

    output_size = 0

    if os.path.isfile(
        output_path
    ):

        output_size = (
            os.path.getsize(
                output_path
            )
            /
            1024
            /
            1024
        )

    # ------------------------------------------------------------
    # 完成資訊
    # ------------------------------------------------------------

    print()
    print(
        "-" * 70
    )

    print(
        f"完成："
        f"{os.path.basename(input_path)}"
    )

    print(
        f"輸出："
        f"{output_path}"
    )

    print(
        f"總頁數："
        f"{total_pages}"
    )

    print(
        f"成功頁數："
        f"{successful_pages}"
    )

    print(
        f"失敗頁數："
        f"{failed_pages}"
    )

    print(
        f"無需轉換頁數："
        f"{pages_without_changes}"
    )

    print(
        f"轉換文字區塊："
        f"{total_changed}"
    )

    print(
        f"輸出大小："
        f"{output_size:.2f} MB"
    )

    print(
        f"處理時間："
        f"{format_time(total_time)}"
    )

    print(
        f"儲存時間："
        f"{format_time(save_time)}"
    )

    print(
        "-" * 70
    )

    return {
        "success": True,
        "pages": total_pages,
        "changed": total_changed,
        "failed": failed_pages,
        "time": total_time
    }


# ====================================================================
# 主程式
# ====================================================================

def main():

    print()
    print(
        "=" * 70
    )

    print(
        "PDF 簡體中文 → 台灣繁體中文"
    )

    print(
        "遞迴批次處理模式"
    )

    print(
        "=" * 70
    )

    print()

    print(
        f"搜尋目錄：{ROOT_DIR}"
    )

    print(
        "正在搜尋所有 PDF..."
    )

    # ------------------------------------------------------------
    # 搜尋所有 PDF
    # ------------------------------------------------------------

    pdf_files = find_all_pdfs(
        ROOT_DIR
    )

    print()

    # ------------------------------------------------------------
    # 沒有找到 PDF
    # ------------------------------------------------------------

    if not pdf_files:

        print(
            "找不到任何需要處理的 PDF。"
        )

        print()

        return

    # ------------------------------------------------------------
    # 顯示找到多少 PDF
    # ------------------------------------------------------------

    print(
        f"找到 {len(pdf_files)} 個 PDF："
    )

    print()

    for index, path in enumerate(
        pdf_files,
        start=1
    ):

        print(
            f"{index:>4}. {path}"
        )

    print()

    print(
        "=" * 70
    )

    print(
        "開始批次處理"
    )

    print(
        "=" * 70
    )

    # ------------------------------------------------------------
    # 整體計時
    # ------------------------------------------------------------

    overall_start = time.time()

    total_pages = 0
    total_changed = 0
    total_failed_pages = 0
    successful_files = 0
    failed_files = 0

    # ------------------------------------------------------------
    # 逐一處理 PDF
    # ------------------------------------------------------------

    for index, pdf_path in enumerate(
        pdf_files,
        start=1
    ):

        try:

            result = process_pdf(

                pdf_path,

                index,

                len(pdf_files)
            )

            total_pages += result[
                "pages"
            ]

            total_changed += result[
                "changed"
            ]

            total_failed_pages += result[
                "failed"
            ]

            if result[
                "success"
            ]:

                successful_files += 1

            else:

                failed_files += 1

        except KeyboardInterrupt:

            print()
            print()
            print(
                "使用者中斷程式。"
            )

            return

        except Exception as e:

            failed_files += 1

            print()
            print(
                f"[嚴重錯誤]："
                f"{pdf_path}"
            )

            print(
                e
            )

            traceback.print_exc()

    # ------------------------------------------------------------
    # 整體統計
    # ------------------------------------------------------------

    overall_time = (
        time.time()
        -
        overall_start
    )

    print()
    print()
    print(
        "=" * 70
    )

    print(
        "全部 PDF 處理完成"
    )

    print(
        "=" * 70
    )

    print()

    print(
        f"搜尋目錄："
        f"{ROOT_DIR}"
    )

    print(
        f"找到 PDF："
        f"{len(pdf_files)} 個"
    )

    print(
        f"成功處理："
        f"{successful_files} 個"
    )

    print(
        f"處理失敗："
        f"{failed_files} 個"
    )

    print(
        f"總頁數："
        f"{total_pages}"
    )

    print(
        f"轉換文字區塊："
        f"{total_changed}"
    )

    print(
        f"失敗頁面："
        f"{total_failed_pages}"
    )

    print(
        f"總處理時間："
        f"{format_time(overall_time)}"
    )

    if overall_time > 0:

        print(
            f"平均速度："
            f"{total_pages / overall_time:.2f}"
            f" 頁/秒"
        )

    print()

    print(
        "輸出檔案會與原始 PDF 放在相同目錄，"
        "檔名結尾為 _tw.pdf。"
    )

    print()

    print(
        "=" * 70
    )

    print(
        "程式結束"
    )

    print(
        "=" * 70
    )

    print()


# ====================================================================
# 執行
# ====================================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()
        print()
        print(
            "程式已由使用者中斷。"
        )

    except Exception as e:

        print()
        print(
            "程式發生未預期錯誤："
        )

        print(
            e
        )

        traceback.print_exc()

        print()
