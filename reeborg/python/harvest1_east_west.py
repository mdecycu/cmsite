def turn(n):
    for i in range(n):
        turn_left()
        
def turn_right():
    for i in range(3):
        turn_left()
        
def new_move(n):
    for i in range(n):
        move()
        
def harvest_one_row():
    global object_taken
    while object_here() and object_taken < 36:
        take()
        object_taken += 1
    # 只要沒達到 36 就繼續 move
    if object_taken < 36:
        move()
        
def is_facing_east():
    # 記錄原本面向的方向
    count = 0
    while not is_facing_north():
        turn_left()
        count += 1
        if count == 4:
            break
    # 轉到北方後，左轉三次就會面向東
    turn(3)
    return True

object_taken = 0
# move to the field
new_move(2)
turn_left()
new_move(2)

done = False
while is_facing_east() and not done:
    for i in range(2):
        # 面向東直走收成
        for j in range(6):
            harvest_one_row()
            if object_taken >= 36:
                done = True
                break
        if done:
            break
        for k in range(2):
            turn_left()
            move()
        # 面向西直走收成
        for j in range(6):
            harvest_one_row()
            if object_taken >= 36:
                done = True
                break
        if done:
            break
        for k in range(2):
            turn_right()
            move()
    if object_taken >= 36:
        print("task completed!")
        break