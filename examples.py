def example1():
    name = input("Enter your name: ")
    print(f"Hello, {name}!")

    number = int(input("Enter a number: "))
    print(f"The square of {number} is {number ** 2}.")

def example2():
    
    #this is a starter code 
    tasks = ["study", "clean room", "play guitar"]
    i = 1
    for task in tasks:
        print(f"Task {i}: {task}")
        i += 1
    
    #where as this is a more pythonic way to do the same thing
    tasks = ["study", "clean room", "play guitar"]
    for i, task in enumerate(tasks, start=1):
        print(f"Task {i}: {task}")

def example3():
    
    tasks = ["study", "clean room", "play guitar"]

    def show_tasks():
        for i, task in enumerate(tasks, start=1):
            print(f"{i}. {task}")

    def add_task():
        new_task = input("Enter a new task: ")
        tasks.append(new_task)
        print(f"Task '{new_task}' added.")

    def remove_task():
        remove_task = input("Enter the task to remove: ")
        if remove_task in tasks:
            tasks.remove(remove_task)
            print(f"Task '{remove_task}' removed.")
        else:
            print(f"Task '{remove_task}' not found.")
    #It is better to use functions to organize code into reusable blocks

    while True:
        show_tasks()
        choice = input("Type 'add', 'remove', or 'exit': ")

        if choice == "add":
            add_task()
        elif choice == "remove":
            remove_task()
        elif choice == "exit":
            print("Exiting...")
            break
        else:
            print("Invalid option.")

import os
import json

FILENAME = "tasks.json"

def example4():

    # --- Load tasks from file or start fresh ---
    if os.path.exists(FILENAME):
        with open(FILENAME, 'r') as file:
            tasks = json.load(file)
    else:
        tasks = []

    # --- Save tasks to file ---
    def save_tasks():
        with open(FILENAME, 'w') as file:
            json.dump(tasks, file, indent=4)
        print("Tasks saved.\n")

    # --- Show tasks with status ---
    def show_tasks():
        if not tasks:
            print("No tasks available.\n")
            return
        print("\nCurrent Tasks:")
        for i, task in enumerate(tasks, start=1):
            status = "✓" if task["finished"] else " "
            print(f"{i}. [{status}] {task['name']}")
        print("")  # extra newline for spacing

    # --- Add a new task ---
    def add_task():
        new_task = input("Enter a new task: ").strip()
        if new_task:  # ignore empty input
            tasks.append({"name": new_task, "finished": False})
            print(f"Task '{new_task}' added.\n")
            save_tasks()
        else:
            print("Task cannot be empty.\n")

    # --- Remove a task by name ---
    def remove_task():
        remove_task = input("Enter the task to remove: ").strip()
        for task in tasks:
            if task["name"].lower() == remove_task.lower():
                tasks.remove(task)
                print(f"Task '{remove_task}' removed.\n")
                save_tasks()
                return
        print(f"Task '{remove_task}' not found.\n")

    # --- Mark a task as finished ---
    def mark_finished():
        finish_task = input("Enter the task to mark as finished: ").strip()
        for task in tasks:
            if task["name"].lower() == finish_task.lower():
                if not task["finished"]:
                    task["finished"] = True
                    print(f"Task '{finish_task}' marked as finished.\n")
                    save_tasks()
                else:
                    print(f"Task '{finish_task}' is already finished.\n")
                return
        print(f"Task '{finish_task}' not found.\n")

    # --- Main loop ---
    while True:
        show_tasks()
        choice = input("Type 'add', 'remove', 'finish' or 'exit': ").strip().lower()

        if choice == "add":
            add_task()
        elif choice == "remove":
            remove_task()
        elif choice == "finish":
            mark_finished()
        elif choice == "exit":
            print("Exiting...")
            break
        else:
            print("Invalid option.\n")


    




#decomment the function calls below to run the examples

#example1() # This function prompts the user for their name and a number, then prints a greeting and the square of the number.
#example2() # This function demonstrates a more pythonic way to enumerate tasks in a list.
#example3() # This function organizes task management into reusable functions.
#example4() # This function adds persistent storage to the task manager using a JSON file.
