#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <DHT.h>
#include <Adafruit_BMP085.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <time.h>

// WIFI
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";

// MQTT / NODE-RED
const char* MQTT_SERVER = "hivemq.example.com";
const int MQTT_PORT = 8883;
const char* MQTT_USER = "seu_usuario";
const char* MQTT_PASSWORD = "sua_senha";

// PINOS ESP32
#define PIN_DHT 4
#define PIN_LDR 34

#define PIN_LED_VERMELHO 26
#define PIN_LED_VERDE 25

#define PIN_SDA 21
#define PIN_SCL 22


// DHT22
#define DHT_TYPE DHT22
DHT dht(PIN_DHT, DHT_TYPE);

// BMP180
Adafruit_BMP085 bmp;

// OLED
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1



Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

//MQTT
WiFiClientSecure espClient;
PubSubClient mqtt(espClient);


// CONTROLE
unsigned long lastSend = 0;
const unsigned long SEND_INTERVAL = 5000;

bool sistemaOk = false;
String ultimoErro = "";

// TOPICOS MQTT
const char* TOPIC_DHT_TEMP = "estufa/dht22/temperatura";
const char* TOPIC_DHT_UMID = "estufa/dht22/umidade";

const char* TOPIC_LDR = "estufa/ldr/luminosidade";

const char* TOPIC_BMP_TEMP = "estufa/bmp180/temperatura";
const char* TOPIC_BMP_PRESSAO = "estufa/bmp180/pressao";
const char* TOPIC_BMP_ALTITUDE = "estufa/bmp180/altitude";

const char* TOPIC_STATUS = "estufa/status";
const char* TOPIC_ERRO = "estufa/erro";

// FUNCOES


void atualizarDisplay();

void erroSistema(String erro) {

  pinMode(PIN_LED_VERDE, OUTPUT);
  pinMode(PIN_LED_VERMELHO, OUTPUT);

  sistemaOk = false;
  ultimoErro = erro;

  digitalWrite(PIN_LED_VERDE, LOW);
  digitalWrite(PIN_LED_VERMELHO, HIGH);

  Serial.println("ERRO: " + erro);

  if (mqtt.connected()) {
    mqtt.publish(TOPIC_STATUS, "erro");
    mqtt.publish(TOPIC_ERRO, erro.c_str());
  }

  atualizarDisplay();
}

void sistemaOnline() {

  pinMode(PIN_LED_VERDE, OUTPUT);
  pinMode(PIN_LED_VERMELHO, OUTPUT);

  sistemaOk = true;
  ultimoErro = "";

  digitalWrite(PIN_LED_VERDE, HIGH);
  digitalWrite(PIN_LED_VERMELHO, LOW);

  if (mqtt.connected()) {
    mqtt.publish(TOPIC_STATUS, "online");
    mqtt.publish(TOPIC_ERRO, "nenhum");
  }

  atualizarDisplay();
}

//led



String pegarHora() {
  struct tm timeinfo;

  if (!getLocalTime(&timeinfo)) {
    return "--:--:--";
  }

  char buffer[16];
  strftime(buffer, sizeof(buffer), "%H:%M:%S", &timeinfo);

  return String(buffer);
}

void atualizarDisplay() {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);

  display.setCursor(0, 0);
  display.println("Estufa Inteligente");

  display.setCursor(0, 12);
  display.print("Sistema: ");
  display.println(sistemaOk ? "ONLINE" : "ERRO");

  display.setCursor(0, 24);
  display.print("WiFi: ");
  display.println(WiFi.status() == WL_CONNECTED ? "OK" : "OFF");

  display.setCursor(0, 34);
  display.print("MQTT: ");
  display.println(mqtt.connected() ? "OK" : "OFF");

  display.setCursor(0, 44);
  display.print("Hora: ");
  display.println(pegarHora());

  if (ultimoErro != "") {
    display.setCursor(0, 54);
    display.print("Erro: ");
    display.println(ultimoErro.substring(0, 14));
  }

  display.display();
}

bool conectarWiFi() {


  Serial.println("Conectando ao WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int tentativas = 0;

  while (WiFi.status() != WL_CONNECTED && tentativas < 20) {
    delay(500);
    Serial.print(".");
    tentativas++;
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("WiFi conectado. IP: ");
    Serial.println(WiFi.localIP());
    return true;
  }

  return false;
}


bool conectarMQTT() {
  Serial.println("Conectando ao MQTT...");

  String clientId = "estufa_esp32_" + String(random(0xffff), HEX);

  if (mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASSWORD)) {
    Serial.println("MQTT conectado");
    mqtt.publish(TOPIC_STATUS, "online");
    return true;
  }

  Serial.print("Falha MQTT. Codigo: ");
  Serial.println(mqtt.state());

  return false;
}

void configurarHora() {
  configTime(-3 * 3600, 0, "pool.ntp.org", "time.nist.gov");
}

void publicarFloat(const char* topico, float valor) {
  char payload[20];
  dtostrf(valor, 1, 2, payload);
  mqtt.publish(topico, payload);
}

void lerSensoresEEnviar() {
  float dhtTemperatura = dht.readTemperature();
  float dhtUmidade = dht.readHumidity();

  if (isnan(dhtTemperatura) || isnan(dhtUmidade)) {
    erroSistema("Falha DHT22");
    return;
  }

  int luminosidade = analogRead(PIN_LDR);

  float bmpTemperatura = bmp.readTemperature();
  float bmpPressao = bmp.readPressure() / 100.0; // hPa
  float bmpAltitude = bmp.readAltitude(101325);

  publicarFloat(TOPIC_DHT_TEMP, dhtTemperatura);
  publicarFloat(TOPIC_DHT_UMID, dhtUmidade);

  mqtt.publish(TOPIC_LDR, String(luminosidade).c_str());

  publicarFloat(TOPIC_BMP_TEMP, bmpTemperatura);
  publicarFloat(TOPIC_BMP_PRESSAO, bmpPressao);
  publicarFloat(TOPIC_BMP_ALTITUDE, bmpAltitude);

  mqtt.publish(TOPIC_STATUS, "online");

  Serial.println("Dados enviados:");
  Serial.println("DHT22 Temperatura: " + String(dhtTemperatura) + " C");
  Serial.println("DHT22 Umidade: " + String(dhtUmidade) + " %");
  Serial.println("LDR Luminosidade: " + String(luminosidade));
  Serial.println("BMP180 Temperatura: " + String(bmpTemperatura) + " C");
  Serial.println("BMP180 Pressao: " + String(bmpPressao) + " hPa");
  Serial.println("BMP180 Altitude: " + String(bmpAltitude) + " m");

  sistemaOnline();
}

// OLED

void setup() {


  Serial.begin(115200);

  pinMode(PIN_LED_VERDE, OUTPUT);
  pinMode(PIN_LED_VERMELHO, OUTPUT);

  digitalWrite(PIN_LED_VERDE, LOW);
  digitalWrite(PIN_LED_VERMELHO, HIGH);

  Wire.begin(PIN_SDA, PIN_SCL);

  espClient.setInsecure(); // Demonstração: não valida o certificado do broker.
  mqtt.setServer(MQTT_SERVER, MQTT_PORT);
  mqtt.setSocketTimeout(15);

  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("Falha ao iniciar OLED");
  } else {
    display.clearDisplay();
    display.setTextColor(SSD1306_WHITE);
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.println("Iniciando estufa...");
    display.display();
  }

  dht.begin();

  if (!bmp.begin()) {
    erroSistema("Falha BMP180");
    digitalWrite(PIN_LED_VERDE, LOW);
    digitalWrite(PIN_LED_VERMELHO, HIGH);
    return;
  }

  if (!conectarWiFi()) {
    erroSistema("Falha WiFi");
    digitalWrite(PIN_LED_VERDE, LOW);
    digitalWrite(PIN_LED_VERMELHO, HIGH);
    return;
  }

  configurarHora();

  if (!conectarMQTT()) {
    erroSistema("Falha MQTT");
    digitalWrite(PIN_LED_VERDE, LOW);
    digitalWrite(PIN_LED_VERMELHO, HIGH);
    return;
  }

  sistemaOnline();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    erroSistema("WiFi caiu");
    digitalWrite(PIN_LED_VERDE, LOW);
    digitalWrite(PIN_LED_VERMELHO, HIGH);
    delay(3000);

    if (!conectarWiFi()) {
      return;
    }
  }

  if (!mqtt.connected()) {
    erroSistema("MQTT caiu");
    digitalWrite(PIN_LED_VERDE, LOW);
    digitalWrite(PIN_LED_VERMELHO, HIGH);
    delay(3000);

    if (!conectarMQTT()) {
      return;
    }

    sistemaOnline();
  }

  mqtt.loop();

  unsigned long agora = millis();

  if (agora - lastSend >= SEND_INTERVAL) {
    lastSend = agora;
    lerSensoresEEnviar();
    atualizarDisplay();
  }
}
