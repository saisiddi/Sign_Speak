"""
SignSpeak - Snippets Manager
Stores gesture -> phrase assignments in a JSON file.
Provides get/set API used by main.py endpoints.
"""

import json
import os

SNIPPETS_FILE = os.path.join(os.path.dirname(__file__), "snippets.json")

# Default gesture -> phrase mapping
DEFAULT_SNIPPETS = {
    "Open_Palm":   "Hello",
    "Thumb_Up":    "Yes",
    "Thumb_Down":  "No",
    "Victory":     "Thank you",
    "Pointing_Up": "I need help",
    "Closed_Fist": "Please stop",
    "ILoveYou":    "I love you",
}


def load_snippets() -> dict:
    """Load snippets from file, fall back to defaults if missing."""
    if os.path.exists(SNIPPETS_FILE):
        try:
            with open(SNIPPETS_FILE, "r") as f:
                data = json.load(f)
                # Merge with defaults so new gestures always have a phrase
                merged = DEFAULT_SNIPPETS.copy()
                merged.update(data)
                return merged
        except Exception as e:
            print(f"[Snippets] Error loading: {e}")
    return DEFAULT_SNIPPETS.copy()


def save_snippets(snippets: dict) -> bool:
    """Save snippets to file."""
    try:
        with open(SNIPPETS_FILE, "w") as f:
            json.dump(snippets, f, indent=2)
        return True
    except Exception as e:
        print(f"[Snippets] Error saving: {e}")
        return False


def get_phrase(gesture: str) -> str:
    """Get the phrase for a gesture. Returns default if no custom assigned."""
    snippets = load_snippets()
    return snippets.get(gesture, gesture)


def reset_to_defaults() -> bool:
    """Reset all snippets to defaults."""
    return save_snippets(DEFAULT_SNIPPETS.copy())
