#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "OneWire.h" 
#include "DallasTemperature.h"
#include "env.h"

#define light_pin 2
#define fan_pin   4
#define pir_pin  15
#define temp_senor 22

OneWire oneWire(22);
DallasTemperature sensors(&oneWire);

void setup() {
  pinMode(light_pin, OUTPUT);
  pinMode(fan_pin, OUTPUT);
  pinMode(pir_pin,INPUT);

  Serial.begin(9600);
  sensors.begin();
  WiFi.begin("Wokwi-GUEST", "");

  // Connect to wifi
  Serial.println("Connecting");
  while(WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.print("Connected to WiFi network with IP Address: ");
  Serial.println(WiFi.localIP());
}

//POST REQUEST
void set_parameters()
{
  //Temperature sensor
  sensors.requestTemperatures();
  float temp_reading= sensors.getTempCByIndex(0);
  Serial.print("temperature:");
  Serial.print(temp_reading);
  

  //PIR motion sensor
  int pirState = LOW;  
  int val=0;
  bool presence_reading=false;
  val= digitalRead(pir_pin);
  if(val==HIGH)
  {
    presence_reading= true;
  }
  else{
    presence_reading=false;
  }
  Serial.print("Presence:");
  Serial.print(presence_reading);
  

  HTTPClient http;
  String http_response;

  http.begin(ENDPOINT1);

  http.addHeader("Content-type", "application/json");

  StaticJsonDocument<96> doc;
  String httpRequestData;

  doc["temperature"] = temp_reading;
  doc["presence"] = presence_reading;

  serializeJson(doc, httpRequestData);

  int httpResponseCode= http.POST(httpRequestData);
  
  if(httpResponseCode>0)
    {
      Serial.print("HTTP Response Code: ");
      Serial.println(httpResponseCode);
    }
    else{
      Serial.print("Error: ");
      Serial.println(httpResponseCode);
    }
  http.end();
}

//GET REQUEST
void get_state(){
  HTTPClient http;
   String http_response;
  http.begin(ENDPOINT2);

  int httpResponseCode= http.GET(); //if a negative number is return then a connection to the servo was not established 
  
    if(httpResponseCode>0)
    {
      Serial.print("HTTP Response Code: ");
      Serial.println(httpResponseCode);
      Serial.print("Response from server");
      http_response=http.getString();
      Serial.println(http_response);
    } 
    else{
      Serial.print("Error code: ");
      Serial.println(httpResponseCode);
    }
    http.end();

    //http_response= http.getString();

    StaticJsonDocument<192> doc;

    DeserializationError error = deserializeJson(doc, http_response);

    if (error) {
      Serial.print("deserializeJson() failed: ");
      Serial.println(error.c_str());
      return;
    }

    const char* id = doc["_id"]; // "646995b6e9adbf9f95b64330"
    bool fan = doc["fan"]; // true
    bool light = doc["light"]; // false
    const char* current_time = doc["current_time"]; // "2023-05-20T21:46:42.941692"
      
      Serial.println("Light:");
      Serial.println(light);
      Serial.println("Fan:");
      Serial.println(fan);


  digitalWrite(fan_pin,fan);
  digitalWrite(light_pin,light);
}

void loop() {
  if(WiFi.status()== WL_CONNECTED){
    Serial.println("");
    Serial.println("");

    set_parameters();
    get_state();
  }
  else {
    return;
}
}
