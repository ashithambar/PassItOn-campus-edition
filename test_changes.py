import re
import unittest
from datetime import date, timedelta

from app import create_app
from app.config import Config
from app.models import BorrowRequest, Category, HandoverRecord, Listing, Order, User, db
from sqlalchemy.orm import configure_mappers


class TestConfig(Config):
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False


class ListingSetupTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            admin = User(
                name="Test Administrator",
                email="admin@example.com",
                phone="1234567890",
                department="Administration",
                year_semester="Administration",
                college="Test Campus",
                role="admin",
            )
            admin.set_password("test-password")
            db.session.add(admin)
            db.session.commit()

        self.client.post(
            "/auth/login",
            data={"email": "admin@example.com", "password": "test-password"},
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def homepage_category_count(self, slug):
        response = self.client.get("/")
        card_pattern = (
            rb'<a href="[^"]*category='
            + re.escape(slug.encode())
            + rb'" class="category-card">(.*?)</a>'
        )
        card = re.search(card_pattern, response.data, re.DOTALL)
        self.assertIsNotNone(card, f"Homepage category card for {slug} was not rendered")
        count = re.search(rb"(\d+) items", card.group(1))
        self.assertIsNotNone(count, f"Homepage category count for {slug} was not rendered")
        return int(count.group(1))

    def create_buyer(self, email="buyer@example.com"):
        buyer = User(
            name="Test Buyer",
            email=email,
            phone="0987654321",
            department="Engineering",
            year_semester="Year 1",
            college="Test Campus",
            role="student",
        )
        buyer.set_password("buyer-password")
        db.session.add(buyer)
        return buyer

    def test_mapper_configuration_and_marketplace_routes(self):
        configure_mappers()
        with self.app.app_context():
            category = Category(name="Calculators", slug="calculators", icon="bi-calculator")
            buyer = User(
                name="Test Buyer",
                email="buyer@example.com",
                phone="0987654321",
                department="Engineering",
                year_semester="Year 1",
                college="Test Campus",
                role="student",
            )
            buyer.set_password("buyer-password")
            db.session.add_all([category, buyer])
            db.session.flush()
            seller = User.query.filter_by(email="admin@example.com").one()
            listing = Listing(
                seller_id=seller.id,
                category_id=category.id,
                title="Route Test Calculator",
                description="A working scientific calculator for route tests.",
                condition="Good",
                price=250,
                location="Campus Library",
                listing_type="sell_and_borrow",
                status="available",
            )
            db.session.add(listing)
            db.session.flush()
            order = Order(
                order_number="ORD-ROUTE-TEST",
                listing_id=listing.id,
                buyer_id=buyer.id,
                seller_id=seller.id,
                payment_method="cash",
                status="rejected",
            )
            db.session.add(order)
            db.session.commit()
            listing_id = listing.id
            order_id = order.id

        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/listings/buy").status_code, 200)
        self.assertEqual(self.client.get("/borrow/").status_code, 200)
        self.assertEqual(self.client.get("/dashboard/my-listings").status_code, 200)
        self.assertEqual(self.client.get("/borrow/requests").status_code, 200)

        self.client.get("/auth/logout")
        self.client.post(
            "/auth/login",
            data={"email": "buyer@example.com", "password": "buyer-password"},
        )
        self.assertEqual(self.client.get("/dashboard/my-listings").status_code, 200)
        self.assertEqual(self.client.get("/borrow/my").status_code, 200)
        self.assertEqual(self.client.get(f"/borrow/request/{listing_id}").status_code, 200)
        self.assertEqual(self.client.get(f"/orders/request/{listing_id}").status_code, 200)
        self.assertEqual(self.client.get(f"/orders/{order_id}").status_code, 200)

    def test_buy_request_accepts_available_items_and_rejects_sold_items(self):
        with self.app.app_context():
            category = Category(name="Books", slug="books", icon="bi-book")
            buyer = self.create_buyer()
            db.session.add(category)
            db.session.flush()
            seller = User.query.filter_by(email="admin@example.com").one()
            available = Listing(
                seller_id=seller.id,
                category_id=category.id,
                title="Available Book",
                description="A textbook available for purchase on campus.",
                condition="Good",
                price=100,
                location="Campus Library",
                listing_type="sell_only",
                status="available",
            )
            sold = Listing(
                seller_id=seller.id,
                category_id=category.id,
                title="Sold Book",
                description="A textbook that has already been sold.",
                condition="Used",
                price=50,
                location="Campus Library",
                listing_type="sell_only",
                status="sold",
            )
            db.session.add_all([available, sold])
            db.session.commit()
            available_id = available.id
            sold_id = sold.id
            buyer_id = buyer.id

        self.client.get("/auth/logout")
        self.client.post("/auth/login", data={"email": "buyer@example.com", "password": "buyer-password"})
        response = self.client.post(
            f"/orders/request/{available_id}",
            data={"payment_method": "cash", "notes": "Meet at the library"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your request has been submitted", response.data)
        with self.app.app_context():
            order = Order.query.filter_by(listing_id=available_id, buyer_id=buyer_id).one()
            self.assertEqual(order.status, "request_sent")
            self.assertEqual(order.payment.status, "pending")
            self.assertEqual(order.listing.status, "available")

        sold_response = self.client.get(f"/orders/request/{sold_id}")
        self.assertEqual(sold_response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(Order.query.filter_by(listing_id=sold_id).count(), 0)

    def test_borrow_request_acceptance_exclusion_and_return_workflow(self):
        with self.app.app_context():
            category = Category(name="Lab Tools", slug="lab-tools", icon="bi-tools")
            buyer = self.create_buyer()
            db.session.add(category)
            db.session.flush()
            seller = User.query.filter_by(email="admin@example.com").one()
            listing = Listing(
                seller_id=seller.id,
                category_id=category.id,
                title="Borrowable Meter",
                description="A lab meter available for temporary borrowing.",
                condition="Good",
                price=0,
                location="Engineering Lab",
                listing_type="borrow_only",
                status="available",
            )
            db.session.add(listing)
            db.session.commit()
            listing_id = listing.id
            buyer_id = buyer.id

        self.client.get("/auth/logout")
        self.client.post("/auth/login", data={"email": "buyer@example.com", "password": "buyer-password"})
        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=3)
        response = self.client.post(
            f"/borrow/request/{listing_id}",
            data={"start_date": start.isoformat(), "expected_return_date": end.isoformat()},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your borrowing request was sent", response.data)
        with self.app.app_context():
            borrow_request = BorrowRequest.query.filter_by(listing_id=listing_id).one()
            request_id = borrow_request.id
            self.assertEqual(borrow_request.status, "pending")
            self.assertEqual(borrow_request.active_listing_id, listing_id)
            self.assertEqual(borrow_request.listing.status, "reserved")

        unauthorized = self.client.post(f"/borrow/requests/{request_id}/accept")
        self.assertEqual(unauthorized.status_code, 403)

        self.client.get("/auth/logout")
        self.client.post("/auth/login", data={"email": "admin@example.com", "password": "test-password"})
        accepted = self.client.post(f"/borrow/requests/{request_id}/accept", follow_redirects=True)
        self.assertEqual(accepted.status_code, 200)
        with self.app.app_context():
            self.assertEqual(db.session.get(BorrowRequest, request_id).status, "approved")

        handed_over = self.client.post(f"/borrow/requests/{request_id}/mark-borrowed", follow_redirects=True)
        self.assertEqual(handed_over.status_code, 200)
        with self.app.app_context():
            borrow_request = db.session.get(BorrowRequest, request_id)
            self.assertEqual(borrow_request.status, "borrowed")
            self.assertEqual(borrow_request.listing.status, "borrowed")

        self.client.get("/auth/logout")
        self.client.post(
            "/auth/login",
            data={"email": "buyer@example.com", "password": "buyer-password"},
        )
        second_response = self.client.get(f"/borrow/request/{listing_id}")
        self.assertEqual(second_response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(BorrowRequest.query.filter_by(listing_id=listing_id).count(), 1)

        return_requested = self.client.post(
            f"/borrow/requests/{request_id}/request-return",
            follow_redirects=True,
        )
        self.assertEqual(return_requested.status_code, 200)
        self.client.get("/auth/logout")
        self.client.post("/auth/login", data={"email": "admin@example.com", "password": "test-password"})
        returned = self.client.post(
            f"/borrow/requests/{request_id}/confirm-return",
            follow_redirects=True,
        )
        self.assertEqual(returned.status_code, 200)
        with self.app.app_context():
            borrow_request = db.session.get(BorrowRequest, request_id)
            self.assertEqual(borrow_request.status, "returned")
            self.assertIsNone(borrow_request.active_listing_id)
            self.assertEqual(borrow_request.listing.status, "available")
            self.assertNotEqual(borrow_request.listing.status, "sold")

        with self.app.app_context():
            rejected_listing = Listing(
                seller_id=User.query.filter_by(email="admin@example.com").one().id,
                category_id=Category.query.filter_by(slug="lab-tools").one().id,
                title="Rejected Borrow Item",
                description="A second item used to test request rejection.",
                condition="Good",
                price=0,
                location="Engineering Lab",
                listing_type="borrow_only",
                status="available",
            )
            db.session.add(rejected_listing)
            db.session.commit()
            rejected_listing_id = rejected_listing.id
        self.client.get("/auth/logout")
        self.client.post("/auth/login", data={"email": "buyer@example.com", "password": "buyer-password"})
        self.client.post(
            f"/borrow/request/{rejected_listing_id}",
            data={"start_date": start.isoformat(), "expected_return_date": end.isoformat()},
        )
        with self.app.app_context():
            rejected_request_id = BorrowRequest.query.filter_by(listing_id=rejected_listing_id).one().id
        self.client.get("/auth/logout")
        self.client.post("/auth/login", data={"email": "admin@example.com", "password": "test-password"})
        rejected = self.client.post(
            f"/borrow/requests/{rejected_request_id}/reject",
            follow_redirects=True,
        )
        self.assertEqual(rejected.status_code, 200)
        with self.app.app_context():
            rejected_request = db.session.get(BorrowRequest, rejected_request_id)
            self.assertEqual(rejected_request.status, "rejected")
            self.assertIsNone(rejected_request.active_listing_id)
            self.assertEqual(rejected_request.listing.status, "available")

    def test_empty_store_and_missing_category_state(self):
        home = self.client.get("/")
        browse = self.client.get("/listings/")
        sell = self.client.get("/listings/create")

        self.assertEqual(home.status_code, 200)
        self.assertIn(b"0</div>", home.data)
        self.assertNotIn(b"25+", home.data)
        self.assertIn(b"No campus listings available right now.", home.data)
        self.assertIn(b"Showing 0 verified items", browse.data)
        self.assertIn(b'id="category_id" disabled', sell.data)
        self.assertIn(b"No categories available", sell.data)
        self.assertIn(b"Manage categories", sell.data)
        self.assertRegex(sell.data, re.compile(rb'<button[^>]*disabled[^>]*>'))

    def test_admin_category_is_selectable_and_saved_on_new_listing(self):
        admin_listings = self.client.get("/admin/listings")
        self.assertIn(b"Add Product", admin_listings.data)

        category_response = self.client.post(
            "/admin/categories",
            data={
                "name": "Calculators",
                "icon": "bi-calculator",
                "description": "Scientific calculators",
            },
            follow_redirects=True,
        )
        self.assertEqual(category_response.status_code, 200)
        self.assertIn(b"Calculators", category_response.data)

        duplicate_response = self.client.post(
            "/admin/categories",
            data={
                "name": "calculators",
                "icon": "bi-calculator",
                "description": "Duplicate should be rejected",
            },
            follow_redirects=True,
        )
        self.assertIn(b"already exists", duplicate_response.data)

        with self.app.app_context():
            category = Category.query.filter_by(slug="calculators").one()
            self.assertEqual(Category.query.count(), 1)
            category_id = category.id

        form_page = self.client.get("/listings/create")
        self.assertIn(b'<select class="form-select" id="category_id"', form_page.data)
        self.assertIn(b'value="' + str(category_id).encode() + b'">Calculators</option>', form_page.data)

        response = self.client.post(
            "/listings/create",
            data={
                "title": "Campus Calculator",
                "category_id": str(category_id),
                "description": "A working scientific calculator for campus use.",
                "condition": "Good",
                "price": "250",
                "original_price": "",
                "item_age_months": "0",
                "location": "Campus Library",
                "contact_info": "1234567890",
                "extra_details": "",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Campus Calculator", response.data)
        self.assertIn(b"Calculators", response.data)

        with self.app.app_context():
            listing = Listing.query.filter_by(title="Campus Calculator").one()
            self.assertEqual(listing.category_id, category_id)
            self.assertEqual(listing.category.name, "Calculators")

        browse = self.client.get("/listings/")
        self.assertIn(b"Campus Calculator", browse.data)

    def test_smart_price_validation_and_default_avatar(self):
        with self.app.app_context():
            category = Category(name="Books", slug="books", icon="bi-book")
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        valid = self.client.get(
            f"/listings/api/smart-price?category_id={category_id}&condition=Good&original_price=1000&item_age_months=2"
        )
        self.assertEqual(valid.status_code, 200)
        self.assertGreater(valid.get_json()["suggested_price"], 0)

        missing = self.client.get("/listings/api/smart-price")
        self.assertEqual(missing.status_code, 400)
        self.assertIn("category", missing.get_json()["error"].lower())

        invalid = self.client.get("/listings/api/smart-price?category_id=999")
        self.assertEqual(invalid.status_code, 400)

        avatar = self.client.get("/static/default_avatar.png")
        self.assertEqual(avatar.status_code, 200)
        self.assertEqual(avatar.mimetype, "image/png")
        avatar.close()

    def test_admin_can_edit_and_delete_categories(self):
        created = self.client.post(
            "/admin/categories",
            data={"name": "Lab Tools", "icon": "bi-tools", "description": ""},
        )
        self.assertEqual(created.status_code, 302)

        with self.app.app_context():
            category_id = Category.query.filter_by(slug="lab-tools").one().id

        edited = self.client.post(
            f"/admin/categories/{category_id}/edit",
            data={
                "name": "Laboratory Tools",
                "icon": "bi-tools",
                "description": "Campus lab equipment",
            },
        )
        self.assertEqual(edited.status_code, 302)

        with self.app.app_context():
            category = Category.query.filter_by(slug="laboratory-tools").one()
            self.assertEqual(category.name, "Laboratory Tools")

        deleted = self.client.post(f"/admin/categories/{category_id}/delete")
        self.assertEqual(deleted.status_code, 302)

        with self.app.app_context():
            self.assertIsNone(db.session.get(Category, category_id))

    def test_available_listing_count_tracks_category_and_status_changes(self):
        with self.app.app_context():
            calculators = Category(name="Calculators", slug="calculators", icon="bi-calculator")
            books = Category(name="Books", slug="books", icon="bi-book")
            db.session.add_all([calculators, books])
            db.session.commit()
            calculator_id = calculators.id
            books_id = books.id

        response = self.client.post(
            "/listings/create",
            data={
                "title": "Unsold Calculator",
                "category_id": str(calculator_id),
                "description": "A working scientific calculator.",
                "condition": "Good",
                "price": "250",
                "original_price": "",
                "item_age_months": "0",
                "location": "Campus Library",
                "contact_info": "1234567890",
                "extra_details": "",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            listing = Listing.query.filter_by(title="Unsold Calculator").one()
            self.assertEqual(listing.status, "available")
            self.assertEqual(listing.category_id, calculator_id)
            listing_id = listing.id

        my_listings = self.client.get("/dashboard/my-listings")
        self.assertIn(b"Unsold Calculator", my_listings.data)
        self.assertIn(b'badge-status-available">Available', my_listings.data)
        self.assertEqual(self.homepage_category_count("calculators"), 1)

        with self.app.app_context():
            listing = db.session.get(Listing, listing_id)
            listing.category_id = books_id
            db.session.commit()
        self.assertEqual(self.homepage_category_count("calculators"), 0)
        self.assertEqual(self.homepage_category_count("books"), 1)

        with self.app.app_context():
            listing = db.session.get(Listing, listing_id)
            listing.status = "reserved"
            db.session.commit()
        self.assertEqual(self.homepage_category_count("books"), 0)

        with self.app.app_context():
            listing = db.session.get(Listing, listing_id)
            listing.status = "sold"
            db.session.commit()
        self.assertEqual(self.homepage_category_count("books"), 0)

        with self.app.app_context():
            listing = db.session.get(Listing, listing_id)
            listing.status = "deleted"
            db.session.commit()
        self.assertEqual(self.homepage_category_count("books"), 0)

    def test_listing_cannot_be_marked_sold_without_verified_handover(self):
        with self.app.app_context():
            category = Category(name="Calculators", slug="calculators", icon="bi-calculator")
            db.session.add(category)
            db.session.commit()
            category_id = category.id

        self.client.post(
            "/listings/create",
            data={
                "title": "Pending Sale Calculator",
                "category_id": str(category_id),
                "description": "A working scientific calculator.",
                "condition": "Good",
                "price": "250",
                "original_price": "",
                "item_age_months": "0",
                "location": "Campus Library",
                "contact_info": "1234567890",
                "extra_details": "",
            },
        )

        with self.app.app_context():
            listing = Listing.query.filter_by(title="Pending Sale Calculator").one()
            listing_id = listing.id

        rejected = self.client.post(
            f"/listings/{listing_id}/mark-sold",
            follow_redirects=True,
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertIn(b"completed, verified handover", rejected.data)
        with self.app.app_context():
            self.assertEqual(db.session.get(Listing, listing_id).status, "available")

        with self.app.app_context():
            buyer = User(
                name="Test Buyer",
                email="buyer@example.com",
                phone="0987654321",
                department="Engineering",
                year_semester="Year 1",
                college="Test Campus",
                role="student",
            )
            buyer.set_password("buyer-password")
            listing = db.session.get(Listing, listing_id)
            listing.status = "reserved"
            order = Order(
                order_number="ORD-VERIFIED-TEST",
                listing_id=listing_id,
                buyer=buyer,
                seller_id=listing.seller_id,
                payment_method="cash",
                status="handover_pending",
            )
            order.handover = HandoverRecord(
                token="verified-handover-test-token",
                qr_image_path="handover_qrs/test.png",
            )
            db.session.add(order)
            db.session.commit()
            order_id = order.id

        completed = self.client.post(
            f"/orders/{order_id}/verify-handover",
            data={"token": "verified-handover-test-token"},
            follow_redirects=True,
        )
        self.assertEqual(completed.status_code, 200)
        with self.app.app_context():
            order = db.session.get(Order, order_id)
            self.assertEqual(order.status, "completed")
            self.assertTrue(order.handover.is_used)
            self.assertEqual(order.listing.status, "sold")


if __name__ == "__main__":
    unittest.main()
