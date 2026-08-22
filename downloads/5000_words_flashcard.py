import os
import random
import re
import tkinter as tk
from tkinter import messagebox

class FlashcardApp:
    def __init__(self, root, word_list):
        self.root = root
        self.word_list = word_list
        self.current_index = 0
        self.state = "SHOW_WORD"  # 狀態：SHOW_WORD (顯英文) 或 SHOW_ANSWER (顯中文)
        
        # 打亂單字順序
        random.shuffle(self.word_list)
        self.total_words = len(self.word_list)
        
        # 視窗設定
        self.root.title("Python 隨機單字卡")
        self.root.geometry("600x400")
        self.root.configure(bg="#F0F4F8") # 淺藍灰色背景
        
        # 建立介面元件
        self.setup_ui()
        
        # 綁定鍵盤與滑鼠事件 (按 Enter、空白鍵或點擊視窗都會觸發)
        self.root.bind("<Return>", self.handle_click)
        self.root.bind("<space>", self.handle_click)
        self.root.bind("<Button-1>", self.handle_click)
        
        # 顯示第一個單字
        self.show_next()

    def setup_ui(self):
        # 進度標籤 (例如: 1 / 5000)
        self.progress_label = tk.Label(
            self.root, text="", font=("Arial", 14), 
            bg="#F0F4F8", fg="#666666"
        )
        self.progress_label.pack(pady=10)
        
        # 英文單字欄位
        self.word_label = tk.Label(
            self.root, text="", font=("Arial", 36, "bold"), 
            bg="#F0F4F8", fg="#2C3E50", wraplength=550
        )
        self.word_label.pack(expand=True, fill="both", pady=10)
        
        # 詞性與中文解釋欄位
        self.answer_label = tk.Label(
            self.root, text="", font=("Microsoft JhengHei", 22), 
            bg="#F0F4F8", fg="#27AE60", wraplength=550
        )
        self.answer_label.pack(expand=True, fill="both", pady=10)
        
        # 底部提示文字
        self.tip_label = tk.Label(
            self.root, text="點擊視窗或按 Enter 顯示答案", font=("Microsoft JhengHei", 12), 
            bg="#F0F4F8", fg="#95A5A6"
        )
        self.tip_label.pack(pady=15)

    def show_next(self):
        if self.current_index >= self.total_words:
            messagebox.showinfo("完成", "恭喜你！所有單字都複習完囉！")
            self.root.quit()
            return
            
        # 取得當前單字資料
        english, pos, chinese = self.word_list[self.current_index]
        
        # 更新進度與英文
        self.progress_label.config(text=f"進度：{self.current_index + 1} / {self.total_words}")
        self.word_label.config(text=english)
        
        # 隱藏答案，修改狀態
        self.answer_label.config(text="")
        self.tip_label.config(text="👉 請按 Enter 或點擊畫面顯示答案...")
        self.state = "SHOW_ANSWER"

    def show_answer(self):
        english, pos, chinese = self.word_list[self.current_index]
        
        # 顯示詞性與中文
        self.answer_label.config(text=f"【 {pos} 】 {chinese}")
        self.tip_label.config(text="👉 請按 Enter 或點擊畫面進入下一單字...")
        
        # 準備進入下一個單字
        self.current_index += 1
        self.state = "SHOW_WORD"

    def handle_click(self, event=None):
        # 根據當前狀態決定顯示答案或換下一題
        if self.state == "SHOW_ANSWER":
            self.show_answer()
        elif self.state == "SHOW_WORD":
            self.show_next()

def load_words(filename):
    word_list = []
    pattern = re.compile(r'^([a-zA-Z\-\s]+)\s+([a-z\./]+)\s*(.+)$')
    
    if not os.path.exists(filename):
        return word_list

    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            match = pattern.match(line)
            if match:
                english = match.group(1).strip()
                pos = match.group(2).strip()
                chinese = match.group(3).strip()
                word_list.append((english, pos, chinese))
    return word_list

if __name__ == "__main__":
    # --- 關鍵修正：自動定位到程式碼所在目錄 ---
    current_dir = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(current_dir, "5000_words.txt")
    print(current_dir)
    # ----------------------------------------
    
    words = load_words(filename)
    
    if not words:
        # 如果還是找不到，彈出視窗提示具體尋找的路徑，方便偵錯
        root = tk.Tk()
        root.withdraw() # 隱藏主視窗
        messagebox.showerror("錯誤", f"在下列路徑找不到單字檔：\n{filename}\n\n請確認檔案名稱與位置是否正確！")
        root.destroy()
    else:
        # 啟動 Tkinter 圖形介面
        root = tk.Tk()
        app = FlashcardApp(root, words)
        root.mainloop()
