
#object relation mapping tecnique which interacts with the databse.
#will be used in main.py to connect to the flask 
#Stores events from different service
#filtering by the user as well 
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


DATABASE_URL = "sqlite:///./logs.db"


# Engine connects to DB
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Session = DB connection instance
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()