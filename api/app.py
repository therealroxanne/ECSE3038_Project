import os
from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
import motor.motor_asyncio
from bson import ObjectId
import pydantic
from pydantic import BaseModel
import requests
from dotenv import load_dotenv
from datetime import datetime
import re
from datetime import timedelta

load_dotenv()

app= FastAPI()

origins=[
    "http://localhost:8000",
    "https://simple-smart-hub-client.netlify.app"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client= motor.motor_asyncio.AsyncIOMotorClient(os.getenv("mongo_db_url"))
db= client.smat_control

pydantic.json.ENCODERS_BY_TYPE[ObjectId]=str

regex = re.compile(r'((?P<hours>\d+?)h)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?')
def parse_time(time_str):
    parts = regex.match(time_str)
    if not parts:
        return
    parts = parts.groupdict()
    time_params = {}
    for name, param in parts.items():
        if param:
            time_params[name] = int(param)
    return timedelta(**time_params)

def getsunset_time():
    response= requests.get("https://api.sunrise-sunset.org/json?lat=18.1155&lng=-77.2760")
    data= response.json()
    sunset= data["results"]["sunset"]
    utc_sunset=datetime.strptime(sunset, "%I:%M:%S %p")
    time_string='05:00:00'
    time_object= datetime.strptime(time_string, '%H:%M:%S')
    est_sunset_time= utc_sunset - time_object
    return est_sunset_time

@app.get("/graph")
async def get_parameter(request: Request):
    n = int(request.query_params.get('size', 10))
    sensor_input= await db["data_input"].find().to_list(n)

    global presence
    presence= [param["presence"] for param in sensor_input]
    global temperatures
    temperatures=[param["temperature"] for param in sensor_input]
    global datetimes
    datetimes= [param["datetime"] for param in sensor_input]

    output=[]
    if temperatures and presence and datetimes:
        output.append({
            "temperature": temperatures,
            "presence": presence,
            "datetime": datetimes
            })
        
    while len(output) < n:
        output.append({
            "temperature": 0.0,
            "presence": False,
            "datetime": datetime.now()
        })

    return output

@app.put("/settings", status_code=201)
async def create_parameter(request:Request):
    parameter= await request.json()
    global temp
    temp= parameter["user_temp"]
    global light
    light= parameter["user_light"]
    global duration_time
    duration_time= parameter["light_duration"]

    if light=="sunset":
        global light_preference
        light_preference=getsunset_time()
    else: light_preference= datetime.strptime(light, "%H:%M:%S")

    duration_time= light_preference+ parse_time(duration_time)

    user_data={
        "user_temp": temp,
        "user_light": str(light_preference.time()),
        "light_time_off":str(duration_time.time())
    }
    user_preference= await db["control_system"].insert_one(user_data)
    input_preference= await db["control_system"].find_one({"_id":user_preference.inserted_id})

    return input_preference 

@app.get("/output", status_code=201)
async def get_states():
    state_object= await db["data_input"].find().sort('datetime',-1).to_list(1)
    
    fan_val= False
    if len(temperatures)==0:
        return{
            "fan": fan_val
        }
    if temperatures[0]>= temp and presence[0]==True:
        fan_val= True
    else: fan_val= False

    light_val= False

    if len(datetimes)==0:
        return{
            "light": light_val
        }

    if light_preference>= datetimes[0] and presence[0]==True:
        light_val=True
    else: light_val==False

    return {
        "light":light_val,
        "fan":fan_val
    }
