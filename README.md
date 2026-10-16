# Arduino Etch-A-Sketch

A DIY Etch-A-Sketch made using an Arduino Nano and two rotary encoders. Built for the ATMOS tech fest workshop.

## What's in the kit?
- Arduino Nano + USB cable
- 2 rotary encoders
- 400-point breadboard
- 3 mm MDF pieces for the snap-fit enclosure

## Getting started
1. Assemble the MDF pieces and wire up the components.
2. Open `EtchASketch.ino` in the Arduino IDE and upload it to the Nano. Install any required libraries if prompted.
3. Install the Python dependency:
   ```bash
   pip install pyserial
   ```
4. Check the Arduino's serial port in `main.py` and change it if needed.
5. Run the Python script:
   ```bash
   python main.py
   ```

That's it! Left click to start/stop drawing, right click to clear canvas. Let see what you can draw :p 
