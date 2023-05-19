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
from datetime import datetime, datetime, time
import re
from datetime import timedelta

load_dotenv()
#pip
app = FastAPI()

origins=[
    "https://iot-smarthub.onrender.com",
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
    time_object= datetime.strptime(time_string, '%H:%M:%S').time()
    est_sunset_time= datetime.combine(datetime.min, utc_sunset.time()) + timedelta(hours=time_object.hour, minutes=time_object.minute, seconds=time_object.second)
    est_sunset_time=(est_sunset_time).time()
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

    global light_preference
    if parameter["user_light"]=="sunset":
        light_preference=getsunset_time()
    else: light_preference= datetime.strptime(light, "%H:%M:%S").time()

    duration_timedelta = parse_time(duration_time)
    end_time = datetime.combine(datetime.today(), light_preference) + duration_timedelta
    duration_time = end_time.time()
    user_data={
        "user_temp": temp,
        "user_light": str(light_preference),
        "light_time_off":str(duration_time)
    }
    user_preference= await db["control_system"].insert_one(user_data)
    input_preference= await db["control_system"].find_one({"_id":user_preference.inserted_id})

    return input_preference
    
@app.get("/output", status_code=201)
async def get_states():
    state_object= await db["data_input"].find().sort('datetime',-1).to_list(1)
    light_val= False
    fan_val= False
    if len(state_object)==0:
        return{
            "fan": fan_val,
            "light":light_val
        }
    detection=state_object[0].get('presence',[])
    if len(detection)==0:
        return{
            "fan": fan_val,
            "light":light_val
        }
    sensor_temp=state_object[0].get('temperature',[])
    
    
    if len(sensor_temp)==0:
        return{
            "fan": fan_val
        }
    if sensor_temp[0]>= temp and detection[0]==True:
        fan_val= True
    else: fan_val= False


    date_time=state_object[0].get('datetime',[])
    if len(date_time)==0:
        return{
            "light": light_val
        }

    if light_preference>= date_time[0] and detection[0]==True:
        light_val=True
    else: light_val==False

    return {
        "light":light_val,
        "fan":fan_val
    }
