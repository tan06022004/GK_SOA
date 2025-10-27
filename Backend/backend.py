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
import os
import base64
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Load biến môi trường
load_dotenv()

app = FastAPI(title="IBanking Backend")

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Hàm lấy Gmail credentials
def get_gmail_credentials():
    """Lấy và refresh Gmail credentials"""
    SCOPES = ['https://www.googleapis.com/auth/gmail.send']
    creds = None
    token_file = "token.json"
    client_secrets_file = "credentials.json"

    # Load token hiện có
    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        except Exception as e:
            print(f"Token không hợp lệ: {e}")
            os.remove(token_file)
            creds = None

    # Refresh hoặc authorize
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Đang refresh token...")
                creds.refresh(Request())
            except Exception as e:
                print(f"Không thể refresh token: {e}")
                os.remove(token_file)
                creds = None
        
        # Nếu vẫn không có creds, yêu cầu authorize mới
        if not creds:
            if not os.path.exists(client_secrets_file):
                raise FileNotFoundError(f"Không tìm thấy {client_secrets_file}")
            
            print("Đang yêu cầu authorization mới...")
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_file, 
                SCOPES
            )
            creds = flow.run_local_server(
                port=8080,
                access_type='offline',
                prompt='consent'
            )
        
        # Lưu credentials
        with open(token_file, "w") as f:
            f.write(creds.to_json())
        print("✓ Token đã được lưu")

    return creds

# Hàm gửi OTP qua Gmail API
async def send_otp_email(recipient_email: str, otp_code: str):
    """Gửi OTP qua Gmail API"""
    try:
        # Lấy credentials
        creds = get_gmail_credentials()
        
        # Tạo Gmail service
        service = build('gmail', 'v1', credentials=creds)
        
        # Lấy sender email từ .env
        sender_email = os.getenv("SENDER_EMAIL")
        if not sender_email:
            raise HTTPException(status_code=500, detail="SENDER_EMAIL chưa được cấu hình trong .env")

        # Tạo email message
        message = MIMEMultipart('alternative')
        message['From'] = sender_email
        message['To'] = recipient_email
        message['Subject'] = 'Mã OTP - IBanking System'
        
        # HTML body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 20px; border-radius: 10px; }}
                .header {{ text-align: center; color: #333; }}
                .otp-code {{ font-size: 32px; font-weight: bold; color: #4CAF50; text-align: center; 
                             padding: 20px; background-color: #f0f0f0; border-radius: 5px; margin: 20px 0; 
                             letter-spacing: 5px; }}
                .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 20px; }}
                .warning {{ color: #ff5722; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 class="header">🔐 Mã OTP của bạn</h2>
                <p>Xin chào,</p>
                <p>Đây là mã OTP để xác nhận giao dịch của bạn:</p>
                <div class="otp-code">{otp_code}</div>
                <p class="warning">⚠️ Mã này sẽ hết hạn sau 5 phút</p>
                <p>Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email này.</p>
                <div class="footer">
                    <p>© 2025 IBanking System. Đừng chia sẻ mã OTP với bất kỳ ai.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Text body (fallback)
        text_body = f"""
        Mã OTP của bạn: {otp_code}
        
        Mã này sẽ hết hạn sau 5 phút.
        Đừng chia sẻ mã này với bất kỳ ai.
        
        © 2025 IBanking System
        """
        
        # Attach both text and HTML versions
        message.attach(MIMEText(text_body, 'plain'))
        message.attach(MIMEText(html_body, 'html'))
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        # Gửi email
        send_result = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        
        print(f"✓ OTP đã được gửi đến {recipient_email} (Message ID: {send_result['id']})")
        return True
        
    except Exception as e:
        print(f"✗ Lỗi khi gửi email: {e}")
        raise HTTPException(status_code=500, detail=f"Không thể gửi OTP: {str(e)}")

# Hàm gửi email xác nhận thanh toán thành công
async def send_payment_confirmation_email(
    recipient_email: str, 
    recipient_name: str,
    transaction_id: str,
    amount: float,
    payee_mssv: str,
    payee_name: str,
    new_balance: float,
    new_debt: float = None,
    is_self_payment: bool = False
):
    """Gửi email xác nhận thanh toán thành công"""
    try:
        # Lấy credentials
        creds = get_gmail_credentials()
        
        # Tạo Gmail service
        service = build('gmail', 'v1', credentials=creds)
        
        # Lấy sender email từ .env
        sender_email = os.getenv("SENDER_EMAIL")
        if not sender_email:
            raise HTTPException(status_code=500, detail="SENDER_EMAIL chưa được cấu hình trong .env")

        # Tạo email message
        message = MIMEMultipart('alternative')
        message['From'] = sender_email
        message['To'] = recipient_email
        message['Subject'] = '✅ Giao dịch thành công - IBanking System'
        
        # Định dạng số tiền
        formatted_amount = f"{amount:,.0f}".replace(",", ".")
        formatted_balance = f"{new_balance:,.0f}".replace(",", ".")
        
        # Tạo thông tin về debt nếu có
        debt_info = ""
        if new_debt is not None:
            formatted_debt = f"{new_debt:,.0f}".replace(",", ".")
            debt_info = f"""
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>Số dư công nợ mới:</strong></td>
                <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right;">{formatted_debt} VNĐ</td>
            </tr>
            """
        
        # Xác định loại giao dịch
        transaction_type = "Thanh toán công nợ bản thân" if is_self_payment else "Thanh toán công nợ"
        
        # HTML body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 20px auto; background-color: #ffffff; 
                             border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); 
                          padding: 30px 20px; text-align: center; color: white; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .success-icon {{ font-size: 48px; margin-bottom: 10px; }}
                .content {{ padding: 30px 20px; }}
                .info-box {{ background-color: #f9f9f9; border-left: 4px solid #4CAF50; 
                            padding: 15px; margin: 20px 0; border-radius: 5px; }}
                .info-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                .info-table td {{ padding: 10px; border-bottom: 1px solid #eee; }}
                .amount {{ font-size: 28px; color: #4CAF50; font-weight: bold; text-align: center; 
                          padding: 20px; background-color: #f0f9f0; border-radius: 5px; margin: 20px 0; }}
                .footer {{ background-color: #f5f5f5; padding: 20px; text-align: center; 
                          color: #999; font-size: 12px; }}
                .button {{ display: inline-block; padding: 12px 30px; background-color: #4CAF50; 
                          color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div class="success-icon">✅</div>
                    <h1>Giao dịch thành công!</h1>
                </div>
                
                <div class="content">
                    <p>Xin chào <strong>{recipient_name}</strong>,</p>
                    <p>Giao dịch của bạn đã được xử lý thành công.</p>
                    
                    <div class="info-box">
                        <strong>📋 Chi tiết giao dịch</strong>
                    </div>
                    
                    <table class="info-table">
                        <tr>
                            <td><strong>Loại giao dịch:</strong></td>
                            <td style="text-align: right;">{transaction_type}</td>
                        </tr>
                        <tr>
                            <td><strong>Mã giao dịch:</strong></td>
                            <td style="text-align: right; font-family: monospace;">{transaction_id[:16]}...</td>
                        </tr>
                        <tr>
                            <td><strong>Người nhận:</strong></td>
                            <td style="text-align: right;">{payee_name} ({payee_mssv})</td>
                        </tr>
                        <tr>
                            <td><strong>Thời gian:</strong></td>
                            <td style="text-align: right;">{datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M:%S')} UTC</td>
                        </tr>
                    </table>
                    
                    <div class="amount">
                        💰 {formatted_amount} VNĐ
                    </div>
                    
                    <div class="info-box">
                        <strong>💳 Thông tin tài khoản sau giao dịch</strong>
                    </div>
                    
                    <table class="info-table">
                        <tr>
                            <td><strong>Số dư khả dụng:</strong></td>
                            <td style="padding: 10px; border-bottom: 1px solid #eee; text-align: right; color: #4CAF50; font-weight: bold;">{formatted_balance} VNĐ</td>
                        </tr>
                        {debt_info}
                    </table>
                    
                    <p style="color: #666; font-size: 14px; margin-top: 20px;">
                        ℹ️ Nếu bạn không thực hiện giao dịch này, vui lòng liên hệ với chúng tôi ngay lập tức.
                    </p>
                </div>
                
                <div class="footer">
                    <p><strong>IBanking System</strong></p>
                    <p>Cảm ơn bạn đã sử dụng dịch vụ của chúng tôi!</p>
                    <p>© 2025 IBanking System. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Text body (fallback)
        text_body = f"""
        ✅ GIAO DỊCH THÀNH CÔNG
        
        Xin chào {recipient_name},
        
        Giao dịch của bạn đã được xử lý thành công.
        
        CHI TIẾT GIAO DỊCH:
        -------------------
        Loại giao dịch: {transaction_type}
        Mã giao dịch: {transaction_id}
        Người nhận: {payee_name} ({payee_mssv})
        Số tiền: {formatted_amount} VNĐ
        Thời gian: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M:%S')} UTC
        
        THÔNG TIN TÀI KHOẢN:
        --------------------
        Số dư khả dụng: {formatted_balance} VNĐ
        {"Số dư công nợ: " + formatted_debt + " VNĐ" if new_debt is not None else ""}
        
        Nếu bạn không thực hiện giao dịch này, vui lòng liên hệ với chúng tôi ngay.
        
        Cảm ơn bạn đã sử dụng IBanking System!
        © 2025 IBanking System
        """
        
        # Attach both text and HTML versions
        message.attach(MIMEText(text_body, 'plain'))
        message.attach(MIMEText(html_body, 'html'))
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        # Gửi email
        send_result = service.users().messages().send(
            userId='me',
            body={'raw': raw_message}
        ).execute()
        
        print(f"✓ Email xác nhận đã được gửi đến {recipient_email} (Message ID: {send_result['id']})")
        return True
        
    except Exception as e:
        print(f"⚠️ Không thể gửi email xác nhận: {e}")
        # Không raise exception vì thanh toán đã thành công
        return False

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

    # Gửi OTP qua email (Gmail API)
    await send_otp_email(payer["email"], code)

    return OTPResponse(transaction_id=transaction_id)

# Pay Route
# Pay Route với cải tiến xử lý xung đột
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
    max_retries = 5  # Tăng số lần retry
    retry_delay = 0.1
    
    # ===== THÊM: DISTRIBUTED LOCK (Optional) =====
    # Sử dụng Redis hoặc MongoDB để lock payee khi đang update
    lock_key = f"payment_lock:{transaction['mssv']}"
    lock_timeout = 10  # seconds
    
    # Biến để lưu kết quả cuối cùng
    final_payer_result = None
    final_payee_result = None

    if is_self_payment:
        # =====================================================
        # TRƯỜNG HỢP 1: THANH TOÁN BẢN THÂN
        # =====================================================
        for attempt in range(max_retries):
            # Lấy dữ liệu mới nhất của payer
            payer_fresh = await db.students.find_one({"_id": payer["_id"]})
            if not payer_fresh:
                raise HTTPException(status_code=404, detail="Payer not found after retry")

            # Kiểm tra điều kiện trước khi update
            if payer_fresh["balance"] < amount:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Insufficient balance: current={payer_fresh['balance']}, required={amount}"
                )
            
            if payer_fresh["debt"] < amount:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient debt to pay: current={payer_fresh['debt']}, required={amount}"
                )

            # Atomic update với version check
            update_result = await db.students.find_one_and_update(
                {
                    "_id": payer["_id"],
                    "version": payer_fresh["version"],
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
                final_payer_result = update_result
                
                # Gửi email xác nhận
                await send_payment_confirmation_email(
                    recipient_email=payer["email"],
                    recipient_name=payer["name"],
                    transaction_id=request.transaction_id,
                    amount=amount,
                    payee_mssv=payer["mssv"],
                    payee_name=payer["name"],
                    new_balance=update_result["balance"],
                    new_debt=update_result["debt"],
                    is_self_payment=True
                )
                break
            
            # Retry với exponential backoff
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (2 ** attempt))  # 0.1s, 0.2s, 0.4s, 0.8s, 1.6s
                continue
            
            raise HTTPException(
                status_code=409,  # Conflict
                detail=f"Transaction failed after {max_retries} attempts due to concurrent updates. Please try again."
            )
    
    else:
        # =====================================================
        # TRƯỜNG HỢP 2: THANH TOÁN CHO NGƯỜI KHÁC
        # =====================================================
        payee = await db.students.find_one({"mssv": transaction["mssv"]})
        if not payee:
            raise HTTPException(status_code=404, detail="Payee not found")

        # BƯỚC 1: CẬP NHẬT PAYEE (người nhận) - QUAN TRỌNG NHẤT
        allow_partial_payment = True  # Cho phép thanh toán một phần
        actual_payment_amount = amount  # Số tiền thực tế sẽ thanh toán
        
        for attempt in range(max_retries):
            # Lấy dữ liệu mới nhất của payee
            payee_fresh = await db.students.find_one({"mssv": transaction["mssv"]})
            if not payee_fresh:
                raise HTTPException(status_code=404, detail="Payee not found after retry")

            # Kiểm tra debt trước khi update
            if payee_fresh["debt"] < amount:
                if not allow_partial_payment:
                    # Từ chối hoàn toàn
                    if payee_fresh["debt"] == 0:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Payment rejected: The debt for student {transaction['mssv']} has been fully paid by another user. Current debt: 0 VND"
                        )
                    else:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Payment rejected: The debt for student {transaction['mssv']} is now {payee_fresh['debt']:,.0f} VND (less than your payment amount {amount:,.0f} VND). Another user may have made a partial payment."
                        )
                else:
                    # Cho phép thanh toán một phần
                    if payee_fresh["debt"] == 0:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Payment rejected: The debt has been fully paid."
                        )
                    # Điều chỉnh số tiền thanh toán
                    actual_payment_amount = payee_fresh["debt"]
                    print(f"⚠️ Adjusting payment: requested={amount:,.0f}, actual={actual_payment_amount:,.0f}")

            # Atomic update với version check cho payee
            payee_update = await db.students.find_one_and_update(
                {
                    "mssv": transaction["mssv"],
                    "version": payee_fresh["version"],
                    "debt": {"$gte": actual_payment_amount}  # Dùng actual_payment_amount
                },
                {
                    "$inc": {"debt": -actual_payment_amount, "version": 1}
                },
                return_document=ReturnDocument.AFTER
            )

            if payee_update:
                final_payee_result = payee_update
                print(f"✓ Payee updated: mssv={payee_update['mssv']}, new_debt={payee_update['debt']}, version={payee_update['version']}")
                break
            
            # Retry với exponential backoff
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (2 ** attempt))
                continue
            
            raise HTTPException(
                status_code=409,
                detail=f"Payee debt update failed after {max_retries} attempts due to concurrent updates. Please try again."
            )

        # BƯỚC 2: CẬP NHẬT PAYER (người trả)
        rollback_needed = False
        for attempt in range(max_retries):
            # Lấy dữ liệu mới nhất của payer
            payer_fresh = await db.students.find_one({"_id": payer["_id"]})
            if not payer_fresh:
                rollback_needed = True
                raise HTTPException(status_code=404, detail="Payer not found after retry")

            # Kiểm tra balance trước khi update
            if payer_fresh["balance"] < actual_payment_amount:  # Dùng actual_payment_amount
                rollback_needed = True
                raise HTTPException(
                    status_code=400,
                    detail=f"Payer balance insufficient: current={payer_fresh['balance']}, required={actual_payment_amount}"
                )

            # Atomic update với version check cho payer
            payer_update = await db.students.find_one_and_update(
                {
                    "_id": payer["_id"],
                    "version": payer_fresh["version"],
                    "balance": {"$gte": actual_payment_amount}  # Dùng actual_payment_amount
                },
                {
                    "$inc": {"balance": -actual_payment_amount, "version": 1},  # Dùng actual_payment_amount
                    "$set": {"transactions.$[elem].status": "success"}
                },
                array_filters=[{"elem.transaction_id": request.transaction_id}],
                return_document=ReturnDocument.AFTER
            )

            if payer_update:
                final_payer_result = payer_update
                print(f"✓ Payer updated: mssv={payer_update['mssv']}, new_balance={payer_update['balance']}, version={payer_update['version']}")
                
                # Gửi email xác nhận
                await send_payment_confirmation_email(
                    recipient_email=payer["email"],
                    recipient_name=payer["name"],
                    transaction_id=request.transaction_id,
                    amount=actual_payment_amount,  # Dùng actual_payment_amount
                    payee_mssv=payee["mssv"],
                    payee_name=payee["name"],
                    new_balance=payer_update["balance"],
                    new_debt=final_payee_result["debt"],
                    is_self_payment=False
                )
                break
            
            # Retry với exponential backoff
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (2 ** attempt))
                continue
            
            # Nếu hết retry, cần rollback payee
            rollback_needed = True
            raise HTTPException(
                status_code=409,
                detail=f"Payer balance update failed after {max_retries} attempts. Transaction rolled back."
            )
        
        # ROLLBACK: Nếu update payer thất bại, hoàn lại debt cho payee
        if rollback_needed and final_payee_result:
            print(f"⚠️ Rolling back payee debt...")
            max_rollback_retries = 3
            for rollback_attempt in range(max_rollback_retries):
                payee_current = await db.students.find_one({"mssv": transaction["mssv"]})
                if not payee_current:
                    print(f"❌ Rollback failed: payee not found")
                    break
                
                rollback_result = await db.students.find_one_and_update(
                    {
                        "mssv": transaction["mssv"],
                        "version": payee_current["version"]
                    },
                    {
                        "$inc": {"debt": actual_payment_amount, "version": 1}  # Dùng actual_payment_amount
                    },
                    return_document=ReturnDocument.AFTER
                )
                
                if rollback_result:
                    print(f"✓ Rollback successful: debt restored to {rollback_result['debt']}")
                    break
                
                if rollback_attempt < max_rollback_retries - 1:
                    await asyncio.sleep(0.1)
            else:
                print(f"❌ CRITICAL: Rollback failed after {max_rollback_retries} attempts. Manual intervention required!")
                # Log vào database hoặc alert admin
                await db.failed_rollbacks.insert_one({
                    "transaction_id": request.transaction_id,
                    "payee_mssv": transaction["mssv"],
                    "amount": amount,
                    "timestamp": datetime.now(timezone.utc),
                    "error": "Rollback failed"
                })

    # Xóa OTP sau khi hoàn tất
    await db.otps.delete_one({"transaction_id": request.transaction_id})

    print(f"✓ Transaction completed successfully for {payer['email']}")

    return PaymentResponse(
        success=True,
        balance=final_payer_result["balance"],
        debt=final_payer_result["debt"] if is_self_payment else None
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