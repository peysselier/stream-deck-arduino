#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// Pins boutons
int p2  = 2;   // Spotify
int p3  = 3;   // YouTube
int p4  = 4;   // Twitch
int p5  = 5;   // Suivant
int p6  = 6;   // Pause
int p7  = 7;   // Précédent
int p8  = 8;   // Casque 1
int p9  = 9;   // Casque 2
int p10 = 10;  // Écran
int p11 = 11;  // 2ème compte Google
int p12 = 12;  // Réservé
int p13 = 13;  // Réservé

int potPin = A0;

// États précédents
int last_b2  = 0;
int last_b3  = 0;
int last_b4  = 0;
int last_b5  = 0;
int last_b6  = 0;
int last_b7  = 0;
int last_b8  = 0;
int last_b9  = 0;
int last_b10 = 0;
int last_b11 = 0;
int last_b12 = 0;
int last_b13 = 0;

// États toggle
int toggle_b2  = 0;

int lastVolume = -1;

// Données OLED
String mediaSource = "--";
String line1 = "Stream Deck";
String line2 = "Pret";
int volumeDisplay = 0;

void setup() {
  Serial.begin(9600);

  pinMode(p2,  INPUT);
  pinMode(p3,  INPUT);
  pinMode(p4,  INPUT);
  pinMode(p5,  INPUT);
  pinMode(p6,  INPUT);
  pinMode(p7,  INPUT);
  pinMode(p8,  INPUT);
  pinMode(p9,  INPUT);
  pinMode(p10, INPUT);
  pinMode(p11, INPUT);
  pinMode(p12, INPUT);
  pinMode(p13, INPUT);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED non trouve");
    while (true);
  }
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.display();

  Serial.println("[Arduino] Pret");
}

void loop() {
  int b2  = digitalRead(p2);
  int b3  = digitalRead(p3);
  int b4  = digitalRead(p4);
  int b5  = digitalRead(p5);
  int b6  = digitalRead(p6);
  int b7  = digitalRead(p7);
  int b8  = digitalRead(p8);
  int b9  = digitalRead(p9);
  int b10 = digitalRead(p10);
  int b11 = digitalRead(p11);
  int b12 = digitalRead(p12);
  int b13 = digitalRead(p13);

  // Debug moniteur série — affiche tous les états
  Serial.print("Etats: ");
  Serial.print(b2);  Serial.print(" ");
  Serial.print(b3);  Serial.print(" ");
  Serial.print(b4);  Serial.print(" ");
  Serial.print(b5);  Serial.print(" ");
  Serial.print(b6);  Serial.print(" ");
  Serial.print(b7);  Serial.print(" ");
  Serial.print(b8);  Serial.print(" ");
  Serial.print(b9);  Serial.print(" ");
  Serial.print(b10); Serial.print(" ");
  Serial.print(b11); Serial.print(" ");
  Serial.print(b12); Serial.print(" ");
  Serial.println(b13);

  // Bouton TOGGLE : Spotify(p2)
  if (b2 == 1 && last_b2 == 0) {
    toggle_b2 = 1 - toggle_b2;
    Serial.print("BTN:0:"); Serial.println(toggle_b2);
  }

  // Boutons MOMENTANÉS
  if (b3  == 1 && last_b3  == 0) { Serial.println("BTN:1:1"); }
  if (b4  == 1 && last_b4  == 0) { Serial.println("BTN:2:1"); }
  if (b5  == 1 && last_b5  == 0) { Serial.println("BTN:3:1"); }
  if (b6  == 1 && last_b6  == 0) { Serial.println("BTN:4:1"); }
  if (b7  == 1 && last_b7  == 0) { Serial.println("BTN:5:1"); }
  if (b8  == 1 && last_b8  == 0) { Serial.println("BTN:6:1"); }
  if (b9  == 1 && last_b9  == 0) { Serial.println("BTN:7:1"); }
  if (b10 == 1 && last_b10 == 0) { Serial.println("BTN:8:1"); }
  if (b11 == 1 && last_b11 == 0) { Serial.println("BTN:9:1"); }
  if (b12 == 1 && last_b12 == 0) { Serial.println("BTN:10:1"); }
  if (b13 == 1 && last_b13 == 0) { Serial.println("BTN:11:1"); }

  // Potentiomètre
  int raw = analogRead(potPin);
  int volume = map(raw, 0, 1023, 0, 100);
  if (abs(volume - lastVolume) > 1) {
    lastVolume = volume;
    Serial.print("VOL:"); Serial.println(volume);
  }

  // Mise à jour états précédents
  last_b2  = b2;
  last_b3  = b3;
  last_b4  = b4;
  last_b5  = b5;
  last_b6  = b6;
  last_b7  = b7;
  last_b8  = b8;
  last_b9  = b9;
  last_b10 = b10;
  last_b11 = b11;
  last_b12 = b12;
  last_b13 = b13;

  // Réception données PC
  while (Serial.available()) {
    String msg = Serial.readStringUntil('\n');
    msg.trim();
    if (msg.startsWith("SRC:"))       mediaSource   = msg.substring(4);
    else if (msg.startsWith("L1:"))   line1         = msg.substring(3);
    else if (msg.startsWith("L2:"))   line2         = msg.substring(3);
    else if (msg.startsWith("SVOL:")) volumeDisplay = msg.substring(5).toInt();
  }

  // OLED
  display.clearDisplay();
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print("VOL:"); display.print(volumeDisplay); display.print("% ["); display.print(mediaSource); display.print("]");
  int barWidth = map(volumeDisplay, 0, 100, 0, 128);
  display.fillRect(0, 10, barWidth, 4, SSD1306_WHITE);
  display.drawRect(0, 10, 128, 4, SSD1306_WHITE);
  display.setCursor(0, 20);
  if (line1.length() > 21) display.print(line1.substring(0, 21));
  else display.print(line1);
  display.setCursor(0, 35);
  if (line2.length() > 21) display.print(line2.substring(0, 21));
  else display.print(line2);
  display.setCursor(0, 52);
  display.print("SP:"); display.print(toggle_b2);
  display.display();

  delay(10);
}