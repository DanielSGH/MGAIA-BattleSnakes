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


def evaluate_position(head, game_state, my_id):
    score = 0
    food = game_state['board']['food']
    if food:
        min_dist = min(manhattan_dist(head, f) for f in food)
        score += 100 / (min_dist + 1)  # Reward closer food
    opponents = [s for s in game_state['board']['snakes'] if s['id'] != my_id]
    my_length = len(game_state['you']['body'])
    for opp in opponents:
        dist = manhattan_dist(head, opp['body'][0])
        if my_length > len(opp['body']):
            score += 50 / (dist + 1)  # Bonus for hunting smaller opponents
        else:
            score -= 50 / (dist + 1)  # Penalty for being near larger opponents
    score += game_state['you']['health']  # Reward higher health
    score += my_length * 10  # Reward longer length
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


# start is called when your Battlesnake begins a game
def start(game_state: typing.Dict):
    print("GAME START")


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
    
    food = game_state['board']['food']
    if food:
        # Move towards food
        best_moves = get_best_moves_towards(safe_moves, my_head, food)
        next_move = random.choice(best_moves)
    else:
        # Try to box in another snake
        opponents = [s for s in game_state['board']['snakes'] if s['id'] != my_id]
        if opponents:
            opponent_heads = [snake['body'][0] for snake in opponents]
            best_moves = get_best_moves_towards(safe_moves, my_head, opponent_heads)
            next_move = random.choice(best_moves)
        else:
            next_move = random.choice(safe_moves)

    # Use heuristic evaluation to choose the best safe move
    best_score = -float('inf')
    best_move = safe_moves[0]
    
    for move in safe_moves:
        new_head = get_new_head(my_head, move)
        score = evaluate_position(new_head, game_state, my_id)
        if score > best_score:
            best_score = score
            best_move = move
    next_move = best_move

    print(f"MOVE {game_state['turn']}: {next_move}")
    return {"move": next_move}




# Start server when `python main.py` is run
if __name__ == "__main__":
    from server import run_server

    run_server({"info": info, "start": start, "move": move, "end": end})
