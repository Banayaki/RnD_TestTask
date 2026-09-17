from enum import StrEnum


class CommType(StrEnum):
    PUSH_CASHBACK = "push_cashback"
    SMS_CASHBACK = "sms_cashback"
    EMAIL_CASHBACK = "email_cashback"
    PUSH_CREDIT = "push_credit"
    SMS_REFINANCE = "sms_refinance"
    PUSH_SERVICE = "push_service"
    CALL_COLLECT = "call_collect"


class Channel(StrEnum):
    PUSH = "push"
    SMS = "sms"
    EMAIL = "email"
    CALL = "call"
