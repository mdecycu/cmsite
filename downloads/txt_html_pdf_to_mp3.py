# pip install edge-tts pypdf beautifulsoup4
# ============================================================
# PDF / HTML / TXT → Edge TTS
#
# 純 Python 版本
#
# 不需要：
#   FFmpeg
#   FFprobe
#   pydub
#
# 只需要：
#   pip install edge-tts pypdf beautifulsoup4
#
# ============================================================
#
# 功能：
#
# 1. 自動搜尋指定目錄
# 2. 自動搜尋所有深層子目錄
# 3. 支援：
#       .pdf
#       .html
#       .htm
#       .txt
#
# 4. 每個原始檔案獨立產生 MP3
# 5. 每約 1 小時產生一個 MP3
# 6. 純 Python 合併 MP3
# 7. 不使用 FFmpeg
# 8. 不使用 FFprobe
# 9. 不使用 pydub
# 10. TTS 失敗自動重試 3 次
# 11. 失敗句子記錄到 tts_failed.txt
# 12. 顯示處理進度
# 13. 使用 MP3 frame 計算實際音訊長度
# 14. 不會把一句話拆到兩個 MP3
# 15. 已完成的 MP3 可以保留
#
# ============================================================

import asyncio
import os
import re
import struct
import sys
import tempfile

import edge_tts

from bs4 import BeautifulSoup
from pypdf import PdfReader


# ============================================================
# 設定
# ============================================================

VOICE = "zh-TW-HsiaoChenNeural"

# 每個 MP3 目標長度
TARGET_SECONDS = 60 * 60

# TTS 最大重試次數
MAX_RETRIES = 3

# 每句之間等待
SLEEP_BETWEEN_SENTENCES = 0.3

# 支援的檔案
SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".html",
    ".htm",
    ".txt",
}


# ============================================================
# MP3 MPEG Audio Frame 解析
#
# Edge TTS 產生的是標準 MP3。
#
# 我們不重新編碼 MP3，
# 而是：
#
#   MP3 → 找出 frames → frames 串接
#
# 因此不需要 FFmpeg。
# ============================================================


# MPEG Layer III bitrate table
BITRATES_MPEG1_LAYER3 = [
    None,
    32,
    40,
    48,
    56,
    64,
    80,
    96,
    112,
    128,
    160,
    192,
    224,
    256,
    320,
    None,
]

BITRATES_MPEG2_LAYER3 = [
    None,
    8,
    16,
    24,
    32,
    40,
    48,
    56,
    64,
    80,
    96,
    112,
    128,
    144,
    160,
    None,
]

SAMPLE_RATES_MPEG1 = [
    44100,
    48000,
    32000,
]

SAMPLE_RATES_MPEG2 = [
    22050,
    24000,
    16000,
]

SAMPLE_RATES_MPEG25 = [
    11025,
    12000,
    8000,
]


# ============================================================
# 找 MP3 frame
# ============================================================

def find_mp3_frames(data):
    """
    找出 MP3 MPEG Audio frames。

    回傳：
        [
            (start, end, sample_count, sample_rate),
            ...
        ]
    """

    frames = []

    length = len(data)

    pos = 0

    # --------------------------------------------------------
    # 跳過 ID3v2
    # --------------------------------------------------------

    if length >= 10 and data[:3] == b"ID3":

        size_bytes = data[6:10]

        size = (
            ((size_bytes[0] & 0x7F) << 21)
            | ((size_bytes[1] & 0x7F) << 14)
            | ((size_bytes[2] & 0x7F) << 7)
            | (size_bytes[3] & 0x7F)
        )

        pos = 10 + size

        # ID3 footer
        flags = data[5]

        if flags & 0x10:
            pos += 10

    # --------------------------------------------------------
    # 開始找 MPEG frame
    # --------------------------------------------------------

    while pos + 4 <= length:

        b1 = data[pos]
        b2 = data[pos + 1]
        b3 = data[pos + 2]
        b4 = data[pos + 3]

        # ----------------------------------------------------
        # Sync word
        #
        # MPEG frame header 必須：
        #
        # 11111111 111xxxxx
        # ----------------------------------------------------

        if b1 != 0xFF or (b2 & 0xE0) != 0xE0:

            pos += 1
            continue

        version_bits = (b2 >> 3) & 0x03

        layer_bits = (b2 >> 1) & 0x03

        bitrate_index = (b3 >> 4) & 0x0F

        sample_rate_index = (b3 >> 2) & 0x03

        padding = (b3 >> 1) & 0x01

        # ----------------------------------------------------
        # Layer 必須是 Layer III
        # ----------------------------------------------------

        if layer_bits != 1:

            pos += 1
            continue

        # ----------------------------------------------------
        # bitrate index 0 / 15 無效
        # ----------------------------------------------------

        if bitrate_index == 0 or bitrate_index == 15:

            pos += 1
            continue

        # ----------------------------------------------------
        # sample rate index 3 無效
        # ----------------------------------------------------

        if sample_rate_index == 3:

            pos += 1
            continue

        # ----------------------------------------------------
        # MPEG Version
        # ----------------------------------------------------

        if version_bits == 3:

            # MPEG 1
            bitrate = BITRATES_MPEG1_LAYER3[
                bitrate_index
            ]

            sample_rate = SAMPLE_RATES_MPEG1[
                sample_rate_index
            ]

            samples_per_frame = 1152

            frame_length = (
                int(
                    144
                    * bitrate
                    * 1000
                    / sample_rate
                )
                + padding
            )

        elif version_bits == 2:

            # MPEG 2
            bitrate = BITRATES_MPEG2_LAYER3[
                bitrate_index
            ]

            sample_rate = SAMPLE_RATES_MPEG2[
                sample_rate_index
            ]

            samples_per_frame = 576

            frame_length = (
                int(
                    72
                    * bitrate
                    * 1000
                    / sample_rate
                )
                + padding
            )

        elif version_bits == 0:

            # MPEG 2.5
            bitrate = BITRATES_MPEG2_LAYER3[
                bitrate_index
            ]

            sample_rate = SAMPLE_RATES_MPEG25[
                sample_rate_index
            ]

            samples_per_frame = 576

            frame_length = (
                int(
                    72
                    * bitrate
                    * 1000
                    / sample_rate
                )
                + padding
            )

        else:

            pos += 1
            continue

        # ----------------------------------------------------
        # Frame 長度檢查
        # ----------------------------------------------------

        if frame_length < 4:

            pos += 1
            continue

        end = pos + frame_length

        if end > length:

            break

        frames.append(
            (
                pos,
                end,
                samples_per_frame,
                sample_rate
            )
        )

        pos = end

    return frames


# ============================================================
# MP3 取得實際長度
# ============================================================

def get_mp3_duration_from_data(data):

    frames = find_mp3_frames(data)

    if not frames:

        return 0.0

    total_samples = sum(
        frame[2]
        for frame in frames
    )

    sample_rate = frames[0][3]

    if sample_rate <= 0:

        return 0.0

    return (
        total_samples
        / sample_rate
    )


# ============================================================
# 讀取 MP3 frame
# ============================================================

def extract_mp3_audio_frames(data):

    frames = find_mp3_frames(data)

    if not frames:

        raise RuntimeError(
            "找不到有效的 MP3 MPEG Audio frames"
        )

    return b"".join(
        data[start:end]
        for start, end, _, _ in frames
    )


# ============================================================
# 合併 MP3
#
# 純 Python。
#
# 做法：
#
# 第一個 MP3：
#     保留 ID3
#     保留 MPEG frames
#
# 第二個以後：
#     只取 MPEG frames
#
# 因為每個 Edge TTS 片段的編碼格式相同，
# MPEG audio frames 可以直接串接。
# ============================================================

def merge_mp3_files(
    input_files,
    output_file
):

    if not input_files:

        return False

    try:

        with open(
            output_file,
            "wb"
        ) as out:

            first = True

            for input_file in input_files:

                with open(
                    input_file,
                    "rb"
                ) as f:

                    data = f.read()

                frames = find_mp3_frames(
                    data
                )

                if not frames:

                    print(
                        f"無法解析 MP3："
                        f"{input_file}"
                    )

                    continue

                # ------------------------------------------------
                # 第一個檔案可以保留 ID3
                # ------------------------------------------------

                if first:

                    # 找出第一個 frame 的位置
                    first_frame_start = frames[0][0]

                    # 如果有 ID3，保留它
                    if data[:3] == b"ID3":

                        out.write(
                            data[:first_frame_start]
                        )

                    first = False

                # ------------------------------------------------
                # 只寫入 MPEG audio frames
                # ------------------------------------------------

                for start, end, _, _ in frames:

                    out.write(
                        data[start:end]
                    )

        # --------------------------------------------------------
        # 檢查結果
        # --------------------------------------------------------

        if not os.path.exists(
            output_file
        ):

            return False

        if os.path.getsize(
            output_file
        ) == 0:

            return False

        return True

    except Exception as e:

        print()
        print(
            f"MP3 合併失敗：{e}"
        )

        return False


# ============================================================
# 取得 MP3 檔案長度
# ============================================================

def get_mp3_duration(
    filename
):

    try:

        with open(
            filename,
            "rb"
        ) as f:

            data = f.read()

        return get_mp3_duration_from_data(
            data
        )

    except Exception as e:

        print(
            f"無法讀取 MP3 長度："
            f"{filename}"
        )

        print(
            f"   {e}"
        )

        return 0.0


# ============================================================
# 格式化時間
# ============================================================

def format_duration(seconds):

    seconds = max(
        0,
        float(seconds)
    )

    hours = int(
        seconds // 3600
    )

    minutes = int(
        (seconds % 3600) // 60
    )

    secs = int(
        seconds % 60
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{secs:02d}"
    )


# ============================================================
# 安全檔名
# ============================================================

def safe_filename(filename):

    filename = re.sub(
        r'[<>:"/\\|?*]',
        "_",
        filename
    )

    return filename.strip()


# ============================================================
# 讀取 PDF / HTML / TXT
# ============================================================

def extract_text_from_file(
    file_path
):

    ext = os.path.splitext(
        file_path
    )[1].lower()

    text = ""

    # ========================================================
    # HTML
    # ========================================================

    if ext in [
        ".html",
        ".htm"
    ]:

        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as f:

            html = f.read()

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        # 移除不需要的內容
        for tag in soup(
            [
                "script",
                "style",
                "meta",
                "noscript",
                "svg"
            ]
        ):

            tag.decompose()

        text = soup.get_text(
            " ",
            strip=True
        )

    # ========================================================
    # PDF
    # ========================================================

    elif ext == ".pdf":

        reader = PdfReader(
            file_path
        )

        total_pages = len(
            reader.pages
        )

        print(
            f"PDF 共 {total_pages} 頁"
        )

        for page_number, page in enumerate(
            reader.pages,
            1
        ):

            print(
                f"\r正在讀取 PDF "
                f"{page_number}/{total_pages} 頁...",
                end="",
                flush=True
            )

            try:

                page_text = page.extract_text()

            except Exception as e:

                print()

                print(
                    f"PDF 第 "
                    f"{page_number} 頁失敗："
                    f"{e}"
                )

                page_text = ""

            if page_text:

                text += page_text
                text += "\n"

        print()

    # ========================================================
    # TXT
    # ========================================================

    elif ext == ".txt":

        encodings = [
            "utf-8-sig",
            "utf-8",
            "big5",
            "cp950",
        ]

        loaded = False

        for encoding in encodings:

            try:

                with open(
                    file_path,
                    "r",
                    encoding=encoding
                ) as f:

                    text = f.read()

                print(
                    f"TXT 編碼：{encoding}"
                )

                loaded = True

                break

            except UnicodeDecodeError:

                pass

        if not loaded:

            with open(
                file_path,
                "r",
                encoding="utf-8",
                errors="ignore"
            ) as f:

                text = f.read()

    else:

        raise ValueError(
            f"不支援的檔案格式：{ext}"
        )

    return text


# ============================================================
# 清洗文字
# ============================================================

def clean_text(text):

    if not text:

        return ""

    text = text.replace(
        "\r\n",
        "\n"
    )

    text = text.replace(
        "\r",
        "\n"
    )

    text = text.replace(
        "\u00a0",
        " "
    )

    # 多個空白
    text = re.sub(
        r"[ \t]+",
        " ",
        text
    )

    # 多個換行
    text = re.sub(
        r"\n+",
        " ",
        text
    )

    # 多個空白
    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# 中文切句
# ============================================================

def split_into_sentences(
    text
):

    text = clean_text(
        text
    )

    if not text:

        return []

    # --------------------------------------------------------
    # 第一層切句
    # --------------------------------------------------------

    sentences = re.split(
        r"(?<=[。！？!?；;])",
        text
    )

    result = []

    for sentence in sentences:

        sentence = sentence.strip()

        if not sentence:

            continue

        # ----------------------------------------------------
        # 避免單句太長
        # ----------------------------------------------------

        if len(sentence) > 500:

            sub_sentences = re.split(
                r"(?<=[，,：:])",
                sentence
            )

            buffer = ""

            for sub in sub_sentences:

                sub = sub.strip()

                if not sub:

                    continue

                if (
                    len(buffer)
                    + len(sub)
                    <= 500
                ):

                    buffer += sub

                else:

                    if buffer:

                        result.append(
                            buffer
                        )

                    buffer = sub

            if buffer:

                result.append(
                    buffer
                )

        else:

            result.append(
                sentence
            )

    return result


# ============================================================
# Edge TTS
# ============================================================

async def generate_sentence_audio(
    sentence,
    output_file
):

    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):

        try:

            communicate = edge_tts.Communicate(
                sentence,
                VOICE
            )

            await communicate.save(
                output_file
            )

            # ------------------------------------------------
            # 確認檔案
            # ------------------------------------------------

            if not os.path.exists(
                output_file
            ):

                raise RuntimeError(
                    "TTS 沒有產生 MP3"
                )

            if os.path.getsize(
                output_file
            ) == 0:

                raise RuntimeError(
                    "TTS 產生空 MP3"
                )

            # ------------------------------------------------
            # 確認 MP3 frame
            # ------------------------------------------------

            duration = get_mp3_duration(
                output_file
            )

            if duration <= 0:

                raise RuntimeError(
                    "無法解析 TTS MP3 frame"
                )

            return True

        except Exception as e:

            print(
                f"TTS 失敗 "
                f"({attempt}/{MAX_RETRIES})"
            )

            print(
                f"       {e}"
            )

            try:

                if os.path.exists(
                    output_file
                ):

                    os.remove(
                        output_file
                    )

            except Exception:
                pass

            if attempt < MAX_RETRIES:

                wait_seconds = (
                    attempt * 3
                )

                print(
                    f"等待 "
                    f"{wait_seconds} 秒後重試..."
                )

                await asyncio.sleep(
                    wait_seconds
                )

    return False


# ============================================================
# 找出所有檔案
# ============================================================

def find_input_files(
    input_dir
):

    files = []

    for root, dirs, filenames in os.walk(
        input_dir
    ):

        # 排序
        dirs.sort()
        filenames.sort()

        for filename in filenames:

            ext = os.path.splitext(
                filename
            )[1].lower()

            if ext in SUPPORTED_EXTENSIONS:

                full_path = os.path.join(
                    root,
                    filename
                )

                files.append(
                    full_path
                )

    return files


# ============================================================
# 取得輸出資料夾
# ============================================================

def get_output_dir(
    input_dir,
    input_file,
    output_root
):

    relative_path = os.path.relpath(
        input_file,
        input_dir
    )

    relative_dir = os.path.dirname(
        relative_path
    )

    filename = os.path.basename(
        relative_path
    )

    stem = os.path.splitext(
        filename
    )[0]

    stem = safe_filename(
        stem
    )

    audio_dir = (
        stem + "_audio"
    )

    if relative_dir == "":

        return os.path.join(
            output_root,
            audio_dir
        )

    return os.path.join(
        output_root,
        relative_dir,
        audio_dir
    )


# ============================================================
# 儲存失敗清單
# ============================================================

def save_failed_sentences(
    output_dir,
    failed_sentences
):

    if not failed_sentences:

        return

    failed_file = os.path.join(
        output_dir,
        "tts_failed.txt"
    )

    with open(
        failed_file,
        "w",
        encoding="utf-8"
    ) as f:

        for index, sentence in (
            failed_sentences
        ):

            f.write(
                f"{index}\t{sentence}\n"
            )

    print()
    print(
        f"TTS 失敗："
        f"{len(failed_sentences)} 句"
    )

    print(
        f"失敗清單："
        f"{failed_file}"
    )


# ============================================================
# 處理單一檔案
# ============================================================

async def process_single_file(
    input_file,
    input_dir,
    output_root
):

    print()
    print()
    print("=" * 80)
    print("開始處理檔案")
    print("=" * 80)

    print(
        f"來源：{input_file}"
    )

    output_dir = get_output_dir(
        input_dir,
        input_file,
        output_root
    )

    os.makedirs(
        output_dir,
        exist_ok=True
    )

    print(
        f"輸出：{output_dir}"
    )

    print("=" * 80)

    # ========================================================
    # 讀取
    # ========================================================

    print()
    print("【1/3】讀取文字")

    try:

        raw_text = extract_text_from_file(
            input_file
        )

    except Exception as e:

        print(
            f"讀取失敗：{e}"
        )

        return False

    print(
        f"文字長度："
        f"{len(raw_text):,} 字"
    )

    # ========================================================
    # 切句
    # ========================================================

    print()
    print("【2/3】切分句子")

    sentences = split_into_sentences(
        raw_text
    )

    total_sentences = len(
        sentences
    )

    print(
        f"總句數："
        f"{total_sentences:,}"
    )

    if not sentences:

        print(
            "沒有有效文字。"
        )

        return False

    # ========================================================
    # 顯示前 5 句
    # ========================================================

    print()
    print("前 5 句：")

    for i, sentence in enumerate(
        sentences[:5],
        1
    ):

        print(
            f"{i}. {sentence[:100]}"
        )

    # ========================================================
    # 暫存目錄
    # ========================================================

    temp_dir = os.path.join(
        output_dir,
        "_temp"
    )

    os.makedirs(
        temp_dir,
        exist_ok=True
    )

    # ========================================================
    # TTS
    # ========================================================

    print()
    print("【3/3】開始 TTS")
    print()

    failed_sentences = []

    # --------------------------------------------------------
    # 目前 part
    # --------------------------------------------------------

    part_number = 1

    current_files = []

    current_duration = 0.0

    # ========================================================
    # 逐句處理
    # ========================================================

    try:

        for index, sentence in enumerate(
            sentences,
            1
        ):

            print()
            print(
                "-" * 70
            )

            print(
                f"[{index}/{total_sentences}] "
                f"{index / total_sentences * 100:.1f}%"
            )

            print(
                f"目前 MP3："
                f"part_{part_number:03d}.mp3"
            )

            print(
                f"目前長度："
                f"{format_duration(current_duration)}"
                f" / "
                f"{format_duration(TARGET_SECONDS)}"
            )

            print(
                f"文字："
                f"{sentence[:120]}"
            )

            # ------------------------------------------------
            # 每一句獨立暫存
            # ------------------------------------------------

            temp_file = os.path.join(
                temp_dir,
                f"sentence_{index:08d}.mp3"
            )

            sentence_duration = 0.0

            # ------------------------------------------------
            # 如果已經存在暫存檔
            #
            # 中途中斷後再次執行可以直接使用。
            # ------------------------------------------------

            if os.path.exists(
                temp_file
            ):

                sentence_duration = (
                    get_mp3_duration(
                        temp_file
                    )
                )

                if sentence_duration > 0:

                    print(
                        "使用已存在暫存音訊"
                    )

                else:

                    try:

                        os.remove(
                            temp_file
                        )

                    except Exception:
                        pass

            # ------------------------------------------------
            # 沒有暫存檔 → TTS
            # ------------------------------------------------

            if sentence_duration <= 0:

                print(
                    "Edge TTS..."
                )

                success = (
                    await generate_sentence_audio(
                        sentence,
                        temp_file
                    )
                )

                if not success:

                    print(
                        "此句失敗，"
                        "繼續下一句。"
                    )

                    failed_sentences.append(
                        (
                            index,
                            sentence
                        )
                    )

                    continue

                sentence_duration = (
                    get_mp3_duration(
                        temp_file
                    )
                )

            print(
                f"音訊："
                f"{format_duration(sentence_duration)}"
            )

            # =================================================
            # 判斷是否超過 1 小時
            #
            # 不拆句。
            # =================================================

            if (
                current_files
                and
                current_duration
                + sentence_duration
                > TARGET_SECONDS
            ):

                # ------------------------------------------------
                # 先完成目前 part
                # ------------------------------------------------

                output_file = os.path.join(
                    output_dir,
                    f"part_{part_number:03d}.mp3"
                )

                print()
                print(
                    "達到約 1 小時，"
                    "正在合併 MP3..."
                )

                print(
                    f"輸出："
                    f"{output_file}"
                )

                success = merge_mp3_files(
                    current_files,
                    output_file
                )

                if not success:

                    print(
                        "MP3 合併失敗"
                    )

                    return False

                actual_duration = (
                    get_mp3_duration(
                        output_file
                    )
                )

                print(
                    f"完成："
                    f"{output_file}"
                )

                print(
                    f"實際長度："
                    f"{format_duration(actual_duration)}"
                )

                # ------------------------------------------------
                # 刪除已經合併的暫存檔
                # ------------------------------------------------

                for f in current_files:

                    try:

                        os.remove(f)

                    except Exception:
                        pass

                # ------------------------------------------------
                # 下一段
                # ------------------------------------------------

                part_number += 1

                current_files = []

                current_duration = 0.0

            # ------------------------------------------------
            # 把目前句子加入新 part
            # ------------------------------------------------

            current_files.append(
                temp_file
            )

            current_duration += (
                sentence_duration
            )

            print(
                f"    → 累積："
                f"{format_duration(current_duration)}"
            )

            await asyncio.sleep(
                SLEEP_BETWEEN_SENTENCES
            )

        # ====================================================
        # 最後一段
        # ====================================================

        if current_files:

            output_file = os.path.join(
                output_dir,
                f"part_{part_number:03d}.mp3"
            )

            print()
            print("=" * 70)

            print(
                f"正在建立最後一段："
                f"{output_file}"
            )

            success = merge_mp3_files(
                current_files,
                output_file
            )

            if not success:

                print(
                    "最後 MP3 合併失敗"
                )

                return False

            actual_duration = (
                get_mp3_duration(
                    output_file
                )
            )

            print(
                f"完成："
                f"{output_file}"
            )

            print(
                f"實際長度："
                f"{format_duration(actual_duration)}"
            )

            # ------------------------------------------------
            # 刪除暫存
            # ------------------------------------------------

            for f in current_files:

                try:

                    os.remove(f)

                except Exception:
                    pass

    finally:

        # ----------------------------------------------------
        # 儲存失敗清單
        # ----------------------------------------------------

        save_failed_sentences(
            output_dir,
            failed_sentences
        )

        # ----------------------------------------------------
        # 如果沒有剩餘暫存檔，就刪除 _temp
        # ----------------------------------------------------

        try:

            if os.path.exists(
                temp_dir
            ):

                remaining = os.listdir(
                    temp_dir
                )

                if not remaining:

                    os.rmdir(
                        temp_dir
                    )

        except Exception:
            pass

    # ========================================================
    # 完成
    # ========================================================

    print()
    print("=" * 80)

    print(
        f"完成："
        f"{os.path.basename(input_file)}"
    )

    print(
        f"MP3 數量："
        f"{part_number}"
    )

    if failed_sentences:

        print(
            f"失敗句數："
            f"{len(failed_sentences)}"
        )

    else:

        print(
            "所有句子成功"
        )

    print("=" * 80)

    return True


# ============================================================
# 處理整個目錄
# ============================================================

async def process_directory(
    input_dir,
    output_root
):

    if not os.path.isdir(
        input_dir
    ):

        print(
            f"找不到目錄："
            f"{input_dir}"
        )

        return

    # ========================================================
    # 搜尋
    # ========================================================

    print()
    print("=" * 80)
    print("搜尋 PDF / HTML / TXT")
    print("=" * 80)

    files = find_input_files(
        input_dir
    )

    print(
        f"找到 {len(files)} 個檔案"
    )

    if not files:

        print(
            "沒有找到支援的檔案。"
        )

        return

    print()

    for i, file_path in enumerate(
        files,
        1
    ):

        relative = os.path.relpath(
            file_path,
            input_dir
        )

        print(
            f"{i:04d}. {relative}"
        )

    # ========================================================
    # 建立輸出目錄
    # ========================================================

    os.makedirs(
        output_root,
        exist_ok=True
    )

    success_count = 0

    failed_count = 0

    # ========================================================
    # 逐檔處理
    # ========================================================

    for number, input_file in enumerate(
        files,
        1
    ):

        print()
        print()
        print("#" * 80)

        print(
            f"檔案進度："
            f"{number}/{len(files)}"
        )

        print("#" * 80)

        try:

            success = (
                await process_single_file(
                    input_file,
                    input_dir,
                    output_root
                )
            )

            if success:

                success_count += 1

            else:

                failed_count += 1

        except KeyboardInterrupt:

            print()
            print(
                "使用者中止。"
            )

            print(
                "已完成 MP3 會保留。"
            )

            return

        except Exception as e:

            failed_count += 1

            print(
                f"發生錯誤：{e}"
            )

            print(
                "繼續下一個檔案..."
            )

    # ========================================================
    # 全部完成
    # ========================================================

    print()
    print()
    print("=" * 80)

    print("全部完成！")

    print("=" * 80)

    print(
        f"總檔案："
        f"{len(files)}"
    )

    print(
        f"成功："
        f"{success_count}"
    )

    print(
        f"失敗："
        f"{failed_count}"
    )

    print(
        f"輸出："
        f"{output_root}"
    )

    print("=" * 80)


# ============================================================
# 主程式
# ============================================================

def main():

    # ========================================================
    # 修改這裡
    # ========================================================

    # --------------------------------------------------------
    # 原始資料夾
    #
    # 程式會搜尋所有深層子目錄。
    # --------------------------------------------------------

    INPUT_DIR = r"./"

    # --------------------------------------------------------
    # MP3 輸出資料夾
    # --------------------------------------------------------

    OUTPUT_ROOT = r"./audio"

    # ========================================================
    # 不要修改下面
    # ========================================================

    print()
    print("=" * 80)
    print("PDF / HTML / TXT → Edge TTS")
    print("純 Python MP3 合併版")
    print("=" * 80)

    print(
        f"輸入：{INPUT_DIR}"
    )

    print(
        f"輸出：{OUTPUT_ROOT}"
    )

    print(
        f"語音：{VOICE}"
    )

    print(
        f"每段："
        f"{format_duration(TARGET_SECONDS)}"
    )

    print()
    print(
        "不使用 FFmpeg"
    )

    print(
        "不使用 FFprobe"
    )

    print(
        "不使用 pydub"
    )

    print("=" * 80)

    try:

        asyncio.run(
            process_directory(
                INPUT_DIR,
                OUTPUT_ROOT
            )
        )

    except KeyboardInterrupt:

        print()
        print(
            "使用者中止程式。"
        )

    except Exception as e:

        print()
        print("=" * 80)

        print(
            f"程式錯誤："
            f"{type(e).__name__}: {e}"
        )

        print("=" * 80)


# ============================================================
# 執行
# ============================================================

if __name__ == "__main__":

    main()

