from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorDatabase
from configure.db_connect import get_db
from configure.model import StudentLogin, StudentInfor, StudentDebtInfor, OTPRequest, OTPResponse, PaymentRequest, PaymentResponse, Transaction, pwd_context
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from pymongo import ReturnDocument
import secrets
from typing import List
import asyncio
import uvicorn

app = FastAPI(title="IBanking Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes

# Login Route
@app.post("/api/login", response_model=StudentInfor)
async def login(student: StudentLogin, db: AsyncIOMotorDatabase = Depends(get_db)):
    student_doc = await db.students.find_one({"mssv": student.mssv})
    if not student_doc or not pwd_context.verify(student.password, student_doc["password"]):
        raise HTTPException(status_code=401, detail="Invalid Credentials")
    return StudentInfor(
        id=str(student_doc["_id"]),
        mssv=student_doc["mssv"],
        name=student_doc["name"],
        phone=student_doc["phone"],
        email=student_doc["email"],
        balance=student_doc["balance"],
        debt=student_doc["debt"]
    )

# Search Student Route
@app.get("/api/student/{mssv}", response_model=StudentDebtInfor)
async def get_student_debt(mssv: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    student = await db.students.find_one({"mssv": mssv})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    required_fields = ["mssv", "name", "debt"]
    missing_fields = [field for field in required_fields if field not in student or student[field] is None]
    if missing_fields:
        raise HTTPException(status_code=500, detail=f"Invalid student data: missing fields {missing_fields}")
    return StudentDebtInfor(
        mssv=student["mssv"],
        name=student["name"],
        debt=student["debt"]
    )

# OTP Route
@app.post("/api/otp", response_model=OTPResponse)
async def generate_otp(request: OTPRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    payer = await db.students.find_one({"_id": ObjectId(request.student_id)})
    payee = await db.students.find_one({"mssv": request.mssv})

    if not payer or not payee:
        raise HTTPException(status_code=404, detail="Student not found")
    if payer["balance"] < request.amount or payee["debt"] < request.amount:
        raise HTTPException(status_code=400, detail=f"Insufficient balance or debt mismatch: balance={payer['balance']}, debt={payee['debt']}, amount={request.amount}")

    transaction_id = str(ObjectId())
    transaction = {
        "transaction_id": transaction_id,
        "mssv": request.mssv,
        "amount": request.amount,
        "status": "pending",
        "created_at": datetime.now(timezone.utc)
    }

    await db.students.update_one(
        {"_id": ObjectId(request.student_id)},
        {"$push": {"transactions": transaction}}
    )

    code = secrets.token_hex(4).upper()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    try:
        await db.otps.insert_one({
            "transaction_id": transaction_id,
            "code": code,
            "email": payer["email"],
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at
        })
    except Exception:
        raise HTTPException(status_code=400, detail="OTP generation failed (duplicate code)")

    print(f"OTP sent to {payer['email']}: {code}")

    return OTPResponse(transaction_id=transaction_id)

# Pay Route
@app.post("/api/pay", response_model=PaymentResponse)
async def verify_otp_and_pay(request: PaymentRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    # Kiểm tra OTP
    otp_doc = await db.otps.find_one({
        "transaction_id": request.transaction_id,
        "code": request.otp,
        "expires_at": {"$gt": datetime.now(timezone.utc)}
    })
    if not otp_doc:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    # Tìm payer
    payer = await db.students.find_one({"transactions.transaction_id": request.transaction_id})
    if not payer:
        raise HTTPException(status_code=404, detail="Payer not found")

    # Tìm transaction
    transaction = next((t for t in payer["transactions"] if t["transaction_id"] == request.transaction_id), None)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    amount = transaction["amount"]
    is_self_payment = payer["mssv"] == transaction["mssv"]
    max_retries = 3
    retry_delay = 0.1  # seconds

    if is_self_payment:
        # Thử cập nhật cho thanh toán bản thân
        for attempt in range(max_retries):
            payer = await db.students.find_one({"_id": payer["_id"]})  # Lấy lại payer để có version mới nhất
            if not payer:
                raise HTTPException(status_code=404, detail="Payer not found after retry")

            update_result = await db.students.find_one_and_update(
                {
                    "_id": payer["_id"],
                    "version": payer["version"],
                    "balance": {"$gte": amount},
                    "debt": {"$gte": amount}
                },
                {
                    "$inc": {"balance": -amount, "debt": -amount, "version": 1},
                    "$set": {"transactions.$[elem].status": "success"}
                },
                array_filters=[{"elem.transaction_id": request.transaction_id}],
                return_document=ReturnDocument.AFTER
            )

            if update_result:
                break
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            raise HTTPException(
                status_code=400,
                detail=f"Transaction failed after {max_retries} attempts: insufficient balance, debt, or concurrency issue for mssv={payer['mssv']}, balance={payer['balance']}, debt={payer['debt']}, amount={amount}, version={payer['version']}"
            )
    else:
        # Tìm payee
        payee = await db.students.find_one({"mssv": transaction["mssv"]})
        if not payee:
            raise HTTPException(status_code=404, detail="Payee not found")

        # Cập nhật payee trước
        for attempt in range(max_retries):
            payee = await db.students.find_one({"mssv": transaction["mssv"]})
            if not payee:
                raise HTTPException(status_code=404, detail="Payee not found after retry")

            payee_update = await db.students.find_one_and_update(
                {
                    "mssv": transaction["mssv"],
                    "version": payee["version"],
                    "debt": {"$gte": amount}
                },
                {"$inc": {"debt": -amount, "version": 1}},
                return_document=ReturnDocument.AFTER
            )

            if payee_update:
                break
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            raise HTTPException(
                status_code=400,
                detail=f"Debt update failed after {max_retries} attempts: mssv={transaction['mssv']}, current_debt={payee.get('debt', 'N/A')}, current_version={payee.get('version', 'N/A')}, required_debt={amount}, required_version={payee['version']}"
            )

        # Cập nhật payer
        for attempt in range(max_retries):
            payer = await db.students.find_one({"_id": payer["_id"]})
            if not payer:
                raise HTTPException(status_code=404, detail="Payer not found after retry")

            payer_update = await db.students.find_one_and_update(
                {
                    "_id": payer["_id"],
                    "version": payer["version"],
                    "balance": {"$gte": amount}
                },
                {
                    "$inc": {"balance": -amount, "version": 1},
                    "$set": {"transactions.$[elem].status": "success"}
                },
                array_filters=[{"elem.transaction_id": request.transaction_id}],
                return_document=ReturnDocument.AFTER
            )

            if payer_update:
                break
            if attempt < max_retries - 1:
                # Rollback payee_update
                await db.students.find_one_and_update(
                    {"mssv": transaction["mssv"], "version": payee_update["version"]},
                    {"$inc": {"debt": amount, "version": 1}},
                    return_document=ReturnDocument.AFTER
                )
                await asyncio.sleep(retry_delay)
                continue
            raise HTTPException(
                status_code=400,
                detail=f"Transaction failed after {max_retries} attempts: insufficient balance or concurrency issue for mssv={payer['mssv']}, balance={payer['balance']}, amount={amount}, version={payer['version']}"
            )

    # Xóa OTP
    await db.otps.delete_one({"transaction_id": request.transaction_id})

    print(f"Payment confirmation sent to {payer['email']}")

    return PaymentResponse(
        success=True,
        balance=update_result["balance"] if is_self_payment else payer_update["balance"],
        debt=update_result["debt"] if is_self_payment else None
    )

# Transaction Route
@app.get("/api/transaction/{student_id}", response_model=List[Transaction])
async def get_transactions(student_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    student = await db.students.find_one({"_id": ObjectId(student_id)})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return [Transaction(**t) for t in student["transactions"]]

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)