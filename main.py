from fastapi import FastAPI , HTTPException , Depends , status , Request , Response
from pydantic import BaseModel
from typing import Annotated
import models
from database import engine , SessionLocal
from sqlalchemy.orm import Session
from datetime import date , timezone , datetime
import bcrypt
from fastapi.middleware.cors import CORSMiddleware
import uuid
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.responses import JSONResponse


app = FastAPI()
models.Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory="templates")


sessions = {}

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:8080",
    "http://127.0.0.1:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PostBase(BaseModel):
    title : str
    description : str
    category : str
    deadline : date


class UserBase(BaseModel):
    username : str
    password : str 
    email : str
    isEmp : bool

class LoginRequest(BaseModel):
    username: str
    password: str



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session , Depends(get_db)]




@app.post("/posts/" , status_code=status.HTTP_201_CREATED)
async def create_post(post: PostBase , db: db_dependency):
    db_post = models.Post(**post.model_dump())
    db.add(db_post)
    db.commit()

@app.get("/jobs/", response_class=JSONResponse)
async def get_jobs(db: Session = Depends(get_db)):
    """Returns job listings as JSON for the frontend."""
    posts = db.query(models.Post).all()
    
    job_list = [
        {
            "title": post.title,
            "description": post.description,
            "category": post.category,
            "deadline": post.deadline.strftime("%Y-%m-%d") if post.deadline else None
        }
        for post in posts
    ]
    
    return JSONResponse(content=job_list)






def get_current_user(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id is None or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return sessions[session_id]



@app.post("/users/", status_code=status.HTTP_201_CREATED)
async def create_user(user: UserBase, db: db_dependency):
    try:
        # Hash the password
        hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())
        print(" booo " ,hashed_password)
        
        # Create a new User object with the hashed password
        db_user = models.User(
            username=user.username,
            email=user.email,
            password=hashed_password.decode('utf-8'),
            isEmp = user.isEmp   # Store it as a string
        )
        
        db.add(db_user)
        db.commit()
        return {"message": "User created successfully"}
    
    except Exception as e:
        db.rollback()
        print(f"Error occurred: {e}")
        raise HTTPException(status_code=400, detail="Error creating user")
    

@app.post("/login/")
async def login(user: LoginRequest, response: Response, db: db_dependency):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user is None or not bcrypt.checkpw(user.password.encode('utf-8'), db_user.password.encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    # Generate a session ID and store it
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "username": db_user.username,
        "created_at": datetime.now(timezone.utc),
        "isEmp": db_user.isEmp
    }

    # Set the session cookie (HTTP-only for security)
    response.set_cookie(
        key="session_id",
        value=session_id,
        # httponly=True,
        max_age=3600  # Cookie expires in 1 hour
    )
    
    return {"message": "Login successful", "username": db_user.username , "isEmp": db_user.isEmp }


@app.get("/get_user")
async def show_user(request: Request):
    # Get the session_id from cookies
    session_id = request.cookies.get("session_id")
    print("cookies : " , request.cookies)

    # Check if the session exists in the in-memory session store
    
    if session_id is None or session_id not in sessions:
        print("session karlo : " , sessions)
        print("session  : " , session_id)
        # print("wewe  : " , sessions[session_id])
        raise HTTPException(status_code=401, detail="No active session found")

    # Retrieve the user details from the session
    user_session = sessions[session_id]
    print(f"Session Data: {user_session}")
    
    return {
        "session_id": session_id,
        "user": {
            "username": user_session["username"],
            "created_at": user_session["created_at"],
            "isEmp": user_session["isEmp"]
        }
    }


@app.get("/home", response_class=HTMLResponse)
async def home(request: Request):
    session_id = request.cookies.get("session_id")
    print(" radhan" ,session_id)
    if session_id is None or session_id not in sessions:
        return RedirectResponse(url="/")  # Redirect to login if not authenticated

    user_session = sessions[session_id]
    return templates.TemplateResponse("home.html", {"request": request, "username": user_session["username"]})

@app.get("/employee" , response_class=HTMLResponse)
async def home(request: Request):
    session_id = request.cookies.get("session_id")
    print(" radhan" ,session_id)
    if session_id is None or session_id not in sessions:
        return RedirectResponse(url="/")  # Redirect to login if not authenticated

    user_session = sessions[session_id]
    return templates.TemplateResponse("employee.html", {"request": request, "username": user_session["username"]})




@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("log.html", {"request": request})




@app.post("/logout/")
async def logout(response: Response, request: Request):
    session_id = request.cookies.get("session_id")
    print("this be ssession_id : ", session_id)
    if session_id and session_id in sessions:
        print("sess deldetd : " , session_id)
        del sessions[session_id]
        response.set_cookie(key="session_id", value="", max_age=0)
 # Ensure the path matches
    return RedirectResponse(url="/", status_code=303)



@app.post("/")
async def handle_post():
    return {"message": "POST request received"}


    
    

@app.get("/protected/", status_code=status.HTTP_200_OK)
async def protected_route(user: dict = Depends(get_current_user)):
    return {"message": f"Hello, {user['username']}! You are authenticated."}

from fastapi import Request, HTTPException








# @app.get("/users/{user_id}" , status_code=status.HTTP_200_OK )
# async def read_user(user_id: int , db: db_dependency):
#     user = db.query(models.User).filter(models.User.id == user_id).first()
#     if user is None:
#         raise HTTPException(status_code=404 , detail='User not found')
#     return user
