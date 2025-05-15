import React from "react";
import { Btn } from "../../components/Btn";
import { InputFieldIc } from "../../components/InputFieldIc";
import { Ic322Tone2 } from "../../icons/Ic322Tone2";
import "./style.css";

export const DivWrapper = () => {
  return (
    <div className="div-wrapper">
      <div className="login-3">
        <div className="overlap-5">
          <div className="login-box-3">
            <div className="overlap-group-5">
              <p className="text-4">
                <span className="text-wrapper-28">아이엔유로직스</span>

                <span className="text-wrapper-29">에 로그인</span>
              </p>

              <div className="text-5">로그인ID를 입력하세요.</div>

              <div className="logo-4">
                <img
                  className="INU-logistics-4"
                  alt="Inu logistics"
                  src="/img/inu-logistics-2.png"
                />

                <div className="group-9">
                  <div className="ellipse-16" />

                  <div className="ellipse-17" />

                  <div className="ellipse-18" />
                </div>
              </div>

              <div className="field-btn-3">
                <InputFieldIc
                  className="input-field-ic-2"
                  override={<Ic322Tone2 className="property-1-id" />}
                  property1="error"
                />
                <Btn className="btn-2" property1="active" text="Next" />
              </div>
            </div>
          </div>

          <p className="text-error">
            존재하지 않는 아이디입니다. 다시 입력해주세요.
          </p>
        </div>
      </div>
    </div>
  );
};
