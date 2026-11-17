import os
import secrets
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
from app import create_app
from app.models import (
    db, User, Category, Listing, ListingImage, Wishlist, 
    Order, Payment, HandoverRecord, Conversation, Message, 
    Notification, Review, Report
)
from app.utils import generate_handover_qr

app = create_app()

def create_item_image(filename, title, category_name, bg_color, accent_color):
    """Generates an aesthetic item placeholder card image using Pillow"""
    width, height = 600, 450
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Decorative top bar
    draw.rectangle([0, 0, width, 14], fill=accent_color)
    
    # Campus Edition badge
    draw.rounded_rectangle([30, 30, 210, 65], radius=8, fill=accent_color)
    draw.text((45, 40), "PASSITON CAMPUS", fill="white")

    # Category Pill
    draw.rounded_rectangle([width - 180, 30, width - 30, 65], radius=8, fill=(255, 255, 255, 200))
    draw.text((width - 165, 40), category_name[:14].upper(), fill="#1e293b")

    # Subtle grid / geometric pattern
    for i in range(50, height - 100, 35):
        draw.line([(30, i), (width - 30, i)], fill=(255, 255, 255, 25), width=1)

    # Center card container
    draw.rounded_rectangle([40, 100, width - 40, height - 50], radius=16, fill=(255, 255, 255))
    
    # Inner border
    draw.rounded_rectangle([48, 108, width - 48, height - 58], radius=12, outline=accent_color, width=2)

    # Center big icon/initials
    initials = "".join([w[0].upper() for w in title.split()[:3]])
    draw.ellipse([width//2 - 50, 140, width//2 + 50, 240], fill=accent_color)
    draw.text((width//2 - 25, 175), initials, fill="white")

    # Item Title inside card
    # Word wrap roughly
    words = title.split()
    line1 = " ".join(words[:4])
    line2 = " ".join(words[4:]) if len(words) > 4 else ""

    draw.text((width//2 - len(line1)*5, 265), line1, fill="#0f172a")
    if line2:
        draw.text((width//2 - len(line2)*5, 295), line2, fill="#334155")

    # Verified Student Item tag
    draw.rounded_rectangle([width//2 - 110, 345, width//2 + 110, 375], radius=15, fill="#f1f5f9")
    draw.text((width//2 - 95, 352), "✓ Verified Student Item", fill="#0f766e")

    target_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'listings')
    os.makedirs(target_dir, exist_ok=True)
    full_path = os.path.join(target_dir, filename)
    img.save(full_path, quality=90)
    return f"uploads/listings/{filename}"


def create_avatar_image(filename, name, bg_color):
    width, height = 200, 200
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Draw avatar circle
    draw.ellipse([20, 20, 180, 180], fill=(255, 255, 255, 80))
    initials = "".join([part[0].upper() for part in name.split()[:2]])
    draw.text((75, 85), initials, fill="white")
    
    target_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'avatars')
    os.makedirs(target_dir, exist_ok=True)
    full_path = os.path.join(target_dir, filename)
    img.save(full_path, quality=90)
    return f"uploads/avatars/{filename}"


def seed_database():
    with app.app_context():
        print("Clearing old tables and recreating database...")
        db.drop_all()
        db.create_all()

        # 1. Categories
        print("Seeding Categories...")
        categories_data = [
            ("Books", "books", "bi-book", "Textbooks, reference guides, semester notes, entrance prep, fiction & non-fiction."),
            ("Electronics", "electronics", "bi-laptop", "Laptops, monitors, headphones, keyboards, mice, adapters, chargers."),
            ("Calculators", "calculators", "bi-calculator", "Scientific calculators, programmable & graphing calculators for engineering & math."),
            ("Stationery", "stationery", "bi-pencil-square", "Notebooks, sketchbooks, geometry boxes, technical pens, markers."),
            ("Lab Equipment", "lab-equipment", "bi-eyedropper", "Lab coats, safety goggles, breadboards, multimeters, dissecting kits."),
            ("Furniture", "furniture", "bi-lamp", "Hostel study tables, ergonomic chairs, bed tables, desk organizers."),
            ("Clothing", "clothing", "bi-person-badge", "College blazers, lab coats, hoodies, sports jerseys, formal placement wear."),
            ("Accessories", "accessories", "bi-bag-check", "Backpacks, laptop sleeves, water bottles, umbrellas, cycle locks."),
            ("Sports Items", "sports-items", "bi-trophy", "Badminton rackets, cricket bats, footballs, basketballs, gym gear."),
            ("College Supplies", "college-supplies", "bi-mortarboard", "Mini drafters, T-squares, architecture sheets, engineering drawing tools."),
            ("Other", "other", "bi-grid", "Hostel appliances, music instruments, bicycles, room essentials.")
        ]
        
        cat_map = {}
        for name, slug, icon, desc in categories_data:
            c = Category(name=name, slug=slug, icon=icon, description=desc)
            db.session.add(c)
            cat_map[name] = c
        db.session.flush()

        # 2. Users (Admin + 8 Students)
        print("Seeding Admin & Students...")
        
        # Admin
        admin = User(
            name="Campus Administrator",
            email="admin@campus.edu",
            phone="9876543210",
            department="Dean of Student Welfare",
            year_semester="Administration",
            college="Apex Institute of Technology",
            role="admin",
            profile_pic=create_avatar_image("admin_avatar.png", "Campus Admin", (15, 118, 110))
        )
        admin.set_password("Admin@123")
        db.session.add(admin)

        # 8 Students
        students_info = [
            ("Aarav Sharma", "aarav@campus.edu", "9876543211", "Computer Science & Engg", "3rd Year / 5th-6th Sem", "aarav@oksbi", (30, 58, 138)),
            ("Priya Patel", "priya@campus.edu", "9876543212", "Electronics & Communication", "4th Year / 7th-8th Sem", "priya@okhdfcbank", (13, 148, 136)),
            ("Rohan Verma", "rohan@campus.edu", "9876543213", "Mechanical Engineering", "2nd Year / 3rd-4th Sem", "rohan@okaxis", (180, 83, 9)),
            ("Ananya Iyer", "ananya@campus.edu", "9876543214", "Information Technology", "3rd Year / 5th-6th Sem", "ananya@icici", (190, 24, 93)),
            ("Vikram Singh", "vikram@campus.edu", "9876543215", "Civil Engineering", "4th Year / 7th-8th Sem", "vikram@paytm", (67, 56, 202)),
            ("Sneha Reddy", "sneha@campus.edu", "9876543216", "Biotechnology & Chemical", "2nd Year / 3rd-4th Sem", "sneha@oksbi", (5, 150, 105)),
            ("Kabir Mehta", "kabir@campus.edu", "9876543217", "Business & Management (MBA/BBA)", "1st Year / 1st-2nd Sem", "kabir@oksbi", (217, 119, 6)),
            ("Divya Nair", "divya@campus.edu", "9876543218", "Architecture & Design", "3rd Year / 5th-6th Sem", "divya@kotak", (124, 58, 237)),
        ]

        students = []
        for name, email, phone, dept, yr, upi, color in students_info:
            avatar_file = f"avatar_{email.split('@')[0]}.png"
            u = User(
                name=name,
                email=email,
                phone=phone,
                department=dept,
                year_semester=yr,
                college="Apex Institute of Technology",
                upi_id=upi,
                role="student",
                profile_pic=create_avatar_image(avatar_file, name, color)
            )
            u.set_password("Student@123")
            db.session.add(u)
            students.append(u)
        db.session.flush()

        # 3. Listings (~25 realistic campus items)
        print("Seeding ~25 Campus Listings with Images...")
        listings_seed_data = [
            # 1
            {
                "seller": students[0], "cat": "Calculators",
                "title": "Casio Scientific Calculator fx-991EX Classwiz",
                "desc": "High-resolution display, 552 functions including matrix, vector, and calculus. Barely used during 2nd sem. Perfect working condition with slide-on hard case.",
                "cond": "Like New", "price": 500.0, "orig": 1200.0, "age": 6,
                "loc": "Hostel 3 Common Room or CS Dept", "bg": (240, 253, 250), "accent": (13, 148, 136)
            },
            # 2
            {
                "seller": students[1], "cat": "Books",
                "title": "Higher Engineering Mathematics by B.S. Grewal (44th Ed)",
                "desc": "Standard textbook for M-1, M-2, and M-3 semesters. All formulas highlighted, clean pages, no torn sheets. Essential for all engineering branches.",
                "cond": "Good", "price": 250.0, "orig": 850.0, "age": 12,
                "loc": "Central Library Lawn", "bg": (254, 242, 242), "accent": (225, 29, 72)
            },
            # 3
            {
                "seller": students[1], "cat": "Electronics",
                "title": "Arduino Uno R3 Starter Kit with Sensors & Breadboard",
                "desc": "Original Arduino Uno board with USB cable, 400-tie breadboard, ultrasonic sensor HC-SR04, DHT11 temp sensor, LEDs, resistors, and jumper wires.",
                "cond": "Like New", "price": 700.0, "orig": 1500.0, "age": 4,
                "loc": "ECE Innovation Lab / Block B", "bg": (240, 249, 255), "accent": (2, 132, 199)
            },
            # 4
            {
                "seller": students[5], "cat": "Lab Equipment",
                "title": "College Chemistry Lab Coat (White Cotton, Size 40)",
                "desc": "Thick premium cotton white lab coat with college crest. Required for Chem and Biotech lab sessions. Washed, ironed, and in great condition.",
                "cond": "Good", "price": 300.0, "orig": 650.0, "age": 8,
                "loc": "Biotech Block ground floor", "bg": (240, 253, 244), "accent": (22, 163, 74)
            },
            # 5
            {
                "seller": students[2], "cat": "College Supplies",
                "title": "Mini Drafter & Engineering Drawing Tool Set (Omega)",
                "desc": "Standard engineering mini drafter with steel clamp, scale bars, drafting clips, sheet container tube, and drawing compass set. Clear scale markings.",
                "cond": "Good", "price": 400.0, "orig": 950.0, "age": 10,
                "loc": "Mechanical Workshop Shed", "bg": (254, 243, 199), "accent": (217, 119, 6)
            },
            # 6
            {
                "seller": students[0], "cat": "Electronics",
                "title": "Redragon Mechanical Keyboard (Red Switches, Compact)",
                "desc": "TKL 87-key mechanical keyboard with linear quiet red switches and rainbow backlight. Great for hostel coding sessions and gaming. USB wired.",
                "cond": "Used", "price": 600.0, "orig": 1400.0, "age": 14,
                "loc": "Campus Cafeteria or Hostel 3", "bg": (245, 243, 255), "accent": (124, 58, 237)
            },
            # 7
            {
                "seller": students[3], "cat": "Books",
                "title": "The C Programming Language (ANSI C - Ritchie & Kernighan)",
                "desc": "The definitive Bible of C programming by Brian Kernighan and Dennis Ritchie. Clean second edition, very helpful for 1st year coding lab.",
                "cond": "Good", "price": 200.0, "orig": 500.0, "age": 15,
                "loc": "IT Department 2nd Floor", "bg": (255, 241, 242), "accent": (244, 63, 94)
            },
            # 8
            {
                "seller": students[2], "cat": "Calculators",
                "title": "Texas Instruments TI-84 Plus Graphing Calculator",
                "desc": "Advanced graphing calculator for advanced calculus, statistics, and matrices. Built-in USB port. Screen is scratch-free. Includes batteries.",
                "cond": "Good", "price": 1800.0, "orig": 4500.0, "age": 18,
                "loc": "Mech Dept Seminar Hall", "bg": (236, 254, 255), "accent": (8, 145, 178)
            },
            # 9
            {
                "seller": students[0], "cat": "Books",
                "title": "Data Structures & Algorithms in Java (Robert Lafore)",
                "desc": "Comprehensive DSA textbook with clear diagrams and Java implementations. Perfect for 3rd semester DSA course and placement coding prep.",
                "cond": "Like New", "price": 320.0, "orig": 799.0, "age": 5,
                "loc": "Central Library entrance", "bg": (240, 253, 250), "accent": (15, 118, 110)
            },
            # 10
            {
                "seller": students[3], "cat": "Electronics",
                "title": "Raspberry Pi 4 Model B (4GB RAM) with Case & Heatsinks",
                "desc": "Used for IoT final year project. 4GB RAM variant, comes with official acrylic casing, active cooling fan, micro-HDMI adapter, and 32GB SD card.",
                "cond": "Like New", "price": 2800.0, "orig": 5200.0, "age": 7,
                "loc": "IT Server Lab", "bg": (245, 245, 245), "accent": (71, 85, 105)
            },
            # 11
            {
                "seller": students[4], "cat": "Furniture",
                "title": "Ergonomic Study Chair with Lumbar Support",
                "desc": "Black breathable mesh back, adjustable height gas-lift, 360-degree swivel wheels. Excellent for long hostel study nights without back pain.",
                "cond": "Good", "price": 850.0, "orig": 2400.0, "age": 12,
                "loc": "Senior Boys Hostel 1 (Ground floor)", "bg": (255, 247, 237), "accent": (194, 65, 12)
            },
            # 12
            {
                "seller": students[5], "cat": "Furniture",
                "title": "Foldable Wooden Hostel Bed Study Table with Cup Holder",
                "desc": "Compact laptop desk for bed studying. Includes tablet/phone slot, cup holder, and anti-slip curved metal legs. Folds flat for storage.",
                "cond": "Good", "price": 350.0, "orig": 900.0, "age": 9,
                "loc": "Girls Hostel 2 Security Desk", "bg": (254, 242, 242), "accent": (239, 68, 68)
            },
            # 13
            {
                "seller": students[1], "cat": "Lab Equipment",
                "title": "Digital Multimeter with Probe Leads & Transistor Tester (Uni-T)",
                "desc": "Measures AC/DC voltage, current, resistance, capacitance, and diode continuity with buzzer. Auto-backlight display. Required for Analog Lab.",
                "cond": "Like New", "price": 450.0, "orig": 1100.0, "age": 3,
                "loc": "ECE Dept Lobby", "bg": (240, 253, 244), "accent": (16, 185, 129)
            },
            # 14
            {
                "seller": students[4], "cat": "Sports Items",
                "title": "Yonex Carbonex 8000 Badminton Racket with Full Cover",
                "desc": "High modulus graphite shaft, strung at 24 lbs with BG65 strings. No frame cracks. Played for one semester tournament. Free pack of 3 shuttlecocks.",
                "cond": "Like New", "price": 750.0, "orig": 1800.0, "age": 5,
                "loc": "Campus Sports Complex Badminton Courts", "bg": (254, 243, 199), "accent": (245, 158, 11)
            },
            # 15
            {
                "seller": students[6], "cat": "Accessories",
                "title": "Fastrack Campus Casual Backpack (Water Resistant, 30L)",
                "desc": "Dual compartment backpack with padded 15.6-inch laptop pocket, side bottle mesh, and rain cover. Clean and well maintained.",
                "cond": "Good", "price": 550.0, "orig": 1400.0, "age": 8,
                "loc": "Management Block Courtyard", "bg": (240, 249, 255), "accent": (14, 165, 233)
            },
            # 16
            {
                "seller": students[6], "cat": "Electronics",
                "title": "Wireless Presentation Remote Clicker with Red Pointer",
                "desc": "Plug & play 2.4GHz USB receiver, 100ft range, slide forward/backward, and red laser pointer. Used for MBA seminar presentations.",
                "cond": "Like New", "price": 300.0, "orig": 750.0, "age": 3,
                "loc": "Auditorium Annex", "bg": (243, 244, 246), "accent": (75, 85, 99)
            },
            # 17
            {
                "seller": students[6], "cat": "Clothing",
                "title": "Formal Navy Blue Placement Blazer (Raymond Fabric, Size 38)",
                "desc": "Tailored two-button navy blue suit blazer. Worn only 2 times during campus recruitment drives. Dry cleaned and ready to wear.",
                "cond": "Like New", "price": 1100.0, "orig": 3200.0, "age": 4,
                "loc": "Campus Placement Cell Office", "bg": (238, 242, 255), "accent": (79, 70, 229)
            },
            # 18
            {
                "seller": students[4], "cat": "Books",
                "title": "Solid State Physics & Engineering Electromagnetics Bundle",
                "desc": "Both standard reference books included. Ashcroft & Mermin (Solid State) + William Hayt (Electromagnetics). Great for Electrical & Physics courses.",
                "cond": "Used", "price": 280.0, "orig": 950.0, "age": 16,
                "loc": "Civil Engg Staff Room Area", "bg": (255, 241, 242), "accent": (225, 29, 72)
            },
            # 19
            {
                "seller": students[5], "cat": "Lab Equipment",
                "title": "Chemistry Lab Protective Goggles & Test Tube Stand Bundle",
                "desc": "Anti-fog polycarbonate splash-proof goggles and 12-hole wooden test tube rack. Clean and sanitized. Mandatory for 1st year chemistry lab.",
                "cond": "Good", "price": 150.0, "orig": 450.0, "age": 7,
                "loc": "Chemistry Lab Block", "bg": (240, 253, 244), "accent": (5, 150, 105)
            },
            # 20
            {
                "seller": students[0], "cat": "Electronics",
                "title": "Boat Rockerz 550 Over-Ear Wireless Headphones",
                "desc": "50mm dynamic drivers, 20 hours battery life, physical bass boost button, and cushioned earcups. Comes with 3.5mm aux cable and micro-USB cord.",
                "cond": "Good", "price": 650.0, "orig": 1999.0, "age": 11,
                "loc": "Hostel 3 Gate", "bg": (245, 243, 255), "accent": (147, 51, 234)
            },
            # 21
            {
                "seller": students[2], "cat": "Other",
                "title": "Campus Bicycle with Basket & Numbered Wire Lock (Hero)",
                "desc": "Hero Sprint single-speed bicycle, recently greased and fitted with new brake pads and bell. Front wire basket for book bags. Includes combination lock.",
                "cond": "Used", "price": 1900.0, "orig": 5000.0, "age": 20,
                "loc": "Cycle Parking Stand Near Main Gate", "bg": (254, 243, 199), "accent": (202, 138, 4)
            },
            # 22
            {
                "seller": students[3], "cat": "Other",
                "title": "Compact Hostel Induction Cooktop (1200W Prestige)",
                "desc": "Push button controls, Indian preset menus, flame-free hostel cooking. Used for boiling milk, Maggie, and tea. Auto voltage regulator built in.",
                "cond": "Good", "price": 800.0, "orig": 2100.0, "age": 10,
                "loc": "Hostel 2 Dining Hall Entrance", "bg": (254, 242, 242), "accent": (220, 38, 38)
            },
            # 23
            {
                "seller": students[2], "cat": "Sports Items",
                "title": "Nivia Classic Football (Size 5, All-Weather) + Hand Air Pump",
                "desc": "Hand-stitched 32 panel synthetic rubber ball. Retains air pressure well. Comes with compact dual-action air pump and inflation pin.",
                "cond": "Like New", "price": 400.0, "orig": 990.0, "age": 3,
                "loc": "Campus Football Field Bleachers", "bg": (240, 253, 250), "accent": (13, 148, 136)
            },
            # 24
            {
                "seller": students[7], "cat": "College Supplies",
                "title": "Architecture Cutting Mat (A2 Size) + Precision X-Acto Knives",
                "desc": "Self-healing 5-ply A2 green cutting grid mat, steel 30cm ruler, and aluminum hobby knife with 10 spare blades. Ideal for 3D model making.",
                "cond": "Good", "price": 280.0, "orig": 650.0, "age": 6,
                "loc": "Architecture Studio 4", "bg": (243, 244, 246), "accent": (55, 65, 81)
            },
            # 25
            {
                "seller": students[6], "cat": "Clothing",
                "title": "Formal Leather Placement Shoes (Black Oxford, UK 8)",
                "desc": "Genuine black polished leather shoes for college interviews and formal presentations. Cushioned insole, anti-skid rubber sole. Barely worn.",
                "cond": "Like New", "price": 500.0, "orig": 1600.0, "age": 4,
                "loc": "MBA Dept 1st Floor", "bg": (241, 245, 249), "accent": (15, 23, 42)
            }
        ]

        created_listings = []
        for i, item in enumerate(listings_seed_data, start=1):
            img_file = f"item_{i}_{secrets.token_hex(3)}.png"
            img_rel_path = create_item_image(
                filename=img_file,
                title=item["title"],
                category_name=item["cat"],
                bg_color=item["bg"],
                accent_color=item["accent"]
            )
            
            listing = Listing(
                seller_id=item["seller"].id,
                category_id=cat_map[item["cat"]].id,
                title=item["title"],
                description=item["desc"],
                condition=item["cond"],
                price=item["price"],
                original_price=item["orig"],
                item_age_months=item["age"],
                location=item["loc"],
                contact_info=item["seller"].phone,
                extra_details=f"Available for instant handover at {item['loc']}. Inspection welcomed before payment.",
                status='available',
                views_count=10 + (i * 7) % 65,
                created_at=datetime.utcnow() - timedelta(days=25 - i)
            )
            db.session.add(listing)
            db.session.flush()

            # Add primary image
            listing_img = ListingImage(
                listing_id=listing.id,
                image_path=img_rel_path,
                is_primary=True
            )
            db.session.add(listing_img)
            created_listings.append(listing)

        db.session.flush()

        # 4. Orders in Different Lifecycle Statuses
        print("Seeding Sample Orders with UPI and Handover QR codes...")

        # Order 1: COMPLETED (Casio Calculator fx-991EX, bought by Ananya from Aarav)
        # Listing 1: Casio Scientific Calculator
        l1 = created_listings[0]
        l1.status = 'sold'
        
        ord1 = Order(
            order_number="ORD-2026-A101",
            listing_id=l1.id,
            buyer_id=students[3].id,   # Ananya
            seller_id=students[0].id,  # Aarav
            payment_method='upi',
            status='completed',
            notes="Please bring it near CS Dept coffee kiosk after 3 PM.",
            created_at=datetime.utcnow() - timedelta(days=5),
            updated_at=datetime.utcnow() - timedelta(days=4)
        )
        db.session.add(ord1)
        db.session.flush()

        pay1 = Payment(
            order_id=ord1.id,
            buyer_id=ord1.buyer_id,
            seller_id=ord1.seller_id,
            amount=500.0,
            payment_method='upi',
            transaction_reference="UPI/20261112/98342177421",
            status='confirmed',
            created_at=datetime.utcnow() - timedelta(days=5),
            confirmed_at=datetime.utcnow() - timedelta(days=5)
        )
        db.session.add(pay1)

        token1, qr_path1 = generate_handover_qr(ord1.order_number)
        handover1 = HandoverRecord(
            order_id=ord1.id,
            token=token1,
            qr_image_path=qr_path1,
            is_used=True,
            created_at=datetime.utcnow() - timedelta(days=5),
            verified_at=datetime.utcnow() - timedelta(days=4),
            verified_by_id=students[0].id
        )
        db.session.add(handover1)

        # Reviews for Order 1
        rev1_buyer = Review(
            order_id=ord1.id,
            reviewer_id=students[3].id,
            reviewee_id=students[0].id,
            rating=5,
            comment="Aarav was very punctual and the calculator is exactly as described! Even gave me fresh batteries. Highly recommend this seller.",
            role='buyer_to_seller',
            created_at=datetime.utcnow() - timedelta(days=4)
        )
        rev1_seller = Review(
            order_id=ord1.id,
            reviewer_id=students[0].id,
            reviewee_id=students[3].id,
            rating=5,
            comment="Great buyer! Quick UPI payment and smooth handover at CS kiosk.",
            role='seller_to_buyer',
            created_at=datetime.utcnow() - timedelta(days=4)
        )
        db.session.add_all([rev1_buyer, rev1_seller])

        # Order 2: HANDOVER PENDING (Arduino Uno Starter Kit, bought by Rohan from Priya)
        # Listing 3
        l3 = created_listings[2]
        l3.status = 'reserved'
        
        ord2 = Order(
            order_number="ORD-2026-B202",
            listing_id=l3.id,
            buyer_id=students[2].id,   # Rohan
            seller_id=students[1].id,  # Priya
            payment_method='upi',
            status='handover_pending',
            notes="Meeting at ECE lab entrance tomorrow at 11 AM.",
            created_at=datetime.utcnow() - timedelta(days=1),
            updated_at=datetime.utcnow() - timedelta(hours=6)
        )
        db.session.add(ord2)
        db.session.flush()

        pay2 = Payment(
            order_id=ord2.id,
            buyer_id=ord2.buyer_id,
            seller_id=ord2.seller_id,
            amount=700.0,
            payment_method='upi',
            transaction_reference="UPI/20261116/77889922114",
            status='confirmed',
            created_at=datetime.utcnow() - timedelta(days=1),
            confirmed_at=datetime.utcnow() - timedelta(hours=6)
        )
        db.session.add(pay2)

        token2, qr_path2 = generate_handover_qr(ord2.order_number)
        handover2 = HandoverRecord(
            order_id=ord2.id,
            token=token2,
            qr_image_path=qr_path2,
            is_used=False,
            created_at=datetime.utcnow() - timedelta(hours=6)
        )
        db.session.add(handover2)

        # Order 3: PAYMENT COMPLETED (Engineering Drawing Set, bought by Sneha from Rohan)
        # Listing 5
        l5 = created_listings[4]
        l5.status = 'reserved'
        
        ord3 = Order(
            order_number="ORD-2026-C303",
            listing_id=l5.id,
            buyer_id=students[5].id,   # Sneha
            seller_id=students[2].id,  # Rohan
            payment_method='upi',
            status='payment_completed',
            notes="Urgent for next drawing practical class on Tuesday.",
            created_at=datetime.utcnow() - timedelta(hours=8),
            updated_at=datetime.utcnow() - timedelta(hours=2)
        )
        db.session.add(ord3)
        db.session.flush()

        pay3 = Payment(
            order_id=ord3.id,
            buyer_id=ord3.buyer_id,
            seller_id=ord3.seller_id,
            amount=400.0,
            payment_method='upi',
            transaction_reference="UPI/20261117/12984533019",
            status='submitted',
            created_at=datetime.utcnow() - timedelta(hours=2)
        )
        db.session.add(pay3)

        # Order 4: REQUEST SENT (B.S. Grewal Book, requested by Vikram from Priya)
        # Listing 2
        l2 = created_listings[1]
        ord4 = Order(
            order_number="ORD-2026-D404",
            listing_id=l2.id,
            buyer_id=students[4].id,   # Vikram
            seller_id=students[1].id,  # Priya
            payment_method='cash',
            status='request_sent',
            notes="Can we meet at the library lawn during lunch break?",
            created_at=datetime.utcnow() - timedelta(hours=1)
        )
        db.session.add(ord4)
        db.session.flush()

        pay4 = Payment(
            order_id=ord4.id,
            buyer_id=ord4.buyer_id,
            seller_id=ord4.seller_id,
            amount=250.0,
            payment_method='cash',
            status='pending'
        )
        db.session.add(pay4)

        # 5. Conversations and Messages
        print("Seeding Messages & Conversations...")
        convo1 = Conversation(
            listing_id=l1.id,
            user1_id=students[3].id,
            user2_id=students[0].id
        )
        db.session.add(convo1)
        db.session.flush()

        m1 = Message(conversation_id=convo1.id, sender_id=students[3].id, content="Hi Aarav, is the Casio calculator still available?")
        m2 = Message(conversation_id=convo1.id, sender_id=students[0].id, content="Yes Ananya, it is in excellent condition and available!")
        m3 = Message(conversation_id=convo1.id, sender_id=students[3].id, content="Great, I'll send the purchase request now via UPI.")
        db.session.add_all([m1, m2, m3])

        convo2 = Conversation(
            listing_id=l3.id,
            user1_id=students[2].id,
            user2_id=students[1].id
        )
        db.session.add(convo2)
        db.session.flush()

        m4 = Message(conversation_id=convo2.id, sender_id=students[2].id, content="Hi Priya, does the Arduino kit include the ultrasonic sensor?")
        m5 = Message(conversation_id=convo2.id, sender_id=students[1].id, content="Hey Rohan! Yes, HC-SR04 ultrasonic and DHT11 are both included.")
        db.session.add_all([m4, m5])

        # 6. Wishlist Entries
        print("Seeding Wishlist Entries...")
        w1 = Wishlist(user_id=students[0].id, listing_id=created_listings[9].id)  # Aarav wants Raspberry Pi
        w2 = Wishlist(user_id=students[3].id, listing_id=created_listings[5].id)  # Ananya wants Mechanical Keyboard
        w3 = Wishlist(user_id=students[5].id, listing_id=created_listings[10].id) # Sneha wants Study Chair
        w4 = Wishlist(user_id=students[6].id, listing_id=created_listings[13].id) # Kabir wants Badminton Racket
        db.session.add_all([w1, w2, w3, w4])

        # 7. Notifications
        print("Seeding Notifications...")
        n1 = Notification(
            user_id=students[1].id,
            title="New Purchase Request!",
            message="Vikram Singh sent a request to buy 'Higher Engineering Mathematics' for ₹250.",
            link=f"/orders/{ord4.id}",
            notification_type="order_request"
        )
        n2 = Notification(
            user_id=students[2].id,
            title="Payment Marked by Buyer!",
            message="Sneha Reddy submitted payment ref UPI/20261117/12984533019 for 'Mini Drafter'. Please confirm.",
            link=f"/orders/{ord3.id}",
            notification_type="payment_submitted"
        )
        n3 = Notification(
            user_id=students[2].id,
            title="Handover QR Code Ready!",
            message="Priya Patel confirmed your payment! Your Handover QR code is ready for 'Arduino Uno R3'.",
            link=f"/orders/{ord2.id}",
            notification_type="payment_confirmed"
        )
        db.session.add_all([n1, n2, n3])

        # 8. Reports for Admin Review
        print("Seeding Admin Reports...")
        rep1 = Report(
            reporter_id=students[2].id,
            reported_listing_id=created_listings[20].id, # Bicycle
            reason="wrong_info",
            comment="The seller mentioned new brake pads, but I saw the bike at the stand and the front brake cable is missing. Please ask seller to clarify.",
            status="pending"
        )
        db.session.add(rep1)

        db.session.commit()
        print("="*60)
        print("DATABASE SEEDING COMPLETED SUCCESSFULLY!")
        print(f"Categories: {Category.query.count()}")
        print(f"Users: {User.query.count()} (1 Admin + {User.query.filter_by(role='student').count()} Students)")
        print(f"Listings: {Listing.query.count()}")
        print(f"Orders: {Order.query.count()}")
        print(f"Reviews: {Review.query.count()}")
        print("="*60)

if __name__ == '__main__':
    seed_database()
