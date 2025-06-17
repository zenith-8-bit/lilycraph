import time
import random
# Removed numpy as it was not used

from luma.core.interface.serial import spi
from luma.oled.device import ssd1306, sh1106 # Or just ssd1306 if you know your chip
from PIL import ImageDraw, Image # Ensure Image is imported for explicit image creation

# --- Configuration for SPI ---
# SPI uses a bus (0 or 1) and device (0 or 1, for CS0 or CS1)
# Most common setup is bus 0, device 0 (CE0)
SPI_BUS = 0
SPI_DEVICE = 0 # Corresponds to CE0 (GPIO 8)

# GPIO pin numbers for DC and RESET (using BCM numbering)
# Ensure these match your wiring!
DC_PIN = 23    # Connected to GPIO 23 (Physical Pin 16)
RST_PIN = 24   # Connected to GPIO 24 (Physical Pin 18)

# --- OLED Device Initialization ---
# Initialize device to None, so we can check if it was successful later
device = None # Changed from oled_device to device for consistency with previous code
try:
    # Attempt to initialize SSD1306 via SPI
    serial = spi(port=SPI_BUS, device=SPI_DEVICE, gpio_DC=DC_PIN, gpio_RST=RST_PIN)
    device = ssd1306(serial)
    print(f"OLED display initialized successfully: {device.width}x{device.height} via SPI.")
except Exception as e:
    # If SPI device is not found, print a clear message and exit.
    # Removed luma.emulator fallback to simplify troubleshooting for physical hardware.
    print(f"ERROR: Could not initialize OLED display via SPI. Please ensure:")
    print(f"1. SPI is enabled on your Raspberry Pi ('sudo raspi-config' -> Interface Options -> SPI).")
    print(f"2. Your user has permissions to access SPI (sudo adduser $USER spi && reboot).")
    print(f"3. The OLED is correctly wired to the specified SPI (MOSI, CLK, DC, RST, CS) pins.")
    print(f"4. The SPI bus and device (port={SPI_BUS}, device={SPI_DEVICE}) are correct.")
    print(f"Details: {e}")
    exit() # Exit the script as we cannot proceed without a display

# --- Usage of monochrome display colors ---
# In Pillow, '0' is black, '1' is white for 1-bit images.
BGCOLOR = 0 # background and overlays
MAINCOLOR = 1 # drawings

# For mood type switch
DEFAULT = 0
TIRED = 1
ANGRY = 2
HAPPY = 3

# For turning things on or off
ON = True
OFF = False

# For switch "predefined positions"
N = 1 # north, top center
NE = 2 # north-east, top right
E = 3 # east, middle right
SE = 4 # south-east, bottom right
S = 5 # south, bottom center
SW = 6 # south-west, bottom left
W = 7 # west, middle left
NW = 8 # north-west, top left
# for middle center set "DEFAULT"

class RoboEyes:
    def __init__(self, display_device):
        """
        Initializes the RoboEyes class with the OLED display device.
        All parameters are mirrored from the C++ version.
        """
        self.display = display_device

        # For general setup - screen size and max. frame rate
        self.screenWidth = self.display.width  # OLED display width, in pixels
        self.screenHeight = self.display.height # OLED display height, in pixels
        self.frameInterval = 20  # default value for 50 frames per second (1000/50 = 20 milliseconds)
        # Use monotonic_ns for all timers for consistency and precision
        self.fpsTimer = time.monotonic_ns() // 1_000_000

        # For controlling mood types and expressions
        self.tired = False
        self.angry = False
        self.happy = False
        self.curious = False # if true, draw the outer eye larger when looking left or right
        self.cyclops = False # if true, draw only one eye
        self.eyeL_open = False # left eye opened or closed?
        self.eyeR_open = False # right eye opened or closed?

        # *********************************************************************************************
        # Eyes Geometry
        # *********************************************************************************************

        # EYE LEFT - size and border radius
        self.eyeLwidthDefault = 36
        self.eyeLheightDefault = 36
        self.eyeLwidthCurrent = self.eyeLwidthDefault
        self.eyeLheightCurrent = 1 # start with closed eye, otherwise set to eyeLheightDefault
        self.eyeLwidthNext = self.eyeLwidthDefault
        self.eyeLheightNext = self.eyeLheightDefault
        self.eyeLheightOffset = 0
        # Border Radius
        self.eyeLborderRadiusDefault = 8
        self.eyeLborderRadiusCurrent = self.eyeLborderRadiusDefault
        self.eyeLborderRadiusNext = self.eyeLborderRadiusDefault

        # EYE RIGHT - size and border radius
        self.eyeRwidthDefault = self.eyeLwidthDefault
        self.eyeRheightDefault = self.eyeLheightDefault
        self.eyeRwidthCurrent = self.eyeRwidthDefault
        self.eyeRheightCurrent = 1 # start with closed eye, otherwise set to eyeRheightDefault
        self.eyeRwidthNext = self.eyeRwidthDefault
        self.eyeRheightNext = self.eyeRheightDefault
        self.eyeRheightOffset = 0
        # Border Radius
        self.eyeRborderRadiusDefault = 8
        self.eyeRborderRadiusCurrent = self.eyeRborderRadiusDefault
        self.eyeRborderRadiusNext = self.eyeRborderRadiusDefault

        # EYE LEFT - Coordinates
        # These will be initialized properly in the begin() method after screen dimensions are set
        self.spaceBetweenDefault = 10 # Default space between eyes
        self.eyeLxDefault = (self.screenWidth - (self.eyeLwidthDefault + self.spaceBetweenDefault + self.eyeRwidthDefault)) // 2
        self.eyeLyDefault = ((self.screenHeight - self.eyeLheightDefault) // 2)
        self.eyeLx = self.eyeLxDefault
        self.eyeLy = self.eyeLyDefault
        self.eyeLxNext = self.eyeLx
        self.eyeLyNext = self.eyeLy

        # EYE RIGHT - Coordinates
        self.eyeRxDefault = self.eyeLx + self.eyeLwidthCurrent + self.spaceBetweenDefault
        self.eyeRyDefault = self.eyeLy
        self.eyeRx = self.eyeRxDefault
        self.eyeRy = self.eyeRyDefault
        self.eyeRxNext = self.eyeRx
        self.eyeRyNext = self.eyeRy

        # BOTH EYES
        # Eyelid top size
        self.eyelidsHeightMax = self.eyeLheightDefault // 2  # top eyelids max height
        self.eyelidsTiredHeight = 0
        self.eyelidsTiredHeightNext = self.eyelidsTiredHeight
        self.eyelidsAngryHeight = 0
        self.eyelidsAngryHeightNext = self.eyelidsAngryHeight
        # Bottom happy eyelids offset
        self.eyelidsHappyBottomOffsetMax = (self.eyeLheightDefault // 2) + 3
        self.eyelidsHappyBottomOffset = 0
        self.eyelidsHappyBottomOffsetNext = 0
        # Space between eyes
        self.spaceBetweenCurrent = self.spaceBetweenDefault
        self.spaceBetweenNext = 10

        # *********************************************************************************************
        # Macro Animations
        # *********************************************************************************************

        # Animation - horizontal flicker/shiver
        self.hFlicker = False
        self.hFlickerAlternate = False
        self.hFlickerAmplitude = 2

        # Animation - vertical flicker/shiver
        self.vFlicker = False
        self.vFlickerAlternate = False
        self.vFlickerAmplitude = 10

        # Animation - auto blinking
        self.autoblinker = False # activate auto blink animation
        self.blinkInterval = 1 # basic interval between each blink in full seconds
        self.blinkIntervalVariation = 4 # interval variaton range in full seconds, random number inside of given range will be add to the basic blinkInterval, set to 0 for no variation
        self.blinktimer = 0 # for organising eyeblink timing (using time.monotonic_ns)

        # Animation - idle mode: eyes looking in random directions
        self.idle = False
        self.idleInterval = 1 # basic interval between each eye repositioning in full seconds
        self.idleIntervalVariation = 3 # interval variaton range in full seconds, random number inside of given range will be add to the basic idleInterval, set to 0 for no variation
        self.idleAnimationTimer = 0 # for organising eyeblink timing

        # Animation - eyes confused: eyes shaking left and right
        self.confused = False
        self.confusedAnimationTimer = 0
        self.confusedAnimationDuration = 500 # milliseconds
        self.confusedToggle = True

        # Animation - eyes laughing: eyes shaking up and down
        self.laugh = False
        self.laughAnimationTimer = 0
        self.laughAnimationDuration = 500 # milliseconds
        self.laughToggle = True


    # *********************************************************************************************
    # GENERAL METHODS
    # *********************************************************************************************

    def begin(self, width, height, frameRate):
        """
        Startup RoboEyes with defined screen-width, screen-height and max. frame rate.
        """
        self.screenWidth = width
        self.screenHeight = height
        self.display.clear() # clear the display buffer
        self.display.display() # show empty screen
        self.eyeLheightCurrent = 1 # start with closed eyes
        self.eyeRheightCurrent = 1 # start with closed eyes
        self.setFramerate(frameRate) # calculate frame interval based on defined frameRate

        # Re-calculate default eye positions based on new screen dimensions
        self.eyeLxDefault = (self.screenWidth - (self.eyeLwidthDefault + self.spaceBetweenDefault + self.eyeRwidthDefault)) // 2
        self.eyeLyDefault = ((self.screenHeight - self.eyeLheightDefault) // 2)
        self.eyeLx = self.eyeLxDefault
        self.eyeLy = self.eyeLyDefault
        self.eyeLxNext = self.eyeLx
        self.eyeLyNext = self.eyeLy
        self.eyeRxDefault = self.eyeLx + self.eyeLwidthCurrent + self.spaceBetweenDefault
        self.eyeRyDefault = self.eyeLy
        self.eyeRx = self.eyeRxDefault
        self.eyeRy = self.eyeRyDefault
        self.eyeRxNext = self.eyeRx
        self.eyeRyNext = self.eyeRy


    def update(self):
        """
        Limit drawing updates to defined max framerate.
        """
        current_time_ms = time.monotonic_ns() // 1_000_000 # Convert nanoseconds to milliseconds
        if current_time_ms - self.fpsTimer >= self.frameInterval:
            self.drawEyes()
            self.fpsTimer = current_time_ms

    # *********************************************************************************************
    # SETTERS METHODS
    # *********************************************************************************************

    def setFramerate(self, fps):
        """Calculate frame interval based on defined frameRate."""
        self.frameInterval = 1000 // fps

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
        """Set border radius for left and right eye."""
        self.eyeLborderRadiusNext = leftEye
        self.eyeRborderRadiusNext = rightEye
        self.eyeLborderRadiusDefault = leftEye
        self.eyeRborderRadiusDefault = rightEye

    def setSpacebetween(self, space):
        """Set space between the eyes, can also be negative."""
        self.spaceBetweenNext = space
        self.spaceBetweenDefault = space

    def setMood(self, mood):
        """Set mood expression."""
        self.tired = False
        self.angry = False
        self.happy = False
        if mood == TIRED:
            self.tired = True
        elif mood == ANGRY:
            self.angry = True
        elif mood == HAPPY:
            self.happy = True

    def setPosition(self, position):
        """Set predefined position."""
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
        else: # DEFAULT (middle center)
            self.eyeLxNext = max_x // 2
            self.eyeLyNext = max_y // 2

        # Right eye's target position is relative to left eye's target
        self.eyeRxNext = self.eyeLxNext + self.eyeLwidthCurrent + self.spaceBetweenCurrent # Use current eyeLwidth/spaceBetween for smooth follow
        self.eyeRyNext = self.eyeLyNext

    def setAutoblinker(self, active, interval=1, variation=0):
        """Set automated eye blinking."""
        self.autoblinker = active
        self.blinkInterval = interval
        self.blinkIntervalVariation = variation
        # Initialize timer if activating
        if active:
            self.blinktimer = time.monotonic_ns() // 1_000_000 + (self.blinkInterval * 1000) + (random.randint(0, self.blinkIntervalVariation) * 1000)

    def setIdleMode(self, active, interval=1, variation=0):
        """Set idle mode - automated eye repositioning."""
        self.idle = active
        self.idleInterval = interval
        self.idleIntervalVariation = variation
        # Initialize timer if activating
        if active:
            self.idleAnimationTimer = time.monotonic_ns() // 1_000_000 + (self.idleInterval * 1000) + (random.randint(0, self.idleIntervalVariation) * 1000)

    def setCuriosity(self, curiousBit):
        """Set curious mode."""
        self.curious = curiousBit

    def setCyclops(self, cyclopsBit):
        """Set cyclops mode - show only one eye."""
        self.cyclops = cyclopsBit

    def setHFlicker(self, flickerBit, amplitude=2):
        """Set horizontal flickering (displacing eyes left/right)."""
        self.hFlicker = flickerBit
        self.hFlickerAmplitude = amplitude

    def setVFlicker(self, flickerBit, amplitude=10):
        """Set vertical flickering (displacing eyes up/down)."""
        self.vFlicker = flickerBit
        self.vFlickerAmplitude = amplitude

    # *********************************************************************************************
    # GETTERS METHODS
    # *********************************************************************************************

    def getScreenConstraint_X(self):
        """Returns the max x position for left eye."""
        return self.screenWidth - self.eyeLwidthCurrent - self.spaceBetweenCurrent - self.eyeRwidthCurrent

    def getScreenConstraint_Y(self):
        """Returns the max y position for left eye."""
        return self.screenHeight - self.eyeLheightDefault

    # *********************************************************************************************
    # BASIC ANIMATION METHODS
    # *********************************************************************************************

    def close(self, left=True, right=True):
        """Close eye(s)."""
        if left:
            self.eyeLheightNext = 1
            self.eyeL_open = False
        if right:
            self.eyeRheightNext = 1
            self.eyeR_open = False

    def open(self, left=True, right=True):
        """Open eye(s)."""
        if left:
            self.eyeL_open = True
            # Do NOT set eyeLheightNext directly here, rely on drawEyes's tweening
        if right:
            self.eyeR_open = True
            # Do NOT set eyeRheightNext directly here, rely on drawEyes's tweening

    def blink(self, left=True, right=True):
        """Trigger eyeblink animation."""
        self.close(left, right)
        # The 'open' will be handled by drawEyes() as eyeL_open/eyeR_open flags are set
        self.open(left, right)

    # *********************************************************************************************
    # MACRO ANIMATION METHODS
    # *********************************************************************************************

    def anim_confused(self):
        """Play confused animation - one shot animation of eyes shaking left and right."""
        self.confused = True
        self.confusedToggle = True # Reset toggle for a fresh animation start

    def anim_laugh(self):
        """Play laugh animation - one shot animation of eyes shaking up and down."""
        self.laugh = True
        self.laughToggle = True # Reset toggle for a fresh animation start

    # *********************************************************************************************
    # PRE-CALCULATIONS AND ACTUAL DRAWINGS
    # *********************************************************************************************

    def drawEyes(self):
        """
        Performs pre-calculations for eye sizes and animation tweening,
        applies macro animations, and then draws the eyes on the display.
        """
        # Get current time in milliseconds for timers
        current_millis = time.monotonic_ns() // 1_000_000

        #### PRE-CALCULATIONS - EYE SIZES AND VALUES FOR ANIMATION TWEENINGS ####

        # Vertical size offset for larger eyes when looking left or right (curious gaze)
        if self.curious:
            # Replicate C++ logic as closely as possible
            if self.eyeLxNext <= 10:
                self.eyeLheightOffset = 8
            # In C++: `else if (eyeLxNext >= (getScreenConstraint_X()-10) && cyclops)`
            # This condition is tricky. If in cyclops mode and eye is far right, make it curious.
            # Assuming getScreenConstraint_X() is max X for the *left* eye when there's a second eye.
            # For cyclops, the single eye spans the full "two eye" width effectively.
            elif self.eyeLxNext >= (self.screenWidth - self.eyeLwidthCurrent - 10) and self.cyclops:
                 self.eyeLheightOffset = 8
            else:
                self.eyeLheightOffset = 0 # left eye

            if not self.cyclops and self.eyeRxNext >= self.screenWidth - self.eyeRwidthCurrent - 10: # Right eye specific curious, only if not cyclops
                self.eyeRheightOffset = 8
            else:
                self.eyeRheightOffset = 0 # right eye
        else:
            self.eyeLheightOffset = 0  # reset height offset for left eye
            self.eyeRheightOffset = 0  # reset height offset for right eye

        # Left eye height tweening
        self.eyeLheightCurrent = (self.eyeLheightCurrent + self.eyeLheightNext + self.eyeLheightOffset) / 2
        # Vertical centering of eye when closing (adjusting eyeLy)
        # This calculation directly adjusts the Y coordinate, then it's used in the next tween.
        # It needs to be carefully handled to avoid double application or drift.
        # Original C++ had: eyeLy+= ((eyeLheightDefault-eyeLheightCurrent)/2); eyeLy-= eyeLheightOffset/2;
        # We'll apply this offset to the final eyeLy for drawing.
        eyeLy_offset_for_drawing_L = ((self.eyeLheightDefault - self.eyeLheightCurrent) // 2) - (self.eyeLheightOffset // 2)

        # Right eye height tweening
        self.eyeRheightCurrent = (self.eyeRheightCurrent + self.eyeRheightNext + self.eyeRheightOffset) / 2
        eyeRy_offset_for_drawing_R = ((self.eyeRheightDefault - self.eyeRheightCurrent) // 2) - (self.eyeRheightOffset // 2)

        # Open eyes again after closing them (if eye_open flag is True)
        if self.eyeL_open:
            if self.eyeLheightCurrent <= 1 + self.eyeLheightOffset:
                self.eyeLheightNext = self.eyeLheightDefault
        if self.eyeR_open:
            if self.eyeRheightCurrent <= 1 + self.eyeRheightOffset:
                self.eyeRheightNext = self.eyeRheightDefault

        # Left eye width tweening
        self.eyeLwidthCurrent = (self.eyeLwidthCurrent + self.eyeLwidthNext) / 2
        # Right eye width tweening
        self.eyeRwidthCurrent = (self.eyeRwidthCurrent + self.eyeRwidthNext) / 2

        # Space between eyes tweening
        self.spaceBetweenCurrent = (self.spaceBetweenCurrent + self.spaceBetweenNext) / 2

        # Left eye coordinates tweening
        self.eyeLx = (self.eyeLx + self.eyeLxNext) / 2
        self.eyeLy = (self.eyeLy + self.eyeLyNext) / 2 # Base Y position, adjusted by the offset for drawing

        # Right eye coordinates (dependent on left eye's position and space between)
        self.eyeRxNext = self.eyeLxNext + self.eyeLwidthCurrent + self.spaceBetweenCurrent # Right eye's x position depends on left eye's position + space
        self.eyeRyNext = self.eyeLyNext  # Right eye's y position should be the same as for the left eye
        self.eyeRx = (self.eyeRx + self.eyeRxNext) / 2
        self.eyeRy = (self.eyeRy + self.eyeRyNext) / 2 # Base Y position, adjusted by the offset for drawing

        # Left eye border radius tweening
        self.eyeLborderRadiusCurrent = (self.eyeLborderRadiusCurrent + self.eyeLborderRadiusNext) / 2
        # Right eye border radius tweening
        self.eyeRborderRadiusCurrent = (self.eyeRborderRadiusCurrent + self.eyeRborderRadiusNext) / 2

        #### APPLYING MACRO ANIMATIONS ####

        if self.autoblinker:
            if current_millis >= self.blinktimer:
                self.blink()
                self.blinktimer = current_millis + (self.blinkInterval * 1000) + \
                                  (random.randint(0, self.blinkIntervalVariation) * 1000)

        # Laughing - eyes shaking up and down
        if self.laugh:
            if self.laughToggle:
                self.setVFlicker(ON, 5) # Activate vertical flicker
                self.laughAnimationTimer = current_millis
                self.laughToggle = False
            elif current_millis >= self.laughAnimationTimer + self.laughAnimationDuration:
                self.setVFlicker(OFF, 0) # Deactivate vertical flicker
                self.laughToggle = True
                self.laugh = False

        # Confused - eyes shaking left and right
        if self.confused:
            if self.confusedToggle:
                self.setHFlicker(ON, 20) # Activate horizontal flicker
                self.confusedAnimationTimer = current_millis
                self.confusedToggle = False
            elif current_millis >= self.confusedAnimationTimer + self.confusedAnimationDuration:
                self.setHFlicker(OFF, 0) # Deactivate horizontal flicker
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

        #### ACTUAL DRAWINGS ####

        # Create a blank 1-bit PIL Image with the dimensions of the OLED display.
        image = Image.new('1', (self.screenWidth, self.screenHeight))
        # Get an ImageDraw object for the newly created image.
        draw = ImageDraw.Draw(image)

        # Clear the entire image buffer with the background color (black, 0).
        draw.rectangle((0, 0, self.screenWidth, self.screenHeight), fill=BGCOLOR)

        # Draw basic eye rectangles (pupils)
        # Ensure all drawing coordinates and dimensions are integers
        elx_draw = int(self.eyeLx)
        ely_draw = int(self.eyeLy + eyeLy_offset_for_drawing_L) # Apply calculated offset here
        elw_draw = int(self.eyeLwidthCurrent)
        elh_draw = int(self.eyeLheightCurrent)
        elr_draw = int(self.eyeLborderRadiusCurrent)

        draw.rounded_rectangle(
            (elx_draw, ely_draw, elx_draw + elw_draw, ely_draw + elh_draw),
            radius=elr_draw,
            fill=MAINCOLOR
        )

        if not self.cyclops:
            erx_draw = int(self.eyeRx)
            ery_draw = int(self.eyeRy + eyeRy_offset_for_drawing_R) # Apply calculated offset here
            erw_draw = int(self.eyeRwidthCurrent)
            erh_draw = int(self.eyeRheightCurrent)
            err_draw = int(self.eyeRborderRadiusCurrent)
            draw.rounded_rectangle(
                (erx_draw, ery_draw, erx_draw + erw_draw, ery_draw + erh_draw),
                radius=err_draw,
                fill=MAINCOLOR
            )

        # Prepare mood type transitions (logic remains the same, but ensure ints for drawing)
        self.eyelidsTiredHeight = (self.eyelidsTiredHeight + self.eyelidsTiredHeightNext) / 2
        self.eyelidsAngryHeight = (self.eyelidsAngryHeight + self.eyelidsAngryHeightNext) / 2
        self.eyelidsHappyBottomOffset = (self.eyelidsHappyBottomOffset + self.eyelidsHappyBottomOffsetNext) / 2

        # Draw tired top eyelids (triangles for a pointed look)
        # Ensure all coordinates are integers
        if self.eyelidsTiredHeight > 0:
            if not self.cyclops:
                # Left eye tired eyelid
                draw.polygon([
                    (elx_draw, ely_draw - 1),
                    (elx_draw + elw_draw, ely_draw - 1),
                    (elx_draw, ely_draw + int(self.eyelidsTiredHeight) - 1)
                ], fill=BGCOLOR)
                # Right eye tired eyelid
                draw.polygon([
                    (erx_draw, ery_draw - 1),
                    (erx_draw + erw_draw, ery_draw - 1),
                    (erx_draw + erw_draw, ery_draw + int(self.eyelidsTiredHeight) - 1)
                ], fill=BGCOLOR)
            else:
                # Cyclops tired eyelids
                draw.polygon([
                    (elx_draw, ely_draw - 1),
                    (elx_draw + (elw_draw // 2), ely_draw - 1),
                    (elx_draw, ely_draw + int(self.eyelidsTiredHeight) - 1)
                ], fill=BGCOLOR)
                draw.polygon([
                    (elx_draw + (elw_draw // 2), ely_draw - 1),
                    (elx_draw + elw_draw, ely_draw - 1),
                    (elx_draw + elw_draw, ely_draw + int(self.eyelidsTiredHeight) - 1)
                ], fill=BGCOLOR)

        # Draw angry top eyelids (triangles for a furrowed brow look)
        if self.eyelidsAngryHeight > 0:
            if not self.cyclops:
                # Left eye angry eyelid
                draw.polygon([
                    (elx_draw, ely_draw - 1),
                    (elx_draw + elw_draw, ely_draw - 1),
                    (elx_draw + elw_draw, ely_draw + int(self.eyelidsAngryHeight) - 1)
                ], fill=BGCOLOR)
                # Right eye angry eyelid
                draw.polygon([
                    (erx_draw, ery_draw - 1),
                    (erx_draw + erw_draw, ery_draw - 1),
                    (erx_draw, ery_draw + int(self.eyelidsAngryHeight) - 1)
                ], fill=BGCOLOR)
            else:
                # Cyclops angry eyelids
                draw.polygon([
                    (elx_draw, ely_draw - 1),
                    (elx_draw + (elw_draw // 2), ely_draw - 1),
                    (elx_draw + (elw_draw // 2), ely_draw + int(self.eyelidsAngryHeight) - 1)
                ], fill=BGCOLOR)
                draw.polygon([
                    (elx_draw + (elw_draw // 2), ely_draw - 1),
                    (elx_draw + elw_draw, ely_draw - 1),
                    (elx_draw + (elw_draw // 2), ely_draw + int(self.eyelidsAngryHeight) - 1)
                ], fill=BGCOLOR)

        # Draw happy bottom eyelids (rounded rectangles covering lower part)
        if self.eyelidsHappyBottomOffset > 0:
            # Left eye happy eyelid
            draw.rounded_rectangle(
                (elx_draw - 1, (ely_draw + elh_draw) - int(self.eyelidsHappyBottomOffset) + 1,
                 elx_draw + elw_draw + 2, ely_draw + self.eyeLheightDefault), # Use original eyeLheightDefault for size
                radius=elr_draw,
                fill=BGCOLOR
            )
            if not self.cyclops:
                # Right eye happy eyelid
                draw.rounded_rectangle(
                    (erx_draw - 1, (ery_draw + erh_draw) - int(self.eyelidsHappyBottomOffset) + 1,
                     erx_draw + erw_draw + 2, ery_draw + self.eyeRheightDefault), # Use original eyeRheightDefault for size
                    radius=err_draw,
                    fill=BGCOLOR
                )

        # Finally, display the prepared image on the OLED device.
        self.display.display(image)


# --- Main Loop Example ---
# This block handles the starting of the animation and ensures proper cleanup
# if the script is interrupted or finishes.
if device: # Proceed only if the display device was successfully initialized
    try:
        eyes = RoboEyes(device)
        # Initialize the eyes with screen dimensions and desired framerate
        eyes.begin(device.width, device.height, 50) # Set to 50 FPS for smooth animations

        # Set initial eye shape properties
        eyes.setWidth(36, 36)
        eyes.setHeight(36, 36)
        eyes.setBorderradius(8, 8)
        eyes.setSpacebetween(10)
        eyes.close() # Start with closed eyes as in the C++ example

        # --- Event Timer and Flags (mimicking Arduino sketch) ---
        eventTimer = time.monotonic_ns() // 1_000_000 # Start event timer (in milliseconds)
        event1wasPlayed = False
        event2wasPlayed = False
        event3wasPlayed = False

        print("RoboEyes animation sequence started. Press Ctrl+C to exit.")

        while True:
            current_millis = time.monotonic_ns() // 1_000_000 # Get current time in milliseconds

            eyes.update() # Update eyes drawings (this also handles internal animation tweening and FPS)

            # --- LOOPED ANIMATION SEQUENCE (from Arduino sketch) ---

            # Do once after 2 seconds
            if current_millis >= eventTimer + 2000 and not event1wasPlayed:
                event1wasPlayed = True
                eyes.open() # Open eyes
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
                eyes.close() # Close eyes again
                eyes.setMood(DEFAULT)
                print(f"{current_millis - eventTimer:.0f}ms: Eyes Closed, Mood DEFAULT (Resetting sequence)")
                
                # Reset the timer and the event flags to restart the whole animation sequence
                eventTimer = current_millis # reset timer to current time
                event1wasPlayed = False
                event2wasPlayed = False
                event3wasPlayed = False

            # --- END OF LOOPED ANIMATION SEQUENCE ---

            # Small delay to prevent busy-waiting and reduce CPU usage,
            # ensuring the loop doesn't hog the CPU if update() is very fast.
            time.sleep(0.001)

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt detected. Exiting animation.")
    except Exception as e:
        print(f"\nAn unexpected error occurred during animation: {e}")
    finally:
        # This 'finally' block *always* executes, whether an exception occurred or not.
        # It ensures the display is cleared on script termination.
        if device:
            device.clear() # Send the clear command to turn off all pixels
            time.sleep(0.5) # Add a small delay to give the OLED controller time to process
            print("Display cleared and resources released.")
else:
    print("OLED device was not initialized. Cannot run animation sequence.")

