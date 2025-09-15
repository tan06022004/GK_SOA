import React, { useState } from 'react';
import { useNavigate, /*useLocation*/ } from 'react-router-dom';
import './Dashboard.css';

const Dashboard = () => {
  const navigate = useNavigate();
  //const location = useLocation();
  //const username = location.state?.username || 'user123';

  const [fullName] = useState('Nguyễn Văn A');
  const [email] = useState('nguyenvana@email.com');
  const [phone] = useState('0123456789');
  const [balance, setBalance] = useState(50000000); // số dư khả dụng

  // Thông tin học phí
  const [studentId] = useState('TDTU123456');
  const [studentName] = useState('Nguyễn Văn A');
  const [tuitionFee] = useState(10000000);
  const [agree, setAgree] = useState(false);

  const handleLogout = () => {
    navigate('/');
  }

  const handlePayment = () => {
    if (!agree) {
      alert('Bạn cần đồng ý điều khoản trước khi thanh toán!');
      return;
    }
    if (balance < tuitionFee) {
      alert('Số dư không đủ để thanh toán học phí!');
      return;
    }
    setBalance(balance - tuitionFee);
    alert(`Thanh toán ${tuitionFee.toLocaleString()} VND học phí thành công!`);
  };

  return (
    <div className="dashboard-container">
      <div className="toolbar">
      <div className="toolbar-brand">Hệ thống thanh toán học phí</div>
      <div className="toolbar-nav">
        <button className="action-btn secondary" onClick={handleLogout}>
          Đăng xuất
        </button>
      </div>
    </div>
      
      {/* ================== FORM THANH TOÁN HỌC PHÍ ================== */}
      <div className="tuition-section">
        <h2>Thanh toán học phí</h2>

        {/* 1. Người nộp tiền */}
        <div className="form-block">
          <h3>Người nộp tiền</h3>
          <div className="info-row">
            <label>Họ và tên:</label>
            <input type="text" value={fullName} readOnly />
          </div>
          <div className="info-row">
            <label>Số điện thoại:</label>
            <input type="text" value={phone} readOnly />
          </div>
          <div className="info-row">
            <label>Email:</label>
            <input type="text" value={email} readOnly />
          </div>
        </div>

        {/* 2. Thông tin học phí */}
        <div className="form-block">
          <h3>Thông tin học phí</h3>
          <div className="info-row">
            <label>Mã số sinh viên:</label>
            <input type="text" value={studentId} readOnly />
          </div>
          <div className="info-row">
            <label>Tên sinh viên:</label>
            <input type="text" value={studentName} readOnly />
          </div>
          <div className="info-row">
            <label>Số tiền cần nộp:</label>
            <input type="text" value={`${tuitionFee.toLocaleString()} VND`} readOnly />
          </div>
        </div>

        {/* 3. Thông tin thanh toán */}
        <div className="form-block">
          <h3>Thông tin thanh toán</h3>
          <div className="info-row">
            <label>Số dư khả dụng:</label>
            <span>{balance.toLocaleString()} VND</span>
          </div>
          <div className="info-row">
            <label>Số tiền học phí:</label>
            <span>{tuitionFee.toLocaleString()} VND</span>
          </div>
          <div className="checkbox-row">
            <input
              type="checkbox"
              checked={agree}
              onChange={(e) => setAgree(e.target.checked)}
              id="terms"
            />
            <label htmlFor="terms">Tôi đồng ý với các điều khoản và điều kiện của hệ thống</label>
          </div>
        </div>

        {/* 4. Nút xác nhận */}
        <div >
          <button
            className="action-btn primary"
            disabled={!agree}
            onClick={handlePayment}
          >
            Xác nhận thanh toán
          </button>
        </div>
      </div>
      {/* =========================================================== */}
    </div>
  );
};

export default Dashboard;
