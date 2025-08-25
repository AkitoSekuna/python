import random

# Grid size
GRID_SIZE = 5

# Initial positions
player_pos = [0, 0]
ai_pos = [GRID_SIZE - 1, GRID_SIZE - 1]

# Track player moves for AI learning
player_moves_history = []

# Directions mapping
directions = {
    "north": (1, 0),
    "south": (-1, 0),
    "west": (0, -1),
    "east": (0, 1),
    "hide": (0, 0)
}

def print_grid():
    # Flip rows so row 0 is at the bottom
    for i in reversed(range(GRID_SIZE)):
        row = ""
        for j in range(GRID_SIZE):
            if [i, j] == player_pos:
                row += "P "
            elif [i, j] == ai_pos:
                row += "A "
            else:
                row += ". "
        print(row)
    print()

def move(pos, direction):
    delta = directions[direction]
    new_pos = [pos[0] + delta[0], pos[1] + delta[1]]
    # Keep inside grid
    new_pos[0] = max(0, min(GRID_SIZE - 1, new_pos[0]))
    new_pos[1] = max(0, min(GRID_SIZE - 1, new_pos[1]))
    return new_pos

def ai_move():
    if not player_moves_history:
        # Random first move
        return move(ai_pos, random.choice(list(directions.keys())))
    
    # Count most frequent player move
    move_counts = {dir: player_moves_history.count(dir) for dir in directions}
    predicted_move = max(move_counts, key=move_counts.get)
    
    # Predicted player position
    predicted_pos = move(player_pos, predicted_move)
    
    # Determine row movement
    if ai_pos[0] < predicted_pos[0]:
        new_pos = move(ai_pos, "north")
    elif ai_pos[0] > predicted_pos[0]:
        new_pos = move(ai_pos, "south" )
    # If rows match, move column
    elif ai_pos[1] < predicted_pos[1]:
        new_pos = move(ai_pos, "east")
    elif ai_pos[1] > predicted_pos[1]:
        new_pos = move(ai_pos, "west")
    else:
        new_pos = ai_pos  # Already on predicted spot
    
    return new_pos

print("=== AI NEMESIS GAME ===")
print("Commands: north, south, east, west, hide\n")

while True:
    print_grid()
    
    action = input("Your move: ").lower()
    if action not in directions:
        print("Invalid move. Try again.")
        continue
    
    player_pos = move(player_pos, action)
    player_moves_history.append(action)
    
    ai_pos = ai_move()
    
    if player_pos == ai_pos:
        print_grid()
        print("The AI caught you! Game over.")
        break
