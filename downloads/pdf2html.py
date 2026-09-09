# pip install pdfplumber pypdf opencc
# 從 ./pdf 目錄將所有 pdf 檔案轉為 ./dist 目錄中的 html 檔案
import os
import re
from pathlib import Path
import pdfplumber
from pypdf import PdfReader
from opencc import OpenCC

# 初始化簡體轉繁體轉換器 (s2t: Simplified Chinese to Traditional Chinese)
cc = OpenCC('s2t')

SITE_TITLE = cc.convert("PDF 轉檔繁體文件中心")

CSS_STYLE = """
<style>
    body { font-family: 'Segoe UI', 'Microsoft JhengHei', sans-serif; line-height: 1.8; max-width: 900px; margin: 40px auto; padding: 0 20px; color: #333; background-color: #fdfdfd; }
    h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 12px; }
    h2 { color: #16a085; border-bottom: 2px solid #eee; padding-bottom: 8px; margin-top: 30px; }
    .card { background: #fff; border: 1px solid #e9ecef; padding: 25px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    .btn { display: inline-block; padding: 8px 16px; margin-bottom: 20px; background-color: #95a5a6; color: white; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 14px; transition: background 0.2s; }
    .btn:hover { background-color: #7f8c8d; }
    .page-box { border-left: 4px solid #3498db; padding-left: 15px; margin-bottom: 30px; }
    .page-number { font-size: 12px; font-weight: bold; color: #7f8c8d; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
    p { margin-bottom: 12px; white-space: pre-line; word-break: break-word; }
    
    /* 目錄與章節導覽樣式 */
    .toc-box { background: #f8f9fa; border: 1px solid #e9ecef; padding: 20px; border-radius: 8px; margin-bottom: 25px; }
    .toc-box h3 { margin-top: 0; color: #2c3e50; font-size: 18px; border-bottom: 2px solid #ddd; padding-bottom: 8px; }
    ul.toc-list, ul.file-list { list-style-type: none; padding-left: 0; }
    ul.toc-list li, ul.file-list li { margin: 8px 0; }
    ul.toc-list ul { padding-left: 20px; margin-top: 5px; }
    ul.toc-list a, ul.file-list a { color: #2980b9; text-decoration: none; font-weight: bold; font-size: 15px; }
    ul.toc-list a:hover, ul.file-list a:hover { text-decoration: underline; color: #3498db; }
    .toc-page { font-size: 12px; color: #7f8c8d; font-weight: normal; margin-left: 8px; }
</style>
"""

def extract_pdf_outline(pdf_path):
    """使用 pypdf 提取 PDF 的大綱（書籤）結構與對應頁碼"""
    outline_data = []
    try:
        reader = PdfReader(pdf_path)
        if reader.outline:
            def parse_outline(outline_items):
                for item in outline_items:
                    if isinstance(item, list):
                        parse_outline(item)
                    else:
                        try:
                            title = getattr(item, 'title', '未命名章節')
                            # 取得書籤指向的頁碼
                            page_idx = reader.get_destination_page_number(item) + 1
                            outline_data.append({
                                "title": cc.convert(str(title)),
                                "page": page_idx
                            })
                        except Exception:
                            continue
            parse_outline(reader.outline)
    except Exception as e:
        print(f"解析 PDF 大綱失敗 [{pdf_path.name}]: {e}")
    return outline_data

def convert_pdf_to_html(pdf_path, output_html_path, rel_to_root):
    """讀取單一 PDF，提取大綱與頁面文字，簡轉繁後寫入 HTML 檔案"""
    page_blocks = []
    
    # 1. 提取 PDF 原有章節大綱
    outline = extract_pdf_outline(pdf_path)
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            for page_idx, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                # 每一頁加入 id 錨點以便章節連結定位
                page_anchor = f'<div id="page-{page_idx}" class="page-box">'
                
                if text:
                    text_tc = cc.convert(text)
                    safe_text = text_tc.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    
                    page_html = f"""
                    {page_anchor}
                        <div class="page-number">第 {page_idx} 頁 / 共 {total_pages} 頁</div>
                        <p>{safe_text}</p>
                    </div>
                    """
                else:
                    page_html = f"""
                    {page_anchor}
                        <div class="page-number">第 {page_idx} 頁 / 共 {total_pages} 頁</div>
                        <p style="color: #999; font-style: italic;">(此頁面無可提取之文字，可能為純圖片掃描頁)</p>
                    </div>
                    """
                page_blocks.append(page_html)
    except Exception as e:
        print(f"讀取 PDF 失敗 [{pdf_path.name}]: {e}")
        return False

    # 2. 建立頁面內建章節導覽列 (TOC)
    toc_html = ""
    if outline:
        toc_items_html = ""
        for item in outline:
            toc_items_html += f'<li><a href="#page-{item["page"]}">📄 {item["title"]}</a> <span class="toc-page">(第 {item["page"]} 頁)</span></li>'
        
        toc_html = f"""
        <div class="toc-box">
            <h3>📑 {cc.convert("文件章節目錄")}</h3>
            <ul class="toc-list">
                {toc_items_html}
            </ul>
        </div>
        """

    doc_title = cc.convert(pdf_path.stem)
    content_body = "".join(page_blocks) if page_blocks else "<p>無可顯示內容</p>"

    full_html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{doc_title} - {SITE_TITLE}</title>
    {CSS_STYLE}
</head>
<body>
    <a href="{rel_to_root}index.html" class="btn">{cc.convert("回全站首頁")}</a>
    <h1>📄 {doc_title}</h1>
    {toc_html}
    <div class="card">
        {content_body}
    </div>
</body>
</html>
"""

    output_html_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_html_path, 'w', encoding='utf-8') as f:
        f.write(full_html)
        
    return True

def build_pdf_site(source_dir="./", output_dir="./dist"):
    """主程序：掃描 PDF、轉檔繁體 HTML、建立 index.html 導覽頁"""
    src_path = Path(source_dir).resolve()
    out_path = Path(output_dir).resolve()

    out_path.mkdir(parents=True, exist_ok=True)
    pdf_files = list(src_path.rglob("*.pdf"))

    if not pdf_files:
        print(f"在 '{source_dir}' 目錄中未找到任何 .pdf 檔案。")
        return

    print(f"找到 {len(pdf_files)} 個 PDF 檔案，開始檢查是否需要轉換...\n" + "─" * 60)

    all_docs = []
    converted_count = 0
    skipped_count = 0
    failed_count = 0

    for idx, pdf_file in enumerate(pdf_files, 1):
        rel_path = pdf_file.relative_to(src_path)
        out_html_path = out_path / rel_path.with_suffix(".html")

        depth = len(rel_path.parts) - 1
        rel_to_root = "../" * depth if depth > 0 else "./"
        rel_html_str = str(rel_path.with_suffix(".html")).replace('\\', '/')
        doc_title = cc.convert(pdf_file.stem)

        if out_html_path.exists():
            skipped_count += 1
            print(f"[{idx}/{len(pdf_files)}] 跳過轉換: {rel_path}")
            all_docs.append({
                "title": doc_title,
                "path": rel_html_str,
                "dir": str(rel_path.parent) if str(rel_path.parent) != '.' else "根目錄"
            })
            continue

        print(f"[{idx}/{len(pdf_files)}] 正在轉換: {rel_path}")
        if convert_pdf_to_html(pdf_file, out_html_path, rel_to_root):
            converted_count += 1
            all_docs.append({
                "title": doc_title,
                "path": rel_html_str,
                "dir": str(rel_path.parent) if str(rel_path.parent) != '.' else "根目錄"
            })
            print(f"    └─ 成功 ->{out_html_path.relative_to(out_path)}")
        else:
            failed_count += 1

    # 生成 index.html
    dir_structure = {}
    for doc in all_docs:
        d = doc["dir"]
        if d not in dir_structure:
            dir_structure[d] = []
        dir_structure[d].append(doc)

    if not dir_structure:
        index_body = f"""<div class="card"><p>{cc.convert("目前沒有可顯示的文件。")}</p></div>"""
    else:
        index_body = f"<h2>{cc.convert('文件檔案列表')}</h2>"
        for dir_name, docs in dir_structure.items():
            dir_display = cc.convert(dir_name)
            index_body += f"<div class='card'><h3>{dir_display}</h3><ul class='file-list'>"
            for doc in docs:
                index_body += f"<li><a href='{doc['path']}'>📄 {doc['title']}</a></li>"
            index_body += "</ul></div>"

    index_html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{SITE_TITLE}</title>
    {CSS_STYLE}
</head>
<body>
    <h1>{SITE_TITLE}</h1>
    <div class="card">
        <p>
            PDF 總數：{len(pdf_files)} 
            本次轉換：{converted_count} 
            已存在跳過：{skipped_count} 
            失敗：{failed_count}
        </p>
    </div>
    {index_body}
</body>
</html>
"""

    with open(out_path / "index.html", 'w', encoding='utf-8') as f:
        f.write(index_html)

    print("─" * 60)
    print("處理完成！")
    print(f"PDF 總數：{len(pdf_files)}")
    print(f"本次轉換：{converted_count}")
    print(f"已存在跳過：{skipped_count}")
    print(f"轉換失敗：{failed_count}")
    print(f"輸出目錄：'{output_dir}'")
    print(f"請開啟 '{output_dir}/index.html' 瀏覽所有文件。")

if __name__ == "__main__":
    SOURCE_PDF_DIR = "./pdf"
    OUTPUT_HTML_DIR = "./dist"

    build_pdf_site(SOURCE_PDF_DIR, OUTPUT_HTML_DIR)