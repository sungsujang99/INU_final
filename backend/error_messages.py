"""
Error messages in Korean for the warehouse automation system.
"""

ERROR_MESSAGES = {
    # Authentication errors
    "token_required": "인증 토큰이 필요합니다",
    "token_expired": "인증 토큰이 만료되었습니다",
    "invalid_token": "유효하지 않은 인증 토큰입니다",
    "invalid_credentials": "잘못된 로그인 정보입니다",

    # Request format errors
    "json_body_required": "JSON 형식의 요청이 필요합니다",
    "invalid_data_format": "잘못된 데이터 형식입니다. 레코드 목록이 필요합니다",
    "invalid_request_body": "요청 본문은 JSON 작업 배열이어야 합니다",
    "no_tasks_provided": "요청에 작업이 포함되어 있지 않습니다",

    # Task and batch processing errors
    "failed_m_not_found": "메인 장비를 찾을 수 없습니다",
    "failed_rack_not_found": "랙을 찾을 수 없습니다",
    "failed_m_echo": "메인 장비 통신 오류",
    "failed_rack_echo": "랙 통신 오류",
    "failed_m_timeout": "메인 장비 응답 시간 초과",
    "failed_rack_timeout": "랙 응답 시간 초과",
    "failed_invalid_rack_for_m": "잘못된 랙 ID",
    "failed_unknown_movement": "알 수 없는 이동 유형",
    "failed_inventory_update": "재고 업데이트 실패",
    "failed_exception": "작업 처리 중 오류 발생",

    # Inventory errors
    "slot_occupied": "슬롯 {rack}-{slot}이(가) 이미 사용 중입니다",
    "multiple_in_operations": "슬롯 {rack}-{slot}에 대한 중복 입고 작업이 있습니다",
    "no_inventory": "슬롯 {rack}-{slot}에 재고가 없습니다",
    "multiple_out_operations": "슬롯 {rack}-{slot}에 대한 중복 출고 작업이 있습니다",
    "invalid_movement": "잘못된 이동 유형: {movement}",

    # Database errors
    "database_error": "데이터베이스 오류",
    "fetch_tasks_error": "작업 목록 조회 실패",
    "fetch_counts_error": "작업 수 조회 실패",
    "batch_not_found": "배치 ID를 찾을 수 없습니다",

    # General errors
    "unexpected_error": "예기치 않은 오류가 발생했습니다",
    "serial_disabled": "시리얼 통신이 비활성화되어 있습니다",
    "missing_racks": "연결되지 않은 랙: {racks}"
}

def get_error_message(error_code: str, **kwargs) -> str:
    """
    Get the Korean error message for the given error code.
    Optionally format the message with provided kwargs.
    """
    message = ERROR_MESSAGES.get(error_code, "알 수 없는 오류가 발생했습니다")
    if kwargs:
        try:
            return message.format(**kwargs)
        except KeyError:
            return message
    return message 