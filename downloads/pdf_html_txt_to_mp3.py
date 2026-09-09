# pip install beautifulsoup4 pypdf edge-tts asyncio
import asyncio
import os
import re
from bs4 import BeautifulSoup
from pypdf import PdfReader
import edge_tts

# ==========================================
# 步驟 1：讀取檔案文字（支援 HTML, PDF, TXT）
# ==========================================
def extract_text_from_file(file_path):
    # 修正點：os.path.splitext 會回傳 (root, ext)，我們要對副檔名 [1] 進行 lower()
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    
    # 處理 HTML 檔案
    if ext in ['.html', '.htm']:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
            # 移除不必要的網頁語法標籤
            for script in soup(["script", "style", "meta", "noscript"]):
                script.decompose()
            text = soup.get_text()
            
    # 處理 PDF 檔案
    elif ext == '.pdf':
        reader = PdfReader(file_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
                
    # 處理 TXT 檔案
    elif ext == '.txt':
        # 嘗試用 utf-8 讀取，若失敗則嘗試繁體中文常見的 big5 編碼
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='big5', errors='ignore') as f:
                text = f.read()
                
    else:
        raise ValueError("不支援的檔案格式！僅支援 .html, .pdf, .txt")
        
    return text

# ==========================================
# 步驟 2：清洗文字並逐句切分
# ==========================================
def split_into_sentences(text):
    # 移除多餘的空白、重複的換行與縮排
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 使用中文與英文常規標點符號（。！？!?）作為切分依據
    # look-behind (?<=[...]) 確保標點符號保留在句子末尾
    sentences = re.split(r'(?<=[。！？!?])\s*', text)
    
    # 過濾掉空句子
    return [s.strip() for s in sentences if s.strip()]

# ==========================================
# 步驟 3：異步調用 TTS 並轉為 MP3
# ==========================================
async def text_to_mp3(sentences, output_mp3_path):
    # 選擇語音（預設台灣中文女聲 HsiaoChen）
    VOICE = "zh-TW-HsiaoChenNeural" 
    
    print(f"正在將文字轉換為語音，總共 {len(sentences)} 句...")
    
    # 打開輸出的 MP3 檔案，以二進位追加寫入
    with open(output_mp3_path, "wb") as f:
        for i, sentence in enumerate(sentences, 1):
            print(f"正在處理第 {i}/{len(sentences)} 句: {sentence[:15]}...")
            
            # 使用 edge-tts 逐句生成語音串流
            communicate = edge_tts.Communicate(sentence, VOICE)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                    
            # 句與句之間微幅停頓（0.15秒），聽感更自然
            await asyncio.sleep(0.15)
            
    print(f"轉換成功！語音檔案已儲存至：{output_mp3_path}")

# ==========================================
# 主程式執行入口
# ==========================================
def main(input_file, output_mp3):
    try:
        # 1. 讀取文字
        raw_text = extract_text_from_file(input_file)
        
        # 2. 切分句子
        sentences = split_into_sentences(raw_text)
        
        if not sentences:
            print("未在檔案中偵測到任何有效文字。")
            return
            
        # 3. 執行語音轉換
        asyncio.run(text_to_mp3(sentences, output_mp3))
        
    except Exception as e:
        print(f"執行時發生錯誤：{e}")

if __name__ == "__main__":
    # 請確認此檔案名稱與路徑在同目錄下存在，或改為你的目標檔案
    INPUT_FILE = "input.html"  
    OUTPUT_MP3 = "output.mp3"
    
    main(INPUT_FILE, OUTPUT_MP3)
