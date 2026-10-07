# Copyright 2026 Michael Brackx
# SPDX-License-Identifier: Apache-2.0
"""Original escape-room story, compiled into the adventure font at build time.

There is no Python or JavaScript story interpreter at play time.
"""

from collections import deque

TITLE = "THE LAST LIGHT"
MAX_COMMANDS = 128
MAX_COMMAND_LENGTH = 24
KEY, LAMP, FUSE, CRYSTAL = 1, 2, 4, 8
# room, collected items, door unlocked, lamp lit, generator repaired, crystal installed
INITIAL = (0, 0, False, False, False, False)
ROOMS = (
    ("ATRIUM", "Rain taps the glass roof. A south gate needs power and a crystal. The house has locked you in.",
     "NORTH / EAST / WEST / SOUTH (GATE)"),
    ("GALLERY", "Portraits watch the corridor. A locked brass door leads east to the archive.",
     "SOUTH / NORTH / EAST (BRASS DOOR)"),
    ("STUDY", "An unfinished letter lies on a desk. A small brass key rests beside it.", "WEST"),
    ("WORKSHOP", "Tools hang above an empty workbench. Steps descend north into a pitch-black cellar.", "EAST / NORTH (DARK STEPS)"),
    ("GREENHOUSE", "Moonlight falls on tangled vines. An oil lamp waits on a stone bench.", "SOUTH"),
    ("ARCHIVE", "Dust covers the shelves. A clear crystal sits in a padded box, glowing faintly.", "WEST"),
    ("CELLAR", "Your lamp reveals a silent generator. A spare fuse lies on a shelf beside it.", "SOUTH"),
    ("COURTYARD - YOU ESCAPED!", "The gate swings open. You step into the rain as the house lights up behind you. Dawn is close.", "YOUR JOURNEY IS COMPLETE"),
)
EXITS = {0: {"north": 1, "east": 2, "west": 3, "south": 7},
         1: {"south": 0, "north": 4, "east": 5}, 2: {"west": 0},
         3: {"east": 0, "north": 6}, 4: {"south": 1},
         5: {"west": 1}, 6: {"south": 3}, 7: {}}
ITEMS = {"key": (KEY, 2), "lamp": (LAMP, 4), "fuse": (FUSE, 6), "crystal": (CRYSTAL, 5)}
COMMANDS = ("north", "south", "east", "west", "look", "inventory", "help",
            "take key", "take lamp", "take fuse", "take crystal", "unlock door",
            "light lamp", "use fuse", "use crystal", "unknown")
ALIASES = {"n": "north", "s": "south", "e": "east", "w": "west",
           "l": "look", "i": "inventory", "repair generator": "use fuse",
           "install crystal": "use crystal"}
MESSAGES = {
    "ready": "Find a way out. Type HELP for commands.",
    "moved": "You enter the next room.",
    "look": "You take another look around.",
    "inventory": "Your carried items are listed above.",
    "help": "NORTH / SOUTH / EAST / WEST / LOOK\nTAKE KEY / LAMP / FUSE / CRYSTAL\nUNLOCK DOOR / LIGHT LAMP\nUSE FUSE / USE CRYSTAL / INVENTORY",
    "no_exit": "There is no passage in that direction.",
    "locked": "The brass door is locked. Find its key.",
    "dark": "The cellar is too dark. Light a lamp first.",
    "gate": "The gate needs generator power and a crystal in its socket.",
    "absent": "That item is not in this room.",
    "already": "You have already collected that item.",
    "key": "You pick up the brass key.",
    "lamp": "You pick up the oil lamp.",
    "fuse": "You pick up the spare fuse.",
    "crystal": "You pick up the glowing crystal.",
    "wrong_door": "The brass door is in the gallery.",
    "need_key": "You need the brass key to unlock the door.",
    "door_open": "The brass door is already unlocked.",
    "unlocked": "The key turns. The archive door opens.",
    "need_lamp": "You need to collect the oil lamp first.",
    "lit": "A warm flame lights the oil lamp.",
    "already_lit": "The lamp is already burning.",
    "wrong_fuse": "The generator is in the cellar.",
    "need_fuse": "You need the spare fuse to repair it.",
    "powered": "The fuse clicks into place. The generator hums. The house has power.",
    "already_powered": "The generator is already running.",
    "wrong_crystal": "The crystal socket is in the atrium.",
    "need_crystal": "You need the crystal from the archive.",
    "installed": "The crystal fits the gate socket. Its edges shine with a pale light.",
    "already_installed": "The crystal is already in the socket.",
    "unknown": "Unknown command. Type HELP to see the commands you can use.",
    "won": "You escaped! Undo to revisit the house, or start a new game.",
}


def transition(state, command):
    """Build-time rules: return the next world state and a feedback identifier."""
    room, items, door, lit, power, crystal = state
    command = ALIASES.get(command, command)
    if room == 7:
        return state, "won"
    if command in ("look", "inventory", "help"):
        return state, command
    if command in ("north", "south", "east", "west"):
        destination = EXITS[room].get(command)
        if destination is None:
            return state, "no_exit"
        if destination == 5 and not door:
            return state, "locked"
        if destination == 6 and not lit:
            return state, "dark"
        if destination == 7 and not (power and crystal):
            return state, "gate"
        return (destination, *state[1:]), "won" if destination == 7 else "moved"
    if command.startswith("take ") and command[5:] in ITEMS:
        item = command[5:]
        flag, location = ITEMS[item]
        if items & flag:
            return state, "already"
        if room != location:
            return state, "absent"
        return (room, items | flag, door, lit, power, crystal), item
    if command == "unlock door":
        if room != 1:
            return state, "wrong_door"
        if door:
            return state, "door_open"
        if not items & KEY:
            return state, "need_key"
        return (room, items, True, lit, power, crystal), "unlocked"
    if command == "light lamp":
        if lit:
            return state, "already_lit"
        if not items & LAMP:
            return state, "need_lamp"
        return (room, items, door, True, power, crystal), "lit"
    if command == "use fuse":
        if room != 6:
            return state, "wrong_fuse"
        if power:
            return state, "already_powered"
        if not items & FUSE:
            return state, "need_fuse"
        return (room, items, door, lit, True, crystal), "powered"
    if command == "use crystal":
        if room != 0:
            return state, "wrong_crystal"
        if crystal:
            return state, "already_installed"
        if not items & CRYSTAL:
            return state, "need_crystal"
        return (room, items, door, lit, power, True), "installed"
    return state, "unknown"


def reachable_states():
    """Only compile reachable worlds, sharing their scenes and text outlines."""
    seen, queue = {INITIAL}, deque([INITIAL])
    while queue:
        state = queue.popleft()
        for command in COMMANDS:
            target, _ = transition(state, command)
            if target not in seen:
                seen.add(target)
                queue.append(target)
    return sorted(seen)


def state_name(state):
    return "world_" + "_".join(str(int(value)) for value in state)


def inventory(state):
    items, power, crystal = state[1], state[4], state[5]
    return [name.upper() for name, (flag, _) in ITEMS.items()
            if items & flag and not (name == "fuse" and power)
            and not (name == "crystal" and crystal)]


def room_view(state):
    """Build-time scene variants reflect collected items and solved puzzles."""
    room, items, door, lit, power, crystal = state
    title, description, exits = ROOMS[room]
    if room == 0:
        if power and crystal:
            description = "The south gate stands open. Beyond it, you hear rain on the courtyard stones."
        elif crystal:
            description = "The crystal is seated in the gate socket, but the house still needs power."
        elif power:
            description = "The house lights are on. The south gate still needs a crystal in its socket."
    elif room == 1 and door:
        description = "Portraits watch the corridor. The unlocked brass door leads east to the archive."
        exits = "SOUTH / NORTH / EAST"
    elif room == 2 and items & KEY:
        description = "An unfinished letter lies on a desk. The space beside it is empty."
    elif room == 3 and lit:
        description = "Tools hang above an empty workbench. With your lamp, you can descend north into the cellar."
        exits = "EAST / NORTH"
    elif room == 4 and items & LAMP:
        description = "Moonlight falls on tangled vines. The stone bench is empty."
    elif room == 5 and items & CRYSTAL:
        description = "Dust covers the shelves. The padded crystal box is empty."
    elif room == 6:
        description = ("The generator hums steadily." if power else "Your lamp reveals a silent generator.")
        description += " The shelf beside it is empty." if items & FUSE else " A spare fuse lies on a shelf beside it."
    return title, description, exits


WINNING_COMMANDS = ("east", "take key", "west", "north", "unlock door", "east",
                    "take crystal", "west", "north", "take lamp", "light lamp",
                    "south", "south", "west", "north", "take fuse", "use fuse",
                    "south", "east", "use crystal", "south")
