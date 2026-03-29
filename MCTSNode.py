import math
from copy import deepcopy
import random
import typing

class MCTSNode:
  def __init__(self, game_state, id, parent, action):
    self.game_state = game_state
    self.id = id
    self.parent = parent
    self.action = action
    self.nodeVisits = 0
    self.totalVisits = 0
    self.wins = 0
    self.children: typing.List['MCTSNode'] = []
    self.available_actions = self.get_available_actions(game_state)

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

  # maybe this could be better so our code can be more DRY
  def get_available_actions(self, game_state):
    my_id = game_state['you']['id']
    my_snake = next(s for s in game_state['board']['snakes'] if s['id'] == my_id)
    if not my_snake:
      return []

    my_head = my_snake['body'][0]
    my_neck = my_snake['body'][1] if len(my_snake['body']) > 1 else my_head
    board_width = game_state['board']['width']
    board_height = game_state['board']['height']
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
      if not (0 <= new_head["x"] < board_width and 0 <= new_head["y"] < board_height):
        is_move_safe[m] = False
        continue

      for snake in game_state['board']['snakes']:
        body_to_check = snake['body'][:-1]
        if new_head in body_to_check:
          is_move_safe[m] = False
          break

    return [m for m, safe in is_move_safe.items() if safe]
  
  def is_fully_expanded(self):
    return len(self.available_actions) == 0
  
  def expand(self):
    if self.is_fully_expanded():
      return None
    
    action = self.available_actions.pop()
    new_game_state = deepcopy(self.game_state)
    new_head = self.get_new_head(new_game_state['you']['body'][0], action)
    new_game_state['you']['body'].insert(0, new_head)
    child_node = MCTSNode(new_game_state, id=None, parent=self, action=action)
    self.children.append(child_node)
    return child_node

  def is_terminal(self) -> bool:
    snakes = self.game_state['board']['snakes']
    my_id = self.game_state['you']['id']
    return not any(s['id'] == my_id for s in snakes)
  
  def ucb1_score(self, C=1.414213562):
    if self.nodeVisits == 0:
      return math.inf
    
    Q_sa = self.wins / self.nodeVisits
    N_s = self.nodeVisits
    N_sa = self.totalVisits
    return Q_sa + C * math.sqrt(math.log(N_s) / N_sa)
  
  # TODO: Implement
  def rapid_value_action_estimation(self):
    raise NotImplementedError("RAVE is not implemented yet")
  
  def best_child(self, C=1.414213562) -> typing.Optional['MCTSNode']:
    for child in self.children:
      if child.nodeVisits == 0:
        return child
      
    best_score = -math.inf
    best_child = None
    for child in self.children:
      score = child.wins / child.nodeVisits + C * math.sqrt((2 * math.log(self.nodeVisits)) / child.nodeVisits)
      if score > best_score:
        best_score = score
        best_child = child
    return best_child
  
  def backpropagate(self, result):
    self.nodeVisits += 1
    self.totalVisits += 1
    if result:
      self.wins += 1
    
    if self.parent:
      self.parent.backpropagate(result)

  def rollout(self):
    depth = 0
    max_depth = 100

    current_state = deepcopy(self.game_state)
    my_id = current_state['you']['id']
    while depth < max_depth:
      snakes = current_state['board']['snakes']
      if not any(s['id'] == my_id for s in snakes):
        return False

      available_moves = self.get_available_actions(current_state)
      if not available_moves:
        return False

      move = random.choice(available_moves)
      new_head = self.get_new_head(current_state['you']['body'][0], move)
      current_state['you']['body'].insert(0, new_head)
      depth += 1