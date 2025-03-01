from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime, timezone

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(50), unique=True, index=True, nullable=False)
    contact = Column(String(15), unique=True, index=True,nullable=False )
    isTpo = Column(Boolean, default=None, nullable=True)

    password = Column(String(100), nullable=False)
    isEmp = Column(Boolean, nullable=False, default=False)

    employer = relationship("Employer", back_populates="user", uselist=False)
    tpo = relationship("TPO", back_populates="user", uselist=False, cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="user")

class TPO(Base):
    __tablename__ = "tpos"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    college_name = Column(String(100), nullable=False)
    college_location = Column(String(100), nullable=False)
    
    user = relationship("User", back_populates="tpo")

class Employer(Base):
    __tablename__ = 'employers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, )
    company_name = Column(String(100), nullable=True)

    user = relationship("User", back_populates="employer")
    jobs = relationship("Post", back_populates="employer")

class Post(Base):
    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    employer_id = Column(Integer, ForeignKey('employers.id'), nullable=False)
    title = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    deadline = Column(DateTime, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    employer = relationship("Employer", back_populates="jobs")
    applications = relationship("Application", back_populates="post")

    def update_active_status(self):
        if self.deadline < datetime.now(timezone.utc):
            self.active = False

class Application(Base):
    __tablename__ = 'applications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    post_id = Column(Integer, ForeignKey('posts.id'), nullable=False)
    applied_at = Column(DateTime, default=datetime.now(timezone.utc))
    status = Column(Enum('pending', 'accepted', 'rejected', name='application_status'), default='pending')
    resume_url = Column(String(255), nullable=True)
    cover_letter = Column(Text, nullable=True)

    user = relationship("User", back_populates="applications")
    post = relationship("Post", back_populates="applications")
