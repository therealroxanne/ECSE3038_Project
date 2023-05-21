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
    sensor_input= await db["sensor_input"].find().to_list(n)

    presence= [param["presence"] for param in sensor_input]
    temperatures=[param["temperature"] for param in sensor_input]
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

    temp= parameter["user_temp"]
    light= parameter["user_light"]
    duration_time= parameter["light_duration"]

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
    state_object= await db["sensor_input"].find().sort('datetime',-1).to_list(1)
    if len(state_object)==0:
        return{
            "temperature": 0.0,
            "presence": False,
            "datetime":datetime.now()
        }

    return state_object

@app.put("/update")
async def update_state(request:Request):
    update_obj= await request.json()
   
    sensor_temp= update_obj.get("temperature")
    detection= update_obj.get("presence")
    date_time= update_obj.get("datetime")

    update_obj["current_time"]= datetime.now()

    user_data= await db["control_system"].find_one()
    user_temp= user_data["user_temp"]
    user_light= user_data["user_light"]
    duration_time= user_data["light_time_off"]

    if len(user_data)==0:
        return{
            update_obj["fan"]: False,
            update_obj["light"]:False,
            update_obj["current_time"]:datetime.now()
    }

    if len(update_obj)==0:
        return{
            update_obj["fan"]: False,
            update_obj["light"]:False,
            update_obj["current_time"]:datetime.now()
        }
    if sensor_temp is not None and user_temp is not None and isinstance(sensor_temp, int) and isinstance(user_temp, int):
        if sensor_temp>= user_temp and detection==True:
             update_obj["fan"]= True
        else: update_obj["fan"]= False
    else:
        update_obj["fan"] = False 

    if user_light is not None and date_time is not None and isinstance(user_light, datetime.time) and isinstance(date_time, datetime.time):
        if user_light <= date_time < duration_time and detection == True:
            update_obj["light"] = True
        else:
            update_obj["light"] = False
    else:
        update_obj["light"] = False 
 
    updated_data= await db["data_input"].insert_one(update_obj)
    send_data=await db["data_input"].find_one({"id":updated_data.inserted_id})
    return send_data
