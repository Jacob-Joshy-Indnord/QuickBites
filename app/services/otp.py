import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models import Customer, OtpRequest, PhoneLockout
from app.models import Session as SessionModel
from app.sms import SmsProvider

OTP_LENGTH = 6
OTP_VALIDITY = timedelta(minutes=5)
MAX_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=30)


def utcnow() -> datetime:
    return datetime.utcnow()


def _hash_code(phone_number: str, code: str) -> str:
    return hashlib.sha256(f"{phone_number}:{code}".encode()).hexdigest()


def _generate_code() -> str:
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


class LockedOutError(Exception):
    def __init__(self, locked_until: datetime):
        self.locked_until = locked_until
        super().__init__(f"phone number locked until {locked_until.isoformat()}")


class OtpError(Exception):
    """Base class for OTP verification failures that are not a lockout."""


class NoActiveOtpError(OtpError):
    pass


class ExpiredOtpError(OtpError):
    pass


class IncorrectOtpError(OtpError):
    def __init__(self, attempts_remaining: int):
        self.attempts_remaining = attempts_remaining
        super().__init__(f"incorrect code, {attempts_remaining} attempts remaining")


def get_active_lockout(db: DbSession, phone_number: str, now: datetime | None = None) -> PhoneLockout | None:
    now = now or utcnow()
    lockout = db.get(PhoneLockout, phone_number)
    if lockout and lockout.locked_until > now:
        return lockout
    return None


def request_otp(
    db: DbSession,
    phone_number: str,
    sms_provider: SmsProvider,
    now: datetime | None = None,
) -> OtpRequest:
    now = now or utcnow()

    lockout = get_active_lockout(db, phone_number, now)
    if lockout:
        raise LockedOutError(lockout.locked_until)

    stmt = select(OtpRequest).where(
        OtpRequest.phone_number == phone_number,
        OtpRequest.consumed == False,  # noqa: E712
        OtpRequest.superseded == False,  # noqa: E712
    )
    for previous in db.scalars(stmt):
        previous.superseded = True

    code = _generate_code()
    otp_request = OtpRequest(
        phone_number=phone_number,
        code_hash=_hash_code(phone_number, code),
        created_at=now,
        expires_at=now + OTP_VALIDITY,
        attempts=0,
        max_attempts=MAX_ATTEMPTS,
    )
    db.add(otp_request)
    db.commit()
    db.refresh(otp_request)

    sms_provider.send(phone_number, f"Your QuickBites verification code is {code}")

    return otp_request


@dataclass
class VerifyResult:
    customer_id: str
    session_token: str


def _active_request(db: DbSession, phone_number: str) -> OtpRequest | None:
    stmt = (
        select(OtpRequest)
        .where(
            OtpRequest.phone_number == phone_number,
            OtpRequest.consumed == False,  # noqa: E712
            OtpRequest.superseded == False,  # noqa: E712
        )
        .order_by(OtpRequest.created_at.desc())
    )
    return db.scalars(stmt).first()


def verify_otp(
    db: DbSession,
    phone_number: str,
    code: str,
    now: datetime | None = None,
) -> VerifyResult:
    now = now or utcnow()

    lockout = get_active_lockout(db, phone_number, now)
    if lockout:
        raise LockedOutError(lockout.locked_until)

    otp_request = _active_request(db, phone_number)
    if otp_request is None:
        raise NoActiveOtpError()

    if otp_request.expires_at <= now:
        raise ExpiredOtpError()

    if otp_request.code_hash != _hash_code(phone_number, code):
        otp_request.attempts += 1
        if otp_request.attempts >= otp_request.max_attempts:
            otp_request.consumed = True
            locked_until = now + LOCKOUT_DURATION
            existing = db.get(PhoneLockout, phone_number)
            if existing:
                existing.locked_until = locked_until
            else:
                db.add(PhoneLockout(phone_number=phone_number, locked_until=locked_until))
            db.commit()
            raise LockedOutError(locked_until)
        db.commit()
        raise IncorrectOtpError(otp_request.max_attempts - otp_request.attempts)

    otp_request.consumed = True

    customer = db.scalars(select(Customer).where(Customer.phone_number == phone_number)).first()
    if customer is None:
        customer = Customer(phone_number=phone_number, phone_verified=True)
        db.add(customer)
    else:
        customer.phone_verified = True

    db.flush()

    session = SessionModel(customer_id=customer.id, created_at=now)
    db.add(session)
    db.commit()

    return VerifyResult(customer_id=customer.id, session_token=session.token)
