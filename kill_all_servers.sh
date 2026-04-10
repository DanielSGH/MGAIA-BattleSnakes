#!/bin/bash

for port in 8001 8002 8003 8004; do
  kill $(lsof -t -i:$port)
done
