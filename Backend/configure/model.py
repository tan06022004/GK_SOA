from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import timezone, datetime
from bson import ObjectId
from passlib.context import CryptContext
from .db_connect import get_db
import os

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class StudentLogin(BaseModel):
    mssv: str
    password: str

class StudentInfor(BaseModel):
    id: str
    mssv: str
    name: str
    phone: str
    email: EmailStr
    balance: float
    debt: float

class StudentDebtInfor(BaseModel):
    mssv: str
    name: str
    debt: float

class OTPRequest(BaseModel):
    student_id: str
    mssv: str
    amount: float = Field(gt=0)

class OTPResponse(BaseModel):
    transaction_id: str

class PaymentRequest(BaseModel):
    transaction_id: str
    otp: str

class PaymentResponse(BaseModel):
    success: bool
    balance: Optional[float]
    debt: Optional[float]

class Transaction(BaseModel):
    transaction_id: str
    mssv: str
    amount: float
    status: str
    created_at: datetime

async def seed_data():
    try:
        db = await get_db()

        await db.students.drop()  
        await db.otps.delete_many({})

        hashed1 = pwd_context.hash("password1")
        hashed2 = pwd_context.hash("password2")
        hashed3 = pwd_context.hash("password3")
        hashed4 = pwd_context.hash("password4")

        student1_id = str(ObjectId())
        student2_id = str(ObjectId())
        student3_id = str(ObjectId())
        student4_id = str(ObjectId())

        student1 = StudentInfor(
            id=student1_id,
            mssv="522H0042",
            name="Nguyen Bui Hong Tien",
            phone="0858750342",
            email="tien@gmail.com",
            balance=10000000.00,
            debt=200000.00
        )

        student2 = StudentInfor(
            id=student2_id,
            mssv="522H0089",
            name="Zo Hoang Tan",
            phone="0918977844",
            email="tan@gmail.com",
            balance=50000000.00,
            debt=200000.00
        )

        student3 = StudentInfor(
            id=student3_id,
            mssv="522H0007",
            name="Minh Khoi Dao",
            phone="09189778234",
            email="Khoi@gmail.com",
            balance=50000000.00,
            debt=300000.00
        )

        student4 = StudentInfor(
            id=student4_id,
            mssv="522H0012",
            name="Nguyen Tan Beo",
            phone="0918972342",
            email="Beo@gmail.com",
            balance=30000000.00,
            debt=320000.00
        )

        await db.students.insert_many([
            {
                "_id": ObjectId(student1_id),
                "password": hashed1,
                **student1.model_dump(exclude={"id"}),
                "transactions": [],
                "version": 0,
                "created_at": datetime.now(timezone.utc)
            },
            {
                "_id": ObjectId(student2_id),
                "password": hashed2,
                **student2.model_dump(exclude={"id"}),
                "transactions": [],
                "version": 0,
                "created_at": datetime.now(timezone.utc)
            },
            {
                "_id": ObjectId(student3_id),
                "password": hashed3,
                **student3.model_dump(exclude={"id"}),
                "transactions": [],
                "version": 0,
                "created_at": datetime.now(timezone.utc)
            },
            {
                "_id": ObjectId(student4_id),
                "password": hashed4,
                **student4.model_dump(exclude={"id"}),
                "transactions": [],
                "version": 0,
                "created_at": datetime.now(timezone.utc)
            }
        ])

        print("Data Seed Successfully!")

    except Exception as e:
        print(f"Error seeding data: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_data())