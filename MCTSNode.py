import math
from copy import deepcopy
import random
import typing

class MCTSNode:
	def __init__(self, game_state, parent, action):
		self.game_state = game_state
		self.board_width = game_state['board']['width']
		self.board_height = game_state['board']['height']
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
 
	def flood_fill(self, start, game_state, max_tiles=50):
		# checks if we are trapped or not, and how much space we have to move around in
		visited = set()
		stack = [(start['x'], start['y'])]
		occupied = set()

		for s in game_state['board']['snakes']:
			for b in s['body']:
				occupied.add((b['x'], b['y']))

		if 'hazards' in game_state['board']:
			for h in game_state['board']['hazards']:
				occupied.add((h['x'], h['y']))

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
		food = game_state['board']['food']
		if food:
			min_dist = min(self.manhattan_dist(head, f) for f in food)
			score += 100 / (min_dist + 1)  # Reward closer food

		opponents = [s for s in game_state['board']['snakes'] if s['id'] != my_id]
		my_length = len(game_state['you']['body'])
		for opp in opponents:
			opp_head = opp['body'][0]
			dist = self.manhattan_dist(head, opp_head)

			if my_length > len(opp['body']):
				score += 100 / (dist + 1)  # stronger hunting
			elif my_length < len(opp['body']):
				score -= 150 / (dist + 1)  # stronger fear
			else:
				score -= 80 / (dist + 1)   # avoid equal fights

		score += game_state['you']['health']  # Reward higher health
		score += my_length * 10  # Reward longer length

		num_snakes = len(game_state['board']['snakes']) # Fewer opponents is better, outlive them
		score += (10 - num_snakes) * 200

		safe_moves = len(self.get_available_actions(game_state, game_state['you'])) # More safe moves means more options and less chance of getting trapped
		score += safe_moves * 50

		space = self.flood_fill(head, game_state) # More space means less chance of getting trapped, and more room to maneuver
		score += space * 3

		return score

	def is_fully_expanded(self):
		return len(self.available_actions) == 0 and len(self.children) > 0 # can we not have a node with no children if all actions lead to terminal states?

	def is_dead_end(self):
		return len(self.available_actions) == 0 and len(self.children) == 0 # or is that this function, but it is not used anywhere in the code

	def expand(self):
		if self.is_fully_expanded():
			return None

		action = self.available_actions.pop()
		new_game_state = deepcopy(self.game_state)
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

	# TODO: Implement
	def rapid_value_action_estimation(self):
		raise NotImplementedError("RAVE is not implemented yet")

	def best_child(self) -> typing.Optional['MCTSNode']:
		if not self.children:
			return None
		return max(self.children, key=lambda c: c.ucb1_score())

	def backpropagate(self, result):
		self.nodeVisits += 1
		self.totalVisits += 1
		if result != 0:
			self.wins += result

		if self.parent:
			self.parent.backpropagate(result)

	def rollout(self):
		depth = 0
		max_depth = 100

		current_state = deepcopy(self.game_state)
		my_id = self.game_state['you']['id']
		turn = current_state.get('turn', 0)
		survived = 0
		while depth < max_depth:
			snakes = current_state['board']['snakes']
			if not any(s['id'] == my_id for s in snakes):
				return 0  # Lost

			survived += 1
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

			# Resolve ALL collisions and hazard damage after movement
			current_state = self.resolve_collisions(current_state, turn + depth)
			snakes = current_state['board']['snakes']

			depth += 1
		# Reward: survived max_depth
		return self.evaluate_position(current_state['you']['body'][0], current_state)