import pandas as pd
import trueskill
import matplotlib.pyplot as plt
from collections import defaultdict
import argparse
import glob
import os

csv_base_path = "logs"
subfolders = [d for d in os.listdir(csv_base_path) if os.path.isdir(os.path.join(csv_base_path, d))]

for subfolder in subfolders:
    csv_files = glob.glob(f"{csv_base_path}/{subfolder}/*.csv")
    
    if not csv_files:
        continue
    
    df = pd.concat([pd.read_csv(file) for file in csv_files], ignore_index=True)
    
    alive_df = df[df["alive"] == 1]
    
    last_turn = (
        alive_df
        .groupby(["game_id", "snake_name"])["turn"]
        .max()
        .reset_index()
    )
    
    games = []
    
    for game_id, group in last_turn.groupby("game_id"):
        sorted_group = group.sort_values("turn", ascending=False)
        game = [(row["snake_name"],) for _, row in sorted_group.iterrows()]
        games.append(game)
    
    env = trueskill.TrueSkill()
    ratings = defaultdict(env.Rating)
    
    for game in games:
        teams = [[ratings[player[0]]] for player in game]
        new_ratings = env.rate(teams)
        
        for i, team in enumerate(game):
            player = team[0]
            ratings[player] = new_ratings[i][0]
    
    results = pd.DataFrame([
        {
            "snake": name,
            "mu": r.mu,
            "sigma": r.sigma,
            "score": r.mu - 3 * r.sigma
        }
        for name, r in ratings.items()
    ])
    
    results = results.sort_values("score", ascending=False)
    print(f"\n{subfolder}:")
    print(results)
    
    plt.figure(figsize=(12, 6))
    plt.bar(results["snake"], results["score"])
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("TrueSkill Value")
    plt.title(f"TrueSkill Ratings - {subfolder}")
    plt.tight_layout()
    plt.savefig(f"trueskill_{subfolder}.png", dpi=300, bbox_inches="tight")
    plt.close()