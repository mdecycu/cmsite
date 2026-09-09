import os
import shutil
import re
import mobi
from opencc import OpenCC

def convert_mobi_to_structured_html():
    # 取得目前腳本目錄
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mobi_path = os.path.join(current_dir, '1.mobi')
    html_out_path = os.path.join(current_dir, '1.html')
    
    # 定義目標子目錄
    images_dir = os.path.join(current_dir, 'images')
    static_dir = os.path.join(current_dir, 'static')
    
    if not os.path.exists(mobi_path):
        print(f"錯誤：找不到檔案 {mobi_path}")
        return

    print("正在解析 MOBI 檔案...")
    # temp_dir 內包含解壓出的所有檔案
    temp_dir, html_file_path = mobi.extract(mobi_path)
    
    try:
        # 清理並重建 images 與 static 資料夾，確保目錄乾淨
        for folder in [images_dir, static_dir]:
            if os.path.exists(folder):
                shutil.rmtree(folder)
            os.makedirs(folder)

        print("正在遞迴搜尋書中所有插圖...")
        # 2026/09 改用 os.walk 進行地毯式搜尋，支援所有深度的子目錄
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
        image_count = 0
        
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.lower().endswith(image_extensions):
                    src_image_path = os.path.join(root, file)
                    dest_image_path = os.path.join(images_dir, file)
                    # 複製圖片到目標的 images 子目錄
                    shutil.copy(src_image_path, dest_image_path)
                    image_count += 1
                    
        print(f"成功提取了 {image_count} 張圖片到 images/ 目錄。")

        print("正在讀取原文內容並轉換為繁體...")
        with open(html_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            html_content = f.read()
            
        # 逐字簡轉繁（不轉換用語）
        cc = OpenCC('s2t')
        traditional_html = cc.convert(html_content)
        
        print("正在修正 HTML 的圖片路徑...")
        # 使用正規表達式，將不論是 src="OEBPS/Images/01.jpg"、src="./01.jpg" 或 src="1_files/01.jpg"
        # 統一模糊比對，只擷取檔名部分，並強制作為 src="images/檔名.副檔名"
        fixed_html = re.sub(r'src=["\'][^"\']*/([^"\']+?\.[a-zA-Z0-9]+)["\']', r'src="images/\1"', traditional_html)

        print("正在生成獨立 CSS 檔案並寫入 static 子目錄...")
        # 護眼易讀性樣式
        css_content = """body {
    background-color: #f6f1e5 !important;
    color: #2c2c2c !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", "Microsoft JhengHei", "PingFang TC", sans-serif !important; 
    line-height: 1.8 !important;
    letter-spacing: 0.05em !important;
    max-width: 800px !important;
    margin: 0 auto !important;
    padding: 40px 20px !important;
    font-size: 18px !important;
}
p {
    margin-bottom: 1.5em !important;
    text-align: justify !important;
}
h1, h2, h3, h4, h5, h6 {
    color: #1a1a1a !important;
    margin-top: 2em !important;
    margin-bottom: 1em !important;
    border-bottom: 1px solid #e0dad0;
    padding-bottom: 0.3em;
}
img {
    max-width: 100% !important;
    height: auto !important;
    display: block;
    margin: 20px auto !important;
}
* {
    background-color: transparent !important;
}"""
        
        # 寫入 static/style.css
        css_path = os.path.join(static_dir, 'style.css')
        with open(css_path, 'w', encoding='utf-8') as f:
            f.write(css_content)

        print("正在引入外部 CSS 樣式至 HTML...")
        css_link = '<link rel="stylesheet" type="text/css" href="static/style.css">\n'
        
        if "</head>" in fixed_html:
            final_html = fixed_html.replace("</head>", f"{css_link}</head>")
        else:
            final_html = css_link + fixed_html
            
        # 寫入同目錄下的 1.html
        with open(html_out_path, 'w', encoding='utf-8') as f:
            f.write(final_html)
            
        print(f"\n轉換成功！目錄結構已就緒：")
        print(f"├── 1.html (主要網頁)")
        print(f"├── images/ (已擷取 {image_count} 張圖片)")
        print(f"└── static/ (style.css 樣式表)")
        
    except Exception as e:
        print(f"轉換過程中出錯：{e}")
        
    finally:
        # 清理解壓出來的臨時垃圾檔案
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

if __name__ == '__main__':
    convert_mobi_to_structured_html()
