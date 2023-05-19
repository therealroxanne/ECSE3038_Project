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
DallasTemperature tempSensor(&oneWire);

void setup() {
  pinMode(light_pin, OUTPUT);
  pinMode(fan_pin, OUTPUT);
  pinMode(pir_pin,INPUT);

  Serial.begin(9600);
  tempSensor.begin();
  // WiFi_SSID and WIFI_PASS should be stored in the env.h
  WiFi.begin(WIFI_SSID, WIFI_PASS);

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

//PUT REQUEST
void set_parameters()
{
  //Temperature sensor
  tempSensor.requestTemperaturesByIndex(0);
  float temp_reading= tempSensor.getTempCByIndex(0);
  Serial.print(tempSensor.getTempCByIndex(0));
  
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
  StaticJsonDocument<32> doc;
  String httpRequestData;

  doc["temperature"] = temp_reading;
  doc["presence"] = presence_reading;

  serializeJson(doc, httpRequestData);

  HTTPClient http;

  String url= String(ENDPOINT)+"/graph";
  http.begin(url);

  http.addHeader("Content-type", "application/json");
  int status_code = http.PUT(httpRequestData);

  if(status_code<0){
    Serial.print("Error occurred");
  }
  if (status_code==204)
  {
    Serial.print("Successful");
  }

  http.end();
}

//GET REQUEST
void get_state(){
  HTTPClient http;
  String url= String(ENDPOINT)+"/output";
  http.begin(url);

  int httpResponseCode= http.GET(); //if a negative number is return then a connection to the servo was not established 
 
  String http_response;

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
    
    String response_body= http.getString();
    StaticJsonDocument<128> doc;

    DeserializationError error = deserializeJson(doc, http_response);

    if (error) {
     Serial.print("deserializeJson() failed: ");
     Serial.println(error.c_str());
     return;
}

const char* id = doc["_id"]; // "640e1fc87a0bf6493917690b"
bool fan = doc["fan"]; // "True"
bool light = doc["light"]; // "False"

if (fan==false)
{
  digitalWrite(fan_pin,HIGH);
}
else
{
  digitalWrite(fan_pin,LOW);
}

if (light==true)
{
  digitalWrite(light_pin,HIGH);
}
else
{
  digitalWrite(light_pin,LOW);
}
http.end();
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
