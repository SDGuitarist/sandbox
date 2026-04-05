#!/usr/bin/env python3
"""
todo.py — A simple CLI todo app. Stores todos in ~/.todos.json.

Usage:
  python todo.py add "Buy milk"
  python todo.py list [--pending-only]
  python todo.py complete <id>
  python todo.py delete <id>
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

TODOS_FILE = Path.home() / ".todos.json"


def load_todos():
    if not TODOS_FILE.exists():
        return {"todos": []}
    try:
        with open(TODOS_FILE, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        print(f"Error: todos file is corrupted. Delete {TODOS_FILE} to reset.")
        sys.exit(1)


def save_todos(data):
    with open(TODOS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_next_id(todos):
    if not todos:
        return 1
    return max(t["id"] for t in todos) + 1


def find_todo(todos, todo_id):
    for t in todos:
        if t["id"] == todo_id:
            return t
    return None


def cmd_add(args):
    title = args.title.strip()
    if not title:
        print("Error: title cannot be empty.")
        sys.exit(1)

    data = load_todos()
    todos = data["todos"]
    new_todo = {
        "id": get_next_id(todos),
        "title": title,
        "done": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    todos.append(new_todo)
    save_todos(data)
    print(f"Added: [{new_todo['id']}] {new_todo['title']}")


def cmd_list(args):
    data = load_todos()
    todos = data["todos"]

    if args.pending_only:
        todos = [t for t in todos if not t["done"]]

    if not todos:
        print("No todos yet.")
        return

    for t in todos:
        marker = "\u2713" if t["done"] else "\u25cb"
        date = t["created_at"][:10]
        print(f"{marker} [{t['id']}] {t['title']}  ({date})")


def cmd_complete(args):
    data = load_todos()
    todo = find_todo(data["todos"], args.id)

    if todo is None:
        print(f"Error: todo #{args.id} not found.")
        sys.exit(1)

    todo["done"] = True
    save_todos(data)
    print(f"Completed: [{todo['id']}] {todo['title']}")


def cmd_delete(args):
    data = load_todos()
    todo = find_todo(data["todos"], args.id)

    if todo is None:
        print(f"Error: todo #{args.id} not found.")
        sys.exit(1)

    data["todos"] = [t for t in data["todos"] if t["id"] != args.id]
    save_todos(data)
    print(f"Deleted: [{todo['id']}] {todo['title']}")


def main():
    parser = argparse.ArgumentParser(
        description="A simple CLI todo app. Todos are stored in ~/.todos.json."
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")
    subparsers.required = True

    # add
    p_add = subparsers.add_parser("add", help="Add a new todo")
    p_add.add_argument("title", help="The todo title")
    p_add.set_defaults(func=cmd_add)

    # list
    p_list = subparsers.add_parser("list", help="List todos")
    p_list.add_argument(
        "--pending-only", action="store_true", help="Show only incomplete todos"
    )
    p_list.set_defaults(func=cmd_list)

    # complete
    p_complete = subparsers.add_parser("complete", help="Mark a todo as complete")
    p_complete.add_argument("id", type=int, help="The todo ID to complete")
    p_complete.set_defaults(func=cmd_complete)

    # delete
    p_delete = subparsers.add_parser("delete", help="Delete a todo")
    p_delete.add_argument("id", type=int, help="The todo ID to delete")
    p_delete.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
