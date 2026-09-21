from app.models import Customer
from app.services import addresses as address_service


def _make_customer(db_session, phone="+919876543210"):
    customer = Customer(phone_number=phone, phone_verified=True)
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


class TestAddressCrud:
    def test_address_saved_with_geo_point_is_retrievable(self, db_session):
        customer = _make_customer(db_session)

        created = address_service.create_address(
            db_session,
            customer_id=customer.id,
            label="Home",
            full_text="221B Baker Street, Metro City",
            latitude=12.9716,
            longitude=77.5946,
            delivery_instructions="Leave with the security guard",
        )

        fetched = address_service.get_address(db_session, customer.id, created.id)
        assert fetched.label == "Home"
        assert fetched.full_text == "221B Baker Street, Metro City"
        assert fetched.latitude == 12.9716
        assert fetched.longitude == 77.5946
        assert fetched.delivery_instructions == "Leave with the security guard"

    def test_list_addresses_returns_all_for_customer(self, db_session):
        customer = _make_customer(db_session)
        address_service.create_address(
            db_session, customer.id, "Home", "Addr 1", 12.0, 77.0, None
        )
        address_service.create_address(
            db_session, customer.id, "Work", "Addr 2", 13.0, 78.0, None
        )

        addresses = address_service.list_addresses(db_session, customer.id)
        assert len(addresses) == 2

    def test_update_address_changes_fields(self, db_session):
        customer = _make_customer(db_session)
        address = address_service.create_address(
            db_session, customer.id, "Home", "Old text", 12.0, 77.0, None
        )

        updated = address_service.update_address(
            db_session, customer.id, address.id, full_text="New text", label=None
        )

        assert updated.full_text == "New text"
        assert updated.label == "Home"

    def test_delete_address_removes_it(self, db_session):
        customer = _make_customer(db_session)
        address = address_service.create_address(
            db_session, customer.id, "Home", "Addr", 12.0, 77.0, None
        )

        address_service.delete_address(db_session, customer.id, address.id)

        remaining = address_service.list_addresses(db_session, customer.id)
        assert remaining == []

    def test_deleting_default_promotes_another_address(self, db_session):
        customer = _make_customer(db_session)
        first = address_service.create_address(
            db_session, customer.id, "Home", "Addr 1", 12.0, 77.0, None
        )
        second = address_service.create_address(
            db_session, customer.id, "Work", "Addr 2", 13.0, 78.0, None
        )
        assert first.is_default is True

        address_service.delete_address(db_session, customer.id, first.id)

        remaining = address_service.get_address(db_session, customer.id, second.id)
        assert remaining.is_default is True


class TestDefaultAddress:
    def test_first_address_is_default_automatically(self, db_session):
        customer = _make_customer(db_session)

        address = address_service.create_address(
            db_session, customer.id, "Home", "Addr", 12.0, 77.0, None
        )

        assert address.is_default is True

    def test_only_one_default_address_at_a_time(self, db_session):
        customer = _make_customer(db_session)
        first = address_service.create_address(
            db_session, customer.id, "Home", "Addr 1", 12.0, 77.0, None
        )
        second = address_service.create_address(
            db_session, customer.id, "Work", "Addr 2", 13.0, 78.0, None
        )
        assert first.is_default is True
        assert second.is_default is False

        address_service.set_default_address(db_session, customer.id, second.id)

        addresses = {a.id: a for a in address_service.list_addresses(db_session, customer.id)}
        assert addresses[first.id].is_default is False
        assert addresses[second.id].is_default is True

    def test_setting_default_again_is_idempotent(self, db_session):
        customer = _make_customer(db_session)
        first = address_service.create_address(
            db_session, customer.id, "Home", "Addr 1", 12.0, 77.0, None
        )
        address_service.create_address(
            db_session, customer.id, "Work", "Addr 2", 13.0, 78.0, None
        )

        address_service.set_default_address(db_session, customer.id, first.id)

        addresses = address_service.list_addresses(db_session, customer.id)
        defaults = [a for a in addresses if a.is_default]
        assert len(defaults) == 1
        assert defaults[0].id == first.id


class TestAddressApi:
    def test_create_and_fetch_address_via_api(self, client, db_session):
        customer = _make_customer(db_session)

        create_response = client.post(
            f"/customers/{customer.id}/addresses",
            json={
                "label": "Home",
                "full_text": "221B Baker Street",
                "latitude": 12.9716,
                "longitude": 77.5946,
                "delivery_instructions": "Ring twice",
            },
        )
        assert create_response.status_code == 201
        address_id = create_response.json()["id"]

        get_response = client.get(f"/customers/{customer.id}/addresses/{address_id}")
        assert get_response.status_code == 200
        assert get_response.json()["label"] == "Home"

    def test_set_default_via_api_unsets_previous(self, client, db_session):
        customer = _make_customer(db_session)
        first = client.post(
            f"/customers/{customer.id}/addresses",
            json={"label": "Home", "full_text": "Addr 1", "latitude": 12.0, "longitude": 77.0},
        ).json()
        second = client.post(
            f"/customers/{customer.id}/addresses",
            json={"label": "Work", "full_text": "Addr 2", "latitude": 13.0, "longitude": 78.0},
        ).json()

        response = client.post(f"/customers/{customer.id}/addresses/{second['id']}/default")
        assert response.status_code == 200
        assert response.json()["is_default"] is True

        first_after = client.get(f"/customers/{customer.id}/addresses/{first['id']}").json()
        assert first_after["is_default"] is False
