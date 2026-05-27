#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

#define LED_PIN  14
#define SDA_PIN  32
#define SCL_PIN  33

Adafruit_MPU6050 mpu;

void blink(int vezes, int tempo = 80) {
  for (int i = 0; i < vezes; i++) {
    digitalWrite(LED_PIN, HIGH); delay(tempo);
    digitalWrite(LED_PIN, LOW);  delay(tempo);
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(LED_PIN, OUTPUT);

  Serial.println("================================");
  Serial.println("  SOPHIA ∞ MVP — Boot v1.0.0  ");
  Serial.println("================================");

  Wire.begin(SDA_PIN, SCL_PIN);

  Serial.print("[SENSOR] MPU6050... ");
  if (!mpu.begin()) {
    Serial.println("ERRO: nao encontrado!");
    while (true) { blink(3, 100); delay(500); }
  }

  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
  mpu.setGyroRange(MPU6050_RANGE_500_DEG);
  mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  Serial.println("OK");

  Serial.println("[SOPHIA] Sistema nervoso ativo.");
  Serial.println("[STATE]  IDLE");

  blink(3, 100);
}

void loop() {
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  float movimento = fabs(sqrt(
    a.acceleration.x * a.acceleration.x +
    a.acceleration.y * a.acceleration.y +
    a.acceleration.z * a.acceleration.z
  ) - 9.8f);

  if (movimento > 2.5f) {
    Serial.print("[EVENT]  MOVEMENT_DETECTED | intensidade: ");
    Serial.println(movimento, 2);
    blink(1, 60);
  }

  delay(100);
}
