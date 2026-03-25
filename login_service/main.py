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
@app.get("/")
def home():
        return{"message": "Login Service Running yay"}  # just to test for our sake , if the service runs

    #---signup API to create a new user--- 
@app.post("/signup")
def signup(data: SignupRequest): # takes in the inputs username , password and role (student/teacher)
        if data.role not in ["student", "teacher"]:  # to avoid any other role but student or teacher
            raise HTTPException(status_code=400, detail="Role must be either 'student' or 'teacher'") #if role is not valid , send error response
        success = create_user(data.username, data.password, data.role) #create user using the function we defined in auth.py
        if not success: # if user already exists and someone tries to sign in 
            raise HTTPException(status_code=400, detail="Username already exists") #if user already exists , send error response
        return {"message": "User created successfully"} #if user is created successfully , send success response 

    
#-- login API (to authenticate existing user and return their role)---
@app.post("/login")
def login(data: LoginRequest): #takes in username and password as input , validated and verifies
    user = authenticate_user(data.username, data.password) #authenticate user using the function we defined in auth.py by calling it
    if not user: #if authentication fails (likee if user doesnt exist or password is wrong)
        raise HTTPException(status_code=401, detail="Invalid username or password") #send error response
    return {"message": "Login successful", "role": user["role"]} #if login is successful , send success response with the user's role (student/teacher)