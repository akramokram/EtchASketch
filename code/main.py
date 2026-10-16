import sys
import tkinter as tk
import serial
import serial.tools.list_ports

# ---------------- CONFIGURATION ---------------- #
COMPORT = 'COM6'   # Change if needed, or let script auto-detect
BAUDRATE = 115200  # Must match the Arduino baud rate
RES_SIZE = 10
# ------------------------------------------------ #

def find_serial_port():
    """Finds and opens the requested COM port or falls back to an available one."""
    global COMPORT
    available_ports = [p.device for p in serial.tools.list_ports.comports()]
    
    if not available_ports:
        print("ERROR: No serial COM ports detected. Check your USB connection.")
        sys.exit(1)

    if COMPORT not in available_ports:
        print(f"Target port '{COMPORT}' not detected. Found: {available_ports}")
        COMPORT = available_ports[0]
        print(f"Connecting to available port: {COMPORT}")

    try:
        ser = serial.Serial(COMPORT, BAUDRATE, timeout=0.05)
        print(f"Connected to {COMPORT} at {BAUDRATE} baud.")
        return ser
    except serial.SerialException as e:
        print(f"Could not open port {COMPORT}: {e}")
        print("Make sure the Arduino IDE Serial Monitor is closed!")
        sys.exit(1)

ser = find_serial_port()

# GUI Setup
root = tk.Tk()
root.state('zoomed')
root.minsize(800, 800)
root.title("Etch-A-Sketch")

canvas = tk.Canvas(root, width=800, height=800, bg="white")
canvas.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

# Tracking state
cursor = None
cursor_x = 400
cursor_y = 400
cursor_drawing = False
l_button = False

def clearCanvas():
    """Clears canvas drawings and re-renders grid and cursor."""
    global cursor
    canvas.delete("all")

    # Draw grid
    for i in range(0, 801, RES_SIZE):
        canvas.create_line(i, 0, i, 800, fill="#eeeeee")
        canvas.create_line(0, i, 800, i, fill="#eeeeee")

    # Initial cursor box
    cursor = canvas.create_rectangle(
        cursor_x,
        cursor_y,
        cursor_x + RES_SIZE,
        cursor_y + RES_SIZE,
        fill="red",
        outline="grey"
    )

clearCanvas()

def draw_line_blocks(x0, y0, x1, y1):
    """Fills all intermediate grid blocks to prevent skipped gaps during fast turns."""
    step_x = RES_SIZE if x1 > x0 else (-RES_SIZE if x1 < x0 else 0)
    step_y = RES_SIZE if y1 > y0 else (-RES_SIZE if y1 < y0 else 0)

    curr_x, curr_y = x0, y0

    # Fill intermediate steps along X
    while curr_x != x1:
        curr_x += step_x
        canvas.create_rectangle(
            curr_x, curr_y,
            curr_x + RES_SIZE, curr_y + RES_SIZE,
            fill="grey", outline=""
        )

    # Fill intermediate steps along Y
    while curr_y != y1:
        curr_y += step_y
        canvas.create_rectangle(
            curr_x, curr_y,
            curr_x + RES_SIZE, curr_y + RES_SIZE,
            fill="grey", outline=""
        )

def update_canvas():
    global cursor_x, cursor_y, l_button, cursor_drawing

    try:
        if ser.in_waiting > 0:
            # Read everything in the buffer at once to prevent stale backlog
            raw_bytes = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
            lines = [l.strip() for l in raw_bytes.strip().split('\n') if l.strip()]

            # Find the most recent complete packet
            latest_line = None
            for line in reversed(lines):
                if line.startswith('{') and line.endswith('}'):
                    latest_line = line
                    break

            if latest_line:
                # Format: "{x = 400, y = 400, LBut = 0, RBut = 0}"
                content = latest_line.strip("{}")
                parts = dict(item.split(" = ") for item in content.split(", "))

                new_x = int(parts['x'])
                new_y = int(parts['y'])
                cursor_drawing = bool(int(parts['LBut']))
                l_button = bool(int(parts['RBut']))

                if l_button:
                    clearCanvas()

                # If pen is down, fill continuous path between points
                if cursor_drawing:
                    if (new_x != cursor_x) or (new_y != cursor_y):
                        draw_line_blocks(cursor_x, cursor_y, new_x, new_y)
                    else:
                        canvas.create_rectangle(
                            new_x, new_y,
                            new_x + RES_SIZE, new_y + RES_SIZE,
                            fill="grey", outline=""
                        )

                # Update positions
                cursor_x = new_x
                cursor_y = new_y

                # Move cursor overlay
                canvas.moveto(cursor, cursor_x, cursor_y)
                canvas.itemconfig(cursor, fill="blue" if cursor_drawing else "red")

    except Exception as e:
        print(f"Serial Read Error: {e}")

    # 10ms loop rate gives smooth ~100 FPS
    root.after(10, update_canvas)

root.after(50, update_canvas)
root.mainloop()

if ser and ser.is_open:
    ser.close()