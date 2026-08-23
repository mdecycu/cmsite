from pathlib import Path
import struct
import sys


def binary_stl_to_ascii(input_file):
    """
    將 Binary STL 轉換成 ASCII STL。

    使用方式：
        python binary_to_ascii.py my_binary.stl

    輸出：
        my_binary_ascii.stl

    注意：
        輸入檔名可以包含中文。
        輸出的 STL 內部 solid name 固定使用 ASCII，
        避免舊版 CAD 系統發生編碼問題。
    """

    input_path = Path(input_file)

    if not input_path.exists():
        raise FileNotFoundError(
            f"找不到輸入檔案：{input_path}"
        )

    if not input_path.is_file():
        raise ValueError(
            f"輸入路徑不是檔案：{input_path}"
        )

    # ------------------------------------------------------------
    # 自動產生輸出檔名
    #
    # 工具座1-1.stl
    #
    # →
    #
    # 工具座1-1_ascii.stl
    # ------------------------------------------------------------

    output_path = input_path.with_name(
        input_path.stem + "_ascii.stl"
    )

    print("=" * 70)
    print("Binary STL → ASCII STL")
    print("=" * 70)
    print()

    print(f"輸入檔案：{input_path}")
    print(f"輸出檔案：{output_path}")
    print()

    # ------------------------------------------------------------
    # 讀取 Binary STL
    #
    # Binary STL：
    #
    # 80 bytes  Header
    # 4 bytes   Triangle count
    #
    # 每個 Triangle：
    #
    # 12 bytes  Normal
    # 36 bytes  3 Vertices
    # 2 bytes   Attribute
    #
    # 每個 triangle = 50 bytes
    # ------------------------------------------------------------

    with open(input_path, "rb") as f:

        header = f.read(80)

        if len(header) != 80:
            raise ValueError(
                "檔案不足 80 bytes，"
                "不是有效的 Binary STL。"
            )

        count_data = f.read(4)

        if len(count_data) != 4:
            raise ValueError(
                "無法讀取 Binary STL 的 Triangle Count。"
            )

        triangle_count = struct.unpack(
            "<I",
            count_data
        )[0]

        print(
            f"Triangle 數量："
            f"{triangle_count:,}"
        )

        # --------------------------------------------------------
        # 檢查檔案大小
        # --------------------------------------------------------

        expected_size = (
            84 +
            triangle_count * 50
        )

        actual_size = input_path.stat().st_size

        print(
            f"實際檔案大小："
            f"{actual_size:,} bytes"
        )

        print(
            f"預期檔案大小："
            f"{expected_size:,} bytes"
        )

        if actual_size != expected_size:

            raise ValueError(
                "\n"
                "Binary STL 檔案大小與 "
                "Triangle Count 不一致。\n\n"
                f"預期大小：{expected_size:,} bytes\n"
                f"實際大小：{actual_size:,} bytes\n\n"
                "可能原因：\n"
                "1. 檔案不是標準 Binary STL\n"
                "2. STL 檔案已損壞\n"
                "3. STL 使用特殊格式\n"
            )

        print()
        print("開始讀取 Triangle...")

        triangles = []

        # --------------------------------------------------------
        # 逐一讀取 Triangle
        # --------------------------------------------------------

        for i in range(triangle_count):

            # Normal + 3 vertices = 48 bytes
            data = f.read(48)

            if len(data) != 48:

                raise ValueError(
                    f"讀取第 {i + 1:,} 個 Triangle "
                    "時資料不足。"
                )

            values = struct.unpack(
                "<12f",
                data
            )

            # Normal
            normal = values[0:3]

            # Vertex 1
            v1 = values[3:6]

            # Vertex 2
            v2 = values[6:9]

            # Vertex 3
            v3 = values[9:12]

            # Attribute byte count
            attribute = f.read(2)

            if len(attribute) != 2:

                raise ValueError(
                    f"讀取第 {i + 1:,} 個 Triangle "
                    "的 Attribute 時資料不足。"
                )

            triangles.append(
                (
                    normal,
                    v1,
                    v2,
                    v3
                )
            )

            # ----------------------------------------------------
            # 顯示讀取進度
            # ----------------------------------------------------

            if (
                (i + 1) % 10000 == 0
                or i + 1 == triangle_count
            ):

                percent = (
                    (i + 1)
                    / triangle_count
                    * 100
                )

                print(
                    f"\r讀取："
                    f"{i + 1:,}/"
                    f"{triangle_count:,} "
                    f"({percent:6.2f}%)",
                    end="",
                    flush=True
                )

    print()
    print()

    # ------------------------------------------------------------
    # ASCII STL 的 solid name
    #
    # 不使用原始中文檔名。
    #
    # 這是為了兼容舊版 CAD / NX。
    # ------------------------------------------------------------

    solid_name = "stl_model"

    print(
        f"ASCII STL solid name：{solid_name}"
    )

    print()
    print("開始建立 ASCII STL...")

    # ------------------------------------------------------------
    # 寫出 ASCII STL
    # ------------------------------------------------------------

    with open(
        output_path,
        "w",
        encoding="ascii",
        newline="\n"
    ) as f:

        f.write(
            f"solid {solid_name}\n"
        )

        for i, triangle in enumerate(
            triangles
        ):

            normal, v1, v2, v3 = triangle

            nx, ny, nz = normal

            # ----------------------------------------------------
            # facet normal
            # ----------------------------------------------------

            f.write(
                "  facet normal "
                f"{nx:.9g} "
                f"{ny:.9g} "
                f"{nz:.9g}\n"
            )

            f.write(
                "    outer loop\n"
            )

            # ----------------------------------------------------
            # Vertex 1
            # ----------------------------------------------------

            f.write(
                "      vertex "
                f"{v1[0]:.9g} "
                f"{v1[1]:.9g} "
                f"{v1[2]:.9g}\n"
            )

            # ----------------------------------------------------
            # Vertex 2
            # ----------------------------------------------------

            f.write(
                "      vertex "
                f"{v2[0]:.9g} "
                f"{v2[1]:.9g} "
                f"{v2[2]:.9g}\n"
            )

            # ----------------------------------------------------
            # Vertex 3
            # ----------------------------------------------------

            f.write(
                "      vertex "
                f"{v3[0]:.9g} "
                f"{v3[1]:.9g} "
                f"{v3[2]:.9g}\n"
            )

            f.write(
                "    endloop\n"
            )

            f.write(
                "  endfacet\n"
            )

            # ----------------------------------------------------
            # 顯示寫入進度
            # ----------------------------------------------------

            if (
                (i + 1) % 10000 == 0
                or i + 1 == triangle_count
            ):

                percent = (
                    (i + 1)
                    / triangle_count
                    * 100
                )

                print(
                    f"\r寫入："
                    f"{i + 1:,}/"
                    f"{triangle_count:,} "
                    f"({percent:6.2f}%)",
                    end="",
                    flush=True
                )

        f.write(
            f"endsolid {solid_name}\n"
        )

    print()
    print()

    print("=" * 70)
    print("轉換完成")
    print("=" * 70)
    print()

    print(f"輸出檔案：{output_path}")
    print(
        f"Triangle 數量："
        f"{triangle_count:,}"
    )

    print()


def main():

    # ------------------------------------------------------------
    # 使用方式：
    #
    # python binary_to_ascii.py my_binary.stl
    # ------------------------------------------------------------

    if len(sys.argv) != 2:

        print()
        print(
            "使用方式："
        )

        print()

        print(
            "    python binary_to_ascii.py my_binary.stl"
        )

        print()

        print(
            "例如："
        )

        print(
            "    python binary_to_ascii.py 工具座1-1.stl"
        )

        print()

        print(
            "輸出："
        )

        print(
            "    工具座1-1_ascii.stl"
        )

        print()

        sys.exit(1)

    input_file = sys.argv[1]

    try:

        binary_stl_to_ascii(
            input_file
        )

    except Exception as e:

        print()
        print("=" * 70)
        print("錯誤")
        print("=" * 70)
        print()
        print(str(e))
        print()

        sys.exit(1)


if __name__ == "__main__":
    main()
