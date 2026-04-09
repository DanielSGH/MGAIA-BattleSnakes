import math
from copy import deepcopy
import random
import typing
from collections import defaultdict
import time


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
 
	def flood_fill(self, start, game_state, max_tiles=100):
		"""
		Tail-aware flood fill: allows us our snake to step onto its own body segments that will have moved by the time the fill reaches them.
		"""
		my_id = game_state['you']['id']
		my_snake = next((s for s in game_state['board']['snakes'] if s['id'] == my_id), None)
		if not my_snake:
			return 0, dict()  # No snake, no space
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

		visited = dict()
		# Each stack entry: (x, y, steps_from_head)
		stack = [(start['x'], start['y'], 0)]
		count = 0
		while stack and count < max_tiles:
			x, y, steps = stack.pop()
			if (x, y) in visited:
				if visited[(x, y)] <= steps:
					continue
				else:
					count -= 1

			# Out of bounds
			if not (0 <= x < self.board_width and 0 <= y < self.board_height):
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

			visited[(x, y)] = steps
			count += 1

			# Add neighbors
			stack.extend([
				(x+1, y, steps+1), (x-1, y, steps+1),
				(x, y+1, steps+1), (x, y-1, steps+1)
			])

		return count, visited

	def flood_dist(self, visited, target):
		return visited[(target['x'], target['y'])] if (target['x'], target['y']) in visited else float('inf')

	def evaluate_position(self, head, game_state):
		my_id = game_state['you']['id']
		score = 0
		snakes = game_state['board']['snakes']
		max_tiles = self.board_width * self.board_height
		space, visited = self.flood_fill(head, game_state, max_tiles) # More space means less chance of getting trapped, and more room to maneuver
		   
		hazards = set()
		if 'hazards' in game_state['board']:
			for h in game_state['board']['hazards']:
				hazards.add((h['x'], h['y']))
   
		health = game_state['you']['health']
		if health <= 0:
			return -3  # Immediate death
		score -= 50 * (100/max(health, 1))
      
		food = game_state['board']['food']
		min_dist = 0
		if food:
			min_dist = min(min(self.flood_dist(visited, f) for f in food), 0)
			score += (500 / (min_dist + 1)) * (200/max(health, 1))  # Reward closer food
   
		if (head['x'], head['y']) in hazards:
			damage = self.get_hazard_damage(game_state.get('turn', 0))
			if health-damage <= 0:
				return -3  # Immediate death
			score -= 300 + 40 * 100/(max(health-damage, 1))  # strong penalty
			# score += 10 * (health-damage-min_dist)
   
		opponents = [s for s in snakes if s['id'] != my_id]
		my_length = len(game_state['you']['body'])
		for opp in opponents:
			opp_head = opp['body'][0]
			dist = self.flood_dist(visited, opp_head)

			if my_length > len(opp['body']):
				score += 200 / (max(dist**2, 1))
			else:
				score -= 1500 / (max(dist**2, 1))

		health = game_state['you']['health']
		score += health * 3  # Reward higher health
   
		score += my_length * 50  # Reward longer length

		num_snakes = len(snakes) # Fewer opponents is better, outlive them
		score += (self.max_snakes - num_snakes) * 200

		safe_moves = len(self.get_available_actions(game_state, game_state['you'])) # More safe moves means more options and less chance of getting trapped
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
		self.wins += result
		self.wins_sq += result * result

		if self.parent:
			self.parent.backpropagate(result, amaf_actions)

	def rollout(self):
		depth = 0
		max_depth = 30 # or a differen value, not to big since looking far ahead is not very useful in this game, and it will also make the simulations slower

		current_state = fast_copy_game_state(self.game_state)
		my_id = self.game_state['you']['id']
		turn = current_state.get('turn', 0)
		survived = 0
		amaf_actions = []  # Track all actions taken by our agent
		while depth < max_depth:
			snakes = current_state['board']['snakes']
			if not any(s['id'] == my_id for s in snakes):
				# Return both result and actions for AMAF
				return -3, amaf_actions  # Lost

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
							# temp_game_state = self.resolve_collisions(temp_game_state, turn + depth)
							score = self.evaluate_position(new_head, temp_game_state)
							if score > best_score:
								best_score = score
								best_move = move
							elif score == best_score and random.random() < 0.5:  # Tie-breaker
								best_move = move
						if best_move is None:
							best_move = random.choice(moves)
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
			if not any(s['id'] == my_id for s in snakes):
				# Return both result and actions for AMAF
				return -3, amaf_actions  # Lost

			depth += 1
		# Reward: survived max_depth
		final_score = self.evaluate_position(current_state['you']['body'][0], current_state)
		return final_score, amaf_actions

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
    global max_snakes
    max_snakes = max(len(game_state['board']['snakes']), 2)  # Assume at least 2 snakes at start

# end is called when your Battlesnake finishes a game
def end(game_state: typing.Dict):
    print("GAME OVER\n")

def make_mcts_move(game_state: typing.Dict, policy: str, score_method: str) -> str:
    root = MCTSNode(fast_copy_game_state(game_state), None, None, policy=policy, score_method=score_method)

    deadline = time.time() + 490 / 1000.0
    
    while time.time() < deadline:
        node = root
        # Selection: descend the tree using best_child until a node is not fully expanded or is terminal
        while not node.is_terminal() and not node.is_dead_end():
            if not node.is_fully_expanded():
                # Expansion: expand one of the untried actions
                node = node.expand()
                break
            else:
                node = node.best_child()

        # Simulation and Backpropagation
        winner, amaf_actions = node.rollout()
        node.backpropagate(winner, amaf_actions)

    if root.children:
        best_child = max(root.children, key=lambda c: c.nodeVisits)
        # best_child = max(root.children, key=lambda c: c.wins / c.nodeVisits if c.nodeVisits > 0 else float('-inf'))
        for c in root.children:
            print("\n")
            print(f"Move: {c.action}, Visits: {c.nodeVisits}, Wins: {c.wins}, Winrate: {c.wins / c.nodeVisits if c.nodeVisits > 0 else 0:.2f}")
        print(f"Selected move: {best_child.action} on turn {game_state['turn']}")
    else:
        safe = MCTSNode(game_state, None, None).available_actions
        return {"move": random.choice(safe) if safe else "up"}

    return {"move": best_child.action}


# Start server when `python main.py` is run
if __name__ == "__main__":
	from server import run_server
	import argparse

	parser = argparse.ArgumentParser(description='Configure MCTS parameters')
	parser.add_argument('--policy',
											choices=['random', 'heuristic'],
											default='heuristic',
											help='Rollout policy to use during simulations'
	)
	parser.add_argument('--score-method',
										 choices=['ucb1', 'ucb1_tuned', 'rave'],
										 default='ucb1',
										 help='Tree policy method for selecting child nodes'
	)

	args = parser.parse_args()

	print(f"Running main_MCTS with policy={args.policy} and score_method={args.score_method}")
	run_server({"info": info, "start": start, "move": lambda game_state: make_mcts_move(game_state, args.policy, args.score_method), "end": end})