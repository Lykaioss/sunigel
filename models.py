from sqlalchemy import Boolean , Column , Integer , String , DateTime
from database import Base
from datetime import datetime ,timezone

class User(Base):
    __tablename__ = 'users'

    
    username = Column(String(50) , primary_key=True ,  unique=True  )
    email = Column(String(50) , unique=True , index=True)
    password = Column(String(100))
    isEmp = Column(Boolean)

class Post(Base):
    __tablename__ = 'posts'

    id = Column(Integer , primary_key=True , index=True)
    title = Column(String(50))
    category = Column(String(50))
    description = Column(String(100))
    deadline = Column(DateTime )
    active = Column(Boolean, default=True)

   

