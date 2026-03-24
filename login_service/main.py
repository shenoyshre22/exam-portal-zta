#importing fastAPI (framework that helps build APIs) and hhtp exception to send proper error responses
from fastapi import FastAPI, HTTPException
from models import LoginRequest, SignupRequest  #importing the data models we defined for login and signup
from auth import authenticate_user,create_user #importing the auth+ user creation login
from database import create_users_table , get_db_connection #importing database setup functions
from passlib.context import CryptContext #for hashing passwords
#creating FastAPI instance
app = FastAPI()
#setup password hashing context--> to hash passwords before storing them
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
#the bootstrap program for the server
@app.on_event("startup")  #on_event is an older way
def startup():
    create_users_table() #this will create the users table in the database when the server starts up, if not already present
    conn=get_db_connection() #connect to the database
    #this is for our testing and demo purpose 
    users= [
        ("teacher1", pwd_context.hash("password1"), "teacher"),
        ("student1", pwd_context.hash("password2"), "student")
    ]
    #insert users into the database
    for user in users:
        try:
            conn.exceute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", user)
        except:
            #if user already exosts , ignore the error
            pass
        #save changes and close the database connection
        conn.commit()
        conn.closer()
        
