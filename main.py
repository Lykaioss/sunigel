from fastapi import FastAPI, HTTPException, Depends, status, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from database import engine, SessionLocal
import models
from datetime import datetime, timezone, date
import bcrypt
from fastapi.middleware.cors import CORSMiddleware
import uuid
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

app = FastAPI()
models.Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory="templates")

sessions = {}

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------- DATABASE DEPENDENCY --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Depends(get_db)

# -------------------- SCHEMAS --------------------
class PostBase(BaseModel):
    title: str
    description: str
    category: str
    deadline: date

class UserBase(BaseModel):
    username: str
    password: str
    email: str
    isEmp: bool

class LoginRequest(BaseModel):
    username: str
    password: str

class ApplyRequest(BaseModel):
    job_id: int
    user_id: int  # User ID instead of username
    resume_url: str | None = None
    cover_letter: str | None = None

# -------------------- JOB POSTINGS --------------------
@app.post("/posts/", status_code=status.HTTP_201_CREATED)
async def create_post(post: PostBase, db: Session = db_dependency, request: Request = None):
    user_session = get_current_user(request)
    
    # Ensure only employers can post jobs
    if not user_session["isEmp"]:
        raise HTTPException(status_code=403, detail="Only employers can post jobs")

    employer = db.query(models.Employer).filter(models.Employer.user_id == user_session["id"]).first()
    if not employer:
        raise HTTPException(status_code=403, detail="Employer account required to post jobs")

    new_post = models.Post(
        employer_id=employer.id,
        title=post.title,
        description=post.description,
        category=post.category,
        deadline=post.deadline,
    )

    db.add(new_post)
    db.commit()
    return {"message": "Job posted successfully"}

def update_expired_jobs(db: Session):
    """Updates expired jobs by setting active=False for past deadlines."""
    db.query(models.Post).filter(models.Post.deadline < datetime.now(timezone.utc), models.Post.active == True).update({"active": False})
    db.commit()

@app.get("/jobs/", response_class=JSONResponse)
async def get_jobs(db: Session = db_dependency):
    """Returns only active job listings."""
    update_expired_jobs(db)
    
    posts = db.query(models.Post).filter(models.Post.active == True).options(joinedload(models.Post.employer)).all()

    job_list = [
        {
            "id": post.id,
            "title": post.title,
            "description": post.description,
            "category": post.category,
            "deadline": post.deadline.strftime("%Y-%m-%d"),
            "company": post.employer.company_name if post.employer else "Unknown"
        }
        for post in posts
    ]
    
    return JSONResponse(content=job_list)

# -------------------- JOB APPLICATION --------------------
@app.post("/apply/")
async def apply_for_job(application: ApplyRequest, db: Session = db_dependency):
    """Allows a user to apply for a job, ensuring one application per user."""
    
    # Check if job exists
    job = db.query(models.Post).filter(models.Post.id == application.job_id, models.Post.active == True).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired")

    # Check if user exists
    user = db.query(models.User).filter(models.User.id == application.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Ensure user is not an employer
    if user.isEmp:
        raise HTTPException(status_code=403, detail="Employers cannot apply for jobs")

    # Check if the user has already applied
    existing_application = db.query(models.Application).filter(
        models.Application.post_id == application.job_id,
        models.Application.user_id == application.user_id
    ).first()

    if existing_application:
        raise HTTPException(status_code=400, detail="You have already applied for this job")

    # Create and store the application
    db_application = models.Application(
        post_id=application.job_id,
        user_id=application.user_id,
        applied_at=datetime.utcnow(),
        resume_url=application.resume_url,
        cover_letter=application.cover_letter
    )
    db.add(db_application)
    db.commit()

    return {"message": "Application submitted successfully"}

# -------------------- GET APPLICATIONS FOR A JOB --------------------
@app.get("/applications/{job_id}")
async def get_applications(job_id: int, request: Request, db: Session = db_dependency):
    """Employers can view applicants for their job listings."""
    user_session = get_current_user(request)

    employer = db.query(models.Employer).filter(models.Employer.user_id == user_session["id"]).first()
    if not employer:
        raise HTTPException(status_code=403, detail="Employer access only")

    job = db.query(models.Post).filter(models.Post.id == job_id, models.Post.employer_id == employer.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or unauthorized")

    applications = db.query(models.Application).filter(models.Application.post_id == job_id).all()
    
    applicants = [{"user_id": app.user_id, "resume_url": app.resume_url, "cover_letter": app.cover_letter} for app in applications]
    
    return {"job_id": job_id, "applicants": applicants}

# -------------------- USER AUTHENTICATION --------------------
def get_current_user(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id is None or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return sessions[session_id]

@app.post("/users/", status_code=status.HTTP_201_CREATED)
async def create_user(user: UserBase, db: Session = db_dependency):
    try:
        hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())

        new_user = models.User(
            username=user.username,
            email=user.email,
            password=hashed_password.decode('utf-8'),
            isEmp=user.isEmp
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # If the user is an employer, create an employer profile
        if user.isEmp:
            employer = models.Employer(user_id=new_user.id, company_name=None)
            db.add(employer)
            db.commit()

        return {"message": "User created successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/login/")
async def login(user: LoginRequest, response: Response, db: Session = db_dependency):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user is None or not bcrypt.checkpw(user.password.encode('utf-8'), db_user.password.encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "id": db_user.id,
        "username": db_user.username,
        "created_at": datetime.now(timezone.utc),
        "isEmp": db_user.isEmp
    }

    response.set_cookie(key="session_id", value=session_id, max_age=3600)
    return {"message": "Login successful", "username": db_user.username, "isEmp": db_user.isEmp}



# -------------------- TEMPLATED ROUTES --------------------
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("log.html", {"request": request})

@app.get("/home", response_class=HTMLResponse)
async def home(request: Request):
    user_session = get_current_user(request)
    return templates.TemplateResponse("home.html", {"request": request, "username": user_session["username"]})

@app.get("/employee", response_class=HTMLResponse)
async def employee_dashboard(request: Request):
    user_session = get_current_user(request)
    return templates.TemplateResponse("employee.html", {"request": request, "username": user_session["username"]})

@app.get("/protected/", status_code=status.HTTP_200_OK)
async def protected_route(user: dict = Depends(get_current_user)):
    return {"message": f"Hello, {user['username']}! You are authenticated."}
