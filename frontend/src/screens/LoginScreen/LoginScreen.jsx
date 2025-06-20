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
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  useEffect(() => {
    // Check if we have the login ID from the previous step
    const loginId = localStorage.getItem('temp_login_id');
    if (!loginId) {
      navigate('/'); // Go back to first login page if no ID
    }

    // Check if user is already logged in
    const existingToken = localStorage.getItem('inu_token');
    if (existingToken) {
      console.log('[LoginScreen] User already has a token, redirecting to dashboard');
      navigate('/dashboardu40onu41');
    }
  }, [navigate]);

  const handleLogin = async () => {
    if (isLoggingIn) {
      console.log('[LoginScreen] Login already in progress, ignoring duplicate attempt');
      return;
    }

    try {
      setIsLoggingIn(true);
      setError("");
      
      // Check if there's already a token (in case of multiple tabs)
      const existingToken = localStorage.getItem('inu_token');
      if (existingToken) {
        console.log('[LoginScreen] Token already exists, user might be logged in another tab');
        setError("이미 로그인되어 있습니다. 다른 탭을 확인해주세요.");
        setIsLoggingIn(false);
        return;
      }

      const loginId = localStorage.getItem('temp_login_id');
      console.log('[LoginScreen] Attempting login for user:', loginId);
      
      const response = await login(loginId, password);
      console.log('[LoginScreen] Login successful, setting token');
      
      setToken(response.token);
      localStorage.removeItem('temp_login_id'); // Clean up
      
      console.log('[LoginScreen] Redirecting to dashboard');
      navigate('/dashboardu40onu41');
    } catch (err) {
      console.error('Login failed:', err);
      setError("비밀번호가 올바르지 않습니다.");
    } finally {
      setIsLoggingIn(false);
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
            
            <div style={{ fontSize: '12px', color: '#666', textAlign: 'center', marginBottom: '10px' }}>
              ⚠️ 여러 탭에서 동시에 로그인하지 마세요
            </div>

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
                disabled={isLoggingIn}
              />
              <Btn
                className="design-component-instance-node-2"
                divClassName="btn-instance"
                property1={isLoggingIn ? "disabled" : "active"}
                text={isLoggingIn ? "로그인 중..." : "Login"}
                onClick={handleLogin}
                disabled={isLoggingIn}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
