import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
import serial

app = Flask(__name__)
socketio = SocketIO(app)

# DEVELOPMENT_MODE disables hardware control
DEVELOPMENT_MODE = False

if not DEVELOPMENT_MODE:
    # Initialize serial connection
    serial_port = '/dev/serial0'  # Replace with your ESP32 serial port
    serial_baud_rate = 115200
    serial_connection = serial.Serial(serial_port, serial_baud_rate, timeout=1, write_timeout=2)
    print(f"Connected to ESP32 on {serial_port}")
else:
    print("Development mode enabled.")

# Global variables
light_states = [0, 0, 0, 0]  # PWM duty cycles (0-255 for each light)
previous_light_states = [0, 0, 0, 0]  # Track last known light states
current_behavior = "default"
behavior_thread = None
minimum_on_time = 2.0  # Default minimum ON time (seconds at 100% speed)
speed_adjustment = 0  # Speed adjustment percentage (-100% to +100%)
minimum_pwm = 0  # Default minimum PWM
maximum_pwm = 255  # Default maximum PWM
all_lights_on = False  # Flag to track if 'All Lights On' is set

def stop_current_behavior():
    """Stop any ongoing behavior."""
    global current_behavior, behavior_thread, light_states, all_lights_on
    if current_behavior != "default":
        current_behavior = "default"
        if behavior_thread and behavior_thread.is_alive():
            behavior_thread.join()
        # Restore lights based on 'all_lights_on' flag
        if all_lights_on:
            # Turn all lights on
            for i in range(4):
                light_states[i] = 255
        else:
            # Turn all lights off
            for i in range(4):
                light_states[i] = 0
        update_light_states()
        socketio.emit("update_light_states", light_states)

def calculate_adjusted_duration():
    """Calculate the adjusted duration based on the speed adjustment."""
    global minimum_on_time, speed_adjustment
    # Adjusted duration inversely proportional to speed adjustment
    adjusted_duration = minimum_on_time / (1 + (speed_adjustment / 100))
    return max(0.1, adjusted_duration)  # Ensure duration is not too short

def update_light_states():
    """Send updates for lights only if their state has changed."""
    global light_states, previous_light_states, serial_connection

    changes_detected = False
    for i in range(4):
        if light_states[i] != previous_light_states[i]:
            changes_detected = True
            previous_light_states[i] = light_states[i]

    if changes_detected and not DEVELOPMENT_MODE:
        try:
            # Construct and send the PWM command
            command = ",".join([f"L{i + 1}:{duty}" for i, duty in enumerate(light_states)])
            serial_connection.write((command + "\n").encode('utf-8'))
            print(f"Updated lights: {command}")
        except Exception as e:
            print(f"Error updating light states: {e}")

def set_light(index, duty_cycle):
    """Set the PWM value (duty cycle) of a specific light."""
    global light_states
    if current_behavior == "default":
        light_states[index] = duty_cycle
        update_light_states()  # Check for changes and update if needed
        socketio.emit("update_light_states", light_states)
    else:
        # Behavior is active, do not update light_states directly
        pass  # The behavior controls light_states during the behavior

def fade_light(index, start_value, end_value, duration):
    """Gradually change the PWM value of a light from start_value to end_value."""
    max_update_rate = 20  # Maximum updates per second
    total_steps = max(1, int(duration * max_update_rate))
    steps = min(50, total_steps)  # Limit to a maximum of 50 steps for smooth fading
    step_duration = duration / steps
    delta = (end_value - start_value) / steps

    for step in range(steps + 1):  # Include the final value
        current_value = int(start_value + delta * step)
        light_states[index] = current_value  # Update light_states directly
        update_light_states()
        socketio.emit("update_light_states", light_states)
        time.sleep(step_duration)

def marquee_behavior():
    """Marquee behavior: Lights fade in and out sequentially with overlap."""
    overlap_ratio = 0.75  # Overlap starts when the current light reaches 75% of its duration
    while current_behavior == "marquee":
        for i in range(4):
            next_index = (i + 1) % 4  # Wrap around to the first light
            total_duration = calculate_adjusted_duration()
            fade_out_duration = total_duration
            fade_in_delay = total_duration * overlap_ratio
            fade_in_duration = total_duration - fade_in_delay

            start_time = time.time()
            elapsed_time = 0

            while elapsed_time < total_duration and current_behavior == "marquee":
                elapsed_time = time.time() - start_time
                # Fade out current light
                fade_out_progress = min(elapsed_time / fade_out_duration, 1.0)
                current_brightness = int(maximum_pwm - fade_out_progress * (maximum_pwm - minimum_pwm))
                light_states[i] = current_brightness

                # Fade in next light after delay
                if elapsed_time >= fade_in_delay:
                    fade_in_progress = min((elapsed_time - fade_in_delay) / fade_in_duration, 1.0)
                    next_brightness = int(minimum_pwm + fade_in_progress * (maximum_pwm - minimum_pwm))
                    light_states[next_index] = next_brightness

                update_light_states()
                socketio.emit("update_light_states", light_states)
                time.sleep(0.05)  # Sleep for 50ms to control update rate

def alternating_behavior():
    """Alternating behavior: Fade odd and even lights in alternation."""
    while current_behavior == "alternating":
        total_duration = calculate_adjusted_duration()

        # Fade in odd lights, fade out even lights
        start_time = time.time()
        elapsed_time = 0

        while elapsed_time < total_duration and current_behavior == "alternating":
            elapsed_time = time.time() - start_time
            progress = min(elapsed_time / total_duration, 1.0)

            for i in range(4):
                if i % 2 == 0:
                    # Even lights fade out
                    brightness = int(maximum_pwm - progress * (maximum_pwm - minimum_pwm))
                else:
                    # Odd lights fade in
                    brightness = int(minimum_pwm + progress * (maximum_pwm - minimum_pwm))
                light_states[i] = brightness

            update_light_states()
            socketio.emit("update_light_states", light_states)
            time.sleep(0.05)  # Sleep for 50ms

        # Fade in even lights, fade out odd lights
        start_time = time.time()
        elapsed_time = 0

        while elapsed_time < total_duration and current_behavior == "alternating":
            elapsed_time = time.time() - start_time
            progress = min(elapsed_time / total_duration, 1.0)

            for i in range(4):
                if i % 2 == 0:
                    # Even lights fade in
                    brightness = int(minimum_pwm + progress * (maximum_pwm - minimum_pwm))
                else:
                    # Odd lights fade out
                    brightness = int(maximum_pwm - progress * (maximum_pwm - minimum_pwm))
                light_states[i] = brightness

            update_light_states()
            socketio.emit("update_light_states", light_states)
            time.sleep(0.05)  # Sleep for 50ms

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/control-light", methods=["POST"])
def control_light():
    """Manually set an individual light's PWM duty cycle."""
    data = request.json
    light = int(data["light"]) - 1
    duty_cycle = max(0, min(255, int(data["duty_cycle"])))  # Clamp to 0-255
    # Individual light adjustment does not affect 'all_lights_on' flag
    set_light(light, duty_cycle)
    return jsonify(light_states)

@app.route("/turn-all-lights", methods=["POST"])
def turn_all_lights():
    """Set all lights to the same PWM duty cycle."""
    global all_lights_on
    data = request.json
    duty_cycle = max(0, min(255, int(data["duty_cycle"])))  # Clamp to 0-255
    if duty_cycle == 255:
        all_lights_on = True
    else:
        all_lights_on = False
    if current_behavior == "default":
        for i in range(4):
            light_states[i] = duty_cycle
        update_light_states()
        socketio.emit("update_light_states", light_states)
    else:
        # Behavior is active, do not change light_states now
        pass
    return jsonify(light_states)

@app.route("/set-behavior", methods=["POST"])
def set_behavior():
    """Set a specific light behavior."""
    global current_behavior, behavior_thread
    data = request.json
    behavior = data["behavior"]

    if behavior == current_behavior:
        return f"Behavior already set to {behavior}"

    if behavior in ["marquee", "alternating"]:
        # Stop current behavior
        stop_current_behavior()
        # Before starting the new behavior, turn all lights off
        for i in range(4):
            light_states[i] = 0
        update_light_states()
        socketio.emit("update_light_states", light_states)
        # Start the new behavior
        current_behavior = behavior
        if behavior == "marquee":
            behavior_thread = threading.Thread(target=marquee_behavior)
            behavior_thread.start()
        elif behavior == "alternating":
            behavior_thread = threading.Thread(target=alternating_behavior)
            behavior_thread.start()
    else:
        # Behavior is 'default' or unrecognized
        stop_current_behavior()

    return f"Behavior set to {behavior}"

@app.route("/set-speed", methods=["POST"])
def set_speed():
    """Update the speed adjustment percentage."""
    global speed_adjustment
    data = request.json
    speed_adjustment = max(-100, min(100, int(data["speed"])))  # Clamp to -100% to +100%
    print(f"Updated speed adjustment: {speed_adjustment}%")
    return jsonify({"speed": speed_adjustment})

@app.route("/set-minimum-on-time", methods=["POST"])
def set_minimum_on_time():
    """Update the minimum on time for the behaviors."""
    global minimum_on_time
    data = request.json
    minimum_on_time = max(0.1, float(data["minimum_on_time"]))  # Ensure it's at least 0.1 seconds
    print(f"Updated minimum on time: {minimum_on_time}s")
    return jsonify({"minimum_on_time": minimum_on_time})

@socketio.on('connect')
def handle_connect():
    # Send initial settings to the client
    emit('initial_settings', {
        'speed_adjustment': speed_adjustment,
        'minimum_on_time': minimum_on_time,
        'light_states': light_states  # Send current light states
    })

if __name__ == "__main__":
    try:
        # Run the Flask-SocketIO app
        socketio.run(app, host="0.0.0.0", port=80)
    except Exception as e:
        print(f"Error: {e}")
        if not DEVELOPMENT_MODE and serial_connection:
            serial_connection.close()
