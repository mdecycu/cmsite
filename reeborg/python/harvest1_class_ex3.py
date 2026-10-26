class NormalizeCarrot:
    def __init__(self, x1, y1, x2, y2):
        """
        初始化（constructor），設定田地對角座標區間。
        參數:
            x1, y1, x2, y2: 採收區域對角的兩點座標 (可任意順序)
        """
        # 取得 x 軸最小值，作為田地的左邊界
        self.x_min = min(x1, x2)
        # 取得 x 軸最大值，作為田地的右邊界
        self.x_max = max(x1, x2)
        # 取得 y 軸最小值，作為田地的下邊界
        self.y_min = min(y1, y2)
        # 取得 y 軸最大值，作為田地的上邊界
        self.y_max = max(y1, y2)

    def turn_left_n(self, n):
        """
        讓 Reeborg 連續左轉 n 次，每次 90 度。
        參數:
            n: 左轉的次數
        """
        for _ in range(n):
            turn_left()  # 單次左轉

    def move_n(self, n):
        """
        讓 Reeborg 連續前進 n 格。
        參數:
            n: 前進的格數
        """
        for _ in range(n):
            move()  # 單次前進

    def normalize_one_cell(self):
        """
        調整當前格子的紅蘿蔔數量，確保只剩下1個。
        - 若格子上有多個紅蘿蔔，全部拿起來只放回一個
        - 若格子上一個都沒有，則放入一個
        - 若格子上本來就有一個，則保持不變
        """
        count = 0  # 用來計算這格原本有幾個紅蘿蔔
        # 只要這格還有紅蘿蔔，就不斷拿起來並累加計數
        while object_here():
            take()      # 拿起一個紅蘿蔔
            count += 1  # 計數加一
        # 如果原本有一個或多個紅蘿蔔，就放回一個
        if count >= 1:
            put()
        # 如果原本完全沒有紅蘿蔔，也要放一個
        elif count == 0:
            put()

    def normalize_one_row(self, cells):
        """
        依序處理一排的每個格子，使其每格都只剩1個紅蘿蔔。
        參數:
            cells: 這排有幾個格子
        """
        for i in range(cells):
            self.normalize_one_cell()  # 處理當前格子
            if i < cells - 1:          # 若不是這排最後一格
                move()                 # 往前走到下一格

    def move_to_field(self):
        """
        讓 Reeborg 從起始點 (1,1) 面東，走到田地的左下角 (x_min, y_min)，並保持面東。
        （預設 Reeborg 初始面東）
        """
        self.move_n(self.x_min - 1)    # 先向東走到 x_min
        self.turn_left_n(1)            # 左轉，改面北
        self.move_n(self.y_min - 1)    # 向北走到 y_min
        self.turn_left_n(3)            # 左轉三次，回到面東

    def normalize_field(self):
        """
        以蛇行（zigzag）方式，遍歷整個田地區域，
        並將每格紅蘿蔔數量調整到只剩一個。
        """
        rows = self.y_max - self.y_min + 1   # 計算總排數（y方向格數）
        cols = self.x_max - self.x_min + 1   # 每排的格數（x方向）
        self.move_to_field()                 # 先移動到田地左下角
        for r in range(rows):
            self.normalize_one_row(cols)     # 處理一整排
            if r < rows - 1:                 # 不是最後一排時要蛇行轉彎
                if r % 2 == 0:
                    # 偶數排（從左到右）結束：
                    # 左轉、前進一格、再左轉，準備往回走
                    self.turn_left_n(1)
                    move()
                    self.turn_left_n(1)
                else:
                    # 奇數排（從右到左）結束：
                    # 右轉（左轉三次）、前進一格、再右轉，準備往回走
                    self.turn_left_n(3)
                    move()
                    self.turn_left_n(3)

# 使用範例
# 將 (3,3) 到 (8,8) 區域的每格紅蘿蔔數量調整到只剩一個
n = NormalizeCarrot(3, 3, 8, 8)
n.normalize_field()