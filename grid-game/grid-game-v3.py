#!/usr/bin/env python3
import curses
import random
import json
import os
from collections import deque, defaultdict, Counter

# ----------------------
# CONFIG
# ----------------------
GRID_SIZE = 9
NUM_OBSTACLES = 12
NUM_TRAPS = 3
AI_STUN_TURNS = 2
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "ai_memory.json")
MARKOV_ORDER = 2            # how many recent moves to use for context
RECENCY_WEIGHT = 2.0        # weight for this game's recent move counts vs. global
PREDICT_FUZZ = 0.15         # small randomness so AI isn’t perfectly deterministic
CLOSE_RANGE = 2             # if AI is within this Manhattan distance, it hunts harder

# Tiles
EMPTY = '.'
WALL  = '#'
GOAL  = 'G'
PLAYER= 'P'
AI    = 'A'
TRAP  = 'T'

# Directions
DIRS = {
    "north": (-1, 0),
    "south": (1, 0),
    "west": (0, -1),
    "east": (0, 1),
}

DIR_KEYS = {                # curses key -> canonical label
    curses.KEY_UP:    "north",
    curses.KEY_DOWN:  "south",
    curses.KEY_LEFT:  "west",
    curses.KEY_RIGHT: "east",
}

# ----------------------
# MEMORY (JSON)
# ----------------------
def load_memory(path=MEMORY_FILE):
    if not os.path.exists(path):
        return {"games": []}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        # corrupt or unreadable; start fresh
        return {"games": []}

def save_game(moves, result, path=MEMORY_FILE):
    data = load_memory(path)
    data["games"].append({
        "moves": moves,          # list of "north"/"south"/...
        "result": result,        # "win" or "loss" or "quit"
        "grid": GRID_SIZE
    })
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def build_markov_model(memory, order=2):
    """
    Returns:
      model: dict mapping tuple(context) -> Counter(next_move)
      global_counts: Counter of all moves
    """
    model = defaultdict(Counter)
    global_counts = Counter()
    for g in memory.get("games", []):
        seq = g.get("moves", [])
        global_counts.update(seq)
        if not seq:
            continue
        # contexts
        for i in range(len(seq)):
            for k in range(1, order+1):
                if i - k < 0: break
                ctx = tuple(seq[i-k:i])
                model[ctx][seq[i]] += 1
    return model, global_counts

# ----------------------
# GRID + POSITIONS
# ----------------------
def random_empty_cell(grid):
    n = len(grid)
    while True:
        r = random.randrange(n)
        c = random.randrange(n)
        if grid[r][c] == EMPTY:
            return [r, c]

def make_grid():
    grid = [[EMPTY for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    # obstacles
    placed = 0
    while placed < NUM_OBSTACLES:
        r = random.randrange(GRID_SIZE)
        c = random.randrange(GRID_SIZE)
        if grid[r][c] == EMPTY:
            grid[r][c] = WALL
            placed += 1
    return grid

def place_entities(grid):
    player_pos = random_empty_cell(grid)
    ai_pos     = random_empty_cell(grid)
    goal_pos   = random_empty_cell(grid)
    # Avoid initial overlaps or too-close starts
    while ai_pos == player_pos or goal_pos == player_pos or goal_pos == ai_pos:
        ai_pos   = random_empty_cell(grid)
        goal_pos = random_empty_cell(grid)
    return player_pos, ai_pos, goal_pos

# ----------------------
# PATHFINDING
# ----------------------
def neighbors(r, c, grid):
    n = len(grid)
    for dr, dc in DIRS.values():
        nr, nc = r+dr, c+dc
        if 0 <= nr < n and 0 <= nc < n and grid[nr][nc] != WALL:
            yield nr, nc

def bfs_first_step(start, target, grid):
    """
    BFS from start to target; return the *next* step on the shortest path.
    If no path, return None.
    """
    if start == target:
        return start
    q = deque([start])
    prev = {tuple(start): None}
    n = len(grid)

    while q:
        r, c = q.popleft()
        for nr, nc in neighbors(r, c, grid):
            if (nr, nc) not in prev:
                prev[(nr, nc)] = (r, c)
                if [nr, nc] == target:
                    # reconstruct first move
                    cur = (nr, nc)
                    while prev[cur] != tuple(start):
                        cur = prev[cur]
                    return [cur[0], cur[1]]
                q.append((nr, nc))
    return None

# ----------------------
# AI PREDICTION
# ----------------------
def choose_from_counter(counter_dict):
    """Sample from a Counter-like dict, with probabilities proportional to counts."""
    items = list(counter_dict.items())
    if not items:
        return random.choice(list(DIRS.keys()))
    total = sum(v for _, v in items)
    r = random.random() * total
    acc = 0
    for k, v in items:
        acc += v
        if r <= acc:
            return k
    return items[-1][0]

def predict_next_move(this_game_moves, model, global_counts, order=2):
    """
    Predict the player's next move using:
      - Markov model from past games (contexts of up to 'order')
      - Recent moves in THIS game (recency-weight blending)
      - Small randomness (PREDICT_FUZZ)
    """
    # Try longest context first
    combined = Counter()

    # recent context from this game
    for k in reversed(range(1, order+1)):
        if len(this_game_moves) >= k:
            ctx = tuple(this_game_moves[-k:])
            combined.update(model.get(ctx, Counter()))

    # blend in global counts (weak prior)
    # and this game's recent histogram (stronger)
    game_counts = Counter(this_game_moves[-8:])  # look at last up-to-8 moves
    for m in DIRS.keys():
        combined[m] += 0.50 * global_counts.get(m, 0) + RECENCY_WEIGHT * game_counts.get(m, 0)

    # add a tiny fuzz to avoid zero-probability traps and predictability
    for m in DIRS.keys():
        combined[m] += PREDICT_FUZZ

    return choose_from_counter(combined)

# ----------------------
# GAME LOOP (CURSES)
# ----------------------
def draw(stdscr, grid, player_pos, ai_pos, goal_pos, traps, traps_left, msg, turn):
    stdscr.clear()
    n = len(grid)
    max_x = curses.COLS - 1  # Get terminal width
    # Header
    header = "AI NEMESIS — reach G, avoid A | arrows: move | t: trap | q: quit"
    stdscr.addstr(0, 0, header[:max_x])
    stdscr.addstr(1, 0, f"Traps left: {traps_left}   Turn: {turn}"[:max_x])
    # Grid
    for r in range(n):
        line = []
        for c in range(n):
            ch = grid[r][c]
            if player_pos == [r, c]:
                ch = PLAYER
            elif ai_pos == [r, c]:
                ch = AI
            elif goal_pos == [r, c]:
                ch = GOAL
            elif (r, c) in traps:
                ch = TRAP
            line.append(ch)
        line_str = " ".join(line)
        stdscr.addstr(3 + r, 0, line_str[:max_x])
    # Footer
    if msg:
        stdscr.addstr(3 + n + 1, 0, msg[:max_x])
    stdscr.refresh()

def in_bounds(pos):
    return 0 <= pos[0] < GRID_SIZE and 0 <= pos[1] < GRID_SIZE

def try_move(pos, move_label, grid):
    dr, dc = DIRS[move_label]
    nr, nc = pos[0] + dr, pos[1] + dc
    if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE and grid[nr][nc] != WALL:
        return [nr, nc]
    return pos

def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def ai_turn(ai_pos, player_pos, grid, traps, this_moves, model, global_counts, stunned, goal_pos=None):
    """Return new_ai_pos, stunned_left"""
    if stunned > 0:
        return ai_pos, stunned - 1

    # If AI is far, move twice per turn
    moves = 1
    if manhattan(ai_pos, player_pos) > CLOSE_RANGE + 2:
        moves = 2

    new_ai_pos = ai_pos
    stunned_left = 0
    for _ in range(moves):
        # Intercept: target the player's shortest path to the goal
        path_step = bfs_first_step(player_pos, goal_pos, grid)
        if path_step:
            intercept_target = path_step
        else:
            intercept_target = player_pos

        step = bfs_first_step(new_ai_pos, intercept_target, grid)
        if step is None:
            # No path: fallback greedy one-step toward intercept_target
            best = new_ai_pos
            best_d = 10**9
            for name, (dr, dc) in DIRS.items():
                cand = [new_ai_pos[0] + dr, new_ai_pos[1] + dc]
                if in_bounds(cand) and grid[cand[0]][cand[1]] != WALL:
                    d = manhattan(cand, intercept_target)
                    if d < best_d:
                        best_d = d
                        best = cand
            step = best

        # Trap check
        if tuple(step) in traps:
            traps.remove(tuple(step))
            stunned_left = AI_STUN_TURNS
            new_ai_pos = step
            break
        new_ai_pos = step

    return new_ai_pos, stunned_left

def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(False)  # blocking input per turn
    stdscr.keypad(True)

    memory = load_memory()
    model, global_counts = build_markov_model(memory, MARKOV_ORDER)

    grid = make_grid()
    player_pos, ai_pos, goal_pos = place_entities(grid)
    traps = set()
    traps_left = NUM_TRAPS
    this_game_moves = []
    ai_stunned = 0
    msg = ""
    turn = 1

    while True:
        draw(stdscr, grid, player_pos, ai_pos, goal_pos, traps, traps_left, msg, turn)
        msg = ""

        # --- Player input ---
        ch = stdscr.getch()
        if ch == ord('q'):
            save_game(this_game_moves, "quit")
            return

        if ch == ord('t'):
            if traps_left > 0 and tuple(player_pos) not in traps:
                traps.add(tuple(player_pos))
                traps_left -= 1
                msg = "Trap placed."
            else:
                msg = "No traps left or trap already here."
            # No movement this turn if placing trap; AI still moves
        elif ch in DIR_KEYS:
            move_label = DIR_KEYS[ch]
            new_pos = try_move(player_pos, move_label, grid)
            if new_pos != player_pos:
                player_pos = new_pos
                this_game_moves.append(move_label)
            else:
                msg = "Blocked."
        else:
            msg = "Use arrows to move, 't' for trap, 'q' to quit."

        # Win check
        if player_pos == goal_pos:
            draw(stdscr, grid, player_pos, ai_pos, goal_pos, traps, traps_left, "You reached the goal! You win.", turn)
            curses.napms(900)
            save_game(this_game_moves, "win")
            return

        # --- AI move ---
        
        ai_pos, stunned_new = ai_turn(ai_pos, player_pos, grid, traps, this_game_moves, model, global_counts, ai_stunned, goal_pos)

        if stunned_new > 0:
            msg = "AI stunned!"
        ai_stunned = stunned_new

        # Lose check
        if ai_pos == player_pos:
            draw(stdscr, grid, player_pos, ai_pos, goal_pos, traps, traps_left, "Caught by AI. Game over.", turn)
            curses.napms(900)
            save_game(this_game_moves, "loss")
            return

        turn += 1

if __name__ == "__main__":
    curses.wrapper(main)