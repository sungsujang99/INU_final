# INU Logistics

INU 물류 랙 제어 시스템입니다. React 프론트엔드, Flask 백엔드, SQLite 데이터베이스, Socket.IO 실시간 이벤트, USB 카메라 스트림, 시리얼 장비 제어가 함께 동작합니다.

## 목차

- [프로젝트 구조](#프로젝트-구조)
- [주요 실행 진입점](#주요-실행-진입점)
- [로컬 개발 실행](#로컬-개발-실행)
- [장비 및 배포 실행](#장비-및-배포-실행)
- [데이터베이스](#데이터베이스)
- [사용자 계정](#사용자-계정)
- [인증과 세션](#인증과-세션)
- [주요 API](#주요-api)
- [작업 처리 흐름](#작업-처리-흐름)
- [시리얼 장비 통신](#시리얼-장비-통신)
- [카메라](#카메라)
- [프론트엔드](#프론트엔드)
- [빌드와 점검](#빌드와-점검)
- [운영 문제 해결](#운영-문제-해결)
- [유지보수 주의사항](#유지보수-주의사항)
- [첫 인수 점검 체크리스트](#첫-인수-점검-체크리스트)

## 프로젝트 구조

```text
INU_final/
├── backend/                         Flask API, DB 초기화, 작업 큐, 시리얼/카메라 제어
├── frontend/                        Vite + React 화면
├── docs/                            설치, 세션, 단일 사용자 접근 관련 문서
├── database.db                      실제 기본 SQLite DB
├── requirements.txt                 루트 Python 패키지 목록
├── quick_start.sh                   라즈베리파이/리눅스 빠른 실행 스크립트
├── inu-logistics-backend.service    systemd 백엔드 서비스 예시
├── inu-logistics-frontend.service   systemd 프론트엔드 서비스 예시
├── debug_db.py                      루트 DB 점검 스크립트
└── test_api_fix.py                  API 점검 스크립트
```

관련 문서:

| 문서 | 용도 |
| --- | --- |
| [docs/RASPBERRY_PI_SETUP.md](docs/RASPBERRY_PI_SETUP.md) | 라즈베리파이 설치 안내 |
| [docs/SESSION_TROUBLESHOOTING.md](docs/SESSION_TROUBLESHOOTING.md) | 로그인/세션 문제 해결 |
| [docs/SINGLE_USER_ACCESS.md](docs/SINGLE_USER_ACCESS.md) | 단일 사용자 접근 정책 |
| [docs/README.md](docs/README.md) | 기존 인수인계 메모 |

## 주요 실행 진입점

| 구분 | 경로 |
| --- | --- |
| 백엔드 앱 | `backend/app.py` |
| 백엔드 DB 설정 | `backend/db.py` |
| 백엔드 인증 | `backend/auth.py` |
| 작업 큐 | `backend/task_queue.py` |
| 시리얼 통신 | `backend/serial_io.py` |
| 카메라 설정 | `backend/camera_config.py` |
| 프론트엔드 HTML | `frontend/index.html` |
| React 진입점 | `frontend/src/index.jsx` |
| React 라우터 | `frontend/src/App.jsx` |
| 프론트엔드 API 함수 | `frontend/src/lib/api.jsx` |
| Socket.IO 클라이언트 | `frontend/src/socket.js` |
| 백엔드 URL 자동 감지 | `frontend/src/config.js` |
| Vite 프록시 | `frontend/vite.config.js` |

## 로컬 개발 실행

### 1. 백엔드 실행

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
python -m backend.app
```

백엔드는 기본적으로 `0.0.0.0:5001`에서 실행됩니다.

Windows PowerShell에서는 가상환경 활성화 명령을 다음처럼 바꿉니다.

```powershell
.\venv\Scripts\Activate.ps1
```

하드웨어 없이 개발할 때는 [backend/app.py](backend/app.py)의 값을 `False`로 바꾸는 것을 고려합니다.

```python
SERIAL_COMMUNICATION_ENABLED = False
```

### 2. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

Vite 기본 주소는 `http://localhost:5173`입니다.

프론트엔드 개발 서버의 `/api` 요청은 [frontend/vite.config.js](frontend/vite.config.js)에 설정된 백엔드 주소로 프록시됩니다. 개발 PC나 장비 IP가 다르면 `VITE_BACKEND_URL` 또는 `vite.config.js`의 `target`을 실제 백엔드 주소로 맞춥니다.

## 장비 및 배포 실행

리눅스 또는 라즈베리파이에서는 루트의 [quick_start.sh](quick_start.sh)를 사용합니다.

```bash
./quick_start.sh
```

상세 설치는 [docs/RASPBERRY_PI_SETUP.md](docs/RASPBERRY_PI_SETUP.md)를 확인합니다.

systemd 배포 시 아래 파일의 경로와 사용자 계정을 실제 장비 환경에 맞게 수정해야 합니다.

| 파일 | 주의사항 |
| --- | --- |
| [inu-logistics-backend.service](inu-logistics-backend.service) | 예시 경로가 `/home/inu/INU_final` 기준입니다. |
| [inu-logistics-frontend.service](inu-logistics-frontend.service) | 예시 경로가 `/home/pi/inu_upgrade/frontend` 기준입니다. |

## 데이터베이스

실제 DB 경로는 [backend/db.py](backend/db.py)의 `DB_NAME`으로 결정됩니다.

```python
DB_NAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database.db")
```

기본 사용 DB는 루트의 [database.db](database.db)입니다. [backend/database.db](backend/database.db)도 존재하지만, 코드 기준 기본 DB는 루트 DB입니다.

백엔드 시작 시 `init_db()`가 테이블이 없으면 생성합니다.

| 테이블 | 용도 |
| --- | --- |
| `users` | 사용자 계정, 표시 이름, 비밀번호 해시, 권한 |
| `login_counter` | 로그인 횟수 카운터, 5회마다 `product_logs` 초기화 |
| `product_logs` | 입출고 요청 로그 |
| `current_inventory` | 현재 재고 상태 |
| `work_tasks` | 장비가 처리할 작업 큐 |
| `batch_task_links` | 업로드 배치와 작업 연결 |
| `camera_batch_history` | 카메라/작업 완료 이력 |

## 사용자 계정

사용자 생성 스크립트는 [backend/add_user.py](backend/add_user.py)입니다.

```bash
python -m backend.add_user
```

현재 스크립트에는 예시 계정이 하드코딩되어 있습니다.

| ID | 비밀번호 | 권한 |
| --- | --- | --- |
| `admin` | `admin123` | `admin` |
| `user1` | `user123` | `user` |
| `viewer1` | `viewer123` | `notouch` |

운영 전에는 반드시 비밀번호를 변경하거나 예시 계정을 제거합니다. 권한값은 `admin`, `user`, `notouch` 중 하나입니다.

## 인증과 세션

JWT 토큰은 프론트엔드 `localStorage`의 `inu_token`에 저장됩니다.

[backend/auth.py](backend/auth.py)는 전역 `current_active_session`으로 현재 활성 세션을 하나만 유지합니다. 새 로그인이 발생하면 이전 세션은 무효화됩니다. 서버 재시작 후 유효한 JWT가 오면 세션을 다시 설정하는 로직이 있습니다.

| API | 용도 |
| --- | --- |
| `POST /api/login` | 로그인 |
| `POST /api/check-user` | 사용자 존재 확인 |
| `POST /api/logout` | 로그아웃 |
| `GET /api/session-status` | 세션 상태 확인 |
| `GET /api/debug/session-info` | 세션 디버그 정보 |

주의할 점:

- [frontend/src/lib/api.jsx](frontend/src/lib/api.jsx)는 `inu_token`을 사용합니다.
- [frontend/src/api/client.ts](frontend/src/api/client.ts)는 `token`을 사용합니다.
- 실제 화면에서 주로 쓰는 쪽은 `frontend/src/lib/api.jsx`입니다.
- [backend/auth.py](backend/auth.py)의 `SECRET = "ChangeThisSecret!"`는 운영 환경에서 환경변수 기반 비밀키로 교체해야 합니다.

## 주요 API

백엔드 기본 포트는 `5001`입니다. 권한이 필요한 API는 `Authorization: Bearer <token>` 헤더가 필요합니다.

| Method | Endpoint | 설명 |
| --- | --- | --- |
| `GET` | `/api/ping` | 상태 확인 |
| `POST` | `/api/login` | 로그인 |
| `POST` | `/api/logout` | 로그아웃 |
| `GET` | `/api/session-status` | 현재 세션 확인 |
| `GET` | `/api/inventory` | 전체 재고 조회 |
| `GET` | `/api/inventory?rack=A` | 랙별 재고 조회 |
| `GET` | `/api/inventory?rack=A&slot=1` | 랙/슬롯 재고 조회 |
| `POST` | `/api/record` | 재고 기록 추가 및 작업 큐 등록 |
| `POST` | `/api/upload-tasks` | 작업 배열을 배치로 업로드 |
| `GET` | `/api/work-tasks?status=pending` | 작업 목록 조회 |
| `GET` | `/api/pending-task-counts` | 대기 중인 IN/OUT 작업 수 |
| `GET` | `/api/activity-logs` | 완료 작업 로그 |
| `GET` | `/api/camera-history` | 카메라 작업 이력 |
| `GET` | `/api/download-batch-task/<batch_id>` | 배치 CSV 다운로드 |
| `POST` | `/api/reset` | 장비 리셋 및 대기 큐 삭제 |
| `GET` | `/api/camera/<rack_id>/mjpeg_feed` | 랙 카메라 MJPEG 스트림 |
| `GET` | `/api/cameras/available` | 사용 가능한 카메라 조회 |
| `GET` | `/api/cameras/diagnostics` | 카메라 진단 |
| `GET` | `/api/optional-module/status` | 선택 모듈 상태 |
| `POST` | `/api/optional-module/activate` | 선택 모듈 활성화 |

## 작업 처리 흐름

1. 사용자가 프론트엔드에서 입고/출고 작업을 등록합니다.
2. 프론트엔드는 `/api/record` 또는 `/api/upload-tasks`로 작업 배열을 보냅니다.
3. [backend/inventory.py](backend/inventory.py)의 `add_records()`가 입력값을 검증하고 `product_logs`, `work_tasks`, `batch_task_links`에 기록합니다.
4. [backend/task_queue.py](backend/task_queue.py)의 백그라운드 worker가 `pending` 작업 하나를 `in_progress`로 선점합니다.
5. worker가 [backend/serial_io.py](backend/serial_io.py)의 `serial_mgr.send()`로 M 장비와 A/B/C 랙 장비에 명령을 보냅니다.
6. 장비가 echo와 완료 토큰을 보내면 작업을 `done`으로 변경합니다.
7. [backend/inventory_updater.py](backend/inventory_updater.py)가 `current_inventory`를 갱신합니다.
8. 완료 내역은 `camera_batch_history`에 저장되고 Socket.IO 이벤트로 화면이 갱신됩니다.

작업 중인 항목이 있거나 직전 완료 후 1초 이내이면 `/api/record`, `/api/upload-tasks`는 `429 busy`를 반환합니다.

## 시리얼 장비 통신

시리얼 통신은 [backend/serial_io.py](backend/serial_io.py)가 담당합니다.

| 항목 | 값 |
| --- | --- |
| Baud rate | `19200` |
| 장비 ID | `A`, `B`, `C`, `M` |
| 선택 모듈 ID | `I` |
| 식별 명령 | `WHO\n` |
| 일반 완료 토큰 | `done` |
| M 장비 완료 토큰 | `fin` |
| 리셋 명령 | `99` |

장비 탐색 포트:

| OS | 포트 |
| --- | --- |
| Linux | `/dev/ttyUSB*`, `/dev/ttyACM*` |
| macOS | `/dev/tty.usbserial*`, `/dev/tty.usbmodem*` |
| Windows | `COM1`부터 `COM20` |

작업 명령 규칙:

- M 장비 명령은 `rack_number * 100 + slot`입니다.
- 랙 번호는 `A=1`, `B=2`, `C=3`입니다.
- OUT 작업은 음수 명령을 사용합니다.
- 랙 장비 명령은 `slot` 번호입니다.
- 랙 장비의 OUT 작업은 음수 `slot`을 사용합니다.

[backend/app.py](backend/app.py)의 `SERIAL_COMMUNICATION_ENABLED`가 `True`이면 시작 시 장비를 탐색하고 발견된 랙을 리셋합니다.

## 카메라

카메라 설정은 [backend/camera_config.py](backend/camera_config.py)에 있습니다. 기본은 `/dev/v4l/by-path/...video-index0` 형식의 안정적인 USB 카메라 경로를 사용합니다.

운영 장비에서 카메라가 바뀌거나 USB 허브 위치가 바뀌면 다음 도구로 확인합니다.

```bash
cd backend
python list_usb_v4l_paths.py
python link_cameras.py --list
python link_cameras.py
```

진단 API:

- `/api/cameras/available`
- `/api/cameras/diagnostics`

스트림 API:

- `/api/camera/M/mjpeg_feed`
- `/api/camera/A/mjpeg_feed`
- `/api/camera/B/mjpeg_feed`
- `/api/camera/C/mjpeg_feed`

[quick_start.sh](quick_start.sh) 안의 예전 카메라 URL 예시는 `/api/camera/0/live_feed` 형식입니다. 현재 백엔드 라우트는 랙 ID 기반 `/api/camera/<rack_id>/mjpeg_feed`를 사용합니다.

## 프론트엔드

라우트는 [frontend/src/App.jsx](frontend/src/App.jsx)에서 정의합니다.

| 경로 | 화면 |
| --- | --- |
| `/` | `/login`으로 이동 |
| `/login` | 사용자 ID 확인 화면 |
| `/login-password` | 비밀번호 입력 화면 |
| `/dashboard` | 대시보드 |
| `/camera` | 카메라 화면 |
| `/work-status` | 작업 상태 화면 |
| 그 외 | `/login`으로 이동 |

`/dashboard`, `/camera`, `/work-status`는 `ProtectedRoute`를 거치며 `localStorage.inu_token`이 없으면 로그인으로 이동합니다.

프론트엔드 API/프록시 주의사항:

- [frontend/vite.config.js](frontend/vite.config.js)의 `/api` 프록시 기본 대상은 `http://192.168.0.37:5001`입니다.
- [frontend/src/config.js](frontend/src/config.js)는 브라우저 hostname 기준으로 `http://<현재호스트>:5001`을 만듭니다.
- 일부 API 함수는 상대경로 `/api/...`를 직접 사용합니다.
- Socket.IO는 `config.js`의 URL을 사용합니다.

## 빌드와 점검

### 프론트엔드 빌드

```bash
cd frontend
npm run build
```

### Storybook

```bash
cd frontend
npm run storybook
```

### 백엔드 점검 스크립트

```bash
cd backend
python check_setup.py
python test_db.py
python test_task.py
python test_usb_cameras.py
python test_camera_config.py
```

루트에도 [test_api_fix.py](test_api_fix.py), [debug_db.py](debug_db.py)가 있습니다.

## 운영 문제 해결

### 로그인이 갑자기 풀림

이 시스템은 `current_active_session` 하나만 유지합니다. 다른 브라우저나 다른 탭에서 새 로그인하면 이전 토큰은 `session_invalidated`로 거부됩니다.

자세한 내용은 [docs/SESSION_TROUBLESHOOTING.md](docs/SESSION_TROUBLESHOOTING.md)를 확인합니다.

### 카메라가 안 보임

확인 순서:

1. `/api/cameras/diagnostics` 응답 확인
2. [backend/camera_config.py](backend/camera_config.py)의 `by-path` 경로 확인
3. `python list_usb_v4l_paths.py` 실행
4. `python link_cameras.py`로 랙별 카메라 재매핑
5. Linux 권한 문제라면 서비스 사용자에게 `video` 그룹 권한 부여

### 장비가 움직이지 않음

확인 순서:

1. 백엔드 시작 로그에서 발견된 랙 ID 확인
2. `SERIAL_COMMUNICATION_ENABLED` 값 확인
3. 포트 권한 확인
4. 장비가 `WHO`에 `A`, `B`, `C`, `M`으로 응답하는지 확인
5. echo 실패와 `done`/`fin` timeout 로그 확인

### 작업 등록이 busy로 막힘

`work_tasks`에 `pending` 또는 `in_progress`가 남아 있거나 직전 완료 후 1초 이내이면 새 작업이 막힙니다.

아래 API로 상태를 확인합니다.

```text
/api/work-tasks?status=pending
/api/work-tasks?status=in_progress
```

## 유지보수 주의사항

- 디자인은 기존 Anima 산출물과 CSS에 강하게 묶여 있습니다. 요구가 없으면 화면 레이아웃, 색상, 크기, 이미지, CSS를 변경하지 않습니다.
- 인코딩이 깨진 한글 문자열이 여러 파일에 있습니다. 기능 변경과 무관하게 대량 수정하면 회귀 위험이 큽니다.
- 루트 [database.db](database.db)와 [backend/database.db](backend/database.db)가 모두 있으므로 실제 사용 DB는 항상 [backend/db.py](backend/db.py) 기준으로 확인합니다.
- [backend/auth.py](backend/auth.py)의 비밀키, [backend/add_user.py](backend/add_user.py)의 예시 비밀번호, service 파일의 절대 경로는 운영 전 반드시 환경에 맞게 정리합니다.
- 하드웨어 없이 개발할 때는 [backend/app.py](backend/app.py)의 `SERIAL_COMMUNICATION_ENABLED = False` 설정을 고려합니다.
- 프론트엔드 토큰 키가 `inu_token`과 `token`으로 혼재되어 있으므로 인증 관련 수정 시 실제 사용 컴포넌트를 먼저 확인합니다.
- [quick_start.sh](quick_start.sh)와 systemd 파일에는 현재 코드와 다른 오래된 경로나 URL 예시가 일부 남아 있습니다. 배포 전에 실제 장비 기준으로 확인합니다.

## 첫 인수 점검 체크리스트

- [ ] 백엔드가 `python -m backend.app`로 실행되는지 확인
- [ ] `http://localhost:5001/api/ping`에서 `pong` 확인
- [ ] 프론트엔드 `npm run dev` 실행
- [ ] 로그인 가능 여부 확인
- [ ] `/api/cameras/diagnostics` 확인
- [ ] 백엔드 로그에서 `A`/`B`/`C`/`M` 장비 탐색 여부 확인
- [ ] [database.db](database.db) 백업 후 테스트 작업 등록
