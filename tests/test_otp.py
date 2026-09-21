from datetime import timedelta

import pytest

from app.models import Customer
from app.services import otp as otp_service


def _get_sent_code(fake_sms, phone_number):
    message = next(msg for (phone, msg) in fake_sms.sent if phone == phone_number)
    return message.rsplit(" ", 1)[-1]


class TestGenerateOtp:
    def test_generates_six_digit_code_valid_for_five_minutes(self, db_session, fake_sms):
        phone = "+919876543210"

        otp_request = otp_service.request_otp(db_session, phone, fake_sms)

        code = _get_sent_code(fake_sms, phone)
        assert len(code) == 6
        assert code.isdigit()
        assert otp_request.expires_at - otp_request.created_at == timedelta(minutes=5)

    def test_delivers_via_sms_provider(self, db_session, fake_sms):
        phone = "+919876543210"

        otp_service.request_otp(db_session, phone, fake_sms)

        assert len(fake_sms.sent) == 1
        assert fake_sms.sent[0][0] == phone

    def test_new_request_supersedes_previous_active_request(self, db_session, fake_sms):
        phone = "+919876543210"

        first = otp_service.request_otp(db_session, phone, fake_sms)
        second = otp_service.request_otp(db_session, phone, fake_sms)

        db_session.refresh(first)
        assert first.superseded is True
        assert second.superseded is False


class TestVerifyOtp:
    def test_correct_code_within_validity_verifies_and_creates_session(self, db_session, fake_sms):
        phone = "+919876543210"
        otp_service.request_otp(db_session, phone, fake_sms)
        code = _get_sent_code(fake_sms, phone)

        result = otp_service.verify_otp(db_session, phone, code)

        assert result.session_token
        customer = db_session.get(Customer, result.customer_id)
        assert customer.phone_verified is True
        assert customer.phone_number == phone

    def test_expired_code_is_rejected(self, db_session, fake_sms):
        phone = "+919876543210"
        otp_service.request_otp(db_session, phone, fake_sms)
        code = _get_sent_code(fake_sms, phone)
        later = otp_service.utcnow() + timedelta(minutes=5, seconds=1)

        with pytest.raises(otp_service.ExpiredOtpError):
            otp_service.verify_otp(db_session, phone, code, now=later)

    def test_five_incorrect_attempts_trigger_thirty_minute_lockout(self, db_session, fake_sms):
        phone = "+919876543210"
        otp_service.request_otp(db_session, phone, fake_sms)

        for _ in range(4):
            with pytest.raises(otp_service.IncorrectOtpError):
                otp_service.verify_otp(db_session, phone, "000000")

        now = otp_service.utcnow()
        with pytest.raises(otp_service.LockedOutError) as exc_info:
            otp_service.verify_otp(db_session, phone, "000000", now=now)

        assert exc_info.value.locked_until - now == timedelta(minutes=30)

    def test_lockout_blocks_further_attempts_even_with_correct_code(self, db_session, fake_sms):
        phone = "+919876543210"
        otp_service.request_otp(db_session, phone, fake_sms)
        code = _get_sent_code(fake_sms, phone)

        for _ in range(5):
            with pytest.raises((otp_service.IncorrectOtpError, otp_service.LockedOutError)):
                otp_service.verify_otp(db_session, phone, "000000")

        with pytest.raises(otp_service.LockedOutError):
            otp_service.verify_otp(db_session, phone, code)

    def test_lockout_also_blocks_new_otp_requests(self, db_session, fake_sms):
        phone = "+919876543210"
        otp_service.request_otp(db_session, phone, fake_sms)
        for _ in range(5):
            with pytest.raises((otp_service.IncorrectOtpError, otp_service.LockedOutError)):
                otp_service.verify_otp(db_session, phone, "000000")

        with pytest.raises(otp_service.LockedOutError):
            otp_service.request_otp(db_session, phone, fake_sms)

    def test_lockout_expires_after_thirty_minutes(self, db_session, fake_sms):
        phone = "+919876543210"
        otp_service.request_otp(db_session, phone, fake_sms)
        for _ in range(5):
            with pytest.raises((otp_service.IncorrectOtpError, otp_service.LockedOutError)):
                otp_service.verify_otp(db_session, phone, "000000")

        after_lockout = otp_service.utcnow() + timedelta(minutes=30, seconds=1)
        # A fresh OTP request should succeed once the lockout window has passed.
        otp_service.request_otp(db_session, phone, fake_sms, now=after_lockout)

    def test_verify_without_pending_request_raises(self, db_session, fake_sms):
        with pytest.raises(otp_service.NoActiveOtpError):
            otp_service.verify_otp(db_session, "+919876543210", "123456")


class TestOtpApi:
    def test_request_and_verify_round_trip(self, client, fake_sms):
        phone = "+919876543210"

        response = client.post("/auth/otp/request", json={"phone_number": phone})
        assert response.status_code == 201

        code = _get_sent_code(fake_sms, phone)
        verify_response = client.post(
            "/auth/otp/verify", json={"phone_number": phone, "code": code}
        )
        assert verify_response.status_code == 200
        body = verify_response.json()
        assert body["verified"] is True
        assert body["customer_id"]
        assert body["session_token"]

    def test_verify_wrong_code_returns_401(self, client, fake_sms):
        phone = "+919876543210"
        client.post("/auth/otp/request", json={"phone_number": phone})

        response = client.post(
            "/auth/otp/verify", json={"phone_number": phone, "code": "000000"}
        )
        assert response.status_code == 401

    def test_lockout_returns_423(self, client, fake_sms):
        phone = "+919876543210"
        client.post("/auth/otp/request", json={"phone_number": phone})

        for _ in range(5):
            client.post("/auth/otp/verify", json={"phone_number": phone, "code": "000000"})

        response = client.post(
            "/auth/otp/verify", json={"phone_number": phone, "code": "000000"}
        )
        assert response.status_code == 423
