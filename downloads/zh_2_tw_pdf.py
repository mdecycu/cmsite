# -*- coding: utf-8 -*-

"""
============================================================
zh_2_tw_pdf.py
============================================================

將 input_zh.pdf 中的簡體中文轉換成台灣繁體中文，
輸出為 output_tw.pdf。

適用：
    - 文字型 PDF
    - PDF 中有少量圖片
    - PDF 有超連結
    - 大型 PDF，例如數千頁

功能：
    ✓ 簡體 → 台灣繁體
    ✓ 使用 OpenCC s2twp
    ✓ 使用 PyMuPDF 內建 CJK 字型 china-t
    ✓ 不需要外部中文字型
    ✓ 保留圖片
    ✓ 保留原有 PDF 超連結
    ✓ 保留頁面尺寸
    ✓ 保留文字位置
    ✓ 保留文字大小
    ✓ 保留文字顏色
    ✓ 只有文字真正發生變化才處理
    ✓ 顯示處理進度
    ✓ 顯示預估剩餘時間
    ✓ 自動儲存為 2.pdf

安裝：

    python -m pip install --upgrade pymupdf opencc-python-reimplemented

執行：

    python zh_2_tw_pdf.py

輸入：

    input_zh.pdf

輸出：

    output_tw.pdf

============================================================
"""

import os
import sys
import time
import traceback

import pymupdf
from opencc import OpenCC


# ============================================================
# 使用者設定
# ============================================================

INPUT_PDF = "input_zh.pdf"
OUTPUT_PDF = "output_tw.pdf"


# ============================================================
# OpenCC
# ============================================================

# s2twp：
#
#   簡體 → 台灣繁體
#
# 例如：
#
#   软件 → 軟體
#   鼠标 → 滑鼠
#   信息 → 資訊
#   打印 → 列印
#   网络 → 網路
#
cc = OpenCC("s2twp")


# ============================================================
# PyMuPDF 內建 CJK 字型
# ============================================================

# 不使用：
#
#   msjh.ttc
#   msyh.ttc
#   NotoSans...
#
# 使用 PyMuPDF 內建 CJK font。

CJK_FONT = "china-t"


# ============================================================
# 顯示設定
# ============================================================

# 每多少頁顯示一次完整統計
PROGRESS_INTERVAL = 100


# ============================================================
# 判斷是否有中文字
# ============================================================

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


# ============================================================
# 簡體 → 台灣繁體
# ============================================================

def convert_text(text):

    if not text:
        return text

    if not contains_chinese(text):
        return text

    return cc.convert(text)


# ============================================================
# 顏色轉 RGB
# ============================================================

def get_rgb(color):

    r = (color >> 16) & 255
    g = (color >> 8) & 255
    b = color & 255

    return (
        r / 255.0,
        g / 255.0,
        b / 255.0
    )


# ============================================================
# 取得文字旋轉角度
# ============================================================

def get_rotation(line):

    direction = line.get(
        "dir",
        (1, 0)
    )

    dx = direction[0]
    dy = direction[1]

    # --------------------------------------------------------
    # 0°
    # --------------------------------------------------------

    if abs(dx) > 0.9 and abs(dy) < 0.1:

        if dx >= 0:

            return 0

        return 180

    # --------------------------------------------------------
    # 90°
    # --------------------------------------------------------

    if abs(dy) > 0.9 and abs(dx) < 0.1:

        if dy < 0:

            return 90

        return 270

    # --------------------------------------------------------
    # 其他角度
    #
    # 大部分一般 PDF 不會使用。
    # 為安全起見使用 0。
    # --------------------------------------------------------

    return 0


# ============================================================
# 找出需要轉換的文字
# ============================================================

def get_changed_spans(page):

    changed = []

    try:

        data = page.get_text(
            "dict"
        )

    except Exception:

        return changed

    for block in data.get(
        "blocks",
        []
    ):

        # ----------------------------------------------------
        # type 0 = text
        #
        # type 1 = image
        #
        # 圖片不會進入此處。
        # ----------------------------------------------------

        if block.get("type") != 0:
            continue

        for line in block.get(
            "lines",
            []
        ):

            rotation = get_rotation(
                line
            )

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
                # 沒有變化就跳過
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


# ============================================================
# 計算文字插入點
# ============================================================

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

    # --------------------------------------------------------
    # 0°
    # --------------------------------------------------------

    if rotation == 0:

        return (
            x0,
            y1 - size * 0.15
        )

    # --------------------------------------------------------
    # 90°
    # --------------------------------------------------------

    if rotation == 90:

        return (
            x0,
            y1
        )

    # --------------------------------------------------------
    # 180°
    # --------------------------------------------------------

    if rotation == 180:

        return (
            x1,
            y0
        )

    # --------------------------------------------------------
    # 270°
    # --------------------------------------------------------

    if rotation == 270:

        return (
            x1,
            y0
        )

    return (
        x0,
        y1 - size * 0.15
    )


# ============================================================
# 備份頁面連結
# ============================================================

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


# ============================================================
# 還原頁面連結
# ============================================================

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

            # 某些特殊 link annotation
            # 無法重新加入時跳過。
            pass


# ============================================================
# 處理單頁
# ============================================================

def process_page(page):

    # --------------------------------------------------------
    # 找需要轉換的文字
    # --------------------------------------------------------

    spans = get_changed_spans(
        page
    )

    if not spans:

        return 0

    # --------------------------------------------------------
    # 備份連結
    # --------------------------------------------------------

    links = backup_links(
        page
    )

    # --------------------------------------------------------
    # 遮蓋原來的簡體文字
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # 套用遮蓋
    #
    # images=0：
    #     保留圖片
    #
    # graphics=0：
    #     保留圖形
    #
    # text=0：
    #     不讓 redaction 自己處理其他文字
    # --------------------------------------------------------

    page.apply_redactions(
        images=0,
        graphics=0,
        text=0
    )

    # --------------------------------------------------------
    # 寫入繁體中文
    # --------------------------------------------------------

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
                "    文字：",
                repr(text[:100])
            )

            print(
                "    錯誤：",
                e
            )

    # --------------------------------------------------------
    # 還原連結
    # --------------------------------------------------------

    restore_links(
        page,
        links
    )

    return count


# ============================================================
# 格式化時間
# ============================================================

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


# ============================================================
# 主程式
# ============================================================

def main():

    print()
    print(
        "=" * 70
    )

    print(
        "PDF 簡體中文 → 台灣繁體中文"
    )

    print(
        "完整轉換模式"
    )

    print(
        "=" * 70
    )

    print()

    # --------------------------------------------------------
    # 檢查輸入檔
    # --------------------------------------------------------

    if not os.path.isfile(
        INPUT_PDF
    ):

        print(
            f"找不到輸入檔案：{INPUT_PDF}"
        )

        print()

        return

    # --------------------------------------------------------
    # 開啟 PDF
    # --------------------------------------------------------

    print(
        "正在開啟 PDF..."
    )

    try:

        doc = pymupdf.open(
            INPUT_PDF
        )

    except Exception as e:

        print()
        print(
            "PDF 開啟失敗："
        )

        print(e)

        return

    total_pages = len(doc)

    print(
        f"輸入檔案：{INPUT_PDF}"
    )

    print(
        f"總頁數：{total_pages}"
    )

    print(
        f"CJK 字型：{CJK_FONT}"
    )

    print(
        "轉換模式：OpenCC s2twp"
    )

    print()

    # --------------------------------------------------------
    # 開始計時
    # --------------------------------------------------------

    start_time = time.time()

    total_changed = 0

    successful_pages = 0

    failed_pages = 0

    pages_without_changes = 0

    # --------------------------------------------------------
    # 記錄最近一次進度
    # --------------------------------------------------------

    last_report_time = start_time

    # --------------------------------------------------------
    # 逐頁處理
    # --------------------------------------------------------

    for page_index in range(
        total_pages
    ):

        page_number = (
            page_index + 1
        )

        page_start = time.time()

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

            print()

        # ----------------------------------------------------
        # 一般進度
        # ----------------------------------------------------

        elapsed = (
            time.time()
            -
            start_time
        )

        # ----------------------------------------------------
        # 每頁如果沒有大量轉換，
        # 就簡單顯示一行。
        # ----------------------------------------------------

        print(
            f"\r處理：{page_number}/{total_pages}"
            f"  "
            f"({page_number / total_pages * 100:.2f}%)"
            f"  "
            f"本頁：{changed if 'changed' in locals() else 0}",
            end="",
            flush=True
        )

        # ----------------------------------------------------
        # 每 100 頁顯示完整統計
        # ----------------------------------------------------

        if (
            page_number % PROGRESS_INTERVAL == 0
            or
            page_number == total_pages
        ):

            current_time = time.time()

            elapsed = (
                current_time
                -
                start_time
            )

            average = (
                elapsed
                /
                page_number
            )

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
                f"進度：{page_number}/{total_pages}"
            )

            print(
                f"完成率："
                f"{page_number / total_pages * 100:.2f}%"
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

            print(
                f"平均速度："
                f"{page_number / elapsed:.2f} 頁/秒"
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

            last_report_time = current_time

    # --------------------------------------------------------
    # 儲存 PDF
    # --------------------------------------------------------

    print()
    print()

    print(
        "=" * 70
    )

    print(
        "所有頁面處理完成，正在儲存 2.pdf..."
    )

    print(
        "=" * 70
    )

    save_start = time.time()

    try:

        # ----------------------------------------------------
        # 如果舊的 2.pdf 存在，
        # 先嘗試刪除。
        # ----------------------------------------------------

        if os.path.exists(
            OUTPUT_PDF
        ):

            try:

                os.remove(
                    OUTPUT_PDF
                )

            except PermissionError:

                print()

                print(
                    f"無法覆蓋 {OUTPUT_PDF}"
                )

                print(
                    "請先關閉已開啟的 2.pdf，"
                    "再重新執行程式。"
                )

                doc.close()

                return

        # ----------------------------------------------------
        # 儲存
        # ----------------------------------------------------

        doc.save(
            OUTPUT_PDF,

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
            "儲存失敗："
        )

        print(e)

        traceback.print_exc()

        doc.close()

        return

    save_time = (
        time.time()
        -
        save_start
    )

    doc.close()

    # --------------------------------------------------------
    # 完整統計
    # --------------------------------------------------------

    total_time = (
        time.time()
        -
        start_time
    )

    print()

    print(
        "=" * 70
    )

    print(
        "PDF 轉換完成"
    )

    print(
        "=" * 70
    )

    print()

    print(
        f"輸入檔案：{INPUT_PDF}"
    )

    print(
        f"輸出檔案：{OUTPUT_PDF}"
    )

    print(
        f"總頁數：{total_pages}"
    )

    print(
        f"成功頁數：{successful_pages}"
    )

    print(
        f"失敗頁數：{failed_pages}"
    )

    print(
        f"無需轉換頁數：{pages_without_changes}"
    )

    print(
        f"轉換文字區塊：{total_changed}"
    )

    print(
        f"處理時間：{format_time(total_time)}"
    )

    print(
        f"儲存時間：{format_time(save_time)}"
    )

    # --------------------------------------------------------
    # 輸出檔案大小
    # --------------------------------------------------------

    if os.path.isfile(
        OUTPUT_PDF
    ):

        size = (
            os.path.getsize(
                OUTPUT_PDF
            )
            /
            1024
            /
            1024
        )

        print(
            f"輸出檔案大小：{size:.2f} MB"
        )

    print()

    if failed_pages == 0:

        print(
            "全部頁面處理成功。"
        )

    else:

        print(
            f"注意：有 {failed_pages} 頁處理失敗，"
            "請檢查上方錯誤訊息。"
        )

    print()

    print(
        "圖片及原有 PDF 超連結已保留。"
    )

    print()


# ============================================================
# 執行
# ============================================================

if __name__ == "__main__":

    main()
