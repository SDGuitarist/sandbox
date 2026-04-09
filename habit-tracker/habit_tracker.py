#!/usr/bin/env python3
"""
habit_tracker.py -- A CLI habit tracker with streaks. Stores data in ~/.habit_tracker.json.

Usage:
  python habit_tracker.py add "Exercise"
  python habit_tracker.py log <id>
  python habit_tracker.py list
  python habit_tracker.py delete <id>
  python habit_tracker.py stats <id>
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

DATA_FILE = Path.home() / ".habit_tracker.json"


def load_data():
    if not DATA_FILE.exists():
        return {"habits": []}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error: data file is corrupted. Delete {DATA_FILE} to reset.")
        sys.exit(1)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_next_id(habits):
    if not habits:
        return 1
    return max(h["id"] for h in habits) + 1


def find_habit(habits, habit_id):
    for h in habits:
        if h["id"] == habit_id:
            return h
    return None


def compute_streak(completions):
    if not completions:
        return 0
    dates = sorted([date.fromisoformat(d) for d in completions], reverse=True)
    today = date.today()
    if dates[0] != today and dates[0] != today - timedelta(days=1):
        return 0
    streak = 1
    for i in range(1, len(dates)):
        if dates[i - 1] - dates[i] == timedelta(days=1):
            streak += 1
        else:
            break
    return streak


def compute_longest_streak(completions):
    if not completions:
        return 0
    dates = sorted([date.fromisoformat(d) for d in completions])
    longest = 1
    current = 1
    for i in range(1, len(dates)):
        if dates[i] - dates[i - 1] == timedelta(days=1):
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def cmd_add(args):
    name = args.name.strip()
    if not name:
        print("Error: name cannot be empty.")
        sys.exit(1)

    data = load_data()
    habits = data["habits"]
    new_habit = {
        "id": get_next_id(habits),
        "name": name,
        "created_at": date.today().isoformat(),
        "completions": [],
    }
    habits.append(new_habit)
    save_data(data)
    print(f"Added: [{new_habit['id']}] {new_habit['name']}")


def cmd_log(args):
    data = load_data()
    habit = find_habit(data["habits"], args.id)

    if habit is None:
        print(f"Error: habit #{args.id} not found.")
        sys.exit(1)

    today_str = date.today().isoformat()
    if today_str not in habit["completions"]:
        habit["completions"].append(today_str)
        save_data(data)
        print(f"Logged: [{habit['id']}] {habit['name']} for {today_str}")
    else:
        print(f"Already logged: [{habit['id']}] {habit['name']} for {today_str}")


def cmd_list(args):
    data = load_data()
    habits = data["habits"]

    if not habits:
        print("No habits yet.")
        return

    today_str = date.today().isoformat()
    for h in habits:
        done = "\u2713" if today_str in h["completions"] else "\u25cb"
        streak = compute_streak(h["completions"])
        streak_display = f"{streak}d streak" if streak > 0 else "no streak"
        print(f"{done} [{h['id']}] {h['name']}  ({streak_display})")


def cmd_delete(args):
    data = load_data()
    habit = find_habit(data["habits"], args.id)

    if habit is None:
        print(f"Error: habit #{args.id} not found.")
        sys.exit(1)

    data["habits"] = [h for h in data["habits"] if h["id"] != args.id]
    save_data(data)
    print(f"Deleted: [{habit['id']}] {habit['name']}")


def cmd_stats(args):
    data = load_data()
    habit = find_habit(data["habits"], args.id)

    if habit is None:
        print(f"Error: habit #{args.id} not found.")
        sys.exit(1)

    current = compute_streak(habit["completions"])
    longest = compute_longest_streak(habit["completions"])
    total = len(habit["completions"])

    print(f"Stats for [{habit['id']}] {habit['name']}:")
    print(f"  Current streak: {current} day{'s' if current != 1 else ''}")
    print(f"  Longest streak: {longest} day{'s' if longest != 1 else ''}")
    print(f"  Total completions: {total}")


def main():
    parser = argparse.ArgumentParser(
        description="A CLI habit tracker with streaks. Data stored in ~/.habit_tracker.json."
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")
    subparsers.required = True

    # add
    p_add = subparsers.add_parser("add", help="Add a new habit")
    p_add.add_argument("name", help="The habit name")
    p_add.set_defaults(func=cmd_add)

    # log
    p_log = subparsers.add_parser("log", help="Log a habit as done for today")
    p_log.add_argument("id", type=int, help="The habit ID to log")
    p_log.set_defaults(func=cmd_log)

    # list
    p_list = subparsers.add_parser("list", help="List all habits with streaks")
    p_list.set_defaults(func=cmd_list)

    # delete
    p_delete = subparsers.add_parser("delete", help="Delete a habit")
    p_delete.add_argument("id", type=int, help="The habit ID to delete")
    p_delete.set_defaults(func=cmd_delete)

    # stats
    p_stats = subparsers.add_parser("stats", help="Show detailed stats for a habit")
    p_stats.add_argument("id", type=int, help="The habit ID to show stats for")
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
