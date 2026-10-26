def turn(int):
    for i in range(int):
        turn_left()
        
def new_move(int):
    for i in range(int):
        move()
        
def harvest_one_row():
    while object_here():
        take()
    else:
        move()
# move to the field
new_move(2)
turn_left()
new_move(2)

for i in range(3):
    while is_facing_north():
        for i in range(6):
            harvest_one_row()
        for i in range(2):
            turn(3)
            move() 
    else:
        for i in range(6):
            harvest_one_row()
        for i in range(2):
            turn_left()
            move()