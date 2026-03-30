import math
from copy import deepcopy
import random
import typing

class MCTSNode:
  def __init__(self, game_state, id, parent, action):
    self.game_state = game_state
    self.board_width = game_state['board']['width']
    self.board_height = game_state['board']['height']
    self.id = id
    self.parent = parent
    self.action = action
    self.nodeVisits = 0
    self.totalVisits = 0
    self.wins = 0
    self.children: typing.List['MCTSNode'] = []
    self.available_actions = self.get_available_actions(game_state, game_state['you'])

  def get_new_head(self, head, move):
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
    
  def resolve_collisions(self, game_state):
    snakes = game_state['board']['snakes']

    # Remove snakes out of bounds or starved
    alive = []
    for s in snakes:
      head = s['body'][0]
      if not (0 <= head['x'] < self.board_width and 0 <= head['y'] < self.board_height):
        continue
      if s['health'] <= 0:
        continue
      alive.append(s)

    snakes = alive

    # Body collisions
    occupied = set()
    for s in snakes:
      for segment in s['body'][1:]:
        occupied.add((segment['x'], segment['y']))

    alive = []
    for s in snakes:
      head = s['body'][0]
      if (head['x'], head['y']) in occupied:
        continue
      alive.append(s)

    snakes = alive

    # Head-to-head collisions
    head_positions = {}
    for s in snakes:
      pos = (s['body'][0]['x'], s['body'][0]['y'])
      head_positions.setdefault(pos, []).append(s)

    survivors = []
    for pos, ss in head_positions.items():
      if len(ss) == 1:
        survivors.append(ss[0])
      else:
        max_len = max(len(s['body']) for s in ss)
        biggest = [s for s in ss if len(s['body']) == max_len]

        if len(biggest) == 1:
          survivors.append(biggest[0])

    game_state['board']['snakes'] = survivors

    return game_state

  # maybe this could be better so our code can be more DRY
  def get_available_actions(self, game_state, snake):
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
      new_head = self.get_new_head(my_head, m)
      # Out of bounds
      if not (0 <= new_head["x"] < self.board_width and 0 <= new_head["y"] < self.board_height):
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
  
  def is_fully_expanded(self):
    return len(self.available_actions) == 0 and len(self.children) > 0 # can we not have a node with no children if all actions lead to terminal states?
  
  def is_dead_end(self):
    return len(self.available_actions) == 0 and len(self.children) == 0 # or is that this function, but it is not used anywher in the code
  
  def expand(self):
    if self.is_fully_expanded():
      return None

    action = self.available_actions.pop()
    new_game_state = deepcopy(self.game_state)
    my_id = self.id

    snakes = new_game_state['board']['snakes']

    moves_dict = {}

    # Set our move
    moves_dict[my_id] = action

    # Sample opponent moves once
    for snake in snakes:
      if snake['id'] == my_id:
        continue
      moves = self.get_available_actions(new_game_state, snake)
      if moves:
        moves_dict[snake['id']] = random.choice(moves)
      else:
        moves_dict[snake['id']] = None

    # Apply all moves
    for snake in snakes:
      move = moves_dict[snake['id']]
      if move is None:
        continue

      new_head = self.get_new_head(snake['body'][0], move)
      snake['body'].insert(0, new_head)
      snake['health'] -= 1

      if new_head in new_game_state['board']['food']:
        snake['health'] = 100
        new_game_state['board']['food'].remove(new_head)

    # Resolve collisions
    new_game_state = self.resolve_collisions(new_game_state)

    # Sync our snake
    for snake in new_game_state['board']['snakes']:
      if snake['id'] == my_id:
        new_game_state['you'] = snake
        break
    else:
      new_game_state['you']['body'] = []
      new_game_state['you']['health'] = 0

    child_node = MCTSNode(new_game_state, id=my_id, parent=self, action=action)
    self.children.append(child_node)
    return child_node

  def is_terminal(self) -> bool:
    snakes = self.game_state['board']['snakes']
    my_id = self.id
    return not any(s['id'] == my_id for s in snakes)
  
  def ucb1_score(self, C=1.414213562):
    if self.nodeVisits == 0:
      return math.inf
    
    Q_sa = self.wins / self.nodeVisits
    N_s = self.parent.nodeVisits
    N_sa = self.nodeVisits
    return Q_sa + C * math.sqrt(math.log(N_s) / N_sa)
  
  # TODO: Implement
  def rapid_value_action_estimation(self):
    raise NotImplementedError("RAVE is not implemented yet")
  
  def best_child(self, C=1.414213562) -> typing.Optional['MCTSNode']:
    if not self.children:
        return None
    return max(self.children, key=lambda c: c.ucb1_score(C))
  
  def backpropagate(self, result):
    self.nodeVisits += 1
    self.totalVisits += 1
    if result:
      self.wins += 1
    
    if self.parent:
      self.parent.backpropagate(result)

  def rollout(self): # maybe use 1 and 0 instead of True or False, or maybe depth/max_depth or the heuristic score of the final state
    depth = 0
    max_depth = 100

    current_state = deepcopy(self.game_state)
    my_id = self.id
    while depth < max_depth:
      snakes = current_state['board']['snakes']
      if not any(s['id'] == my_id for s in snakes):
        return 0

      # Move all snakes randomly
      moves_dict = {}
      for snake in snakes:
        moves = self.get_available_actions(current_state, snake)
        if moves:
          moves_dict[snake['id']] = random.choice(moves)
        else:
          moves_dict[snake['id']] = None

      # Apply moves
      for snake in snakes:
        move = moves_dict[snake['id']]
        if move is None:
          continue

        new_head = self.get_new_head(snake['body'][0], move)
        snake['body'].insert(0, new_head)
        snake['health'] -= 1

        if new_head in current_state['board']['food']:
          snake['health'] = 100
          current_state['board']['food'].remove(new_head)

      # Resolve ALL collisions after  movement
      current_state = self.resolve_collisions(current_state)

      snakes = current_state['board']['snakes']

      depth += 1
    # Reward: survived max_depth
    return 1