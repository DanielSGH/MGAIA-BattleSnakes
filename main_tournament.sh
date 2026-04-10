#!/bin/sh

./kill_all_servers.sh

PORT=8001 python main_MCTS.py --policy "random" --score-method "rave" &
PID1=$!
PORT=8002 python main_MCTS.py --policy "random" --score-method "grave" &
PID2=$!
PORT=8003 python main_MCTS.py --policy "random" --score-method "ucb1" &
PID3=$!
PORT=8004 python main_MCTS.py --policy "random" --score-method "ucb1_tuned" &
PID4=$!

echo "Running PIDs: $PID1 $PID2 $PID3 $PID4"

# # Kill all processes
# kill $PID1 $PID2 $PID3 $PID4