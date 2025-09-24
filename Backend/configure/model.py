from ast import TryStar
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import timezone, datetime
from bson import ObjectId
from passlib.context import CryptContext
from db_connect import get_db
import os


pwd_context = CryptContext(schemes=["bcrypt"], deprecated = "auto")


class UserLogin(BaseModel):
    username: str
    password: str

class UserInfor(BaseModel):
    id: str
    name: str
    phone: str
    email: EmailStr
    balance: float

class StudentInfor(BaseModel):
    mssv: str
    name: str
    debt: float

class OTPRequest(BaseModel):
    user_id: str
    mssv: str
    balance: float = Field(gt=0)

class OTPResponse(BaseModel):
    transaction_id: str

class PaymentRequest(BaseModel):
    transaction_id: str
    otp: str

class PaymentResponse(BaseModel):
    success: bool
    balance: Optional[float]

class Transaction(BaseModel):
    transaction_id: str
    mss: str
    amount: float
    status: str
    createdd_at: datetime


async def seed_data():
    try: 

        db = await get_db()

        await db.user.delete_many({})
        await db.student.delete_many({})
        await db.otps.delete_many({})

        hashed1 = pwd_context.hash("password1")
        hashed2 = pwd_context.hash("password2")

        user1_id = str(ObjectId())
        user2_id = str(ObjectId())

        user1 = UserInfor(
            id = user1_id,
            name = "Do Duy Tan",
            phone = "0237492930",
            email = "tanbeo@gmail.com",
            balance = 10000000.00
        )

        user2 = UserInfor(
            id = user2_id,
            name = "Nguyen Bui Hong Tien",
            phone = "0858750342",
            email = "tien@gmail.com",
            balance = 50000000.00
        )

        await db.users.insert_many([
            {
            "id": ObjectId(user1_id),
            "username": "user1",
            "password": hashed1,
            **user1.model_dump(exclude={"id"}),
            "transaction": [],
            "version": 0,
            "created_at": datetime.now(timezone.utc)
            },
            {
            "id": ObjectId(user2_id),
            "username": "user2",
            "password": hashed2,
            **user2.model_dump(exclude={"id"}),
            "transaction": [],
            "version": 0,
            "created_at": datetime.now(timezone.utc)
            }
        ])

        student1 = StudentInfor(
            mssv = "SV001",
            name = "Le Dat Lep",
            debt = 300000.0
        )

        student2 = StudentInfor(
            mssv = "SV002",
            name = "Chieng Quoc Ku",
            debt = 400000.00
        )

        await db.students.insert_many([
            {**student1.model_dump(), "version": 0},
            {**student2.model_dump(), "version": 0}
        ])


        print("Data Seed Successfully!")

    except Exception as e:
        print(f"Error seeding data: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_data())

