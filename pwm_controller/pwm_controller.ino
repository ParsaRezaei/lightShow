#include <Arduino.h>

// Define PWM parameters
const int pwmPins[] = {0, 1, 2, 3};       // GPIO pins for PWM channels
const int pwmFrequency = 5000;            // Frequency (5 kHz)
const int pwmResolution = 8;              // 8-bit resolution (0-255)

// Current duty cycle values
int dutyCycle[] = {0, 0, 0, 0};  // Start all outputs with 0 duty cycle

// Current sensor parameters
const int currentSensorPin = 4;           // GPIO pin for ACS712 output
const float sensitivity = 0.066;          // Sensitivity of ACS712-30A in V/A (66mV/A)
const float vcc = 3.3;                    // Operating voltage of ESP32
const int adcResolution = 4096;           // ADC resolution (12-bit)

// Function to calculate current
float readCurrent() {
  int rawValue = analogRead(currentSensorPin);  // Read ADC value
  float voltage = (rawValue * vcc) / adcResolution; // Convert to voltage
  float current = (voltage - (vcc / 2)) / sensitivity; // Calculate current
  return current;  // Return current in Amps
}

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
    parseCommand(command);                          // Parse and apply command
  }

  // Read and display current from the sensor
  float current = readCurrent();
  Serial.printf("Measured Current: %.2f A\n", current);
  delay(500);  // Add a delay to prevent spamming the serial monitor
}

void parseCommand(String command) {
  // Parse commands like "L1:128,L2:64,L3:0,L4:255"
  int start = 0;
  int maxDutyCycle = (1 << pwmResolution) - 1;  // Calculate maximum duty cycle based on resolution

  while (start < command.length()) {
    // Find next colon and comma
    int colonIndex = command.indexOf(':', start);
    int commaIndex = command.indexOf(',', colonIndex);

    // Parse light number and duty cycle
    if (colonIndex > start) {
      int lightIndex = command.substring(start + 1, colonIndex).toInt() - 1;
      int duty = command.substring(colonIndex + 1, (commaIndex > 0 ? commaIndex : command.length())).toInt();

      // Validate light index and duty cycle
      if (lightIndex >= 0 && lightIndex < 4) {
        // Ensure duty cycle stays within valid range
        duty = constrain(duty, 0, maxDutyCycle);
        dutyCycle[lightIndex] = duty;                    // Update duty cycle array
        ledcWrite(pwmPins[lightIndex], duty);            // Apply duty cycle
        Serial.printf("Updated Light %d to Duty Cycle %d\n", lightIndex + 1, duty);
      } else {
        Serial.println("Error: Invalid light number");
      }
    }

    // Move to the next command in the string
    start = (commaIndex > 0) ? commaIndex + 1 : command.length();
  }
}
