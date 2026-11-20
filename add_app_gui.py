#!/usr/bin/env python3
"""A simple window for adding an app to the MRC BSU app index.

For anyone who'd rather not use the command line. It does the same checks
as add_app.py, and can then send the change to GitHub for review: it makes
a branch, commits, pushes, and opens the pull request page in your browser.

Run it by double-clicking (if Python is set up to open .py files) or with:
    python add_app_gui.py

It must sit in the root of your copy of the repository, next to add_app.py.
"""

import queue
import re
import subprocess
import threading
import tkinter as tk
import webbrowser
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from add_app import PANELS, check_url, find_duplicate, load_index, save_index

PANEL_LABELS = {"panel1": "MRC BSU Applications", "panel2": "Covid-19 Support"}
DATA_REL = Path("index-app") / "apps.json"
MAIN_BRANCH = "main"


# --------------------------------------------------------------------------
# The work (no window code here, so it can be tested on its own)
# --------------------------------------------------------------------------

class StepError(Exception):
    """A problem to show the user in plain language."""


def run_git(repo, *args):
    try:
        result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    except FileNotFoundError:
        raise StepError("Git isn't installed on this computer. Untick 'Send to GitHub "
                        "for review' to just add the app to the list, or ask the admin team for help.")
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise StepError(f"A git step failed (git {' '.join(args)}):\n\n{detail}")
    return result.stdout.strip()


def slugify(name):
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:40].strip("-") or "app"


def github_compare_url(remote, branch):
    """Turn the repo's remote address into the 'open a pull request' page for a branch."""
    match = re.match(r"^(?:https://github\.com/|git@github\.com:)([^/]+)/(.+?)(?:\.git)?/?$", remote)
    if not match:
        return None
    owner, repo = match.groups()
    return f"https://github.com/{owner}/{repo}/compare/{MAIN_BRANCH}...{branch}?expand=1"


def add_and_submit(repo, entry, panel, submit, say=print):
    """Check and add one app. Returns (message, pull_request_url or None).

    Nothing is changed until every check has passed.
    """
    data_path = repo / DATA_REL

    if submit:
        say("Checking your copy of the repository...")
        run_git(repo, "rev-parse", "--is-inside-work-tree")
        if run_git(repo, "status", "--porcelain"):
            raise StepError("The repository folder has changes that haven't been saved to git yet, "
                            "so it's not safe to continue. Ask the admin team for help.")
        run_git(repo, "checkout", MAIN_BRANCH)
        say("Getting the latest app list from GitHub...")
        run_git(repo, "pull", "--ff-only", "origin", MAIN_BRANCH)

    data = load_index(data_path)
    problem = find_duplicate(data, entry["name"], entry["url"], panel)
    if problem:
        for panel_id, label in PANEL_LABELS.items():
            problem = problem.replace(panel_id, f"'{label}'")
        raise StepError(f"This app can't be added: {problem}.")

    say(f"Checking that {entry['url']} works...")
    ok, message = check_url(entry["url"], timeout=30)
    if not ok:
        raise StepError(f"The URL didn't work ({message}).\n\n"
                        "Check that it opens in your browser and try again.")

    data[panel].append(entry)
    save_index(data_path, data)

    if not submit:
        return (f"'{entry['name']}' was added to the list on this computer.\n\n"
                "It won't appear on the website until the change is sent to GitHub "
                "and approved."), None

    branch = f"add-app/{slugify(entry['name'])}-{datetime.now():%Y%m%d-%H%M%S}"
    say("Sending your change to GitHub...")
    try:
        run_git(repo, "checkout", "-b", branch)
        run_git(repo, "add", str(DATA_REL))
        run_git(repo, "commit", "-m", f"Add app: {entry['name']}")
        run_git(repo, "push", "-u", "origin", branch)
    except StepError:
        # Put things back so the next attempt starts clean.
        subprocess.run(["git", "checkout", "--", str(DATA_REL)], cwd=repo, capture_output=True)
        subprocess.run(["git", "checkout", MAIN_BRANCH], cwd=repo, capture_output=True)
        raise
    run_git(repo, "checkout", MAIN_BRANCH)

    url = github_compare_url(run_git(repo, "remote", "get-url", "origin"), branch)
    if url is None:
        return (f"'{entry['name']}' was sent to GitHub on the branch '{branch}'.\n\n"
                "Open the repository on GitHub and create a pull request from that "
                "branch, and the admin team will review it."), None
    return (f"'{entry['name']}' was sent to GitHub.\n\n"
            "Your browser will now open the pull request page. Click "
            "'Create pull request', and the admin team will review it."), url


# --------------------------------------------------------------------------
# The window
# --------------------------------------------------------------------------

class AddAppWindow:
    def __init__(self, root, repo):
        self.root = root
        self.repo = repo
        self.events = queue.Queue()
        root.title("Add an app to the MRC BSU index")
        root.resizable(True, False)

        frame = ttk.Frame(root, padding=16)
        frame.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="App name").grid(row=0, column=0, sticky="w", pady=4, padx=(0, 12))
        self.name = ttk.Entry(frame, width=60)
        self.name.grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="Web address").grid(row=1, column=0, sticky="w", pady=4, padx=(0, 12))
        self.url = ttk.Entry(frame, width=60)
        self.url.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="Description").grid(row=2, column=0, sticky="nw", pady=4, padx=(0, 12))
        self.description = tk.Text(frame, height=3, width=60, wrap="word")
        self.description.grid(row=2, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="Section").grid(row=3, column=0, sticky="w", pady=4, padx=(0, 12))
        self.panel = tk.StringVar(value=PANELS[0])
        choices = ttk.Frame(frame)
        choices.grid(row=3, column=1, sticky="w", pady=4)
        for panel in PANELS:
            ttk.Radiobutton(choices, text=PANEL_LABELS[panel], value=panel,
                            variable=self.panel).pack(side="left", padx=(0, 16))

        self.submit = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Send to GitHub for review (recommended)",
                        variable=self.submit).grid(row=4, column=1, sticky="w", pady=(8, 4))

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(12, 4))

        self.status = ttk.Label(frame, text="Fill in the details, then click Add app.",
                                wraplength=520, foreground="gray")
        self.status.grid(row=6, column=0, columnspan=2, sticky="w")

        self.button = ttk.Button(frame, text="Add app", command=self.start)
        self.button.grid(row=7, column=1, sticky="e", pady=(12, 0))

        self.name.focus_set()
        root.after(100, self.poll)

    def start(self):
        name = self.name.get().strip()
        url = self.url.get().strip()
        description = " ".join(self.description.get("1.0", "end").split())

        missing = [label for label, value in
                   (("app name", name), ("web address", url), ("description", description)) if not value]
        if missing:
            messagebox.showwarning("Missing details", f"Please fill in the {', '.join(missing)}.")
            return
        if not url.startswith(("http://", "https://")):
            messagebox.showwarning("Check the web address",
                                   "The web address should start with https:// "
                                   "(copy it from your browser's address bar).")
            return

        entry = {"name": name, "url": url, "description": description,
                 "added": date.today().isoformat()}
        self.button.state(["disabled"])
        self.progress.start(12)
        threading.Thread(target=self.work, args=(entry, self.panel.get(), self.submit.get()),
                         daemon=True).start()

    def work(self, entry, panel, submit):
        # Runs in the background so the window doesn't freeze.
        say = lambda message: self.events.put(("status", message))
        try:
            self.events.put(("done", add_and_submit(self.repo, entry, panel, submit, say)))
        except StepError as e:
            self.events.put(("error", str(e)))
        except Exception as e:  # anything unexpected
            self.events.put(("error", f"Something unexpected went wrong:\n\n{e}"))

    def poll(self):
        while not self.events.empty():
            kind, payload = self.events.get()
            if kind == "status":
                self.status.config(text=payload)
            else:
                self.progress.stop()
                self.button.state(["!disabled"])
                if kind == "error":
                    self.status.config(text="Nothing was changed. Fix the problem and try again.")
                    messagebox.showerror("Couldn't add the app", payload)
                else:
                    message, pr_url = payload
                    self.status.config(text="Done.")
                    messagebox.showinfo("App added", message)
                    if pr_url:
                        webbrowser.open(pr_url)
                    for field in (self.name, self.url):
                        field.delete(0, "end")
                    self.description.delete("1.0", "end")
        self.root.after(100, self.poll)


def find_repo(root):
    repo = Path(__file__).resolve().parent
    while not (repo / DATA_REL).exists():
        messagebox.showinfo("Find the app index",
                            "Please choose your copy of the mrc-bsu-apps folder "
                            "(the one containing the index-app folder).")
        chosen = filedialog.askdirectory(title="Choose the mrc-bsu-apps folder")
        if not chosen:
            return None
        repo = Path(chosen)
    return repo


def main():
    root = tk.Tk()
    root.withdraw()
    repo = find_repo(root)
    if repo is None:
        root.destroy()
        return
    AddAppWindow(root, repo)
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()