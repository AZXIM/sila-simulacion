#include <Servo.h>
#include <OneWire.h>
#include <DallasTemperature.h>

const uint8_t PIN_ESC      = 9;
const uint8_t PIN_HALL     = 2;
const uint8_t PIN_TEMP     = 3;
const uint8_t PIN_INICIO   = 4;
const uint8_t PIN_EMERG    = 5;
const uint8_t PIN_RELE     = 7;
const uint8_t PIN_ZUMBADOR = 8;
const uint8_t PIN_LED      = 13;
const uint8_t PIN_POT      = A0;
const uint8_t PIN_CORR     = A1;

const int   ESC_MIN_US       = 1000;
const int   ESC_MAX_US       = 2000;
const float RPM_OBJETIVO     = 2500.0;
const float RPM_TOLERANCIA   = 100.0;
const float I_ATASCO_A       = 85.0;
const float RPM_ATASCO       = 1500.0;
const unsigned long T_ATASCO_MS = 1500;
const float T_MAX_C          = 60.0;
const unsigned long T_SESION_MS = 20UL * 60UL * 1000UL;
const unsigned long T_RAMPA_MS  = 4000;
const uint8_t MAX_REINTENTOS = 3;

const float Q_NOMINAL_LS = 5.0;
const float RHO_MEZCLA   = 1025.0;
const float CW_ALGAS     = 0.06;

const float KP = 0.08;
const float KI = 0.02;

enum Estado { REPOSO, ARMANDO, RAMPA, OPERANDO, ATASCO, FIN_SESION, FALLA };
Estado estado = REPOSO;

Servo esc;
OneWire oneWire(PIN_TEMP);
DallasTemperature sensorTemp(&oneWire);
bool hayTemp = false;

volatile unsigned long pulsosHall = 0;
float rpm = 0, corriente = 0, temperatura = NAN;
float acelUs = ESC_MIN_US, errorPrevio = 0;
bool nuevaMedida = false;
float kgExtraidos = 0;
uint8_t reintentos = 0;
unsigned long tEstado = 0, tSesion = 0, tSobrecarga = 0, tUltimoLog = 0, tUltimaMedida = 0;
float offsetCorriente = 2.5;

void contarPulso() { pulsosHall++; }

void cambiarEstado(Estado nuevo) {
  estado = nuevo;
  tEstado = millis();
}

void escribirEsc(float us) {
  int tope = map(analogRead(PIN_POT), 0, 1023, ESC_MIN_US + 200, ESC_MAX_US);
  acelUs = constrain(us, ESC_MIN_US, tope);
  esc.writeMicroseconds((int)acelUs);
}

void pitar(uint8_t veces) {
  for (uint8_t i = 0; i < veces; i++) {
    digitalWrite(PIN_ZUMBADOR, HIGH); delay(120);
    digitalWrite(PIN_ZUMBADOR, LOW);  delay(120);
  }
}

float leerCorriente() {
  long suma = 0;
  for (uint8_t i = 0; i < 16; i++) suma += analogRead(PIN_CORR);
  float v = (suma / 16.0) * 5.0 / 1023.0;
  return (v - offsetCorriente) / 0.040;
}

void medir() {
  unsigned long ahora = millis();
  unsigned long dt = ahora - tUltimaMedida;
  nuevaMedida = false;
  if (dt < 250) return;
  noInterrupts();
  unsigned long p = pulsosHall;
  pulsosHall = 0;
  interrupts();
  rpm = p * 60000.0 / dt;
  corriente = leerCorriente();
  if (hayTemp) {
    temperatura = sensorTemp.getTempCByIndex(0);
    sensorTemp.requestTemperatures();
  }
  if (estado == OPERANDO || estado == RAMPA) {
    float q = Q_NOMINAL_LS * (rpm / RPM_OBJETIVO);
    kgExtraidos += (q / 1000.0) * (dt / 1000.0) * RHO_MEZCLA * CW_ALGAS;
  }
  tUltimaMedida = ahora;
  nuevaMedida = true;
}

void parar(Estado destino) {
  escribirEsc(ESC_MIN_US);
  errorPrevio = 0;
  cambiarEstado(destino);
}

void registrar() {
  if (millis() - tUltimoLog < 1000) return;
  tUltimoLog = millis();
  const char* nombres[] = {"REPOSO", "ARMANDO", "RAMPA", "OPERANDO", "ATASCO", "FIN", "FALLA"};
  Serial.print((millis() - tSesion) / 1000.0, 0); Serial.print(',');
  Serial.print(nombres[estado]);                   Serial.print(',');
  Serial.print(acelUs, 0);                         Serial.print(',');
  Serial.print(rpm, 0);                            Serial.print(',');
  Serial.print(corriente, 1);                      Serial.print(',');
  if (hayTemp) Serial.print(temperatura, 1); else Serial.print("NA");
  Serial.print(',');
  Serial.print(kgExtraidos, 1);                    Serial.print(',');
  Serial.println(reintentos);
}

bool protecciones() {
  if (digitalRead(PIN_EMERG) == HIGH) {
    digitalWrite(PIN_RELE, LOW);
    parar(FALLA);
    Serial.println(F("# PARADA DE EMERGENCIA"));
    return true;
  }
  if (hayTemp && temperatura > T_MAX_C) {
    parar(FALLA);
    Serial.println(F("# SOBRETEMPERATURA EN REDUCTORA"));
    pitar(5);
    return true;
  }
  return false;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_HALL, INPUT_PULLUP);
  pinMode(PIN_INICIO, INPUT_PULLUP);
  pinMode(PIN_EMERG, INPUT_PULLUP);
  pinMode(PIN_RELE, OUTPUT);
  pinMode(PIN_ZUMBADOR, OUTPUT);
  pinMode(PIN_LED, OUTPUT);
  attachInterrupt(digitalPinToInterrupt(PIN_HALL), contarPulso, FALLING);

  esc.attach(PIN_ESC, ESC_MIN_US, ESC_MAX_US);
  esc.writeMicroseconds(ESC_MIN_US);

  sensorTemp.begin();
  hayTemp = sensorTemp.getDeviceCount() > 0;
  if (hayTemp) {
    sensorTemp.setWaitForConversion(false);
    sensorTemp.requestTemperatures();
  } else {
    Serial.println(F("# AVISO: sin sensor de temperatura -> acelerador limitado al 60%"));
  }

  long suma = 0;
  for (int i = 0; i < 200; i++) { suma += analogRead(PIN_CORR); delay(2); }
  offsetCorriente = (suma / 200.0) * 5.0 / 1023.0;

  Serial.println(F("t_s,estado,acel_us,rpm,corriente_A,temp_C,kg_estimados,reintentos"));
  pitar(1);
}

void loop() {
  medir();
  registrar();
  digitalWrite(PIN_LED, estado == OPERANDO ? HIGH : (millis() / 300) % 2);

  if (estado != REPOSO && estado != FIN_SESION && estado != FALLA && protecciones()) return;

  switch (estado) {
    case REPOSO:
      if (digitalRead(PIN_INICIO) == LOW && digitalRead(PIN_EMERG) == LOW &&
          millis() - tEstado > 1000) {
        digitalWrite(PIN_RELE, HIGH);
        kgExtraidos = 0;
        reintentos = 0;
        tSesion = millis();
        cambiarEstado(ARMANDO);
      }
      break;

    case ARMANDO:
      escribirEsc(ESC_MIN_US);
      if (millis() - tEstado > 3000) { pitar(2); cambiarEstado(RAMPA); }
      break;

    case RAMPA: {
      float f = (millis() - tEstado) / (float)T_RAMPA_MS;
      if (f > 1.0f) f = 1.0f;
      float objetivo = hayTemp ? 1600 : 1450;
      escribirEsc(ESC_MIN_US + f * (objetivo - ESC_MIN_US));
      if (f >= 1.0f) cambiarEstado(OPERANDO);
      break;
    }

    case OPERANDO: {
      if (nuevaMedida) {
        float error = RPM_OBJETIVO - rpm;
        float us = acelUs + KP * (error - errorPrevio) + KI * error;
        errorPrevio = error;
        float topeSinSensor = ESC_MIN_US + 0.6 * (ESC_MAX_US - ESC_MIN_US);
        if (!hayTemp && us > topeSinSensor) us = topeSinSensor;
        escribirEsc(us);
      }

      bool sobrecarga = corriente > I_ATASCO_A || (acelUs > 1700 && rpm < RPM_ATASCO);
      if (sobrecarga) {
        if (tSobrecarga == 0) tSobrecarga = millis();
        if (millis() - tSobrecarga > T_ATASCO_MS) {
          tSobrecarga = 0;
          reintentos++;
          parar(ATASCO);
          Serial.println(F("# ATASCO DETECTADO"));
          pitar(3);
        }
      } else {
        tSobrecarga = 0;
      }

      if (millis() - tSesion > T_SESION_MS) {
        parar(FIN_SESION);
        Serial.print(F("# FIN DE SESION. kg estimados: "));
        Serial.println(kgExtraidos, 1);
        pitar(2);
      }
      break;
    }

    case ATASCO:
      escribirEsc(ESC_MIN_US);
      if (reintentos > MAX_REINTENTOS) {
        cambiarEstado(FALLA);
        Serial.println(F("# FALLA: revisar tobera y cabezal antes de reiniciar"));
        break;
      }
      if (millis() - tEstado > 2000) cambiarEstado(RAMPA);
      break;

    case FIN_SESION:
    case FALLA:
      escribirEsc(ESC_MIN_US);
      if (digitalRead(PIN_INICIO) == LOW && digitalRead(PIN_EMERG) == LOW &&
          millis() - tEstado > 2000) {
        digitalWrite(PIN_RELE, LOW);
        cambiarEstado(REPOSO);
      }
      break;
  }
}
