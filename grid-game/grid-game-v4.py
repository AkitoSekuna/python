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
MARKOV_ORDER = 2
RECENCY_WEIGHT = 2.0
PREDICT_FUZZ = 0.15
CLOSE_RANGE = 2

EMPTY = '.'
WALL  = '#'
GOAL  = 'G'
PLAYER= 'P'
AI    = 'A'
AI2   = 'B'
TRAP  = 'T'

DIRS = {
    "north": (-1, 0),
    "south": (1, 0),
    "west": (0, -1),
    "east": (0, 1),
}

DIR_KEYS = {
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
        return {"games": []}

def save_game(moves, result, path=MEMORY_FILE, successful_traps=0):
    data = load_memory(path)
    data["games"].append({
        "moves": moves,
        "result": result,
        "grid": GRID_SIZE,
        "successful_traps": successful_traps
    })
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def build_markov_model(memory, order=2):
    model = defaultdict(Counter)
    global_counts = Counter()
    for g in memory.get("games", []):
        seq = g.get("moves", [])
        global_counts.update(seq)
        if not seq:
            continue
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
    ai2_pos    = random_empty_cell(grid)
    goal_pos   = random_empty_cell(grid)
    # Ensure no overlap
    while (ai_pos == player_pos or ai2_pos == player_pos or
           goal_pos == player_pos or goal_pos == ai_pos or
           goal_pos == ai2_pos or ai_pos == ai2_pos):
        ai_pos   = random_empty_cell(grid)
        ai2_pos  = random_empty_cell(grid)
        goal_pos = random_empty_cell(grid)
    return player_pos, ai_pos, ai2_pos, goal_pos

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
                    cur = (nr, nc)
                    while prev[cur] != tuple(start):
                        cur = prev[cur]
                    return [cur[0], cur[1]]
                q.append((nr, nc))
    return None

# ----------------------
# AI LOGIC
# ----------------------
def ai_a_turn(ai_pos, player_pos, grid, traps, this_moves, model, global_counts, stunned, goal_pos, ai2_pos):
    if stunned > 0:
        return ai_pos, stunned - 1

    moves = 1
    if manhattan(ai_pos, player_pos) > CLOSE_RANGE + 2:
        moves = 2

    new_ai_pos = ai_pos
    stunned_left = 0
    for _ in range(moves):
        path_step = bfs_first_step(player_pos, goal_pos, grid)
        intercept_target = path_step if path_step else player_pos

        step = bfs_first_step(new_ai_pos, intercept_target, grid)
        if step is None:
            best = new_ai_pos
            best_d = 10**9
            for name, (dr, dc) in DIRS.items():
                cand = [new_ai_pos[0] + dr, new_ai_pos[1] + dc]
                if in_bounds(cand) and grid[cand[0]][cand[1]] != WALL and cand != ai2_pos:
                    d = manhattan(cand, intercept_target)
                    if d < best_d:
                        best_d = d
                        best = cand
            step = best

        if step == ai2_pos:
            break

        if tuple(step) in traps:
            traps.remove(tuple(step))
            stunned_left = AI_STUN_TURNS
            new_ai_pos = step
            break
        new_ai_pos = step

    return new_ai_pos, stunned_left

def ai_b_turn(ai2_pos, player_pos, grid, traps, stunned, ai_pos):
    if stunned > 0:
        return ai2_pos, stunned - 1

    moves = 1
    if manhattan(ai2_pos, player_pos) > CLOSE_RANGE + 2:
        moves = 2

    new_ai2_pos = ai2_pos
    stunned_left = 0
    for _ in range(moves):
        best = new_ai2_pos
        best_d = manhattan(new_ai2_pos, player_pos)
        for name, (dr, dc) in DIRS.items():
            cand = [new_ai2_pos[0] + dr, new_ai2_pos[1] + dc]
            if in_bounds(cand) and grid[cand[0]][cand[1]] != WALL and cand != ai_pos:
                d = manhattan(cand, player_pos)
                if d < best_d:
                    best_d = d
                    best = cand

        if best == ai_pos:
            break

        if tuple(best) in traps:
            traps.remove(tuple(best))
            stunned_left = AI_STUN_TURNS
            new_ai2_pos = best
            break
        new_ai2_pos = best

    return new_ai2_pos, stunned_left

# ----------------------
# AI PREDICTION (for stats/learning)
# ----------------------
def choose_from_counter(counter_dict):
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
    combined = Counter()
    for k in reversed(range(1, order+1)):
        if len(this_game_moves) >= k:
            ctx = tuple(this_game_moves[-k:])
            combined.update(model.get(ctx, Counter()))
    game_counts = Counter(this_game_moves[-8:])
    for m in DIRS.keys():
        combined[m] += 0.50 * global_counts.get(m, 0) + RECENCY_WEIGHT * game_counts.get(m, 0)
    for m in DIRS.keys():
        combined[m] += PREDICT_FUZZ
    return choose_from_counter(combined)

# ----------------------
# GAME LOOP (CURSES)
# ----------------------
def draw(stdscr, grid, player_pos, ai_pos, ai2_pos, goal_pos, traps, traps_left, msg, turn):
    stdscr.clear()
    n = len(grid)
    max_x = curses.COLS - 1
    header = "AI NEMESIS — reach G, avoid A/B | arrows: move | t: trap | q: quit"
    stdscr.addstr(0, 0, header[:max_x])
    stdscr.addstr(1, 0, f"Traps left: {traps_left}   Turn: {turn}"[:max_x])
    for r in range(n):
        line = []
        for c in range(n):
            ch = grid[r][c]
            if player_pos == [r, c]:
                ch = PLAYER
            elif ai_pos == [r, c]:
                ch = AI
            elif ai2_pos == [r, c]:
                ch = AI2
            elif goal_pos == [r, c]:
                ch = GOAL
            elif (r, c) in traps:
                ch = TRAP
            line.append(ch)
        line_str = " ".join(line)
        stdscr.addstr(3 + r, 0, line_str[:max_x])
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

def main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)

    memory = load_memory()
    model, global_counts = build_markov_model(memory, MARKOV_ORDER)

    grid = make_grid()
    player_pos, ai_pos, ai2_pos, goal_pos = place_entities(grid)
    traps = set()
    traps_left = NUM_TRAPS
    this_game_moves = []
    ai_stunned = 0
    ai2_stunned = 0
    msg = ""
    turn = 1
    successful_traps = 0

    while True:
        draw(stdscr, grid, player_pos, ai_pos, ai2_pos, goal_pos, traps, traps_left, msg, turn)
        msg = ""

        ch = stdscr.getch()
        if ch == ord('q'):
            save_game(this_game_moves, "quit", successful_traps=successful_traps)
            return

        if ch == ord('t'):
            if traps_left > 0 and tuple(player_pos) not in traps:
                traps.add(tuple(player_pos))
                traps_left -= 1
                msg = "Trap placed."
            else:
                msg = "No traps left or trap already here."
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

        if player_pos == goal_pos:
            draw(stdscr, grid, player_pos, ai_pos, ai2_pos, goal_pos, traps, traps_left, "You reached the goal! You win.", turn)
            curses.napms(900)
            save_game(this_game_moves, "win", successful_traps=successful_traps)
            return

        prev_ai_stunned = ai_stunned
        ai_pos, ai_stunned = ai_a_turn(ai_pos, player_pos, grid, traps, this_game_moves, model, global_counts, ai_stunned, goal_pos, ai2_pos)
        if ai_stunned > 0 and prev_ai_stunned == 0:
            msg = "AI A stunned!"
            successful_traps += 1

        prev_ai2_stunned = ai2_stunned
        ai2_pos, ai2_stunned = ai_b_turn(ai2_pos, player_pos, grid, traps, ai2_stunned, ai_pos)
        if ai2_stunned > 0 and prev_ai2_stunned == 0:
            msg = "AI B stunned!"
            successful_traps += 1

        if ai_pos == player_pos or ai2_pos == player_pos:
            draw(stdscr, grid, player_pos, ai_pos, ai2_pos, goal_pos, traps, traps_left, "Caught by AI. Game over.", turn)
            curses.napms(900)
            save_game(this_game_moves, "loss", successful_traps=successful_traps)
            return

        turn += 1

def show_menu(stdscr):
    options = ["Play Game", "View Statistics", "Quit"]
    selected = 0
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, "AI NEMESIS — Main Menu")
        for i, opt in enumerate(options):
            prefix = "-> " if i == selected else "   "
            stdscr.addstr(2 + i, 0, f"{prefix}{opt}")
        stdscr.refresh()
        ch = stdscr.getch()
        if ch == curses.KEY_UP and selected > 0:
            selected -= 1
        elif ch == curses.KEY_DOWN and selected < len(options) - 1:
            selected += 1
        elif ch in [curses.KEY_ENTER, 10, 13]:
            return selected

def show_stats(stdscr):
    memory = load_memory()
    games = memory.get("games", [])
    total = len(games)
    wins = sum(1 for g in games if g.get("result") == "win")
    losses = sum(1 for g in games if g.get("result") == "loss")
    quits = sum(1 for g in games if g.get("result") == "quit")
    win_rate = (wins / total * 100) if total else 0
    avg_moves = (sum(len(g.get("moves", [])) for g in games) / total) if total else 0
    total_traps = sum(g.get("successful_traps", 0) for g in games)
    avg_traps = (total_traps / total) if total else 0
    stdscr.clear()
    stdscr.addstr(0, 0, "AI NEMESIS — Statistics")
    stdscr.addstr(2, 0, f"Total games:      {total}")
    stdscr.addstr(3, 0, f"Wins:             {wins}")
    stdscr.addstr(4, 0, f"Losses:           {losses}")
    stdscr.addstr(5, 0, f"Quits:            {quits}")
    stdscr.addstr(6, 0, f"Win rate:         {win_rate:.1f}%")
    stdscr.addstr(7, 0, f"Avg moves:        {avg_moves:.1f}")
    stdscr.addstr(8, 0, f"Successful traps: {total_traps}")
    stdscr.addstr(9, 0, f"Avg traps/game:   {avg_traps:.2f}")
    stdscr.addstr(11, 0, "Press any key to return to menu.")
    stdscr.refresh()
    stdscr.getch()

def main_menu(stdscr):
    while True:
        choice = show_menu(stdscr)
        if choice == 0:
            main(stdscr)
        elif choice == 1:
            show_stats(stdscr)
        elif choice == 2:
            break

if __name__ == "__main__":
    curses.wrapper(main_menu)