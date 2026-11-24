import re
import unittest

from app import create_app
from app.config import Config
from app.models import Category, Listing, User, db


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


if __name__ == "__main__":
    unittest.main()
