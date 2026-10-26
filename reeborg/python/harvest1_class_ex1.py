class Harvest:
    def __init__(self, x1, y1, x2, y2):
        """
        初始化函式，用來設定採收區域的範圍。
        參數:
            x1, y1, x2, y2: 採收區域對角兩點的座標。
        """
        # 取得 x 軸較小的值，作為起點
        self.x_min = min(x1, x2)
        # 取得 x 軸較大的值，作為終點
        self.x_max = max(x1, x2)
        # 取得 y 軸較小的值，作為起點
        self.y_min = min(y1, y2)
        # 取得 y 軸較大的值，作為終點
        self.y_max = max(y1, y2)

    def turn_left_n(self, n):
        """
        讓 Reeborg 左轉 n 次，每次 90 度。
        參數:
            n: 左轉的次數
        """
        for _ in range(n):
            turn_left()  # 執行一次左轉

    def move_n(self, n):
        """
        讓 Reeborg 前進 n 格。
        參數:
            n: 前進的格數
        """
        for _ in range(n):
            move()  # 執行一次前進

    def harvest_one_cell(self):
        """
        在目前格子持續採收紅蘿蔔，直到沒有為止。
        """
        while object_here():  # 如果這格還有物品
            take()            # 採收（拿走）物品

    def harvest_one_row(self, cells):
        """
        採收一整排（從左到右），每格都檢查並採收。
        參數:
            cells: 這一排的格數
        """
        for i in range(cells):
            self.harvest_one_cell()    # 採收當前格子
            if i < cells - 1:          # 不是這排最後一格時
                move()                 # 前進到下一格

    def move_to_field(self):
        """
        將 Reeborg 從起始點 (1,1) 帶到要開始採收的田地左下角 (x_min, y_min)，並面向東（右）。
        假設初始朝向為東。
        """
        self.move_n(self.x_min - 1)    # 向東前進到 x_min
        self.turn_left_n(1)            # 左轉，面向北
        self.move_n(self.y_min - 1)    # 向北前進到 y_min
        self.turn_left_n(3)            # 左轉三次，回到面東

    def harvest_field(self):
        """
        將整個採收區域以蛇行（zigzag）方式全部採收完畢。
        """
        rows = self.y_max - self.y_min + 1        # 計算總排數（y方向有幾排）
        cols = self.x_max - self.x_min + 1        # 計算每排格數（x方向有幾格）
        self.move_to_field()                      # 先移動到起始位置
        for r in range(rows):
            self.harvest_one_row(cols)            # 採收一整排
            if r < rows - 1:                      # 不是最後一排時，準備轉彎
                if r % 2 == 0:
                    # 偶數排（從左往右）：左轉，前進一格，再左轉，準備往回走
                    self.turn_left_n(1)
                    move()
                    self.turn_left_n(1)
                else:
                    # 奇數排（從右往左）：右轉（左轉三次），前進一格，再右轉，準備往回走
                    self.turn_left_n(3)
                    move()
                    self.turn_left_n(3)
        # 採收結束時，Reeborg 會停在田地的最右上角，面向原本的方向

# 使用方式
# 例如, 要採收 (3,3) 到 (8,8) 的區域：
h = Harvest(3, 3, 8, 8)
h.harvest_field()