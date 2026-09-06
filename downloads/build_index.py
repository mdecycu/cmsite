import os
import json
import re
from bs4 import BeautifulSoup  # 如果沒有此套件，請在終端機執行: pip install beautifulsoup4 lxml

def extract_title(html_path):
    """從 HTML 檔案中提取標題，作為搜尋結果顯示的名稱"""
    try:
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            soup = BeautifulSoup(f.read(), 'lxml')
            if soup.title and soup.title.string:
                return soup.title.string.strip()
            # 退而求其次尋找 h1 或 h2
            h1 = soup.find(['h1', 'h2'])
            if h1:
                return h1.get_text().strip()
    except Exception:
        pass
    return os.path.basename(html_path)

def generate_sub_index(dir_path, root_path):
    """在子目錄中生成導覽 index.html (若原先不存在)"""
    index_file = os.path.join(dir_path, 'index.html')
    if os.path.exists(index_file):
        return # 如果本來就有 index.html，就不覆蓋它

    items = os.listdir(dir_path)
    sub_dirs = [d for d in items if os.path.isdir(os.path.join(dir_path, d))]
    html_files = [f for f in items if f.endswith('.html') and f != 'index.html']

    if not sub_dirs and not html_files:
        return

    rel_path_to_root = os.path.relpath(root_path, dir_path).replace('\\', '/')
    dir_name = os.path.basename(dir_path)

    html_content = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <title>目錄: {dir_name}</title>
    <style>
        body {{ font-family: sans-serif; line-height: 1.6; padding: 20px; background: #f8f9fa; }}
        h1 {{ color: #203a43; border-bottom: 2px solid #2c5364; padding-bottom: 10px; }}
        ul {{ list-style-type: none; padding-left: 0; }}
        li {{ margin-bottom: 8px; background: #fff; padding: 10px; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        a {{ text-decoration: none; color: #007bff; font-weight: bold; }}
        a:hover {{ text-decoration: underline; }}
        .nav {{ margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="nav"><a href="{rel_path_to_root}/index.html">🏠 回首頁(搜尋頁)</a></div>
    <h1>子目錄導覽: {dir_name}</h1>
    
    <h3>📁 子資料夾</h3>
    <ul>
    """
    for sd in sub_dirs:
        html_content += f'        <li>📁 <a href="./{sd}/index.html">{sd}</a></li>\n'
    
    html_content += """    </ul>
    <h3>📄 HTML 檔案</h3>
    <ul>"""
    
    for hf in html_files:
        html_content += f'        <li>📄 <a href="./{hf}">{hf}</a></li>\n'
        
    html_content += """    </ul>
</body>
</html>"""

    with open(index_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

def main():
    root_dir = os.getcwd()
    search_index = []
    
    print("⏳ 開始掃描目錄並建立索引...")
    
    for root, dirs, files in os.walk(root_dir):
        # 排除自身以及可能重複生成的總 index.html 邏輯
        if root != root_dir:
            generate_sub_index(root, root_dir)
            
        for file in files:
            if file.endswith('.html') and file != 'index.html':
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, root_dir).replace('\\', '/')
                
                # 提取標題用於搜尋
                title = extract_title(full_path)
                search_index.append({
                    "title": title,
                    "path": rel_path
                })
                
    # 1. 寫入搜尋 JSON 檔
    with open('search_index.json', 'w', encoding='utf-8') as f:
        json.dump(search_index, f, ensure_ascii=False, indent=2)
    print(f"✅ 已成功建立搜尋索引，共 {len(search_index)} 筆網頁。")

    # 2. 建立最外層總 index.html (包含 JS 搜尋與分頁)
    main_index_content = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <title>NX 2512 離線幫助文件搜尋系統</title>
    <style>
        body { font-family: "Segoe UI", sans-serif; margin: 0; padding: 20px; background: #f4f6f9; color: #333; }
        .container { max-width: 900px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
        h1 { text-align: center; color: #1e3d59; }
        .search-box { display: flex; margin-bottom: 20px; gap: 10px; }
        input[type="text"] { flex: 1; padding: 12px; border: 2px solid #ddd; border-radius: 4px; font-size: 16px; outline: none; transition: border 0.3s; }
        input[type="text"]:focus { border-color: #1e3d59; }
        #results { margin-top: 20px; }
        .result-item { padding: 15px; border-bottom: 1px solid #eee; transition: background 0.2s; }
        .result-item:hover { background: #f9fbfd; }
        .result-item a { font-size: 18px; color: #17b978; text-decoration: none; font-weight: bold; }
        .result-item a:hover { text-decoration: underline; }
        .result-path { font-size: 12px; color: #888; margin-top: 5px; word-break: break-all; }
        .pagination { display: flex; justify-content: center; align-items: center; gap: 10px; margin-top: 30px; }
        .page-btn { padding: 8px 16px; border: 1px solid #1e3d59; background: #fff; color: #1e3d59; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .page-btn:disabled { border-color: #ccc; color: #ccc; cursor: not-allowed; }
        .page-btn.active { background: #1e3d59; color: #fff; }
        .info { text-align: center; color: #666; font-size: 14px; margin-bottom: 10px; }
    </style>
</head>
<body>
<div class="container">
    <h1>Siemens NX 2512 Local Help 🔍</h1>
    <div class="search-box">
        <input type="text" id="search-input" placeholder="請輸入關鍵字進行搜尋（例如：Extrude、Sketch）..." oninput="handleSearch()">
    </div>
    <div class="info" id="search-info">載入索引中...</div>
    <div id="results"></div>
    <div class="pagination" id="pagination"></div>
</div>

<script>
    let searchData = [];
    let filteredData = [];
    let currentPage = 1;
    const itemsPerPage = 20;

    // 頁面載入時讀取 JSON
    async function loadIndex() {
        try {
            const response = await fetch('search_index.json');
            searchData = await response.json();
            filteredData = [...searchData];
            document.getElementById('search-info').innerText = `全部文件共 ${searchData.length} 筆，請輸入關鍵字搜尋。`;
            renderPage();
        } catch (error) {
            document.getElementById('search-info').innerText = "❌ 無法載入 search_index.json，請確認是否在伺服器環境或允許本地 fetch。";
            console.error(error);
        }
    }

    function handleSearch() {
        const query = document.getElementById('search-input').value.toLowerCase().trim();
        if (query === "") {
            filteredData = [...searchData];
        } else {
            // 簡單關鍵字過濾（標題或路徑含有關鍵字）
            filteredData = searchData.filter(item => 
                item.title.toLowerCase().includes(query) || 
                item.path.toLowerCase().includes(query)
            );
        }
        currentPage = 1;
        renderPage();
    }

    function renderPage() {
        const resultsDiv = document.getElementById('results');
        const paginationDiv = document.getElementById('pagination');
        resultsDiv.innerHTML = "";
        paginationDiv.innerHTML = "";

        const totalItems = filteredData.length;
        document.getElementById('search-info').innerText = `找到 ${totalItems} 筆結果。`;

        if (totalItems === 0) {
            resultsDiv.innerHTML = "<p style='text-align:center; color:#999;'>無符合條件的搜尋結果</p>";
            return;
        }

        const totalPages = Math.ceil(totalItems / itemsPerPage);
        const startIndex = (currentPage - 1) * itemsPerPage;
        const endIndex = Math.min(startIndex + itemsPerPage, totalItems);

        // 渲染當前頁面的 20 筆資料
        for (let i = startIndex; i < endIndex; i++) {
            const item = filteredData[i];
            const div = document.createElement('div');
            div.className = 'result-item';
            div.innerHTML = `
                <a href="./${item.path}" target="_blank">${item.title}</a>
                <div class="result-path">📁 路徑: ${item.path}</div>
            `;
            resultsDiv.appendChild(div);
        }

        // 渲染分頁按鈕
        if (totalPages > 1) {
            // 上一頁
            const prevBtn = document.createElement('button');
            prevBtn.className = 'page-btn';
            prevBtn.innerText = '◀ 上一頁';
            prevBtn.disabled = currentPage === 1;
            prevBtn.onclick = () => { currentPage--; renderPage(); window.scrollTo(0,0); };
            paginationDiv.appendChild(prevBtn);

            // 頁碼顯示資訊
            const pageInfo = document.createElement('span');
            pageInfo.innerText = ` 頁次: ${currentPage} / ${totalPages} `;
            paginationDiv.appendChild(pageInfo);

            // 下一頁
            const nextBtn = document.createElement('button');
            nextBtn.className = 'page-btn';
            nextBtn.innerText = '下一頁 ▶';
            nextBtn.disabled = currentPage === totalPages;
            nextBtn.onclick = () => { currentPage++; renderPage(); window.scrollTo(0,0); };
            paginationDiv.appendChild(nextBtn);
        }
    }

    // 啟動載入
    window.onload = loadIndex;
</script>
</body>
</html>"""

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(main_index_content)
    print("✅ 最外層首頁建置完畢 (index.html)。")

if __name__ == "__main__":
    main()
