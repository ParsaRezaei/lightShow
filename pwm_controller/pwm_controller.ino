#include <Arduino.h>

// Define PWM parameters
const int pwmPins[] = {3, 4, 5, 6};  // GPIO pins for PWM channels
const int pwmFrequency = 5000;       // Frequency (5 kHz)
const int pwmResolution = 8;         // 8-bit resolution (0-255)

// Current duty cycle values
int dutyCycle[] = {0, 0, 0, 0};  // Start all lights with 0 duty cycle

void setup() {
  Serial.begin(115200);  // Initialize serial communication
  Serial.println("Starting PWM Controller...");

  // Initialize PWM for each pin
  for (int i = 0; i < 4; i++) {
    ledcAttach(pwmPins[i], pwmFrequency, pwmResolution);  // Attach pin to PWM
    ledcWrite(pwmPins[i], dutyCycle[i]);                  // Set initial duty cycle
    Serial.printf("PWM initialized on GPIO %d with duty cycle %d\n", pwmPins[i], dutyCycle[i]);
  }
}

void loop() {
  // Listen for incoming serial commands
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');  // Read incoming command
    command.trim();                                 // Remove whitespace
    parseCommand(command);                         // Parse and apply command
  }
}

void parseCommand(String command) {
  // Parse commands like "L1:128,L2:64,L3:0,L4:255"
  int start = 0;

  while (start < command.length()) {
    // Find next colon and comma
    int colonIndex = command.indexOf(':', start);
    int commaIndex = command.indexOf(',', colonIndex);

    // Parse light number and duty cycle
    if (colonIndex > start) {
      int lightIndex = command.substring(start + 1, colonIndex).toInt() - 1;
      int duty = command.substring(colonIndex + 1, (commaIndex > 0 ? commaIndex : command.length())).toInt();

      // Validate light index and duty cycle
      if (lightIndex >= 0 && lightIndex < 4 && duty >= 0 && duty <= 255) {
        dutyCycle[lightIndex] = duty;  // Update duty cycle array
        ledcWrite(pwmPins[lightIndex], duty);  // Apply duty cycle
        Serial.printf("Updated Light %d to Duty Cycle %d\n", lightIndex + 1, duty);
      } else {
        Serial.println("Error: Invalid light number or duty cycle");
      }
    }

    // Move to the next command in the string
    start = (commaIndex > 0) ? commaIndex + 1 : command.length();
  }
}
