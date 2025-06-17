import time
import math
import random
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306 # Using ssd1306 as specified
from PIL import ImageDraw, Image

# --- Constants (from C++ header) ---
BGCOLOR = 0  # Background color (black for OLED)
MAINCOLOR = 1  # Main drawing color (white for OLED)

# Mood types
DEFAULT = 0
TIRED = 1
ANGRY = 2
HAPPY = 3

# On/Off states
ON = True
OFF = False

# Predefined positions
N = 1
NE = 2
E = 3
SE = 4
S = 5
SW = 6
W = 7
NW = 8

# --- OLED Device Setup ---
# Raspberry Pi 3B with SSD1306 128x64 OLED via I2C
# I2C bus: 1 (common for Raspberry Pi)
# I2C address: 0x3C (common for 128x64 SSD1306 OLEDs)
try:
    serial = i2c(port=1, address=0x3C)
    device = ssd1306(serial, width=128, height=64)
    print("OLED device initialized successfully: SSD1306 128x64 via I2C.")
except Exception as e:
    print(f"Error initializing OLED: {e}")
    print("Falling back to luma.emulator. You won't see output on a physical display.")
    from luma.emulator.device import pygame_display
    device = pygame_display(width=128, height=64, mode="1") # Monochrome mode
    print("Using luma.emulator. Connect to a VNC viewer or monitor to see the output.")

# --- RoboEyes Python Implementation ---
class RoboEyes:
    def __init__(self, display_device):
        self.display = display_device
        # screenWidth and screenHeight will be set by begin()
        self.screenWidth = display_device.width
        self.screenHeight = display_device.height
        self.frameInterval = 20  # default for 50 FPS (1000/50)
        self.fpsTimer = time.time() * 1000  # Convert to milliseconds for consistency

        # Mood and expression flags
        self.tired = False
        self.angry = False
        self.happy = False
        self.curious = False
        self.cyclops = False
        self.eyeL_open = False
        self.eyeR_open = False

        # --- Eye Geometry ---
        # Default values (will be initialized more accurately in begin/setters)
        self.eyeLwidthDefault = 36
        self.eyeLheightDefault = 36
        self.eyeLwidthCurrent = 1 # Start closed
        self.eyeLheightCurrent = 1 # Start closed
        self.eyeLwidthNext = self.eyeLwidthDefault
        self.eyeLheightNext = self.eyeLheightDefault
        self.eyeLheightOffset = 0 # For curious mode
        self.eyeLborderRadiusDefault = 8
        self.eyeLborderRadiusCurrent = self.eyeLborderRadiusDefault
        self.eyeLborderRadiusNext = self.eyeLborderRadiusDefault

        self.eyeRwidthDefault = self.eyeLwidthDefault
        self.eyeRheightDefault = self.eyeLheightDefault
        self.eyeRwidthCurrent = 1 # Start closed
        self.eyeRheightCurrent = 1 # Start closed
        self.eyeRwidthNext = self.eyeRwidthDefault
        self.eyeRheightNext = self.eyeRheightDefault
        self.eyeRheightOffset = 0
        self.eyeRborderRadiusDefault = 8
        self.eyeRborderRadiusCurrent = self.eyeRborderRadiusDefault
        self.eyeRborderRadiusNext = self.eyeRborderRadiusDefault

        # Coordinates - will be calculated based on screen size and eye sizes
        self.spaceBetweenDefault = 10
        self.spaceBetweenCurrent = self.spaceBetweenDefault
        self.spaceBetweenNext = self.spaceBetweenDefault
        self.eyeLxDefault = (self.screenWidth - (self.eyeLwidthDefault + self.spaceBetweenDefault + self.eyeRwidthDefault)) // 2
        self.eyeLyDefault = ((self.screenHeight - self.eyeLheightDefault) // 2)
        self.eyeRxDefault = self.eyeLxDefault + self.eyeLwidthDefault + self.spaceBetweenDefault
        self.eyeRyDefault = self.eyeLyDefault
        self.eyeLx = self.eyeLxDefault
        self.eyeLy = self.eyeLyDefault
        self.eyeRx = self.eyeRxDefault
        self.eyeRy = self.eyeRyDefault
        self.eyeLxNext = self.eyeLx
        self.eyeLyNext = self.eyeLy
        self.eyeRxNext = self.eyeRx
        self.eyeRyNext = self.eyeRy

        # Eyelid offsets for mood expressions
        self.eyelidsHeightMax = self.eyeLheightDefault // 2
        self.eyelidsTiredHeight = 0
        self.eyelidsTiredHeightNext = 0
        self.eyelidsAngryHeight = 0
        self.eyelidsAngryHeightNext = 0
        self.eyelidsHappyBottomOffsetMax = (self.eyeLheightDefault // 2) + 3
        self.eyelidsHappyBottomOffset = 0
        self.eyelidsHappyBottomOffsetNext = 0

        # --- Macro Animations ---
        self.hFlicker = False
        self.hFlickerAlternate = False
        self.hFlickerAmplitude = 2

        self.vFlicker = False
        self.vFlickerAlternate = False
        self.vFlickerAmplitude = 10

        self.autoblinker = False
        self.blinkInterval = 1
        self.blinkIntervalVariation = 4
        self.blinktimer = 0

        self.idle = False
        self.idleInterval = 1
        self.idleIntervalVariation = 3
        self.idleAnimationTimer = 0

        self.confused = False
        self.confusedAnimationTimer = 0
        self.confusedAnimationDuration = 500
        self.confusedToggle = True

        self.laugh = False
        self.laughAnimationTimer = 0
        self.laughAnimationDuration = 500
        self.laughToggle = True

    # --- GENERAL METHODS ---
    def begin(self, width, height, frameRate):
        self.screenWidth = width
        self.screenHeight = height
        self.display.clear() # clear the display buffer
        self.display.display() # show empty screen
        self.eyeLheightCurrent = 1  # start with closed eyes
        self.eyeRheightCurrent = 1  # start with closed eyes
        self.setFramerate(frameRate)  # calculate frame interval

        # Re-calculate default positions based on screen and default eye sizes
        self.eyeLwidthDefault = self.eyeLwidthNext
        self.eyeRwidthDefault = self.eyeRwidthNext
        self.eyeLheightDefault = self.eyeLheightNext
        self.eyeRheightDefault = self.eyeRheightNext
        self.spaceBetweenDefault = self.spaceBetweenNext

        self.eyeLxDefault = (self.screenWidth - (self.eyeLwidthDefault + self.spaceBetweenDefault + self.eyeRwidthDefault)) // 2
        self.eyeLyDefault = ((self.screenHeight - self.eyeLheightDefault) // 2)
        self.eyeRxDefault = self.eyeLxDefault + self.eyeLwidthDefault + self.spaceBetweenDefault
        self.eyeRyDefault = self.eyeLyDefault
        self.eyeLx = self.eyeLxDefault
        self.eyeLy = self.eyeLyDefault
        self.eyeRx = self.eyeRxDefault
        self.eyeRy = self.eyeRyDefault
        self.eyeLxNext = self.eyeLx
        self.eyeLyNext = self.eyeLy
        self.eyeRxNext = self.eyeRx
        self.eyeRyNext = self.eyeRy


    def update(self):
        # Limit drawing updates to defined max framerate
        if (time.time() * 1000) - self.fpsTimer >= self.frameInterval:
            self.drawEyes()
            self.fpsTimer = time.time() * 1000

    # --- SETTERS METHODS ---
    def setFramerate(self, fps):
        self.frameInterval = 1000 / fps

    def setWidth(self, leftEye, rightEye):
        self.eyeLwidthNext = leftEye
        self.eyeRwidthNext = rightEye
        self.eyeLwidthDefault = leftEye
        self.eyeRwidthDefault = rightEye

    def setHeight(self, leftEye, rightEye):
        self.eyeLheightNext = leftEye
        self.eyeRheightNext = rightEye
        self.eyeLheightDefault = leftEye
        self.eyeRheightDefault = rightEye

    def setBorderradius(self, leftEye, rightEye):
        self.eyeLborderRadiusNext = leftEye
        self.eyeRborderRadiusNext = rightEye
        self.eyeLborderRadiusDefault = leftEye
        self.eyeRborderRadiusDefault = rightEye

    def setSpacebetween(self, space):
        self.spaceBetweenNext = space
        self.spaceBetweenDefault = space

    def setMood(self, mood):
        self.tired = (mood == TIRED)
        self.angry = (mood == ANGRY)
        self.happy = (mood == HAPPY)
        # Default is handled by setting all to False if no match

    def setPosition(self, position):
        # Calculate target x and y based on position and current eye sizes
        # Note: This is an approximation. Original C++ calculates based on `_Current` values
        # in some places, which are updated dynamically. For perfect replication,
        # you'd need to consider the order of operations in `drawEyes`.
        
        # Calculate screen constraints first, based on current eye sizes
        max_x = self.getScreenConstraint_X()
        max_y = self.getScreenConstraint_Y()

        if position == N:
            self.eyeLxNext = max_x // 2
            self.eyeLyNext = 0
        elif position == NE:
            self.eyeLxNext = max_x
            self.eyeLyNext = 0
        elif position == E:
            self.eyeLxNext = max_x
            self.eyeLyNext = max_y // 2
        elif position == SE:
            self.eyeLxNext = max_x
            self.eyeLyNext = max_y
        elif position == S:
            self.eyeLxNext = max_x // 2
            self.eyeLyNext = max_y
        elif position == SW:
            self.eyeLxNext = 0
            self.eyeLyNext = max_y
        elif position == W:
            self.eyeLxNext = 0
            self.eyeLyNext = max_y // 2
        elif position == NW:
            self.eyeLxNext = 0
            self.eyeLyNext = 0
        else:  # DEFAULT
            self.eyeLxNext = max_x // 2
            self.eyeLyNext = max_y // 2

        # Right eye's target position is relative to left eye's target
        self.eyeRxNext = self.eyeLxNext + self.eyeLwidthCurrent + self.spaceBetweenCurrent # Use current eyeLwidth/spaceBetween for smooth follow
        self.eyeRyNext = self.eyeLyNext

    def setAutoblinker(self, active, interval=1, variation=4):
        self.autoblinker = active
        self.blinkInterval = interval
        self.blinkIntervalVariation = variation

    def setIdleMode(self, active, interval=1, variation=3):
        self.idle = active
        self.idleInterval = interval
        self.idleIntervalVariation = variation

    def setCuriosity(self, curiousBit):
        self.curious = curiousBit

    def setCyclops(self, cyclopsBit):
        self.cyclops = cyclopsBit

    def setHFlicker(self, flickerBit, amplitude=2):
        self.hFlicker = flickerBit
        self.hFlickerAmplitude = amplitude

    def setVFlicker(self, flickerBit, amplitude=10):
        self.vFlicker = flickerBit
        self.vFlickerAmplitude = amplitude

    # --- GETTERS METHODS ---
    def getScreenConstraint_X(self):
        # Using current values for dynamic constraints, as in C++
        return self.screenWidth - self.eyeLwidthCurrent - self.spaceBetweenCurrent - self.eyeRwidthCurrent

    def getScreenConstraint_Y(self):
        # Using default height as in C++ comment, because current height varies with blinking/curious
        return self.screenHeight - self.eyeLheightDefault

    # --- BASIC ANIMATION METHODS ---
    def close(self, left=True, right=True):
        if left:
            self.eyeLheightNext = 1
            self.eyeL_open = False
        if right:
            self.eyeRheightNext = 1
            self.eyeR_open = False

    def open(self, left=True, right=True):
        if left:
            self.eyeL_open = True
        if right:
            self.eyeR_open = True

    def blink(self, left=True, right=True):
        self.close(left, right)
        # Note: In the original C++ library, the "open" call doesn't immediately
        # open the eye, but sets a flag that drawEyes() will act upon over time.
        # Here, we'll set the flag and rely on update() calls.
        self.open(left, right)

    # --- MACRO ANIMATION METHODS ---
    def anim_confused(self):
        self.confused = True

    def anim_laugh(self):
        self.laugh = True

    # --- PRE-CALCULATIONS AND ACTUAL DRAWINGS ---
    def drawEyes(self):
        # //// PRE-CALCULATIONS - EYE SIZES AND VALUES FOR ANIMATION TWEENINGS ////
        
        # Vertical size offset for larger eyes when looking left or right (curious gaze)
        if self.curious:
            # Replicate C++ logic as closely as possible
            if self.eyeLxNext <= 10:
                self.eyeLheightOffset = 8
            elif self.eyeLxNext >= (self.getScreenConstraint_X() - 10) and self.cyclops: # Only curious if cyclops and looking far right
                self.eyeLheightOffset = 8
            else:
                self.eyeLheightOffset = 0 # left eye

            if self.eyeRxNext >= self.screenWidth - self.eyeRwidthCurrent - 10: # Right eye specific curious
                self.eyeRheightOffset = 8
            else:
                self.eyeRheightOffset = 0 # right eye
        else:
            self.eyeLheightOffset = 0  # reset height offset for left eye
            self.eyeRheightOffset = 0  # reset height offset for right eye

        # Left eye height
        self.eyeLheightCurrent = (self.eyeLheightCurrent + self.eyeLheightNext + self.eyeLheightOffset) / 2
        # Vertical centering of eye when closing/changing height
        # Original C++ adds/subtracts to eyeLy, which is also being tweened.
        # This will be tricky to perfectly replicate without a 1:1 tweening system.
        # We'll apply it relative to the default Y, and let the overall eyeLy tween later.
        
        # Right eye height
        self.eyeRheightCurrent = (self.eyeRheightCurrent + self.eyeRheightNext + self.eyeRheightOffset) / 2

        # Open eyes again after closing them
        if self.eyeL_open:
            if self.eyeLheightCurrent <= 1 + self.eyeLheightOffset:
                self.eyeLheightNext = self.eyeLheightDefault
        if self.eyeR_open:
            if self.eyeRheightCurrent <= 1 + self.eyeRheightOffset:
                self.eyeRheightNext = self.eyeRheightDefault

        # Left eye width
        self.eyeLwidthCurrent = (self.eyeLwidthCurrent + self.eyeLwidthNext) / 2
        # Right eye width
        self.eyeRwidthCurrent = (self.eyeRwidthCurrent + self.eyeRwidthNext) / 2

        # Space between eyes
        self.spaceBetweenCurrent = (self.spaceBetweenCurrent + self.spaceBetweenNext) / 2

        # Left eye coordinates
        self.eyeLx = (self.eyeLx + self.eyeLxNext) / 2
        self.eyeLy_calculated_center_adjust = ((self.eyeLheightDefault - self.eyeLheightCurrent) / 2) - (self.eyeLheightOffset / 2)
        self.eyeLy = (self.eyeLy + self.eyeLyNext) / 2 + self.eyeLy_calculated_center_adjust
        

        # Right eye coordinates
        self.eyeRxNext = self.eyeLxNext + self.eyeLwidthCurrent + self.spaceBetweenCurrent # Right eye's x position depends on left eye's position + space
        self.eyeRyNext = self.eyeLyNext  # Right eye's y position should be the same as for the left eye
        self.eyeRx = (self.eyeRx + self.eyeRxNext) / 2
        self.eyeRy_calculated_center_adjust = ((self.eyeRheightDefault - self.eyeRheightCurrent) / 2) - (self.eyeRheightOffset / 2)
        self.eyeRy = (self.eyeRy + self.eyeRyNext) / 2 + self.eyeRy_calculated_center_adjust

        # Left eye border radius
        self.eyeLborderRadiusCurrent = (self.eyeLborderRadiusCurrent + self.eyeLborderRadiusNext) / 2
        # Right eye border radius
        self.eyeRborderRadiusCurrent = (self.eyeRborderRadiusCurrent + self.eyeRborderRadiusNext) / 2

        # //// APPLYING MACRO ANIMATIONS ////
        current_millis = time.time() * 1000 # Python equivalent of millis()

        if self.autoblinker:
            if current_millis >= self.blinktimer:
                self.blink()
                self.blinktimer = current_millis + (self.blinkInterval * 1000) + \
                                  (random.randint(0, self.blinkIntervalVariation) * 1000)

        # Laughing - eyes shaking up and down
        if self.laugh:
            if self.laughToggle:
                self.setVFlicker(ON, 5)
                self.laughAnimationTimer = current_millis
                self.laughToggle = False
            elif current_millis >= self.laughAnimationTimer + self.laughAnimationDuration:
                self.setVFlicker(OFF, 0)
                self.laughToggle = True
                self.laugh = False

        # Confused - eyes shaking left and right
        if self.confused:
            if self.confusedToggle:
                self.setHFlicker(ON, 20)
                self.confusedAnimationTimer = current_millis
                self.confusedToggle = False
            elif current_millis >= self.confusedAnimationTimer + self.confusedAnimationDuration:
                self.setHFlicker(OFF, 0)
                self.confusedToggle = True
                self.confused = False

        # Idle - eyes moving to random positions on screen
        if self.idle:
            if current_millis >= self.idleAnimationTimer:
                self.eyeLxNext = random.randint(0, self.getScreenConstraint_X())
                self.eyeLyNext = random.randint(0, self.getScreenConstraint_Y())
                self.idleAnimationTimer = current_millis + (self.idleInterval * 1000) + \
                                          (random.randint(0, self.idleIntervalVariation) * 1000)

        # Adding offsets for horizontal flickering/shivering
        if self.hFlicker:
            if self.hFlickerAlternate:
                self.eyeLx += self.hFlickerAmplitude
                self.eyeRx += self.hFlickerAmplitude
            else:
                self.eyeLx -= self.hFlickerAmplitude
                self.eyeRx -= self.hFlickerAmplitude
            self.hFlickerAlternate = not self.hFlickerAlternate

        # Adding offsets for vertical flickering/shivering
        if self.vFlicker:
            if self.vFlickerAlternate:
                self.eyeLy += self.vFlickerAmplitude
                self.eyeRy += self.vFlickerAmplitude
            else:
                self.eyeLy -= self.vFlickerAmplitude
                self.eyeRy -= self.vFlickerAmplitude
            self.vFlickerAlternate = not self.vFlickerAlternate

        # Cyclops mode, set second eye's size and space between to 0
        if self.cyclops:
            self.eyeRwidthCurrent = 0
            self.eyeRheightCurrent = 0
            self.spaceBetweenCurrent = 0

        # //// ACTUAL DRAWINGS ////
        with canvas(self.display) as draw:
            draw.rectangle(self.display.bounding_box, outline=BGCOLOR, fill=BGCOLOR) # Clear background

            # Draw basic eye rectangles
            # Make sure coordinates are integers for Pillow
            elx = int(self.eyeLx)
            ely = int(self.eyeLy)
            elw = int(self.eyeLwidthCurrent)
            elh = int(self.eyeLheightCurrent)
            elr = int(self.eyeLborderRadiusCurrent)

            draw.rounded_rectangle((elx, ely, elx + elw, ely + elh), radius=elr, fill=MAINCOLOR, outline=MAINCOLOR) # left eye

            if not self.cyclops:
                erx = int(self.eyeRx)
                ery = int(self.eyeRy)
                erw = int(self.eyeRwidthCurrent)
                erh = int(self.eyeRheightCurrent)
                err = int(self.eyeRborderRadiusCurrent)
                draw.rounded_rectangle((erx, ery, erx + erw, ery + erh), radius=err, fill=MAINCOLOR, outline=MAINCOLOR) # right eye

            # Prepare mood type transitions
            if self.tired:
                self.eyelidsTiredHeightNext = self.eyeLheightCurrent / 2
                self.eyelidsAngryHeightNext = 0
            else:
                self.eyelidsTiredHeightNext = 0
            
            if self.angry:
                self.eyelidsAngryHeightNext = self.eyeLheightCurrent / 2
                self.eyelidsTiredHeightNext = 0
            else:
                self.eyelidsAngryHeightNext = 0
            
            if self.happy:
                self.eyelidsHappyBottomOffsetNext = self.eyeLheightCurrent / 2
            else:
                self.eyelidsHappyBottomOffsetNext = 0

            # Draw tired top eyelids (triangles for an eyelid shape)
            # Coordinates for fillTriangle(x1, y1, x2, y2, x3, y3, color)
            # Pillow uses polygon for triangles: [(x1,y1), (x2,y2), (x3,y3)]
            self.eyelidsTiredHeight = (self.eyelidsTiredHeight + self.eyelidsTiredHeightNext) / 2
            
            if not self.cyclops:
                draw.polygon([(elx, ely - 1), (elx + elw, ely - 1), (elx, ely + self.eyelidsTiredHeight - 1)], fill=BGCOLOR) # left eye
                draw.polygon([(erx, ery - 1), (erx + erw, ery - 1), (erx + erw, ery + self.eyelidsTiredHeight - 1)], fill=BGCOLOR) # right eye
            else:
                # Cyclops tired eyelids
                draw.polygon([(elx, ely - 1), (elx + (elw / 2), ely - 1), (elx, ely + self.eyelidsTiredHeight - 1)], fill=BGCOLOR) # left eyelid half
                draw.polygon([(elx + (elw / 2), ely - 1), (elx + elw, ely - 1), (elx + elw, ely + self.eyelidsTiredHeight - 1)], fill=BGCOLOR) # right eyelid half


            # Draw angry top eyelids
            self.eyelidsAngryHeight = (self.eyelidsAngryHeight + self.eyelidsAngryHeightNext) / 2
            if not self.cyclops:
                draw.polygon([(elx, ely - 1), (elx + elw, ely - 1), (elx + elw, ely + self.eyelidsAngryHeight - 1)], fill=BGCOLOR) # left eye
                draw.polygon([(erx, ery - 1), (erx + erw, ery - 1), (erx, ery + self.eyelidsAngryHeight - 1)], fill=BGCOLOR) # right eye
            else:
                # Cyclops angry eyelids
                draw.polygon([(elx, ely - 1), (elx + (elw / 2), ely - 1), (elx + (elw / 2), ely + self.eyelidsAngryHeight - 1)], fill=BGCOLOR) # left eyelid half
                draw.polygon([(elx + (elw / 2), ely - 1), (elx + elw, ely - 1), (elx + (elw / 2), ely + self.eyelidsAngryHeight - 1)], fill=BGCOLOR) # right eyelid half


            # Draw happy bottom eyelids
            self.eyelidsHappyBottomOffset = (self.eyelidsHappyBottomOffset + self.eyelidsHappyBottomOffsetNext) / 2
            # Using fillRoundRect for happy bottom eyelids, similar to C++
            draw.rounded_rectangle((elx - 1, (ely + elh) - self.eyelidsHappyBottomOffset + 1,
                                   elx + elw + 2, ely + self.eyeLheightDefault),
                                   radius=elr, fill=BGCOLOR, outline=BGCOLOR) # left eye
            if not self.cyclops:
                draw.rounded_rectangle((erx - 1, (ery + erh) - self.eyelidsHappyBottomOffset + 1,
                                       erx + erw + 2, ery + self.eyeRheightDefault),
                                       radius=err, fill=BGCOLOR, outline=BGCOLOR) # right eye

        # Update the physical display
        self.display.display()


# --- Main Loop Example (Replicating Arduino Sketch Sequence) ---
if __name__ == "__main__":
    eyes = RoboEyes(device)

    # Startup RoboEyes (mimicking Arduino setup())
    # screen-width, screen-height, max framerate - 60-100fps are good for smooth animations
    eyes.begin(device.width, device.height, 100)
    eyes.setPosition(DEFAULT) # eye position should be middle center
    eyes.close() # start with closed eyes

    eventTimer = time.time() * 1000 # Start event timer (in milliseconds)
    event1wasPlayed = False # flag variables
    event2wasPlayed = False
    event3wasPlayed = False

    print("RoboEyes animation sequence started. Press Ctrl+C to exit.")

    try:
        while True:
            current_millis = time.time() * 1000 # Get current time in milliseconds

            eyes.update() # update eyes drawings (this also handles internal animation tweening)

            # --- LOOPED ANIMATION SEQUENCE (from Arduino sketch) ---

            # Do once after 2 seconds
            if current_millis >= eventTimer + 2000 and not event1wasPlayed:
                event1wasPlayed = True
                eyes.open() # open eyes
                print(f"{current_millis - eventTimer:.0f}ms: Eyes Opened")

            # Do once after 4 seconds
            if current_millis >= eventTimer + 4000 and not event2wasPlayed:
                event2wasPlayed = True
                eyes.setMood(HAPPY)
                eyes.anim_laugh()
                print(f"{current_millis - eventTimer:.0f}ms: Mood HAPPY, Laughing")

            # Do once after 6 seconds
            if current_millis >= eventTimer + 6000 and not event3wasPlayed:
                event3wasPlayed = True
                eyes.setMood(TIRED)
                print(f"{current_millis - eventTimer:.0f}ms: Mood TIRED")

            # Do once after 8 seconds, then reset timer and flags to restart
            if current_millis >= eventTimer + 8000:
                eyes.close() # close eyes again
                eyes.setMood(DEFAULT)
                print(f"{current_millis - eventTimer:.0f}ms: Eyes Closed, Mood DEFAULT (Resetting sequence)")
                
                # Reset the timer and the event flags to restart the whole animation sequence
                eventTimer = current_millis # reset timer to current time
                event1wasPlayed = False # reset flags
                event2wasPlayed = False
                event3wasPlayed = False

            # --- END OF LOOPED ANIMATION SEQUENCE ---

            # Small delay to prevent busy-waiting and reduce CPU usage,
            # especially if the update() method is very fast.
            # This also ensures the loop runs roughly at the target FPS.
            time.sleep(0.001) # Sleep for 1ms if nothing is actively updating the display

    except KeyboardInterrupt:
        print("\nExiting RoboEyes animation.")
    finally:
        # Clear the display on exit
        print("Clearing OLED display...")
        device.clear()
        device.display()
        print("Display cleared. Goodbye!")

