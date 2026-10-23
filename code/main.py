import sys
import time
import tkinter as tk
import serial
import serial.tools.list_ports

# ---------------- CONFIGURATION ---------------- #
BAUDRATE = 115200   # Must match the Arduino baud rate
RES_SIZE = 5        # Size of one drawing cell in pixels
CANVAS_SIZE = 800   # Drawing grid is CANVAS_SIZE x CANVAS_SIZE
DOCK_H = 100        # Height of the tool dock below the grid
TOTAL_H = CANVAS_SIZE + DOCK_H

# NOTE: the Arduino limits must match these:
#   X goes 0 .. CANVAS_SIZE - RES_SIZE          (795)
#   Y goes 0 .. CANVAS_SIZE + DOCK_H - RES_SIZE (895)

ERASER_COLOR = "#999999"
COLORS = ["black", "red", "green", "blue", "yellow"]

# Tools
PEN = "pen"
ERASER = "eraser"
# ------------------------------------------------ #


def choose_serial_port():
    """List every COM port and let the user type which one to use."""
    while True:
        ports = sorted((p.device for p in serial.tools.list_ports.comports()),
                       key=lambda name: (len(name), name))
        if not ports:
            input("No COM ports found. Plug in the Arduino, then press Enter to scan again...")
            continue

        choice = input(f"COM ports found: {', '.join(ports)}. "
                       f"Choose which port to connect to: ").strip().upper()
        match = next((p for p in ports if p.upper() == choice), None)
        if match is None:
            print(f"'{choice}' is not one of the ports found. Try again.\n")
            continue

        try:
            connection = serial.Serial(match, BAUDRATE, timeout=0.02)
        except serial.SerialException as exc:
            print(f"Could not open {match}: {exc}")
            print("Make sure the Arduino IDE Serial Monitor is closed!\n")
            continue

        time.sleep(2)  # opening the port resets a Nano; let it finish booting
        connection.reset_input_buffer()
        print(f"Connected to {match} at {BAUDRATE} baud.")
        return connection


ser = choose_serial_port()
serial_ok = True

root = tk.Tk()
root.title("Etch-A-Sketch")
try:
    root.state('zoomed')
except tk.TclError:
    pass

canvas = tk.Canvas(root, width=CANVAS_SIZE, height=TOTAL_H,
                   bg="white", highlightthickness=0)
canvas.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

# Position and button state from the Arduino
cursor_x = 400
cursor_y = 400
synced = False            # becomes True after the first packet
x_button_held = False
y_button_held = False

# Tool state
tool = PEN
pen_color = "black"
pen_down = False
# Each painted cell has one rectangle. Erasing deletes it, exposing the grid.
painted_cells = {}        # (grid_x, grid_y) -> rectangle id

rx_buffer = ""
cursor = None
last_dock_state = None

# Dock buttons: (kind, value, x0, y0, x1, y1, label)
BTN_Y0, BTN_Y1 = CANVAS_SIZE + 20, CANVAS_SIZE + 80
buttons = []
for i, c in enumerate(COLORS):
    bx = 230 + i * 70
    buttons.append(("color", c, bx, BTN_Y0, bx + 60, BTN_Y1, ""))
buttons.append(("eraser", None, 580, BTN_Y0, 650, BTN_Y1, "ERASER"))
buttons.append(("clear", None, 665, BTN_Y0, 785, BTN_Y1, "CLEAR"))


def draw_grid():
    for i in range(0, CANVAS_SIZE + 1, RES_SIZE):
        canvas.create_line(i, 0, i, CANVAS_SIZE, fill="#eeeeee", tags="grid")
        canvas.create_line(0, i, CANVAS_SIZE, i, fill="#eeeeee", tags="grid")


def draw_dock_background():
    canvas.create_rectangle(0, CANVAS_SIZE, CANVAS_SIZE, TOTAL_H,
                            fill="#f2f2f2", outline="", tags="dock_bg")
    canvas.create_line(0, CANVAS_SIZE, CANVAS_SIZE, CANVAS_SIZE,
                       fill="#555555", width=2, tags="dock_bg")


def clamp_cell(x, y):
    """Snap a position to the cell grid, anywhere in the grid + dock area."""
    gx = max(0, min(CANVAS_SIZE - RES_SIZE, (int(x) // RES_SIZE) * RES_SIZE))
    gy = max(0, min(TOTAL_H - RES_SIZE, (int(y) // RES_SIZE) * RES_SIZE))
    return gx, gy


def tool_color():
    return ERASER_COLOR if tool == ERASER else pen_color


def paint_cell(x, y):
    """Paint (or erase) one cell. Does nothing outside the drawing grid."""
    gx, gy = clamp_cell(x, y)
    if gy >= CANVAS_SIZE:
        return
    key = (gx, gy)

    if tool == ERASER:
        rect_id = painted_cells.pop(key, None)
        if rect_id is not None:
            canvas.delete(rect_id)
        return

    rect_id = painted_cells.get(key)
    if rect_id is not None:
        canvas.itemconfig(rect_id, fill=pen_color)
    else:
        painted_cells[key] = canvas.create_rectangle(
            gx, gy, gx + RES_SIZE, gy + RES_SIZE,
            fill=pen_color, outline="", tags="paint"
        )


def draw_line_blocks(x0, y0, x1, y1):
    """Paint or erase every cell along the axis-aligned movement."""
    x0, y0 = clamp_cell(x0, y0)
    x1, y1 = clamp_cell(x1, y1)
    step_x = RES_SIZE if x1 > x0 else (-RES_SIZE if x1 < x0 else 0)
    step_y = RES_SIZE if y1 > y0 else (-RES_SIZE if y1 < y0 else 0)
    curr_x, curr_y = x0, y0
    paint_cell(curr_x, curr_y)
    while curr_x != x1:
        curr_x += step_x
        paint_cell(curr_x, curr_y)
    while curr_y != y1:
        curr_y += step_y
        paint_cell(curr_x, curr_y)


def clear_screen():
    """Remove all painted cells. The grid is kept."""
    canvas.delete("paint")
    painted_cells.clear()


def item_under_cursor():
    """Index of the dock button under the cursor, or None."""
    cx = cursor_x + RES_SIZE / 2
    cy = cursor_y + RES_SIZE / 2
    for i, (_, _, x0, y0, x1, y1, _) in enumerate(buttons):
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            return i
    return None


def draw_dock(hover):
    """Redraw the parts of the dock that change (status text + buttons)."""
    canvas.delete("dock_dyn")
    color = tool_color()

    # Status: square (solid = pen down, outline = pen up) + text
    sx0, sy0 = 20, CANVAS_SIZE + 34
    if pen_down:
        canvas.create_rectangle(sx0, sy0, sx0 + 32, sy0 + 32, fill=color,
                                outline="#444444", width=1, tags="dock_dyn")
    else:
        canvas.create_rectangle(sx0, sy0, sx0 + 32, sy0 + 32, fill="",
                                outline=color, width=3, tags="dock_dyn")
    label = "Eraser selected" if tool == ERASER else "Pen selected"
    canvas.create_text(sx0 + 44, sy0 + 16, text=label, anchor="w",
                       font=("Arial", 14, "bold"), fill="black", tags="dock_dyn")

    # Buttons
    for i, (kind, value, x0, y0, x1, y1, text) in enumerate(buttons):
        if kind == "color":
            fill = value
            selected = (tool == PEN and pen_color == value)
        elif kind == "eraser":
            fill = ERASER_COLOR
            selected = (tool == ERASER)
        else:
            fill = "white"
            selected = False

        if selected:
            outline, width = "black", 4
        elif i == hover:
            outline, width = "#0078d7", 3
        else:
            outline, width = "#888888", 1
        canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline,
                                width=width, tags="dock_dyn")
        if text:
            canvas.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=text,
                               font=("Arial", 11, "bold"), fill="black",
                               tags="dock_dyn")


def update_cursor():
    global last_dock_state

    hover = item_under_cursor()
    state = (tool, pen_color, pen_down, hover)
    if state != last_dock_state:
        last_dock_state = state
        draw_dock(hover)

    canvas.coords(cursor, cursor_x, cursor_y,
                  cursor_x + RES_SIZE, cursor_y + RES_SIZE)
    color = tool_color()
    if pen_down:
        canvas.itemconfig(cursor, fill=color, outline=color, width=1)
    else:
        canvas.itemconfig(cursor, fill="", outline=color, width=2)
    canvas.tag_raise(cursor)


def toggle_pen_down():
    """X encoder click: lift or lower the pen/eraser."""
    global pen_down
    pen_down = not pen_down
    if pen_down:
        paint_cell(cursor_x, cursor_y)


def click_dock():
    """Y encoder click: press whatever dock button the cursor is over."""
    global tool, pen_color
    idx = item_under_cursor()
    if idx is None:
        return
    kind, value = buttons[idx][0], buttons[idx][1]
    if kind == "color":
        tool = PEN
        pen_color = value
    elif kind == "eraser":
        tool = ERASER
    elif kind == "clear":
        clear_screen()


def process_packet(line):
    global cursor_x, cursor_y, synced, x_button_held, y_button_held

    line = line.strip()
    if not (line.startswith("{") and line.endswith("}")):
        return
    try:
        # Format: "{x = 400, y = 400, LBut = 0, RBut = 0}"
        parts = dict(item.strip().split(" = ", 1)
                     for item in line[1:-1].split(","))
        new_x = int(parts["x"])
        new_y = int(parts["y"])
        x_down = bool(int(parts["LBut"]))
        y_down = bool(int(parts["RBut"]))
    except (ValueError, KeyError):
        return

    new_x, new_y = clamp_cell(new_x, new_y)

    # First packet: place the cursor where the hardware is, without drawing.
    if not synced:
        cursor_x, cursor_y = new_x, new_y
        x_button_held, y_button_held = x_down, y_down
        synced = True
        update_cursor()
        return

    # Button presses (down edges only, so holding is a single click)
    # Physical LEFT encoder = pen up/down, physical RIGHT encoder = dock click.
    # (On this build the physical right encoder is the one reported as LBut.)
    if x_down and not x_button_held:
        click_dock()
    if y_down and not y_button_held:
        toggle_pen_down()
    x_button_held = x_down
    y_button_held = y_down

    # Movement paints/erases only while the pen is down
    if pen_down and (new_x != cursor_x or new_y != cursor_y):
        draw_line_blocks(cursor_x, cursor_y, new_x, new_y)

    cursor_x, cursor_y = new_x, new_y
    update_cursor()


def read_serial():
    """Read whatever arrived and process only complete lines."""
    global rx_buffer
    if ser.in_waiting:
        rx_buffer += ser.read(ser.in_waiting).decode("utf-8", errors="ignore")
    if len(rx_buffer) > 4096:      # guard against runaway garbage
        rx_buffer = ""
    *lines, rx_buffer = rx_buffer.split("\n")
    for line in lines:
        process_packet(line)


def update_canvas():
    global serial_ok
    if serial_ok:
        try:
            read_serial()
        except (serial.SerialException, OSError) as exc:
            print(f"Serial Read Error: {exc}  (is the Arduino unplugged?)")
            serial_ok = False
    root.after(5, update_canvas)


def close_app():
    try:
        if ser and ser.is_open:
            ser.close()
    finally:
        root.destroy()


draw_grid()
draw_dock_background()
cursor = canvas.create_rectangle(cursor_x, cursor_y,
                                 cursor_x + RES_SIZE, cursor_y + RES_SIZE,
                                 fill="", outline="black", tags="cursor")
update_cursor()
root.protocol("WM_DELETE_WINDOW", close_app)
root.after(5, update_canvas)
root.mainloop()