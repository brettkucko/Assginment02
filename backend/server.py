from fastapi import FastAPI, HTTPException, status, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from pymongo import MongoClient
from pymongo.errors import PyMongoError, DuplicateKeyError
from bson import ObjectId

from config import MONGODB_URI, DB_NAME

# --- MongoDB connection ---
client = MongoClient(MONGODB_URI)
db = client[DB_NAME]
collection = db["robots"]            # Collection name (not robots.json, just robots)

# --- FastAPI app setup ---
app = FastAPI()

# Optional: enable CORS if you’ll connect from React/React Native
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # or specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Minimal Pydantic model ---
class Robot(BaseModel):
    name: str
    price: float
    description: str
    imageUrl: str

class RobotValidated(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid"
    )
    name: str = Field(min_length=1)
    price: float = Field(ge=0, allow_inf_nan=False)
    description: str = Field(min_length=1)
    imageUrl: HttpUrl



# --- Root endpoint ---
@app.get("/hello")
def read_root():
    return {"message": "Hello from FastAPI + MongoDB Atlas backend!!!!!"}


# --- Get all robots ---
@app.get("/robots")
def get_robots():
    try:
        if "robots" not in db.list_collection_names():
            raise HTTPException(status_code=404, detail="Collection 'robots' not found")

        robots = list(collection.find())      # Retrieve all documents
        for r in robots:
            r["_id"] = str(r["_id"])          # Convert ObjectId to string
        
        return robots
    
    except HTTPException:
        raise  # let FastAPI handle our own HTTP errors
    except PyMongoError as e:
        print("Database error:", e)
        raise HTTPException(status_code=503, detail="Database not reachable")
    except Exception as e:
        print("Unexpected error:", e)
        raise HTTPException(status_code=500, detail="Internal server error")



@app.post("/robots", status_code=status.HTTP_201_CREATED)
def add_robot(robot: Robot):
    try:
        if "robots" not in db.list_collection_names():
            raise HTTPException(status_code=404, detail="Collection 'robots' not found")
        if collection.find_one({"name": robot.name}):
            raise HTTPException(status_code=409, detail="Robot already exists")

        result = collection.insert_one(robot.model_dump())
        return {"message": "Robot added successfully", "id": str(result.inserted_id)}

    except HTTPException:
        raise
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Robot already exists")
    except PyMongoError as e:
        print("Database error:", e)
        raise HTTPException(status_code=503, detail="Database not reachable")
    except Exception as e:
        print("Unexpected error:", e)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/robots/{name}")
def update_robot_with_errors(
    robot: RobotValidated,
    name: str = Path(min_length=1)
):
    try:
        if not name.strip():
            raise HTTPException(status_code=422, detail="Robot name cannot be blank")
        if "robots" not in db.list_collection_names():
            raise HTTPException(status_code=404, detail="Collection 'robots' not found")
        # Find the robot using its current name.
        existing_robot = collection.find_one({"name": name})
        if existing_robot is None:
            raise HTTPException(status_code=404, detail=f"Robot '{name}' not found")
        # Prevent renaming it to another robot's name.
        duplicate = collection.find_one({
            "name": robot.name,
            "_id": {"$ne": existing_robot["_id"]}
        })
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="Another robot already has that name")
        # JSON mode converts HttpUrl to a MongoDB-compatible string.
        updated_data = robot.model_dump(mode="json")
        result = collection.update_one(
            {"_id": existing_robot["_id"]},
            {"$set": updated_data}
        )
        # The robot might have been deleted after the lookup.
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Robot no longer exists")
        if result.modified_count == 0:
            return {
                "message": "No changes needed; robot already has these values",
                "id": str(existing_robot["_id"])
            }
        return {
            "message": "Robot updated successfully",
            "id": str(existing_robot["_id"])
        }
    except HTTPException:
        raise
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="Another robot already has that name")
    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database operation failed")
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/robots/{robot_id}")
def delete_robot(
    # Must be a 24-character hex string. Otherwise FastAPI returns 422 before the function runs.
    robot_id: str = Path(pattern=r"^[0-9a-fA-F]{24}$")
):
    try:
        if "robots" not in db.list_collection_names():
            raise HTTPException(status_code=404, detail="Collection 'robots' not found")

        object_id = ObjectId(robot_id)

        existing_robot = collection.find_one({"_id": object_id})
        if existing_robot is None:
            raise HTTPException(
                status_code=404,
                detail="Robot not found. It may have already been deleted"
            )

        result = collection.delete_one({"_id": object_id})

        # The robot might have been deleted by someone else after the lookup.
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Robot no longer exists")

        return {
            "message": f"Robot '{existing_robot.get('name', '')}' deleted successfully",
            "id": robot_id
        }

    except HTTPException:
        raise

    except PyMongoError:
        raise HTTPException(status_code=503, detail="Database operation failed")

    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")