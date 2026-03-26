import math
from copy import deepcopy

class MCTSNode:
  def __init__(self, game_state, id, parent, action):
    self.game_state = game_state
    self.id = id
    self.parent = parent
    self.action = action
    self.nodeVisits = 0
    self.totalVisits = 0
    self.wins = 0
    self.children = []
    self.available_actions = self.get_available_actions(game_state)

  def get_available_actions(self, game_state):
    raise NotImplementedError("get_available_actions should be implemented based on the game logic")
  
  def is_fully_expanded(self):
    return len(self.available_actions) == 0
  
  def expand(self):
    raise NotImplementedError("expand should be implemented to create a new child node based on the available actions")

  def is_terminal(self):
    snakes = self.game_state['board']['snakes']
    my_id = self.game_state['you']['id']
    return not any(s['id'] == my_id for s in snakes)
  
  def ucb1_score(self, C=1.414213562):
    raise NotImplementedError("ucb1_score should be implemented to calculate the UCB1 score for the node")
    # return Q_sa + C * math.sqrt(math.log(N_s) / N_sa)
  
  # TODO: Implement
  def rapid_value_action_estimation(self):
    raise NotImplementedError("RAVE is not implemented yet")
  
  def best_child(self, C=1.414213562):
    raise NotImplementedError("best_child should be implemented to select the best child node based on the formula in the slides")
  
  def backpropagate(self, result):
    raise NotImplementedError("backpropagate not implemented yet")

  def rollout(self):
    raise NotImplementedError("rollout should be implemented to simulate a random playout from the current game state until a terminal state is reached")