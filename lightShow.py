from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app)

DEVELOPMENT_MODE = True

if not DEVELOPMENT_MODE:
    import RPi.GPIO as GPIO
    relay_pins = [17, 27, 22, 23]  # GPIO pins for 4 lights
    GPIO.setmode(GPIO.BCM)
    for pin in relay_pins:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
else:
    print("Development mode enabled.")

light_states = [False, False, False, False]
current_behavior = "default"
behavior_thread = None
minimum_on_time = 2  # Default minimum ON time (seconds)


def stop_current_behavior():
    """Stop any ongoing behavior."""
    global current_behavior, behavior_thread
    current_behavior = "default"
    if behavior_thread and behavior_thread.is_alive():
        behavior_thread.join()


def set_light(index, state):
    """Set the state of a specific light."""
    light_states[index] = state
    if not DEVELOPMENT_MODE:
        GPIO.output(relay_pins[index], GPIO.HIGH if state else GPIO.LOW)
    else:
        print(f"Light {index + 1} {'ON' if state else 'OFF'}")
    socketio.emit("update_light_states", light_states)


def marquee_behavior():
    """Marquee behavior: Lights turn ON and OFF sequentially, respecting minimum ON time."""
    while current_behavior == "marquee":
        for i in range(4):
            set_light(i, True)  # Turn the light ON
            time.sleep(minimum_on_time)  # Wait for the minimum ON time
            set_light(i, False)  # Turn the light OFF


def alternating_behavior():
    """Alternating behavior: Lights alternate between odd and even, respecting minimum ON time."""
    while current_behavior == "alternating":
        for i in range(4):
            set_light(i, i % 2 == 0)  # Set odd/even lights
        time.sleep(minimum_on_time)
        for i in range(4):
            set_light(i, i % 2 != 0)  # Toggle the other set of lights
        time.sleep(minimum_on_time)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/control-light", methods=["POST"])
def control_light():
    """Manually toggle an individual light."""
    stop_current_behavior()
    data = request.json
    light = int(data["light"]) - 1
    set_light(light, data["action"] == "on")
    return jsonify(light_states)


@app.route("/turn-all-lights", methods=["POST"])
def turn_all_lights():
    """Turn all lights ON or OFF and reset to default behavior."""
    stop_current_behavior()
    data = request.json
    for i in range(4):
        set_light(i, data["action"] == "on")
    return jsonify(light_states)


@app.route("/set-behavior", methods=["POST"])
def set_behavior():
    """Set a specific light behavior."""
    global current_behavior, behavior_thread
    stop_current_behavior()
    data = request.json
    behavior = data["behavior"]
    current_behavior = behavior

    if behavior == "marquee":
        behavior_thread = threading.Thread(target=marquee_behavior)
        behavior_thread.start()
    elif behavior == "alternating":
        behavior_thread = threading.Thread(target=alternating_behavior)
        behavior_thread.start()

    return f"Behavior set to {behavior}"


@app.route("/set-minimum-on-time", methods=["POST"])
def set_minimum_on_time():
    """Update the minimum ON time for the lights."""
    global minimum_on_time
    data = request.json
    minimum_on_time = max(0, data["time"])  # Ensure the time is non-negative
    print(f"Updated minimum ON time: {minimum_on_time}s")
    return jsonify({"minimum_on_time": minimum_on_time})


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
