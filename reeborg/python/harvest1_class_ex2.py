class Harvest:
    def __init__(self, x1, y1, x2, y2, direction="horizontal"):
        """
        初始化函式，用於設定採收區域的座標範圍與採收方向。
        參數:
            x1, y1, x2, y2: 區域對角兩點的 x, y 座標。
            direction: 採收方向，"horizontal"（水平）或 "vertical"（垂直），預設為水平。
        """
        # 設定 x 軸最小值，確保無論傳入的點順序如何都能正確判斷範圍
        self.x_min = min(x1, x2)
        # 設定 x 軸最大值
        self.x_max = max(x1, x2)
        # 設定 y 軸最小值
        self.y_min = min(y1, y2)
        # 設定 y 軸最大值
        self.y_max = max(y1, y2)
        # 設定採收方向
        self.direction = direction

    def turn_left_n(self, n):
        """
        讓 Reeborg 連續左轉 n 次。
        參數:
            n: 需要左轉的次數。
        """
        for _ in range(n):
            turn_left()  # 每次呼叫 turn_left()，Reeborg 會左轉 90 度

    def move_n(self, n):
        """
        讓 Reeborg 連續前進 n 格。
        參數:
            n: 需要前進的格數。
        """
        for _ in range(n):
            move()  # 每次呼叫 move()，Reeborg 會往前移動一格

    def harvest_one_cell(self):
        """
        檢查當前格子是否有紅蘿蔔，有的話就採收（take()）。
        只要有物品就持續採收，直到該格無物品為止。
        """
        while object_here():
            take()  # 如果格子上有物品則採收

    def harvest_one_row(self, cells):
        """
        採收一整排（橫向或縱向）。
        參數:
            cells: 這一排需要採收的格數。
        """
        for i in range(cells):
            self.harvest_one_cell()  # 採收當前格子
            if i < cells - 1:
                move()  # 若不是最後一格，則往前移動到下一格

    def move_to_field_horizontal(self):
        """
        讓 Reeborg 走到採收區域的左下角 (x_min, y_min)，並面向東方（右）。
        適用於水平採收。
        """
        self.move_n(self.x_min - 1)    # 先往東移動到 x_min
        self.turn_left_n(1)            # 左轉，面向北
        self.move_n(self.y_min - 1)    # 往北移動到 y_min
        self.turn_left_n(3)            # 左轉三次，回到面東（右）

    def move_to_field_vertical(self):
        """
        讓 Reeborg 走到採收區域的左下角 (x_min, y_min)，並面向北方。
        適用於垂直採收。
        """
        self.move_n(self.x_min - 1)    # 先往東移動到 x_min
        self.turn_left_n(1)            # 左轉，面向北
        self.move_n(self.y_min - 1)    # 往北移動到 y_min
        # 此時已經面向北方，無需再轉向

    def harvest_field(self):
        """
        主函式，根據 direction 執行蛇行式（zigzag）採收。
        水平採收時，從左下開始，一排排往上採收；
        垂直採收時，從左下開始，一行行往右採收。
        """
        if self.direction == "horizontal":
            # 水平均勻採收
            self.move_to_field_horizontal()        # 先到起始位置
            rows = self.y_max - self.y_min + 1    # 計算總排數（y方向）
            cols = self.x_max - self.x_min + 1    # 計算每排格數（x方向）
            for r in range(rows):
                self.harvest_one_row(cols)        # 採收一排
                if r < rows - 1:                  # 若還沒到最後一排
                    if r % 2 == 0:
                        # 偶數排結束時，左轉、前進一格，再左轉，準備往回走
                        self.turn_left_n(1)
                        move()
                        self.turn_left_n(1)
                    else:
                        # 奇數排結束時，右轉（左轉三次）、前進一格，再右轉
                        self.turn_left_n(3)
                        move()
                        self.turn_left_n(3)
        elif self.direction == "vertical":
            # 垂直均勻採收
            self.move_to_field_vertical()         # 先到起始位置
            cols = self.x_max - self.x_min + 1   # 計算總行數（x方向）
            rows = self.y_max - self.y_min + 1   # 計算每行格數（y方向）
            for c in range(cols):
                for i in range(rows):
                    self.harvest_one_cell()      # 採收當前格子
                    if i < rows - 1:
                        move()                   # 若不是這行最後一格，繼續往北
                if c < cols - 1:                 # 若還沒到最後一行
                    if c % 2 == 0:
                        # 偶數行結束時，右轉（左轉三次）、前進一格，再右轉
                        self.turn_left_n(3)
                        move()
                        self.turn_left_n(3)
                    else:
                        # 奇數行結束時，左轉、前進一格，再左轉
                        self.turn_left_n(1)
                        move()
                        self.turn_left_n(1)

# 範例用法：
# 水平蛇形採收 (預設)
# h1 = Harvest(3, 3, 8, 8)
# h1.harvest_field()

# 垂直蛇形採收
h2 = Harvest(3, 3, 8, 8, direction="vertical")
h2.harvest_field()