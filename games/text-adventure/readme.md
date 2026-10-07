# The Last Light — a text adventure inside a font

An original escape-room adventure with **eight rooms, four items and three
puzzles**. OpenType substitutions perform command parsing, navigation,
inventory changes, locked-door checks, lighting, generator repair, and escape.
The font draws the room description, exits, carried items and latest reply.
There is no game interpreter in the browser.

## Play

From the repository root:

```bash
python3 -m http.server 8000
```

Open <http://localhost:8000/games/text-adventure/playground.html>.
Enter a command and press Enter, or use the common-command buttons. Type
`help` to see the commands. Unknown commands produce a reply and leave the
world unchanged. New game starts over; Undo removes the last command.

You can also open [text-adventure.odt](text-adventure.odt) in **LibreOffice
Writer**. It embeds the adventure font and Roboto, so no font installation or
web server is needed. Place the caret at the end of the blue scene and append
commands such as `east;take key;`. Keep the whole history in that paragraph;
do not press Enter inside it. Delete a complete command to undo. The plain-text
copy above the scene is independent and does not update when you play.

The house has an atrium, gallery, study, workshop, greenhouse, archive,
cellar and courtyard. Find the key, lamp, fuse and crystal. Restore the
house's power and open the south gate to escape.

| Command | Action |
| --- | --- |
| `north`, `south`, `east`, `west` | Move through an exit |
| `look` | Describe the current room |
| `inventory` | Show carried items |
| `take key`, `take lamp`, `take fuse`, `take crystal` | Collect an item in the room |
| `unlock door` | Use the key at the gallery's brass door |
| `light lamp` | Light the collected lamp |
| `use fuse` | Repair the cellar generator |
| `use crystal` | Install the crystal in the atrium's gate socket |
| `help` | Show the command list |

Aliases: `n`, `s`, `e`, `w`, `l`, `i`, `repair generator`, `install crystal`.
Commands are case insensitive. Collected items cannot be collected twice.
The fuse and crystal leave the carried inventory when installed. The lamp
stays lit, and unlocked/repaired objects retain their state. The courtyard
ends the game; further commands keep displaying the successful escape.

## Use the font directly

Install `text-adventure-font.ttf`, select **The Last Light Adventure** in a
text editor with standard ligatures enabled, and type a single uninterrupted
text run:

```text
start;
start;east;
start;east;take key;west;north;unlock door;
```

Begin with `start;`. Append each command followed by `;`. Deleting the last
command restores the previous world because shaping replays the history.
The font recognizes complete commands, so `northeast;` and `take key please;`
cannot accidentally move north or collect a key. An unfinished command
does not change the last completed scene.

The playground's **Save or restore your journey** section lets you copy the
input text to save and paste it back to restore. There is no separate save
file or hidden state. Its controller only validates the input format, edits
the history, loads the font, and sizes the display; it contains no map,
inventory model, puzzle rules or story text.

## Build and check

Requires Python 3.10+ and FontTools. HarfBuzz's `hb-shape` is needed for the
game checks; Node.js checks the browser controller.

```bash
python3 -m pip install fonttools
python3 games/text-adventure/build.py
python3 specimens/build.py --project games/text-adventure
python3 -m unittest discover -s games/text-adventure -p 'test_*.py' -v
node games/text-adventure/test_controls.cjs
```

`build.py` writes the bundled font beside itself by default. Use
`--output /path/to/custom.ttf` to write elsewhere. Importing the builder
does not generate files. Edit `story.py` to change the world and rebuild.
It is a build-time specification, never loaded by the playground.
Rebuild the ODT after rebuilding the font so its embedded copy stays current.

Tests shape both the bundled font and a fresh build. They check all **156
reachable worlds × 16 commands**, independent puzzle/escape scenarios,
whole-command boundaries, unknown-command recovery, aliases, uppercase
input, incomplete commands, the 128-command limit, outline bounds, ASCII
coverage and license metadata. Controller checks cover format validation,
undo, reset, copyable history, restore and the command limit.

## Implementation and limits

- The world is a finite state machine compiled into GSUB ligatures. Only
  reachable combinations of room, collected items and puzzle flags are built.
- A command trie consumes characters after a delimiter. A token is completed
  only at the next delimiter; unknown words produce an unknown-command token.
  Delimiters are removed before evaluating the command sequence.
- Repeated compact contextual lookups invoke shared transition/feedback tables.
  Distinct lookup indices provide clock passes without copying the large
  rule tables. Previous feedback is hidden when a new command is applied.
- World and feedback glyphs draw the latest scene. Room panels, inventory
  panels, lines and original 5×7 letter outlines are shared as TrueType
  components. Input letters and obsolete replies are invisible.
- Up to **128 commands**, each at most **24 printable ASCII characters**,
  in one uninterrupted shaping run. The playground enforces these limits.
  Further commands in raw font input remain unevaluated. Overlong/malformed
  raw commands are outside the supported format and may stop evaluation.
- Raw font input requires exact spelling and one space in multiword commands;
  the playground trims input and collapses repeated spaces. Newlines, tabs,
  non-ASCII input, mixed styles, wrapping or font fallback can split the run.
- There is no general natural-language parser, randomness or editable runtime
  world. Font size and shaping support vary between text editors.
- Scene text is drawn as outlines. Copying/searching/accessibility APIs expose
  the underlying command history, not the displayed room description. The
  playground labels the scene and exposes history and controls, but does not
  supply a screen-reader transcript of the story.

<details>
<summary>Solution — spoilers</summary>

```text
start;east;take key;west;north;unlock door;east;take crystal;west;north;take lamp;light lamp;south;south;west;north;take fuse;use fuse;south;east;use crystal;south;
```

</details>

## License

Apache License 2.0; see the root [LICENSE](../../LICENSE).
The story, game rules, lettering and font are original work. No existing
game, game engine or external font outlines are incorporated.
