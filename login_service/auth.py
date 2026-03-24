from database import get_db_connection #to connect to our database
from passlib.context import CryptContext #this inbuilt library will help us hash out passwords
#the algorithm bcrpyt which is a hashing algorithm used in real systems
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") #this is the setup that will help us hash and verify passwords

#---function to check if the entered password matches the stored password-----
def verify_password(plain_password,hased_password):
    #hashed password is the one stored in the database and plain password is the one entered by the user
    return pwd_context.verify(plain_password,hased_password) #verify will help comparing safely
 
 #---function to fetch a user from the database---
def get_user(username: str):
    conn = get_db_connection() #open and connect to the database 
    #sql query
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone() #fetch the user with the given username
    conn.close() #close the connection
    return user #return the user data

#---function to handle login logic ---
def authenticate_user(username: str , password: str):
    #checks if user exists and if password is correct
    user=get_user(username) 
    if not user:
        return None
    if not verify_password(password,user["password"]):
        return None
    return user #if both checks pass, then return the user data
