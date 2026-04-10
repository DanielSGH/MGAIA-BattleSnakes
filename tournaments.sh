#!/bin/sh

./kill_all_servers.sh

PORT=8001 python main_MCTS.py --policy "$2" --score-method "$1" &
PID1=$!
PORT=8002 python main_MCTS.py --policy "$2" --score-method "$1" &
PID2=$!
PORT=8003 python main_heuristic.py &
PID3=$!
PORT=8004 python main_heuristic.py &
PID4=$!

echo "Running PIDs: $PID1 $PID2 $PID3 $PID4"

# # Kill all processes
# kill $PID1 $PID2 $PID3 $PID4