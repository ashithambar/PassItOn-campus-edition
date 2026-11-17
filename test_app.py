import unittest
import json
from app import create_app
from app.models import db, User, Listing, Category, Order, Payment, HandoverRecord, Wishlist, Review, Report, Conversation, Message

class PassItOnTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False  # disable CSRF for programmatic testing
        cls.client = cls.app.test_client()

    def setUp(self):
        # Ensure fresh logged-out session for each test
        self.client.get('/auth/logout')

    def test_01_public_pages(self):
        """Test public browsing routes"""
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"PassItOn", res.data)
        self.assertIn(b"One student's unused item becomes another student's useful item", res.data)

        res = self.client.get('/safety')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Campus Community Safety Guidelines", res.data)

        res = self.client.get('/about')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Project Mission", res.data)

        res = self.client.get('/listings/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Browse", res.data)

    def test_02_smart_price_api(self):
        """Test rule-based smart price suggestion algorithm API"""
        with self.app.app_context():
            cat = Category.query.first()
            cat_id = cat.id if cat else 1

        res = self.client.get(f'/listings/api/smart-price?category_id={cat_id}&condition=Like+New&original_price=1000&item_age_months=4')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertIn('suggested_price', data)
        self.assertIn('min_price', data)
        self.assertIn('max_price', data)
        self.assertGreater(data['suggested_price'], 0)
        self.assertLessEqual(data['min_price'], data['suggested_price'])
        self.assertGreaterEqual(data['max_price'], data['suggested_price'])

    def test_03_auth_login_logout(self):
        """Test student login and logout"""
        # Valid login
        res = self.client.post('/auth/login', data={
            'email': 'aarav@campus.edu',
            'password': 'Student@123'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Welcome back, Aarav", res.data)

        # Logout
        res = self.client.get('/auth/logout', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"successfully logged out", res.data)

    def test_04_create_listing_and_wishlist(self):
        """Test creating a listing and adding to wishlist"""
        import uuid
        test_title = f"Casio FX-82MS Test {uuid.uuid4().hex[:6]}"

        # Login as Aarav (seller)
        self.client.post('/auth/login', data={'email': 'aarav@campus.edu', 'password': 'Student@123'})
        
        with self.app.app_context():
            cat = Category.query.filter_by(name='Calculators').first()
            cat_id = cat.id

        # Post new listing
        res = self.client.post('/listings/create', data={
            'title': test_title,
            'category_id': cat_id,
            'description': 'Working condition, 240 functions, ideal for 1st year engineering physics.',
            'condition': 'Good',
            'price': '350',
            'original_price': '650',
            'item_age_months': '8',
            'location': 'CS Dept Block 2',
            'contact_info': '9876543211'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(test_title.encode(), res.data)

        # Find created listing id
        with self.app.app_context():
            new_item = Listing.query.filter_by(title=test_title).first()
            self.assertIsNotNone(new_item)
            item_id = new_item.id

        self.client.get('/auth/logout')

        # Login as Priya (buyer) and toggle wishlist
        self.client.post('/auth/login', data={'email': 'priya@campus.edu', 'password': 'Student@123'})
        res = self.client.post(f'/listings/{item_id}/toggle-wishlist', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Check wishlist
        res = self.client.get('/dashboard/wishlist')
        self.assertEqual(res.status_code, 200)
        self.assertIn(test_title.encode(), res.data)

    def test_05_complete_order_and_qr_handover_flow(self):
        """
        Complete end-to-end lifecycle test:
        1. Buyer requests item with UPI payment method
        2. Seller receives and accepts request -> item reserved, payment pending
        3. Buyer submits UPI transaction reference ID -> payment completed
        4. Seller confirms payment -> order enters handover_pending, Handover QR generated
        5. Seller verifies buyer's Handover QR token -> order completed, item sold
        6. Buyer submits review & 5-star rating
        """
        # Find an available listing created by Aarav
        with self.app.app_context():
            item = Listing.query.filter_by(status='available').filter(Listing.seller.has(email='aarav@campus.edu')).first()
            self.assertIsNotNone(item)
            item_id = item.id

        # 1. Buyer (Priya) logs in and requests item
        self.client.post('/auth/login', data={'email': 'priya@campus.edu', 'password': 'Student@123'})
        res = self.client.post(f'/orders/request/{item_id}', data={
            'payment_method': 'upi',
            'notes': 'Meeting at Library lawn at 5 PM'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Your request has been submitted", res.data)

        with self.app.app_context():
            order = Order.query.filter_by(listing_id=item_id, buyer_id=User.query.filter_by(email='priya@campus.edu').first().id).order_by(Order.id.desc()).first()
            self.assertIsNotNone(order)
            self.assertEqual(order.status, 'request_sent')
            order_id = order.id

        self.client.get('/auth/logout')

        # 2. Seller (Aarav) logs in and accepts the request
        self.client.post('/auth/login', data={'email': 'aarav@campus.edu', 'password': 'Student@123'})
        res = self.client.post(f'/orders/{order_id}/accept', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"You accepted the request", res.data)

        with self.app.app_context():
            o = db.session.get(Order, order_id)
            self.assertEqual(o.status, 'payment_pending')
            self.assertEqual(o.listing.status, 'reserved')

        self.client.get('/auth/logout')

        # 3. Buyer (Priya) submits UPI transaction reference ID
        self.client.post('/auth/login', data={'email': 'priya@campus.edu', 'password': 'Student@123'})
        res = self.client.post(f'/orders/{order_id}/submit-payment', data={
            'transaction_reference': 'UPI/TEST/9988776655'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Payment marked as completed", res.data)

        with self.app.app_context():
            o = db.session.get(Order, order_id)
            self.assertEqual(o.status, 'payment_completed')

        self.client.get('/auth/logout')

        # 4. Seller (Aarav) confirms payment -> Handover QR generated
        self.client.post('/auth/login', data={'email': 'aarav@campus.edu', 'password': 'Student@123'})
        res = self.client.post(f'/orders/{order_id}/confirm-payment', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Payment confirmed", res.data)

        with self.app.app_context():
            o = db.session.get(Order, order_id)
            self.assertEqual(o.status, 'handover_pending')
            self.assertIsNotNone(o.handover)
            self.assertFalse(o.handover.is_used)
            handover_token = o.handover.token

        # 5. Seller verifies Handover QR code with security token
        res = self.client.post(f'/orders/{order_id}/verify-handover', data={
            'token': handover_token
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Handover Verified Successfully", res.data)

        with self.app.app_context():
            o = db.session.get(Order, order_id)
            self.assertEqual(o.status, 'completed')
            self.assertTrue(o.handover.is_used)
            self.assertEqual(o.listing.status, 'sold')

        self.client.get('/auth/logout')

        # 6. Buyer submits 5-star review
        self.client.post('/auth/login', data={'email': 'priya@campus.edu', 'password': 'Student@123'})
        res = self.client.post(f'/orders/{order_id}/review', data={
            'rating': '5',
            'comment': 'Item was in mint condition, fast campus handover. Recommended seller!'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Thank you for your rating", res.data)

        with self.app.app_context():
            rev = Review.query.filter_by(order_id=order_id, reviewer_id=User.query.filter_by(email='priya@campus.edu').first().id).first()
            self.assertIsNotNone(rev)
            self.assertEqual(rev.rating, 5)

    def test_06_admin_dashboard_and_controls(self):
        """Test admin dashboard, stats API, users, categories, and report handling"""
        # Login as Admin
        self.client.post('/auth/login', data={'email': 'admin@campus.edu', 'password': 'Admin@123'})

        # Admin overview
        res = self.client.get('/admin/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Admin Console", res.data)

        # Admin stats API
        res = self.client.get('/admin/api/stats')
        self.assertEqual(res.status_code, 200)
        stats = json.loads(res.data)
        self.assertIn('categories', stats)
        self.assertIn('orders', stats)

        # Admin Users management
        res = self.client.get('/admin/users')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Student Users Management", res.data)

        # Admin Categories
        res = self.client.get('/admin/categories')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Categories Management", res.data)

        # Admin Reports
        res = self.client.get('/admin/reports')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Safety & Moderation Reports", res.data)

        # Non-admin access attempt check
        self.client.get('/auth/logout')
        self.client.post('/auth/login', data={'email': 'aarav@campus.edu', 'password': 'Student@123'})
        res = self.client.get('/admin/')
        self.assertEqual(res.status_code, 403)


    def test_07_chat_flow(self):
        """Test student-to-student messaging and polling API"""
        # 1. Aarav starts a chat with Priya regarding her listing
        self.client.post('/auth/login', data={'email': 'aarav@campus.edu', 'password': 'Student@123'})
        
        with self.app.app_context():
            priya_item = Listing.query.filter(Listing.seller.has(email='priya@campus.edu')).first()
            item_id = priya_item.id

        res = self.client.get(f'/chat/start/{item_id}', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with self.app.app_context():
            aarav = User.query.filter_by(email='aarav@campus.edu').first()
            priya = User.query.filter_by(email='priya@campus.edu').first()
            convo = Conversation.query.filter(
                db.or_(
                    db.and_(Conversation.user1_id == aarav.id, Conversation.user2_id == priya.id),
                    db.and_(Conversation.user1_id == priya.id, Conversation.user2_id == aarav.id)
                )
            ).first()
            self.assertIsNotNone(convo)
            convo_id = convo.id

        # 2. Aarav sends a message
        res = self.client.post(f'/chat/send/{convo_id}', json={
            'content': 'Can you bring it tomorrow morning?'
        })
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])

        # 3. Priya logs in and checks messages
        self.client.get('/auth/logout')
        self.client.post('/auth/login', data={'email': 'priya@campus.edu', 'password': 'Student@123'})
        
        res = self.client.get(f'/chat/api/messages/{convo_id}')
        self.assertEqual(res.status_code, 200)
        messages_data = json.loads(res.data)
        self.assertIn('messages', messages_data)
        contents = [m['content'] for m in messages_data['messages']]
        self.assertIn('Can you bring it tomorrow morning?', contents)


if __name__ == '__main__':
    unittest.main()
