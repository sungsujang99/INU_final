NU Logistics 인수인계 문서
이 프로젝트는 INU 물류 랙 제어 시스템입니다. React 프론트엔드, Flask 백엔드, SQLite 데이터베이스, Socket.IO 실시간 이벤트, USB 카메라 스트림, 시리얼 통신 장비 제어가 함께 동작합니다.

1. 전체 구조
INU_final-master/
  backend/                         Flask API, DB 초기화, 작업 큐, 시리얼/카메라 제어
  frontend/                        Vite + React 화면
  database.db                      실제 SQLite DB 경로(db.py 기준)
  requirements.txt                 루트 Python 패키지 목록
  backend/requirements.txt         백엔드 중심 Python 패키지 목록
  quick_start.sh                   라즈베리파이/리눅스 빠른 실행 스크립트
  RASPBERRY_PI_SETUP.md            라즈베리파이 설치 안내
  SESSION_TROUBLESHOOTING.md       세션 문제 해결 문서
  SINGLE_USER_ACCESS.md            단일 사용자 접근 관련 문서
  inu-logistics-backend.service    systemd 백엔드 서비스 예시
  inu-logistics-frontend.service   systemd 프론트엔드 서비스 예시
2. 실행 진입점
백엔드: backend/app.py
프론트엔드 HTML: frontend/index.html
React 진입점: frontend/src/index.jsx
React 라우터: frontend/src/App.jsx
프론트엔드 API 함수: frontend/src/lib/api.jsx
Socket.IO 클라이언트: frontend/src/socket.js
백엔드 URL 자동 감지: frontend/src/config.js
Vite 프록시: frontend/vite.config.js
3. 로컬 개발 실행
백엔드
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
python -m backend.app
백엔드는 0.0.0.0:5001에서 실행됩니다. Windows PowerShell에서는 source venv/bin/activate 대신 .\venv\Scripts\Activate.ps1을 사용합니다.

프론트엔드
cd frontend
npm install
npm run dev -- --host 0.0.0.0
Vite 기본 주소는 http://localhost:5173입니다. 프론트엔드 개발 서버는 /api 요청을 frontend/vite.config.js의 target으로 프록시합니다.

4. 배포/장비 실행
리눅스/라즈베리파이에서는 quick_start.sh가 백엔드와 프론트엔드를 순서대로 실행합니다.
상세 설치는 RASPBERRY_PI_SETUP.md를 확인합니다.
systemd 배포 시 inu-logistics-backend.service, inu-logistics-frontend.service의 경로와 사용자 계정을 실제 장비 환경에 맞게 수정해야 합니다.
백엔드 서비스 예시는 /home/inu/INU_final, 프론트엔드 서비스 예시는 /home/pi/inu_upgrade/frontend를 가리키고 있어 현재 프로젝트 폴더명과 다를 수 있습니다.
5. 데이터베이스
실제 DB 경로는 backend/db.py의 DB_NAME으로 결정됩니다.

DB_NAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database.db")
따라서 기본 사용 DB는 루트의 database.db입니다. backend/database.db도 존재하지만 코드 기준 기본 DB는 루트 DB입니다.

주요 테이블:

users: 사용자 계정, 표시 이름, 비밀번호 해시, 권한
login_counter: 로그인 횟수 카운터, 5회마다 product_logs 초기화
product_logs: 입출고 요청 로그
current_inventory: 현재 재고 상태
work_tasks: 장비가 처리할 작업 큐
batch_task_links: 업로드 배치와 작업 연결
camera_batch_history: 카메라/작업 완료 이력
DB 스키마는 백엔드 시작 시 init_db()가 없으면 생성합니다.

6. 사용자 계정
사용자 생성 스크립트는 backend/add_user.py입니다.

python -m backend.add_user
현재 스크립트에는 예시 계정이 하드코딩되어 있습니다.

admin / admin123 / admin
user1 / user123 / user
viewer1 / viewer123 / notouch
운영 전에는 반드시 비밀번호를 변경하거나 스크립트의 예시 계정을 제거해야 합니다. 권한값은 admin, user, notouch 중 하나입니다.

7. 인증/세션
로그인 API: POST /api/login
사용자 확인 API: POST /api/check-user
로그아웃 API: POST /api/logout
세션 상태 API: GET /api/session-status
디버그 API: GET /api/debug/session-info
JWT 토큰은 프론트엔드에서 localStorage의 inu_token에 저장됩니다. 백엔드 auth.py는 전역 current_active_session으로 현재 활성 세션을 하나만 유지합니다. 새 로그인이 발생하면 이전 세션은 무효화됩니다. 서버 재시작 후 유효한 JWT가 오면 세션을 다시 설정하는 로직이 있습니다.

주의할 점:

frontend/src/lib/api.jsx는 inu_token을 사용합니다.
frontend/src/api/client.ts는 token을 사용합니다. 실제 화면에서 주로 쓰는 쪽은 lib/api.jsx입니다.
auth.py의 SECRET = "ChangeThisSecret!"는 운영 환경에서 환경변수 기반 비밀키로 교체해야 합니다.
8. 주요 API
백엔드 포트는 기본 5001입니다.

GET /api/ping: 상태 확인
POST /api/login: 로그인
POST /api/logout: 로그아웃
GET /api/session-status: 현재 세션 확인
GET /api/inventory: 전체 재고 조회
GET /api/inventory?rack=A: 랙별 재고 조회
GET /api/inventory?rack=A&slot=1: 랙/슬롯 재고 조회
POST /api/record: 재고 기록 추가 및 작업 큐 등록
POST /api/upload-tasks: 작업 배열을 배치로 업로드
GET /api/work-tasks?status=pending: 작업 목록 조회
GET /api/pending-task-counts: 대기 중 IN/OUT 작업 수
GET /api/activity-logs: 완료 작업 로그
GET /api/camera-history: 카메라 작업 이력
GET /api/download-batch-task/<batch_id>: 배치 CSV 다운로드
POST /api/reset: 장비 리셋 및 대기 큐 삭제
GET /api/camera/<rack_id>/mjpeg_feed: 랙 카메라 MJPEG 스트림
GET /api/cameras/available: 사용 가능한 카메라 조회
GET /api/cameras/diagnostics: 카메라 진단
GET /api/optional-module/status: 선택 모듈 상태
POST /api/optional-module/activate: 선택 모듈 활성화
권한이 필요한 API는 Authorization: Bearer <token> 헤더가 필요합니다.

9. 작업 처리 흐름
사용자가 프론트엔드에서 입고/출고 작업을 등록합니다.
프론트엔드는 /api/record 또는 /api/upload-tasks로 작업 배열을 보냅니다.
backend/inventory.py의 add_records()가 입력값을 검증하고 product_logs, work_tasks, batch_task_links에 기록합니다.
backend/task_queue.py의 백그라운드 worker가 pending 작업 하나를 in_progress로 선점합니다.
worker가 serial_io.py의 serial_mgr.send()로 M 장비와 A/B/C 랙 장비에 명령을 보냅니다.
장비가 echo와 완료 토큰을 보내면 작업을 done으로 변경합니다.
inventory_updater.py가 current_inventory를 갱신합니다.
완료 내역은 camera_batch_history에 저장되고 Socket.IO 이벤트로 화면이 갱신됩니다.
작업 중인 항목이 있거나 직전 완료 후 1초 이내이면 /api/record, /api/upload-tasks는 429 busy를 반환합니다.

10. 시리얼 장비 통신
시리얼 통신은 backend/serial_io.py가 담당합니다.

Baud rate: 19200
장비 ID: A, B, C, M
선택 모듈 ID: I
식별 명령: WHO\n
일반 완료 토큰: done
M 장비 완료 토큰: fin
리셋 명령: 99
장비 탐색 포트:

Linux: /dev/ttyUSB*, /dev/ttyACM*
macOS: /dev/tty.usbserial*, /dev/tty.usbmodem*
Windows: COM1부터 COM20
백엔드 app.py의 SERIAL_COMMUNICATION_ENABLED가 True이면 시작 시 장비를 탐색하고 발견된 랙을 리셋합니다. 하드웨어 없이 개발할 때는 이 값을 False로 바꾸면 됩니다.

작업 명령 규칙:

M 장비 명령: rack_number * 100 + slot
랙 번호: A=1, B=2, C=3
OUT 작업은 음수 명령을 사용합니다.
랙 장비 명령: slot 번호, OUT은 음수 slot
11. 카메라
카메라 설정은 backend/camera_config.py에 있습니다. 기본은 /dev/v4l/by-path/...video-index0 형식의 안정적인 USB 카메라 경로를 사용합니다.

운영 장비에서 카메라가 바뀌거나 USB 허브 위치가 바뀌면 다음 도구를 사용합니다.

cd backend
python list_usb_v4l_paths.py
python link_cameras.py --list
python link_cameras.py
진단 API:

/api/cameras/available
/api/cameras/diagnostics
스트림 API:

/api/camera/M/mjpeg_feed
/api/camera/A/mjpeg_feed
/api/camera/B/mjpeg_feed
/api/camera/C/mjpeg_feed
quick_start.sh 안의 예전 카메라 URL 예시는 /api/camera/0/live_feed 형식이라 현재 백엔드 라우트와 다릅니다. 현재 코드는 랙 ID 기반 /api/camera/<rack_id>/mjpeg_feed를 사용합니다.

12. 프론트엔드 라우트
라우트는 frontend/src/App.jsx에서 정의합니다.

/: /login으로 이동
/login: 사용자 ID 확인 화면
/login-password: 비밀번호 입력 화면
/dashboard: 대시보드
/camera: 카메라 화면
/work-status: 작업 상태 화면
그 외 경로: /login으로 이동
/dashboard, /camera, /work-status는 ProtectedRoute를 거치며 localStorage.inu_token이 없으면 로그인으로 이동합니다.

13. 프론트엔드 API/프록시 주의사항
frontend/vite.config.js의 /api 프록시 기본 대상은 http://192.168.0.37:5001입니다.
다른 PC나 장비에서 개발할 경우 VITE_BACKEND_URL 또는 vite.config.js의 target을 실제 백엔드 주소로 맞춰야 합니다.
frontend/src/config.js는 브라우저 hostname 기준으로 http://<현재호스트>:5001을 만듭니다.
일부 API 함수는 상대경로 /api/...를 직접 사용하고, Socket.IO는 config.js의 URL을 사용합니다.
14. 빌드와 테스트
프론트엔드 빌드:

cd frontend
npm run build
Storybook:

cd frontend
npm run storybook
백엔드 점검/테스트성 스크립트:

cd backend
python check_setup.py
python test_db.py
python test_task.py
python test_usb_cameras.py
python test_camera_config.py
루트에도 test_api_fix.py, debug_db.py가 있습니다.

15. 운영 중 자주 보는 증상
로그인이 갑자기 풀림
이 시스템은 current_active_session 하나만 유지합니다. 다른 브라우저나 다른 탭에서 새 로그인하면 이전 토큰은 session_invalidated로 거부됩니다. 자세한 내용은 SESSION_TROUBLESHOOTING.md를 확인합니다.

카메라가 안 보임
/api/cameras/diagnostics 확인
backend/camera_config.py의 by-path 경로 확인
python list_usb_v4l_paths.py 실행
python link_cameras.py로 랙별 카메라 재매핑
Linux 권한 문제면 서비스 사용자에게 video 그룹 권한 부여
장비가 움직이지 않음
백엔드 시작 로그에서 발견된 랙 ID 확인
SERIAL_COMMUNICATION_ENABLED 값 확인
포트 권한 확인
장비가 WHO에 A/B/C/M으로 응답하는지 확인
echo 실패와 done/fin timeout 로그 확인
작업 등록이 busy로 막힘
work_tasks에 pending 또는 in_progress가 남아 있거나 직전 완료 후 1초 이내일 때 새 작업이 막힙니다. 필요하면 /api/work-tasks?status=pending, /api/work-tasks?status=in_progress로 확인합니다.

16. 유지보수 주의사항
디자인은 기존 Anima 산출물과 CSS에 강하게 묶여 있습니다. 요구가 없으면 화면 레이아웃, 색상, 크기, 이미지, CSS를 변경하지 않습니다.
인코딩이 깨진 한글 문자열이 여러 파일에 있습니다. 기능 변경과 무관하게 대량 수정하면 회귀 위험이 큽니다.
루트 database.db와 backend/database.db가 모두 있으므로 실제 사용 DB가 어느 것인지 항상 backend/db.py 기준으로 확인합니다.
auth.py의 비밀키, add_user.py의 예시 비밀번호, 서비스 파일의 절대 경로는 운영 전 반드시 환경에 맞게 정리해야 합니다.
하드웨어 없이 개발할 때는 app.py의 SERIAL_COMMUNICATION_ENABLED = False 설정을 고려합니다.
프론트엔드 토큰 키가 inu_token과 token으로 혼재되어 있으므로 인증 관련 수정 시 실제 사용 컴포넌트를 먼저 확인합니다.
quick_start.sh와 systemd 파일에는 현재 코드와 다른 오래된 경로나 URL 예시가 일부 남아 있습니다. 배포 전에 실제 장비 기준으로 확인해야 합니다.
17. 빠른 점검 체크리스트
인수자가 처음 확인할 항목:

백엔드가 python -m backend.app로 뜨는지 확인
http://localhost:5001/api/ping에서 pong 확인
프론트엔드 npm run dev 실행
로그인 가능 여부 확인
/api/cameras/diagnostics 확인
백엔드 로그에서 A/B/C/M 장비 탐색 여부 확인
database.db 백업 후 테스트 작업 등록
작업 완료 후 current_inventory, work_tasks, camera_batch_history 갱신 확인
