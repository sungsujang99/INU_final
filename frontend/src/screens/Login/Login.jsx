import React, { useState } from "react";
import { Btn } from "../../components/Btn";
import { InputFieldIc } from "../../components/InputFieldIc";
import { Ic322Tone2 } from "../../icons/Ic322Tone2";
import "./style.css";
import { useNavigate } from "react-router-dom";

export const Login = () => {
  const navigate = useNavigate();
  const [loginId, setLoginId] = useState("");
  const [error, setError] = useState("");

  const handleLogin = async () => {
    if (!loginId.trim()) return;

    try {
      const response = await fetch('/api/check-user', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username: loginId.trim() })
      });

      if (response.ok) {
        localStorage.setItem('temp_login_id', loginId.trim());
        navigate('/login-password');
      } else {
        setError("존재하지 않는 사용자입니다.");
      }
    } catch (err) {
      console.error('Error checking user:', err);
      setError("서버 오류가 발생했습니다.");
    }
  };

  return (
    <div className="login">
      <div className="login-box-wrapper">
        <div className="login-box">
          <div className="overlap-group-3">
            <p className="div-4">
              <span className="text-wrapper-23">아이엔유로직스</span>
              <span className="text-wrapper-24">에 로그인</span>
            </p>

            <div className="text-wrapper-25">로그인ID를 입력하세요.</div>

            {error && <div className="error-message" style={{ color: 'red', textAlign: 'center', marginBottom: '10px' }}>{error}</div>}

            <div className="logo-2">
              <img
                className="INU-logistics-2"
                alt="Inu logistics"
                src="/img/inu-logistics-1.png"
              />

              <div className="group-7">
                <div className="ellipse-10" />
                <div className="ellipse-11" />
                <div className="ellipse-12" />
              </div>
            </div>

            <div className="field-btn">
              <InputFieldIc
                className="design-component-instance-node"
                override={<Ic322Tone2 className="ic-32-2tone-2" />}
                property1="active"
                text="login id"
                value={loginId}
                onChange={(value) => setLoginId(value)}
              />
              <Btn
                className="design-component-instance-node"
                property1="active"
                onClick={handleLogin}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
