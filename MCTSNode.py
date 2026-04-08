import math
from copy import deepcopy
import random
import typing
from collections import defaultdict
import numpy as np


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

class MCTSNode:
	def __init__(self, game_state, parent, action, policy='heuristic', score_method='ucb1'):
		self.game_state = game_state
		self.board_width = game_state['board']['width']
		self.board_height = game_state['board']['height']
		self.max_snakes = max(len(game_state['board']['snakes']), parent.max_snakes if parent else 0)
		self.parent = parent
		self.action = action
		self.policy = policy
		self.nodeVisits = 0
		self.totalVisits = 0
		self.wins = 0
		self.wins_sq = 0
		self.score_method = score_method  # or "rave" or "grave"
		self.amaf_visits: typing.Dict[str, int] = defaultdict(int)   # action -> count
		self.amaf_wins: typing.Dict[str, float] = defaultdict(float)     # action -> wins
		self.children: typing.List['MCTSNode'] = []
		self.available_actions = self.get_available_actions(game_state, game_state['you'])
		random.shuffle(self.available_actions)  # Randomize expansion order

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

	def get_hazard_damage(self, turn):
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
	
	def resolve_collisions(self, game_state, turn):
		snakes = game_state['board']['snakes']
		hazard = set()
		if 'hazards' in game_state['board']:
			for h in game_state['board']['hazards']:
				hazard.add((h['x'], h['y']))

		# Remove snakes out of bounds or starved
		alive = []
		for s in snakes:
			head = s['body'][0]
			if not (0 <= head['x'] < self.board_width and 0 <= head['y'] < self.board_height):
				continue
			if s['health'] <= 0:
				continue
			# Hazard damage (only head)
			if (head['x'], head['y']) in hazard:
				s['health'] -= self.get_hazard_damage(turn)
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

	def get_available_actions(self, game_state, snake) -> typing.List[str]:
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
 
	def flood_fill(self, start, game_state, max_tiles=50):
		# checks if we are trapped or not, and how much space we have to move around in
		visited = set()
		stack = [(start['x'], start['y'])]
  
		occupied = set()
		for s in game_state['board']['snakes']:
			for b in s['body']:
				occupied.add((b['x'], b['y']))

		# hazards = set()
		# if 'hazards' in game_state['board']:
		# 	for h in game_state['board']['hazards']:
		# 		hazards.add((h['x'], h['y']))

		count = 0
		while stack and count < max_tiles:
			x, y = stack.pop()
			if (x, y) in visited or (x, y) in occupied:
				continue

			if not (0 <= x < self.board_width and 0 <= y < self.board_height):
				continue

			visited.add((x, y))
			count += 1

			stack.extend([
				(x+1, y), (x-1, y),
				(x, y+1), (x, y-1)
			])

		return count
	
	def manhattan_dist(self, a, b):
		return abs(a['x'] - b['x']) + abs(a['y'] - b['y'])

	def evaluate_position(self, head, game_state):
		my_id = game_state['you']['id']
		score = 0
		snakes = game_state['board']['snakes']
  
		hazards = set()
		if 'hazards' in game_state['board']:
			for h in game_state['board']['hazards']:
				hazards.add((h['x'], h['y']))
   
		health = game_state['you']['health']
		if health < 30:
			score -= (30 - health) * 10  # low health penalty
   
		if (head['x'], head['y']) in hazards:
			damage = self.get_hazard_damage(game_state.get('turn', 0))
			score -= (200 + damage * 5) * 100/health  # strong penalty
   
		food = game_state['board']['food']
		if food:
			min_dist = min(self.manhattan_dist(head, f) for f in food)
			score += (500 / (min_dist + 1)) * 100/health  # Reward closer food

		opponents = [s for s in snakes if s['id'] != my_id]
		my_length = len(game_state['you']['body'])
		for opp in opponents:
			opp_head = opp['body'][0]
			dist = self.manhattan_dist(head, opp_head)

			if my_length > len(opp['body']):
				score += 100 / (dist + 1)  
			else:
				score -= 500 / (dist + 1) 

		health = game_state['you']['health']
		score += health * 3  # Reward higher health
   
		score += my_length * 50  # Reward longer length

		num_snakes = len(snakes) # Fewer opponents is better, outlive them
		score += (self.max_snakes - num_snakes) * 200

		safe_moves = len(self.get_available_actions(game_state, game_state['you'])) # More safe moves means more options and less chance of getting trapped
		score += safe_moves * 100

		space = self.flood_fill(head, game_state) # More space means less chance of getting trapped, and more room to maneuver
		if space < len(game_state['you']['body'])/2:
			score -= 5000  # almost certain death soon
		elif space < len(game_state['you']['body']):
			print(f"Warning: Only {space} spaces available for a snake of length {len(game_state['you']['body'])}")
			score -= 1000  # possible death soon
		else:
			score += space * 50

		return score/100  # scale down to keep values manageable

	def is_fully_expanded(self):
		return len(self.available_actions) == 0 and len(self.children) > 0 # can we not have a node with no children if all actions lead to terminal states?

	def is_dead_end(self):
		return len(self.available_actions) == 0 and len(self.children) == 0 # or is that this function, but it is not used anywhere in the code

	def expand(self):
		if self.is_fully_expanded():
			return None

		action = random.choice(self.available_actions)
		self.available_actions.remove(action)
		new_game_state = fast_copy_game_state(self.game_state)
		my_id = self.game_state['you']['id']
		turn = new_game_state.get('turn', 0)

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
			else:
				snake['body'].pop()  # Remove tail if not eating

		# Resolve collisions and hazard damage
		new_game_state = self.resolve_collisions(new_game_state, turn)

		# Sync our snake
		for snake in new_game_state['board']['snakes']:
			if snake['id'] == my_id:
				new_game_state['you'] = snake
				break
		else:
			new_game_state['you']['body'] = []
			new_game_state['you']['health'] = 0

		child_node = MCTSNode(new_game_state, parent=self, action=action)
		self.children.append(child_node)
		return child_node

	def is_terminal(self) -> bool:
		snakes = self.game_state['board']['snakes']
		my_id = self.game_state['you']['id']
		return not any(s['id'] == my_id for s in snakes)

	def ucb1_score(self):
		if self.nodeVisits == 0:
			return math.inf
		C = math.sqrt(2)
		Q_sa = self.wins / self.nodeVisits
		N_s = self.parent.nodeVisits
		N_sa = self.nodeVisits
		return Q_sa + C * math.sqrt(math.log(N_s) / N_sa)
	
	def ucb1_tuned_score(self):
		if self.nodeVisits == 0:
			return math.inf
		
		r_k = self.wins / self.nodeVisits
		t = self.parent.nodeVisits
		t_k = self.nodeVisits
		V = (self.wins_sq / t_k - r_k**2) + math.sqrt(2 * math.log(t) / t_k)
		return r_k * math.sqrt((math.log(t) * min(0.25, V)) / t_k)

	def rave_score(self):
		if self.nodeVisits == 0:
			return math.inf

		ref = self.parent  # start from parent
		while ref.parent is not None:
			if ref.nodeVisits >= 10:
				break
			ref = ref.parent

		parent = self.parent
		action = self.action

		# Standard value (same as before)
		C = math.sqrt(2)
		Q_sa = self.wins / self.nodeVisits
		N_s = parent.nodeVisits
		N_sa = self.nodeVisits

		if self.score_method == "rave":
			# AMAF rave values
			amaf_n = parent.amaf_visits.get(action, 0)
			amaf_w = parent.amaf_wins.get(action, 0)
		else:
			# AMAF grave values
			amaf_n = ref.amaf_visits.get(action, 0)
			amaf_w = ref.amaf_wins.get(action, 0)

		amaf = amaf_w / amaf_n if amaf_n > 0 else 0

		# Blend
		beta = amaf_n / (self.nodeVisits + amaf_n + 1e-6)

		blended = (1 - beta) * Q_sa + beta * amaf

		return blended + C * math.sqrt(math.log(N_s) / N_sa)

	def best_child(self) -> typing.Optional['MCTSNode']:
		if not self.children:
			return None

		if self.score_method == "ucb1_tuned":
			return max(self.children, key=lambda c: c.ucb1_tuned_score())
		elif self.score_method == "ucb1":
			return max(self.children, key=lambda c: c.ucb1_score())
		else:
			return max(self.children, key=lambda c: c.rave_score())

	def backpropagate(self, result, amaf_actions=None):
		self.nodeVisits += 1
		self.totalVisits += 1
		# Update AMAF stats for all actions taken in the simulation
		if amaf_actions is not None:
			for action in amaf_actions:
				self.amaf_visits[action] += 1
				if result != 0:
					self.amaf_wins[action] += result
		# Standard win update
		if result != 0:
			self.wins += result
			self.wins_sq += result * result

		if self.parent:
			self.parent.backpropagate(result, amaf_actions)

	def rollout(self):
		depth = 0
		max_depth = 40 # or a differen value, not to big since looking far ahead is not very useful in this game, and it will also make the simulations slower

		current_state = fast_copy_game_state(self.game_state)
		my_id = self.game_state['you']['id']
		turn = current_state.get('turn', 0)
		survived = 0
		amaf_actions = []  # Track all actions taken by our agent
		while depth < max_depth:
			snakes = current_state['board']['snakes']
			if not any(s['id'] == my_id for s in snakes):
				# Return both result and actions for AMAF
				return -100, amaf_actions  # Lost

			survived += 1
			# Move all snakes randomly
			moves_dict = {}
			for snake in snakes:
				moves = self.get_available_actions(current_state, snake)
				if moves:
					if snake['id'] == my_id and self.policy == 'heuristic':
						# Pure heuristic: pick the move with the highest evaluation
						best_move = None
						best_score = float('-inf')
						my_head = snake['body'][0]
						for move in moves:
							new_head = self.get_new_head(my_head, move)
							# Simulate the move
							temp_game_state = fast_copy_game_state(current_state)
							temp_snake = next(s for s in temp_game_state['board']['snakes'] if s['id'] == my_id)
							temp_snake['body'] = [new_head] + temp_snake['body']
							if new_head in temp_game_state['board']['food']:
								temp_snake['health'] = 100
								temp_game_state['board']['food'].remove(new_head)
							else:
								temp_snake['body'].pop()  # Remove tail if not eating
							# Replace our snake in temp_game_state
							for idx, s in enumerate(temp_game_state['board']['snakes']):
								if s['id'] == my_id:
									temp_game_state['board']['snakes'][idx] = temp_snake
									break
							temp_game_state['you'] = temp_snake
							score = self.evaluate_position(new_head, temp_game_state)
							if score > best_score:
								best_score = score
								best_move = move
							elif score == best_score and random.random() < 0.5:  # Tie-breaker
								best_move = move
						moves_dict[snake['id']] = best_move
						amaf_actions.append(best_move)
					else:
						chosen = random.choice(moves)
						moves_dict[snake['id']] = chosen
						if snake['id'] == my_id:
							amaf_actions.append(chosen)
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

			# Resolve ALL collisions and hazard damage after movement
			current_state = self.resolve_collisions(current_state, turn + depth)
			snakes = current_state['board']['snakes']

			depth += 1
		# Reward: survived max_depth
		final_score = self.evaluate_position(current_state['you']['body'][0], current_state)
		return final_score, amaf_actions