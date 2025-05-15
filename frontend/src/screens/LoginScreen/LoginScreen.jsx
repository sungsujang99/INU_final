import React, { useState, useEffect } from "react";
import { Btn } from "../../components/Btn";
import { InputFieldIc } from "../../components/InputFieldIc";
import { Property1Password } from "../../icons/Property1Password";
import "./style.css";
import { useNavigate } from "react-router-dom";
import { login, setToken } from "../../lib/api";

export const LoginScreen = () => {
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    // Check if we have the login ID from the previous step
    const loginId = localStorage.getItem('temp_login_id');
    if (!loginId) {
      navigate('/'); // Go back to first login page if no ID
    }
  }, [navigate]);

  const handleLogin = async () => {
    try {
      setError("");
      const loginId = localStorage.getItem('temp_login_id');
      const response = await login(loginId, password);
      setToken(response.token);
      localStorage.removeItem('temp_login_id'); // Clean up
      navigate('/dashboardu40onu41');
    } catch (err) {
      console.error('Login failed:', err);
      setError("비밀번호가 올바르지 않습니다.");
    }
  };

  return (
    <div className="login-screen">
      <div className="login-2">
        <div className="login-box-2">
          <div className="overlap-group-4">
            <p className="text-2">
              <span className="text-wrapper-26">아이엔유로직스</span>
              <span className="text-wrapper-27">에 로그인</span>
            </p>

            <div className="text-3">비밀번호를 입력해주세요.</div>

            <div className="logo-3">
              <img
                className="INU-logistics-3"
                alt="Inu logistics"
                src="/img/inu-logistics-2.png"
              />

              <div className="group-8">
                <div className="ellipse-13" />
                <div className="ellipse-14" />
                <div className="ellipse-15" />
              </div>
            </div>

            {error && <div className="error-message" style={{ color: 'red', textAlign: 'center', marginBottom: '10px' }}>{error}</div>}

            <div className="field-btn-2">
              <InputFieldIc
                className="design-component-instance-node-2"
                frameClassName="input-field-ic-instance"
                hasDiv={false}
                override={<Property1Password className="property-1-password" />}
                property1="default"
                text="password"
                type="password"
                value={password}
                onChange={(value) => setPassword(value)}
              />
              <Btn
                className="design-component-instance-node-2"
                divClassName="btn-instance"
                property1="active"
                text="Login"
                onClick={handleLogin}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
