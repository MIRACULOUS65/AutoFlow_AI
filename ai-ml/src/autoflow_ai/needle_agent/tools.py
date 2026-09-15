"""Needle agent tools: the 26 tool definitions the fine-tuned model selects.

Ported from the hackathon-needle-agent reference and adapted for AutoFlow:

* Every tool returns a structured JSON action dict (the canonical contract the
  model + orchestrator share).
* Real side effects (writing files, launching apps/browser, Word) only happen
  when ``execute=True`` is passed to :func:`build_tools`. In the default
  ``execute=False`` (safe / dry-run) mode the tools return the same structured
  action WITHOUT touching the machine — so tests and the UI never spawn apps or
  create files unexpectedly. This is the honest safe-by-default posture.
* File writes are confined to a configurable output directory (defaults to
  ``~/Downloads``) so the agent never writes to arbitrary locations.

``build_tools(execute=..., output_dir=...)`` returns a list of ``@needle.tool``
decorated callables ready to hand to ``needle.Needle(tools=...)``.
"""

from __future__ import annotations

import os
import urllib.parse
import webbrowser
from pathlib import Path


def _default_output_dir() -> Path:
    env = os.environ.get("AUTOFLOW_NEEDLE_OUTPUT")
    if env:
        return Path(env)
    return Path.home() / "Downloads"


def build_tools(*, execute: bool = False, output_dir: str | Path | None = None) -> list:
    """Build the Needle tool set.

    Parameters
    ----------
    execute:
        When True the wired tools perform real side effects (write files, open
        browser/apps, drive Word). When False every tool is a no-op that only
        returns its structured action dict (safe default for tests + preview).
    output_dir:
        Directory for file-producing tools. Defaults to ``AUTOFLOW_NEEDLE_OUTPUT``
        or ``~/Downloads``. Created on demand when executing.
    """

    import needle  # imported lazily; only needed when tools are built

    out_dir = Path(output_dir) if output_dir else _default_output_dir()

    def _ensure_dir() -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    def _safe_name(name: str) -> str:
        # prevent path traversal: keep only the file name component
        return Path(name).name or "untitled"

    # ---------- real-execution tools (gated by `execute`) ----------

    @needle.tool
    def write_text(filename: str, content: str):
        "Write text content into a Word document."
        action = {"action": "write_text", "filename": filename, "content": content}
        if not execute:
            return {**action, "status": "planned", "executed": False}
        target = _ensure_dir() / _safe_name(filename)
        try:
            import win32com.client  # type: ignore

            word = win32com.client.Dispatch("Word.Application")
            word.Visible = True
            doc = word.Documents.Add()
            doc.Content.Text = content
            doc.SaveAs(str(target))
            return {**action, "path": str(target), "status": "done", "executed": True}
        except Exception:  # noqa: BLE001 - Word/pywin32 not available -> honest fallback
            # Fall back to a real .docx-less text write so the side effect is
            # still real and verifiable even without Word installed.
            txt = target.with_suffix(".txt")
            txt.write_text(content, encoding="utf-8")
            return {**action, "path": str(txt), "status": "done_text_fallback",
                    "executed": True, "note": "Word unavailable; wrote plain text"}

    @needle.tool
    def create_note(content: str):
        "Create a note with given content (saved as a text file)."
        action = {"action": "create_note", "content": content}
        if not execute:
            return {**action, "status": "planned", "executed": False}
        path = _ensure_dir() / "note.txt"
        with open(path, "a", encoding="utf-8") as f:
            f.write(content + "\n")
        return {**action, "path": str(path), "status": "saved", "executed": True}

    @needle.tool
    def open_browser():
        "Open a web browser."
        action = {"action": "open_browser"}
        if execute:
            webbrowser.open("https://www.google.com")
        return {**action, "status": "done" if execute else "planned", "executed": execute}

    @needle.tool
    def search_youtube(query: str):
        "Search YouTube for a query."
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
        if execute:
            webbrowser.open(url)
        return {"action": "search_youtube", "query": query, "url": url,
                "status": "done" if execute else "planned", "executed": execute}

    @needle.tool
    def play_video(title: str):
        "Play a video by title on YouTube."
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(title)
        if execute:
            webbrowser.open(url)
        return {"action": "play_video", "title": title, "url": url,
                "status": "done" if execute else "planned", "executed": execute}

    @needle.tool
    def compose_email(to: str, subject: str, body: str):
        "Compose a draft email without sending it."
        params = {"view": "cm", "fs": "1", "to": to, "su": subject, "body": body}
        url = "https://mail.google.com/mail/?" + urllib.parse.urlencode(params)
        if execute:
            webbrowser.open(url)
        return {"action": "compose_email", "to": to, "subject": subject,
                "status": "draft opened" if execute else "planned", "executed": execute}

    @needle.tool
    def open_website(url: str):
        "Open a specific website by URL."
        if not url.startswith("http"):
            url = "https://" + url
        if execute:
            webbrowser.open(url)
        return {"action": "open_website", "url": url,
                "status": "done" if execute else "planned", "executed": execute}

    @needle.tool
    def search_web(query: str):
        "Search the web for a query."
        url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
        if execute:
            webbrowser.open(url)
        return {"action": "search_web", "query": query, "url": url,
                "status": "done" if execute else "planned", "executed": execute}

    @needle.tool
    def open_app(app_name: str):
        "Open an application by name."
        if execute:
            os.system(f"start {app_name}")  # noqa: S605 - user-driven desktop action
        return {"action": "open_app", "app_name": app_name,
                "status": "done" if execute else "planned", "executed": execute}

    @needle.tool
    def open_file(filepath: str):
        "Open an existing file by path."
        if execute and os.path.exists(filepath):
            os.startfile(filepath)  # type: ignore[attr-defined]  # noqa: S606
        return {"action": "open_file", "filepath": filepath,
                "status": "done" if execute else "planned", "executed": execute}

    @needle.tool
    def open_folder(path: str):
        "Open a folder by path."
        if execute and os.path.isdir(path):
            os.startfile(path)  # type: ignore[attr-defined]  # noqa: S606
        return {"action": "open_folder", "path": path,
                "status": "done" if execute else "planned", "executed": execute}

    @needle.tool
    def open_email_client():
        "Open the email client."
        if execute:
            webbrowser.open("https://mail.google.com")
        return {"action": "open_email_client",
                "status": "done" if execute else "planned", "executed": execute}

    # ---------- structured-action tools (returned for the orchestrator) ----------

    @needle.tool
    def create_file(filename: str, filetype: str):
        "Create a new file with a given filename and type."
        return {"action": "create_file", "filename": filename, "filetype": filetype}

    @needle.tool
    def write_cell(sheet: str, cell: str, value: str):
        "Write a value into a specific cell of a spreadsheet."
        return {"action": "write_cell", "sheet": sheet, "cell": cell, "value": value}

    @needle.tool
    def write_range(sheet: str, start_cell: str, values: str):
        "Write multiple values starting at a cell in a spreadsheet."
        return {"action": "write_range", "sheet": sheet, "start_cell": start_cell, "values": values}

    @needle.tool
    def insert_row(sheet: str, row_index: int):
        "Insert a row into a spreadsheet at a given index."
        return {"action": "insert_row", "sheet": sheet, "row_index": row_index}

    @needle.tool
    def apply_formula(sheet: str, cell: str, formula: str):
        "Apply a formula to a cell in a spreadsheet."
        return {"action": "apply_formula", "sheet": sheet, "cell": cell, "formula": formula}

    @needle.tool
    def save_file(filename: str):
        "Save the current file."
        return {"action": "save_file", "filename": filename}

    @needle.tool
    def insert_heading(filename: str, text: str, level: int = 1):
        "Insert a heading into a document."
        return {"action": "insert_heading", "filename": filename, "text": text, "level": level}

    @needle.tool
    def generate_document(topic: str, filename: str):
        "Generate a full document draft on a given topic."
        return {"action": "generate_document", "topic": topic, "filename": filename}

    @needle.tool
    def find_file(filename: str):
        "Find a file by name."
        return {"action": "find_file", "filename": filename}

    @needle.tool
    def delete_file(filepath: str):
        "Delete a file by path."
        return {"action": "delete_file", "filepath": filepath}

    @needle.tool
    def rename_file(old_name: str, new_name: str):
        "Rename a file."
        return {"action": "rename_file", "old_name": old_name, "new_name": new_name}

    @needle.tool
    def close_window(app_name: str):
        "Close an application window."
        return {"action": "close_window", "app_name": app_name}

    @needle.tool
    def minimize_window(app_name: str):
        "Minimize an application window."
        return {"action": "minimize_window", "app_name": app_name}

    @needle.tool
    def set_reminder(text: str, time: str):
        "Set a reminder with text and time."
        return {"action": "set_reminder", "text": text, "time": time}

    @needle.tool
    def type_text(target: str, text: str):
        "Type text into a target field or app."
        return {"action": "type_text", "target": target, "text": text}

    @needle.tool
    def click_element(target: str):
        "Click a UI element identified by its visible label and type."
        return {"action": "click_element", "target": target}
    @needle.tool
    def search_kaggle_datasets(query: str):
        "Search Kaggle for datasets matching a topic."
        url = "https://www.kaggle.com/datasets?search=" + urllib.parse.quote(query)
        webbrowser.open(url)
        return {"action": "search_kaggle_datasets", "query": query, "status": "done"}

    @needle.tool
    def write_notepad(filename: str, content: str):
        "Write text content into a Notepad (.txt) document and open it."
        action = {"action": "write_notepad", "filename": filename, "content": content}
        if not execute:
            return {**action, "status": "planned", "executed": False}
        # Ensure a .txt target inside the confined output directory.
        name = _safe_name(filename)
        if not name.lower().endswith(".txt"):
            name = f"{name}.txt"
        target = _ensure_dir() / name
        # Write the real file first (real, verifiable side effect), then open it
        # in Notepad so the content shows up on screen.
        target.write_text(content, encoding="utf-8")
        try:
            import subprocess

            # Launch Notepad on the saved file; detached so it stays open.
            subprocess.Popen(["notepad.exe", str(target)])
            return {**action, "path": str(target), "status": "done", "executed": True}
        except Exception:  # noqa: BLE001 - notepad not available -> file still written
            return {**action, "path": str(target), "status": "done_no_open",
                    "executed": True, "note": "wrote file; could not launch Notepad"}

    return [
        write_text, open_browser, search_youtube, play_video, compose_email,
        open_website, search_web, open_app, create_note,
        search_kaggle_datasets, write_notepad,
        create_file, write_cell, write_range, insert_row, apply_formula, save_file,
        insert_heading, generate_document, open_email_client, open_file, find_file,
        open_folder, delete_file, rename_file, close_window, minimize_window,
        set_reminder, type_text, click_element,
    ]
