import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import './Dashboard.css';

const Dashboard = () => {
  const navigate = useNavigate();
  const { state } = useLocation();
  const initialUser = state?.user || JSON.parse(localStorage.getItem('user') || '{}');
  const [user, setUser] = useState(initialUser);
  const [mssv, setMssv] = useState('');
  const [studentInfo, setStudentInfo] = useState(null);
  const [amount, setAmount] = useState('');
  const [transactionId, setTransactionId] = useState('');
  const [otp, setOtp] = useState('');
  const [agree, setAgree] = useState(false);
  const [balance, setBalance] = useState(initialUser?.balance || 0);
  const [debt, setDebt] = useState(initialUser?.debt || 0);
  const [transactions, setTransactions] = useState([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showOtpForm, setShowOtpForm] = useState(false);
  const isMounted = useRef(true);
  const lastFetchRef = useRef(0); // Theo dõi thời điểm gọi API cuối cùng

  // Hàm debounce để giới hạn tần suất gọi API
  const debounce = (func, wait) => {
    let timeout;
    return (...args) => {
      clearTimeout(timeout);
      timeout = setTimeout(() => func(...args), wait);
    };
  };

  // Lấy danh sách giao dịch
  const fetchTransactions = debounce(async () => {
      if (!user.id || Date.now() - lastFetchRef.current < 1000) return;
      lastFetchRef.current = Date.now();
      try {
        const response = await fetch(`http://localhost:8000/api/transaction/${user.id}`, {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Không thể lấy danh sách giao dịch');
        }

        const data = await response.json();
        if (isMounted.current) {
          setTransactions(data);
        }
      } catch (err) {
        if (isMounted.current) {
          setError(err.message || 'Không thể lấy danh sách giao dịch');
        }
        console.error('Fetch transactions failed:', err);
      }
    }, 1000);

  // Lấy thông tin sinh viên (không debounce trong handlePayment)
  const fetchStudentInfoDirect = async () => {
    if (!user.mssv) return;
    try {
      const response = await fetch(`http://localhost:8000/api/student/${user.mssv}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Không thể lấy thông tin sinh viên');
      }

      const data = await response.json();
      if (isMounted.current) {
        setDebt(data.debt);
        setUser(prevUser => {
          const updatedUser = { ...prevUser, debt: data.debt };
          localStorage.setItem('user', JSON.stringify(updatedUser));
          return updatedUser;
        });
      }
    } catch (err) {
      if (isMounted.current) {
        setError(err.message || 'Không thể lấy thông tin sinh viên');
      }
      console.error('Fetch student info failed:', err);
    }
  };

  // Lấy thông tin sinh viên với debounce cho useEffect
  const fetchStudentInfo = debounce(fetchStudentInfoDirect, 1000);

  // Gọi API khi component mount
  useEffect(() => {
  isMounted.current = true;
  if (user?.id && user?.mssv) {
    fetchTransactions();
    fetchStudentInfo();
  }

  return () => {
    isMounted.current = false;
  };
}, [fetchTransactions, fetchStudentInfo, user]);

  // Kiểm tra đăng nhập
  if (!user || !user.id) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <p>Vui lòng đăng nhập để xem thông tin</p>
        <button onClick={() => navigate('/')}>Đăng nhập</button>
      </div>
    );
  }

  // Xử lý đăng xuất
  const handleLogout = () => {
    localStorage.removeItem('user');
    navigate('/');
  };

  // Tìm kiếm sinh viên
  const handleSearchStudent = async () => {
    if (!mssv.trim()) {
      setError('Vui lòng nhập mã số sinh viên');
      return;
    }

    setIsLoading(true);
    setError('');
    setStudentInfo(null);

    try {
      const response = await fetch(`http://localhost:8000/api/student/${mssv}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Không tìm thấy sinh viên');
      }

      const data = await response.json();
      setStudentInfo(data);
      setAmount(data.debt.toString());
      setMessage('Tìm thấy thông tin sinh viên');
    } catch (err) {
      setError(err.message || 'Không thể tìm kiếm sinh viên');
      console.error('Search student failed:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Thanh toán cho bản thân
  const handlePayForSelf = async () => {
    setIsLoading(true);
    setError('');
    await fetchStudentInfoDirect(); // Lấy debt mới nhất
    setStudentInfo({
      mssv: user.mssv,
      name: user.name,
      debt: debt,
    });
    setAmount(debt.toString());
    setMssv(user.mssv);
    setMessage('Đã chọn thanh toán cho bản thân');
    setIsLoading(false);
  };

  // Tạo OTP
  const handleGenerateOTP = async () => {
    if (!studentInfo) {
      setError('Vui lòng chọn sinh viên hoặc thanh toán cho bản thân');
      return;
    }

    if (!amount || parseFloat(amount) <= 0) {
      setError('Số tiền không hợp lệ');
      return;
    }

    if (parseFloat(amount) > balance) {
      setError('Số dư không đủ để thanh toán');
      return;
    }

    if (parseFloat(amount) > studentInfo.debt) {
      setError('Số tiền thanh toán lớn hơn nợ của sinh viên');
      return;
    }

    if (!agree) {
      setError('Bạn cần đồng ý điều khoản trước khi thanh toán');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const response = await fetch('http://localhost:8000/api/otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_id: user.id,
          mssv: studentInfo.mssv,
          amount: parseFloat(amount),
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Không thể tạo OTP');
      }

      const data = await response.json();
      setTransactionId(data.transaction_id);
      setShowOtpForm(true);
      setMessage('OTP đã được gửi đến email của bạn. Vui lòng kiểm tra!');
    } catch (err) {
      setError(err.message || 'Không thể tạo OTP');
      console.error('Generate OTP failed:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Xác nhận thanh toán
  const handlePayment = async () => {
    if (!otp.trim()) {
      setError('Vui lòng nhập mã OTP');
      return;
    }

    if (!transactionId) {
      setError('Không tìm thấy mã giao dịch');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const response = await fetch('http://localhost:8000/api/pay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transaction_id: transactionId,
          otp: otp,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        let errorMessage = errorData.detail || 'Thanh toán thất bại';
        if (errorMessage.includes('Debt update failed')) {
          errorMessage = 'Thanh toán thất bại: Nợ của sinh viên không đủ hoặc có lỗi đồng bộ dữ liệu';
        } else if (errorMessage.includes('Invalid or expired OTP')) {
          errorMessage = 'Mã OTP không hợp lệ hoặc đã hết hạn';
        } else if (errorMessage.includes('Transaction failed')) {
          errorMessage = 'Thanh toán thất bại: Số dư hoặc nợ không đủ, hoặc lỗi đồng bộ dữ liệu';
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();
      console.log('Payment response:', data);

      if (data.success) {
        setBalance(data.balance);
        setMessage(`Thanh toán ${parseFloat(amount).toLocaleString()} VND học phí thành công!`);

        // Cập nhật debt từ phản hồi nếu có (cho thanh toán bản thân)
        if (data.debt !== null && data.debt !== undefined && studentInfo?.mssv === user.mssv) {
          setDebt(data.debt);
          setUser(prevUser => {
            const updatedUser = { ...prevUser, balance: data.balance, debt: data.debt };
            localStorage.setItem('user', JSON.stringify(updatedUser));
            return updatedUser;
          });
          setStudentInfo(prev => ({
            ...prev,
            debt: data.debt,
          }));
        }

        // Reset form
        setMssv('');
        setStudentInfo(null);
        setAmount('');
        setOtp('');
        setTransactionId('');
        setShowOtpForm(false);
        setAgree(false);

        // Fetch lại dữ liệu (tránh debounce)
        await Promise.all([fetchTransactions(), fetchStudentInfoDirect()]);
      }
    } catch (err) {
      setError(err.message || 'Thanh toán thất bại');
      console.error('Payment failed:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="dashboard-container">
      <div className="toolbar">
        <div className="toolbar-brand">Hệ thống thanh toán học phí</div>
        <div className="toolbar-nav">
          <span style={{ marginRight: '20px', color: '#fff' }}>
            Xin chào, {user.name || ''}
          </span>
          <button className="action-btn secondary" onClick={() => {
            fetchTransactions();
            fetchStudentInfo();
          }}>
            Làm mới thông tin
          </button>
          <button className="action-btn secondary" onClick={handleLogout}>
            Đăng xuất
          </button>
        </div>
      </div>

      {error && (
        <div className="error-message" style={{ margin: '20px', padding: '10px', background: '#fee', color: '#c00', borderRadius: '5px' }}>
          {error}
        </div>
      )}
      {message && (
        <div className="success-message" style={{ margin: '20px', padding: '10px', background: '#efe', color: '#060', borderRadius: '5px' }}>
          {message}
        </div>
      )}

      <div className="tuition-section">
        <h2>Thanh toán học phí</h2>

        <div className="form-block">
          <h3>Người nộp tiền</h3>
          <div className="info-row">
            <label>Họ và tên:</label>
            <input type="text" value={user.name || ''} readOnly />
          </div>
          <div className="info-row">
            <label>Số điện thoại:</label>
            <input type="text" value={user.phone || ''} readOnly />
          </div>
          <div className="info-row">
            <label>Email:</label>
            <input type="text" value={user.email || ''} readOnly />
          </div>
          <div className="info-row">
            <label>Số dư khả dụng:</label>
            <input type="text" value={`${balance.toLocaleString()} VND`} readOnly />
          </div>
          <div className="info-row">
            <label>Khoản nợ:</label>
            <input type="text" value={`${debt.toLocaleString()} VND`} readOnly />
          </div>
        </div>

        <div className="form-block">
          <h3>Thông tin sinh viên</h3>
          <div className="info-row">
            <label>Mã số sinh viên:</label>
            <input
              type="text"
              value={mssv}
              onChange={(e) => setMssv(e.target.value)}
              placeholder="Nhập MSSV (VD: 522H0042)"
              disabled={showOtpForm}
            />
            <button
              className="action-btn secondary"
              onClick={handleSearchStudent}
              disabled={isLoading || showOtpForm}
              style={{ marginLeft: '10px' }}
            >
              {isLoading ? 'Đang tìm...' : 'Tìm kiếm'}
            </button>
            <button
              className="action-btn secondary"
              onClick={handlePayForSelf}
              disabled={isLoading || showOtpForm}
              style={{ marginLeft: '10px' }}
            >
              Thanh toán cho bản thân
            </button>
          </div>

          {studentInfo && (
            <>
              <div className="info-row">
                <label>Tên sinh viên:</label>
                <input type="text" value={studentInfo.name || ''} readOnly />
              </div>
              <div className="info-row">
                <label>Số tiền học phí cần nộp:</label>
                <input type="text" value={`${(studentInfo.debt || 0).toLocaleString()} VND`} readOnly />
              </div>
            </>
          )}
        </div>

        {studentInfo && (
          <div className="form-block">
            <h3>Thông tin thanh toán</h3>
            <div className="info-row">
              <label>Số tiền thanh toán:</label>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="Nhập số tiền"
                disabled={showOtpForm}
                min="0"
                max={studentInfo.debt}
              />
            </div>
            <div className="checkbox-row">
              <input
                type="checkbox"
                checked={agree}
                onChange={(e) => setAgree(e.target.checked)}
                id="terms"
                disabled={showOtpForm}
              />
              <label htmlFor="terms">
                Tôi đồng ý với các điều khoản và điều kiện của hệ thống
              </label>
            </div>
          </div>
        )}

        {showOtpForm && (
          <div className="form-block">
            <h3>Xác thực OTP</h3>
            <div className="info-row">
              <label>Mã OTP:</label>
              <input
                type="text"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                placeholder="Nhập mã OTP từ email"
                maxLength="8"
              />
            </div>
            <p style={{ fontSize: '14px', color: '#666', marginTop: '10px' }}>
              Mã OTP đã được gửi đến email: {user.email || ''}
            </p>
          </div>
        )}

        <div style={{ marginTop: '20px' }}>
          {!showOtpForm ? (
            <button
              className="action-btn primary"
              disabled={!studentInfo || !agree || isLoading}
              onClick={handleGenerateOTP}
            >
              {isLoading ? 'Đang xử lý...' : 'Tạo mã OTP'}
            </button>
          ) : (
            <div>
              <button
                className="action-btn primary"
                disabled={isLoading || !otp}
                onClick={handlePayment}
                style={{ marginRight: '10px' }}
              >
                {isLoading ? 'Đang thanh toán...' : 'Xác nhận thanh toán'}
              </button>
              <button
                className="action-btn secondary"
                onClick={() => {
                  setShowOtpForm(false);
                  setOtp('');
                  setTransactionId('');
                }}
                disabled={isLoading}
              >
                Hủy
              </button>
            </div>
          )}
        </div>

        <div className="form-block" style={{ marginTop: '40px' }}>
          <h3>Lịch sử giao dịch</h3>
          {transactions.length > 0 ? (
            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '10px' }}>
              <thead>
                <tr style={{ background: '#317257ff' }}>
                  <th style={{ border: '1px solid #ddd', padding: '8px' }}>ID Giao dịch</th>
                  <th style={{ border: '1px solid #ddd', padding: '8px' }}>MSSV</th>
                  <th style={{ border: '1px solid #ddd', padding: '8px' }}>Số tiền</th>
                  <th style={{ border: '1px solid #ddd', padding: '8px' }}>Trạng thái</th>
                  <th style={{ border: '1px solid #ddd', padding: '8px' }}>Thời gian</th>
                </tr>
              </thead>
              <tbody>
                {transactions.map((tx) => (
                  <tr key={tx.transaction_id}>
                    <td style={{ border: '1px solid #ddd', padding: '8px' }}>{tx.transaction_id}</td>
                    <td style={{ border: '1px solid #ddd', padding: '8px' }}>{tx.mssv}</td>
                    <td style={{ border: '1px solid #ddd', padding: '8px' }}>{tx.amount.toLocaleString()} VND</td>
                    <td style={{ border: '1px solid #ddd', padding: '8px' }}>
                      {tx.status === 'success' ? 'Thành công' : 'Đang chờ'}
                    </td>
                    <td style={{ border: '1px solid #ddd', padding: '8px' }}>
                      {new Date(tx.created_at).toLocaleString('vi-VN')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>Chưa có giao dịch nào.</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;