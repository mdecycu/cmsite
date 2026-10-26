def go_to_field():
    move()
    move()
    turn_left()
    move()
    move()
def turn_right():
    turn_left()
    turn_left()
    turn_left()
    
def harvest_the_row():
    for i in range(6):
        while object_here():
            take()
        else:
            move()
    if is_facing_north():
        turn_right()
        move()
        turn_right()
        move()
    else:
        turn_left()
        move()
        turn_left()
        move()
 
go_to_field()
for i in range(6):
    harvest_the_row()