from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.schemas import OtpRequestIn, OtpRequestOut, OtpVerifyIn, OtpVerifyOut
from app.services import otp as otp_service
from app.sms import SmsProvider, get_sms_provider

router = APIRouter(prefix="/auth/otp", tags=["auth"])


@router.post("/request", response_model=OtpRequestOut, status_code=status.HTTP_201_CREATED)
def request_otp(
    payload: OtpRequestIn,
    db: DbSession = Depends(get_db),
    sms_provider: SmsProvider = Depends(get_sms_provider),
):
    try:
        otp_request = otp_service.request_otp(db, payload.phone_number, sms_provider)
    except otp_service.LockedOutError as exc:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "message": "phone number is locked out, try again later",
                "locked_until": exc.locked_until.isoformat(),
            },
        ) from exc
    return OtpRequestOut(phone_number=otp_request.phone_number, expires_at=otp_request.expires_at)


@router.post("/verify", response_model=OtpVerifyOut)
def verify_otp(payload: OtpVerifyIn, db: DbSession = Depends(get_db)):
    try:
        result = otp_service.verify_otp(db, payload.phone_number, payload.code)
    except otp_service.LockedOutError as exc:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "message": "phone number is locked out due to too many incorrect attempts",
                "locked_until": exc.locked_until.isoformat(),
            },
        ) from exc
    except otp_service.NoActiveOtpError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="no active OTP request for this phone number"
        ) from exc
    except otp_service.ExpiredOtpError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP has expired") from exc
    except otp_service.IncorrectOtpError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": "incorrect code",
                "attempts_remaining": exc.attempts_remaining,
            },
        ) from exc

    return OtpVerifyOut(verified=True, customer_id=result.customer_id, session_token=result.session_token)
