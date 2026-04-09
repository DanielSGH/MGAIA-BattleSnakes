# Welcome to
# __________         __    __  .__                               __
# \______   \_____ _/  |__/  |_|  |   ____   ______ ____ _____  |  | __ ____
#  |    |  _/\__  \\   __\   __\  | _/ __ \ /  ___//    \\__  \ |  |/ // __ \
#  |    |   \ / __ \|  |  |  | |  |_\  ___/ \___ \|   |  \/ __ \|    <\  ___/
#  |________/(______/__|  |__| |____/\_____>______>___|__(______/__|__\\_____>
#
# This file can be a nice home for your Battlesnake logic and helper functions.
#
# To get you started we've included code to prevent your Battlesnake from moving backwards.
# For more info see docs.battlesnake.com

import random
import typing

def fast_copy_game_state(game_state):
    my_id = game_state['you']['id']

    new_snakes = []
    new_you = None

    for s in game_state['board']['snakes']:
        new_s = {
            'id': s['id'],
            'health': s['health'],
            'body': [dict(b) for b in s['body']]
        }
        new_snakes.append(new_s)

        if s['id'] == my_id:
            new_you = new_s  # link to same object

    new_state = {
        'board': {
            'width': game_state['board']['width'],
            'height': game_state['board']['height'],
            'snakes': new_snakes,
            'food': [dict(f) for f in game_state['board']['food']],
        },
        'you': new_you,  # ✅ correct reference
        'turn': game_state.get('turn', 0)
    }

    if 'hazards' in game_state['board']:
        new_state['board']['hazards'] = [
            dict(h) for h in game_state['board']['hazards']
        ]

    return new_state


def get_new_head(head, move):
    new_head = head.copy()
    if move == "up":
        new_head["y"] += 1
    elif move == "down":
        new_head["y"] -= 1
    elif move == "left":
        new_head["x"] -= 1
    elif move == "right":
        new_head["x"] += 1
    return new_head

def get_hazard_damage(turn):
    # Hazards appear from turn 26, stack every 25 turns (up to 4), stay for 75 turns, then drain
    # Each stack: 14 damage, stacks up to 4 (max 56 damage)
    # After 4 stacks, stays for 75 turns, then drains
    if turn < 26:
        return 0
    # Determine stack count
    stack = min(4, ((turn - 26) // 25) + 1)
    # After 4 stacks, stays for 75 turns, then drains
    if stack == 4:
        # 4 stacks start at turn = 26 + 25*3 = 101
        stack_start = 26 + 25*3
        if turn > stack_start + 75:
            # Draining: stacks decrease every 25 turns
            drain_turns = turn - (stack_start + 75)
            stack = max(0, 4 - (drain_turns // 25) - 1)
    return stack * 14

def get_available_actions(game_state, snake):
    board_width = game_state['board']['width']
    board_height = game_state['board']['height']
    
    my_id = snake['id']
    my_snake = next((s for s in game_state['board']['snakes'] if s['id'] == my_id), None)
    if not my_snake:
        return []

    my_head = my_snake['body'][0]
    my_neck = my_snake['body'][1] if len(my_snake['body']) > 1 else my_head

    is_move_safe = {"up": True, "down": True, "left": True, "right": True}

    # No reversing
    if my_neck["x"] < my_head["x"]: is_move_safe["left"] = False
    elif my_neck["x"] > my_head["x"]: is_move_safe["right"] = False
    elif my_neck["y"] < my_head["y"]: is_move_safe["down"] = False
    elif my_neck["y"] > my_head["y"]: is_move_safe["up"] = False

    for m in list(is_move_safe):
        if not is_move_safe[m]:
            continue
        new_head = get_new_head(my_head, m)
        # Out of bounds
        if not (0 <= new_head["x"] < board_width and 0 <= new_head["y"] < board_height):
            is_move_safe[m] = False
            continue

        # Collide with any body (except tail if not eating)
        for snake in game_state['board']['snakes']:
            # If snake will eat, its tail stays; otherwise, tail moves
            body_to_check = snake['body'][:-1] if len(snake['body']) > 1 else snake['body']
            if new_head in body_to_check:
                is_move_safe[m] = False
                break

    return [m for m, safe in is_move_safe.items() if safe]

def manhattan_dist(a, b):
    return abs(a["x"] - b["x"]) + abs(a["y"] - b["y"])

def get_best_moves_towards(safe_moves, head, targets):
    if not targets:
        return safe_moves
    best_moves = []
    min_dist = float('inf')
    for move in safe_moves:
        new_head = get_new_head(head, move)
        dist = min(manhattan_dist(new_head, t) for t in targets)
        if dist < min_dist:
            min_dist = dist
            best_moves = [move]
        elif dist == min_dist:
            best_moves.append(move)
    return best_moves if best_moves else safe_moves


def flood_fill(start, game_state, max_tiles=100):
    """
    Tail-aware flood fill: allows us our snake to step onto its own body segments that will have moved by the time the fill reaches them.
    """
    my_id = game_state['you']['id']
    my_snake = next((s for s in game_state['board']['snakes'] if s['id'] == my_id), None)
    if not my_snake:
        return 0, set()  # No snake, no space
    my_body = my_snake['body']
    # Map body segment positions to their index (distance from head)
    body_pos_to_idx = {(b['x'], b['y']): idx for idx, b in enumerate(my_body)}

    # Build set of all other occupied tiles (other snakes and own head excluded)
    occupied = set()
    for s in game_state['board']['snakes']:
        if s['id'] == my_id:
            # Only add own body except head (handled by logic below)
            for b in s['body'][1:]:
                occupied.add((b['x'], b['y']))
        else:
            for b in s['body']:
                occupied.add((b['x'], b['y']))

    visited = set()
    # Each stack entry: (x, y, steps_from_head)
    stack = [(start['x'], start['y'], 0)]
    count = 0
    while stack and count < max_tiles:
        x, y, steps = stack.pop()
        if (x, y, steps) in visited:
            continue

        # Out of bounds
        if not (0 <= x < game_state['board']['width'] and 0 <= y < game_state['board']['height']):
            continue

        # Check if occupied by own body
        if (x, y) in body_pos_to_idx:
            idx = body_pos_to_idx[(x, y)]
            # Can only step on own body if steps >= idx (tail will have moved)
            if steps < idx:
                continue
        # Check if occupied by other snakes
        elif (x, y) in occupied:
            continue

        visited.add((x, y, steps))
        count += 1

        # Add neighbors
        stack.extend([
            (x+1, y, steps+1), (x-1, y, steps+1),
            (x, y+1, steps+1), (x, y-1, steps+1)
        ])

    return count, visited

def flood_dist(visited, target):
    for vx, vy, steps in visited:
        if (vx, vy) == (target['x'], target['y']):
            return steps
    return float('inf')

def evaluate_position(head, game_state):
    my_id = game_state['you']['id']
    score = 0
    snakes = game_state['board']['snakes']
    max_tiles = game_state['board']['width'] * game_state['board']['height']
    space, visited = flood_fill(head, game_state, max_tiles) # More space means less chance of getting trapped, and more room to maneuver
    min_dist = float('inf')
    for f in game_state['board']['food']:
        min_dist = min(min_dist, flood_dist(visited, f))

    hazards = set()
    if 'hazards' in game_state['board']:
        for h in game_state['board']['hazards']:
            hazards.add((h['x'], h['y']))

    health = game_state['you']['health']
    score -= 50 * (100/(health+1))

    if (head['x'], head['y']) in hazards:
        damage = get_hazard_damage(game_state.get('turn', 0))
        if health-damage <= 0:
            return -3  # Immediate death
        score -= 300 + 40 * 100/(max(health-damage, 1))  # strong penalty

    food = game_state['board']['food']
    if food:
        min_dist = min(flood_dist(visited, f) for f in food)
        score += (500 / (min_dist + 1)) * (200/(health+1))  # Reward closer food

    opponents = [s for s in snakes if s['id'] != my_id]
    my_length = len(game_state['you']['body'])
    for opp in opponents:
        opp_head = opp['body'][0]
        dist = flood_dist(visited, opp_head)

        if my_length > len(opp['body']):
            score += 200 / ((dist**2) + 1)
        else:
            score -= 1500 / ((dist**2) + 1)

    health = game_state['you']['health']
    score += health * 3  # Reward higher health

    score += my_length * 50  # Reward longer length

    num_snakes = len(snakes) # Fewer opponents is better, outlive them
    score += (max_snakes - num_snakes) * 200

    safe_moves = len(get_available_actions(game_state, game_state['you'])) # More safe moves means more options and less chance of getting trapped
    score += safe_moves * 500
    if safe_moves == 0:
        return -3  # Immediate death
    if space <5:
        print(f"Warning: Only {space} spaces available for a snake of length {len(game_state['you']['body'])}")
    if space < len(game_state['you']['body'])/2:
        print(f"Warning: Only {space} spaces available for a snake of length {len(game_state['you']['body'])}")
        score -= 5000  # almost certain death soon
    elif space < len(game_state['you']['body']):
        print(f"Warning: Only {space} spaces available for a snake of length {len(game_state['you']['body'])}")
        score -= 500  # possible death soon
    else:
        score -= (1-(max_tiles/(space+1))) * 500

    score = score / 5000  # scaling
    # score = score + 100  # shift to make positive
    # score = score / 100  # scale to keep close to [-1, 1]
    score = min(max(score, -1), 1)  # clamp to [-1, 1]
    return score

# info is called when you create your Battlesnake on play.battlesnake.com
# and controls your Battlesnake's appearance
# TIP: If you open your Battlesnake URL in a browser you should see this data
def info() -> typing.Dict:
    print("INFO")

    return {
        "apiversion": "1",
        "author": "",  # TODO: Your Battlesnake Username
        "color": "#888888",  # TODO: Choose color
        "head": "default",  # TODO: Choose head
        "tail": "default",  # TODO: Choose tail
    }


max_snakes = 2 # Assume at least 2 snakes at start
# start is called when your Battlesnake begins a game
def start(game_state: typing.Dict):
    global max_snakes
    max_snakes = max(len(game_state['board']['snakes']), 2)  # Assume at least 2 snakes at start



# end is called when your Battlesnake finishes a game
def end(game_state: typing.Dict):
    print("GAME OVER\n")

# move is called on every turn and returns your next move
# Valid moves are "up", "down", "left", or "right"
# See https://docs.battlesnake.com/api/example-move for available data
def move(game_state: typing.Dict) -> typing.Dict:

    is_move_safe = {"up": True, "down": True, "left": True, "right": True}

    # We've included code to prevent your Battlesnake from moving backwards
    my_head = game_state["you"]["body"][0]  # Coordinates of your head
    my_neck = game_state["you"]["body"][1]  # Coordinates of your "neck"

    if my_neck["x"] < my_head["x"]:  # Neck is left of head, don't move left
        is_move_safe["left"] = False

    elif my_neck["x"] > my_head["x"]:  # Neck is right of head, don't move right
        is_move_safe["right"] = False

    elif my_neck["y"] < my_head["y"]:  # Neck is below head, don't move down
        is_move_safe["down"] = False

    elif my_neck["y"] > my_head["y"]:  # Neck is above head, don't move up
        is_move_safe["up"] = False

    # Step 1 - Prevent your Battlesnake from moving out of bounds
    board_width = game_state['board']['width']
    board_height = game_state['board']['height']

    for move in is_move_safe:
        # print the value the arguments to get_new_head
        print(f"my_head: {my_head}, move: {move}")
        new_head = get_new_head(my_head, move)
        if 0 > new_head["y"] >= board_height and 0 > new_head["x"] >= board_width:
                is_move_safe[move] = False

    # Step 2 - Prevent your Battlesnake from colliding with itself
    my_body = game_state['you']['body']

    for move in is_move_safe:
        if not is_move_safe[move]:
            continue
        new_head = get_new_head(my_head, move)
        if new_head in my_body:
            is_move_safe[move] = False

    # Step 3 - Prevent your Battlesnake from colliding with other Battlesnakes
    opponents = game_state['board']['snakes']

    for move in is_move_safe:
        if not is_move_safe[move]:
            continue
        new_head = get_new_head(my_head, move)
        for snake in opponents:
            if new_head in snake['body']:
                is_move_safe[move] = False
                break

    # Are there any safe moves left?
    safe_moves = []
    for move, isSafe in is_move_safe.items():
        if isSafe:
            safe_moves.append(move)

    if len(safe_moves) == 0:
        print(f"MOVE {game_state['turn']}: No safe moves detected! Moving down")
        return {"move": "down"}

    # Step 4 : Choose to move towards food or to box in opponent
    my_id = game_state['you']['id']
    
    # food = game_state['board']['food']
    # if food:
    #     # Move towards food
    #     best_moves = get_best_moves_towards(safe_moves, my_head, food)
    #     next_move = random.choice(best_moves)
    # else:
    #     # Try to box in another snake
    #     opponents = [s for s in game_state['board']['snakes'] if s['id'] != my_id]
    #     if opponents:
    #         opponent_heads = [snake['body'][0] for snake in opponents]
    #         best_moves = get_best_moves_towards(safe_moves, my_head, opponent_heads)
    #         next_move = random.choice(best_moves)
    #     else:
    #         next_move = random.choice(safe_moves)

    # Use heuristic evaluation to choose the best safe move
    best_score = -float('inf')
    best_move = None
    
    for move in safe_moves:
        new_head = get_new_head(my_head, move)
        # Simulate the move
        temp_game_state = fast_copy_game_state(game_state)
        temp_snake = next(s for s in temp_game_state['board']['snakes'] if s['id'] == my_id)
        temp_snake['body'] = [new_head] + temp_snake['body']
        # Replace our snake in temp_game_state
        for idx, s in enumerate(temp_game_state['board']['snakes']):
            if s['id'] == my_id:
                temp_game_state['board']['snakes'][idx] = temp_snake
                break
        temp_game_state['you'] = temp_snake
        score = evaluate_position(new_head, temp_game_state)
        if score > best_score:
            best_score = score
            best_move = move
        elif score == best_score and random.random() < 0.5:  # Tie-breaker
            best_move = move
    if best_move is None:
        best_move = list(is_move_safe.values())[0]
    next_move = best_move

    print(f"MOVE {game_state['turn']}: {next_move}")
    return {"move": next_move}


# Start server when `python main.py` is run
if __name__ == "__main__":
    from server import run_server

    run_server({"info": info, "start": start, "move": move, "end": end})