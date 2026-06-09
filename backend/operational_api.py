import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

import urllib.parse

# We need a separate connection to the main Laravel database
def get_laravel_db_uri():
    uri = os.getenv("LARAVEL_DB_URI")
    if uri:
        return uri
    # Read standard Laravel environment variables directly
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    username = os.getenv("DB_USERNAME", "root")
    password = os.getenv("DB_PASSWORD", "password")
    database = os.getenv("DB_DATABASE", "realdealride")
    
    quoted_password = urllib.parse.quote_plus(password) if password else ""
    return f"mysql+aiomysql://{username}:{quoted_password}@{host}:{port}/{database}"

LARAVEL_DB_URL = get_laravel_db_uri()
laravel_engine = create_async_engine(LARAVEL_DB_URL, echo=False)
LaravelSessionLocal = sessionmaker(
    laravel_engine, class_=AsyncSession, expire_on_commit=False
)

async def search_available_cars(city: str, vehicle_type: str = None, min_price: int = None, max_price: int = None, start_date: str = None, end_date: str = None, limit: int = 10):
    """
    Searches the Laravel 'cars' table for available vehicles matching the criteria.
    This is a read-only query against the live production database.
    """
    async with LaravelSessionLocal() as db:
        try:
            # Build the query dynamically based on parameters
            query_str = """
                SELECT c.id, c.make, c.model, c.year, c.vehicle_type, c.price_per_day, c.locality AS city,
                       c.rating, c.total_trips, c.number_of_seats, c.transmission, c.country, c.generate_code,
                       (SELECT id FROM media WHERE model_type LIKE '%Car' AND model_id = c.id ORDER BY id ASC LIMIT 1) AS media_id,
                       (SELECT file_name FROM media WHERE model_type LIKE '%Car' AND model_id = c.id ORDER BY id ASC LIMIT 1) AS media_file_name
                FROM cars c
                WHERE c.locality LIKE :city
                AND LOWER(c.status) = 'approved'
            """
            
            params = {"city": f"%{city}%", "limit": limit}
            
            if vehicle_type:
                query_str += " AND c.vehicle_type = :v_type"
                params["v_type"] = vehicle_type
                
            if min_price is not None:
                query_str += " AND c.price_per_day >= :min_price"
                params["min_price"] = min_price
                
            if max_price is not None:
                query_str += " AND c.price_per_day <= :max_price"
                params["max_price"] = max_price

            if start_date and end_date:
                query_str += """
                AND c.id NOT IN (
                    SELECT cua.car_id FROM car_un_availabilities cua
                    WHERE cua.is_active = 1
                    AND (
                        (cua.start_date BETWEEN :start_date AND :end_date)
                        OR (cua.end_date BETWEEN :start_date AND :end_date)
                        OR (cua.start_date <= :start_date AND cua.end_date >= :end_date)
                    )
                )
                """
                params["start_date"] = start_date
                params["end_date"] = end_date
                
            query_str += " LIMIT :limit"
            
            result = await db.execute(text(query_str), params)
            cars = result.mappings().all()
            
            if not cars:
                # --- SMART RECOMMENDATION FALLBACK ---
                # If exact match fails, drop the strict filters (price & type) and suggest ANY available car in the city
                fallback_str = """
                    SELECT c.id, c.make, c.model, c.year, c.vehicle_type, c.price_per_day, c.locality AS city,
                           c.rating, c.total_trips, c.number_of_seats, c.transmission, c.country, c.generate_code,
                           (SELECT id FROM media WHERE model_type LIKE '%Car' AND model_id = c.id ORDER BY id ASC LIMIT 1) AS media_id,
                           (SELECT file_name FROM media WHERE model_type LIKE '%Car' AND model_id = c.id ORDER BY id ASC LIMIT 1) AS media_file_name
                    FROM cars c
                    WHERE c.locality LIKE :city
                    AND LOWER(c.status) = 'approved'
                """
                
                fb_params = {"city": f"%{city}%", "limit": limit}
                
                if start_date and end_date:
                    fallback_str += """
                    AND c.id NOT IN (
                        SELECT cua.car_id FROM car_un_availabilities cua
                        WHERE cua.is_active = 1
                        AND (
                            (cua.start_date BETWEEN :start_date AND :end_date)
                            OR (cua.end_date BETWEEN :start_date AND :end_date)
                            OR (cua.start_date <= :start_date AND cua.end_date >= :end_date)
                        )
                    )
                    """
                    fb_params["start_date"] = start_date
                    fb_params["end_date"] = end_date
                    
                fallback_str += " LIMIT :limit"
                fb_result = await db.execute(text(fallback_str), fb_params)
                fallback_cars = fb_result.mappings().all()
                
                if not fallback_cars:
                    return f"I'm sorry, but I couldn't find any available cars in {city} right now."
                    
                response = "<p>I couldn't find an exact match for your specific criteria, but here are some great alternatives available in " + city + ":</p>"
                cars_to_render = fallback_cars
            else:
                response = "<p>Here are some great options I found for you:</p>"
                cars_to_render = cars
                
            response += "<div class='rdr-car-grid' style='display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; margin-top: 15px;'>"
            for car in cars_to_render:
                price = f"${float(car['price_per_day']):.2f}" if car['price_per_day'] else "Price TBD"
                
                # Default image if media not found
                img_url = "https://realdealride.com/public/frontend/images/cars/car-default.jpg"
                if car['media_id'] and car['media_file_name']:
                    img_url = f"https://realdealride.com/storage/{car['media_id']}/{car['media_file_name']}"
                
                rating = float(car['rating']) if car['rating'] else 5.0
                trips = car['total_trips'] if car['total_trips'] else 0
                seats = car['number_of_seats'] or 5
                doors = car.get('doors', 4) or 4
                transmission = "Auto" if str(car['transmission']).lower() == 'automatic' else str(car['transmission']).capitalize()
                
                response += f"<div class='rdr-car-card' style='background: #fff; border: 1px solid #E2E8F0; border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; box-shadow: 0 4px 6px rgba(0,0,0,0.05);'>"
                response += f"<div style='height: 140px; width: 100%; overflow: hidden;'><img src='{img_url}' style='width: 100%; height: 100%; object-fit: cover;' alt='{car['make']} {car['model']}' onerror=\"this.src='https://realdealride.com/public/frontend/images/placeholder.jpg'\"></div>"
                response += f"<div style='padding: 16px; flex-grow: 1; display: flex; flex-direction: column;'>"
                response += f"<h4 style='margin: 0 0 4px 0; font-size: 16px; color: #000000;'>{car['year']} {car['make']} {car['model']}</h4>"
                
                response += f"<div style='display: flex; align-items: center; gap: 4px; margin-bottom: 12px; font-size: 12px; font-weight: 500; color: #64748B;'>"
                response += f"<span style='color: #F59E0B;'>★ {rating}</span>"
                response += f"<span>• {trips} trips</span>"
                response += f"</div>"
                
                response += f"<div style='display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; font-size: 11px; color: #475569;'>"
                response += f"<span style='background: #F1F5F9; padding: 4px 8px; border-radius: 4px;'>💺 {seats} Seats</span>"
                response += f"<span style='background: #F1F5F9; padding: 4px 8px; border-radius: 4px;'>🚪 {doors} Doors</span>"
                response += f"<span style='background: #F1F5F9; padding: 4px 8px; border-radius: 4px;'>⚙️ {transmission}</span>"
                response += f"</div>"
                
                country = str(car['country']).lower() if car['country'] else "us"
                make = urllib.parse.quote(str(car['make']).lower()) if car['make'] else "make"
                model = urllib.parse.quote(str(car['model']).lower()) if car['model'] else "model"
                year = str(car['year']) if car['year'] else "year"
                gen_code = urllib.parse.quote(str(car['generate_code'])) if car['generate_code'] else ""
                detail_url = f"/{country}/car-rental/{make}/{model}/{year}/{gen_code}"

                response += f"<div style='margin-top: auto; padding-top: 12px; border-top: 1px solid #F1F5F9; display: flex; justify-content: space-between; align-items: center;'>"
                response += f"<div style='font-size: 14px; font-weight: 700; color: #1E293B;'>{price} <span style='font-size: 10px; font-weight: 400; color: #94A3B8;'>/ day</span></div>"
                response += f"<a href='{detail_url}' style='background: #ff240d; color: white; padding: 6px 12px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 600;' target='_blank'>Book</a>"
                response += f"</div>"
                
                response += f"</div></div>"
            response += "</div>"
                
            return response
            
        except Exception as e:
            print(f"Error querying Laravel DB: {e}")
            return "I'm having trouble accessing the live inventory right now. Please try again in a moment."

import random

async def check_user_reservations(member_id: int):
    """
    Retrieves all bookings/reservations for a logged-in user (member_id).
    Joins with the cars table to present car details.
    """
    if not member_id or member_id == 0:
        return "I couldn't find any reservations because you are not logged in. Please log in to check your booking status."
        
    async with LaravelSessionLocal() as db:
        try:
            # Query car_bookings joined with cars
            query_str = """
                SELECT b.reservation_id, b.status, b.customer_name, b.created_at,
                       c.year, c.make, c.model, c.price_per_day
                FROM car_bookings b
                JOIN cars c ON b.car_id = c.id
                WHERE b.customer_id = :customer_id
                ORDER BY b.created_at DESC
            """
            result = await db.execute(text(query_str), {"customer_id": member_id})
            bookings = result.mappings().all()
            
            if not bookings:
                return "I couldn't find any active or past car reservations for your account."
                
            response = "<p>Here are the reservations I found for your account:</p>"
            response += "<div style='display: flex; flex-direction: column; gap: 12px; margin-top: 10px;'>"
            for b in bookings:
                status_color = "#10B981" if b['status'] == 'Approved' else "#F59E0B"
                price = f"${float(b['price_per_day']):.2f}" if b['price_per_day'] else "Price TBD"
                # Safe date formatting
                date_str = b['created_at'].strftime('%Y-%m-%d') if b['created_at'] else 'N/A'
                response += f"""
                <div class='rdr-booking-card' style='background: #fff; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);'>
                    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;'>
                        <span style='font-size: 13px; font-weight: 600; color: #64748B;'>ID: {b['reservation_id']}</span>
                        <span style='font-size: 11px; font-weight: 700; background: {status_color}15; color: {status_color}; padding: 3px 8px; border-radius: 999px; text-transform: uppercase;'>{b['status']}</span>
                    </div>
                    <h5 style='margin: 0 0 6px 0; font-size: 15px; color: #1E293B;'>{b['year']} {b['make']} {b['model']}</h5>
                    <div style='font-size: 12px; color: #94A3B8;'>Price: {price}/day • Booked on: {date_str}</div>
                </div>
                """
            response += "</div>"
            return response
            
        except Exception as e:
            print(f"Error checking reservations: {e}")
            return "I ran into a problem while checking your reservations. Please try again in a moment."

async def create_support_ticket(member_id: int, subject: str, description: str, priority: str = "medium"):
    """
    Creates a new support ticket in the Laravel database for the user (member_id).
    Ensures a default support category exists first to satisfy foreign keys.
    """
    if not member_id or member_id == 0:
        return "I can't open a support ticket for you because you are not logged in. Please log in to file a ticket."
        
    async with LaravelSessionLocal() as db:
        try:
            # 1. Ensure a support category exists (foreign key constraint)
            cat_check = await db.execute(text("SELECT id FROM support_categories LIMIT 1"))
            category = cat_check.scalars().first()
            
            if not category:
                # Insert a default category
                insert_cat = """
                    INSERT INTO support_categories (id, name, description, status, sort_order, created_at, updated_at)
                    VALUES (1, 'General Support', 'Default category for chatbot support tickets', 'active', 0, NOW(), NOW())
                """
                await db.execute(text(insert_cat))
                await db.commit()
                category_id = 1
            else:
                category_id = category
                
            # 2. Generate a Unique Ticket ID
            ticket_num = random.randint(100000, 999999)
            ticket_id = f"TKT-{ticket_num}"
            
            # 3. Insert the support ticket
            insert_ticket = """
                INSERT INTO support_tickets (ticket_id, category_id, customer_id, priority, status, subject, description, created_at, updated_at)
                VALUES (:ticket_id, :category_id, :customer_id, :priority, 'open', :subject, :description, NOW(), NOW())
            """
            await db.execute(text(insert_ticket), {
                "ticket_id": ticket_id,
                "category_id": category_id,
                "customer_id": member_id,
                "priority": priority.lower(),
                "subject": subject,
                "description": description
            })
            await db.commit()
            
            return f"""
            <div style='background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 16px; color: #166534; margin-top: 10px;'>
                <h5 style='margin: 0 0 6px 0; font-size: 15px; font-weight: 700;'>Ticket Created Successfully!</h5>
                <p style='margin: 0 0 8px 0; font-size: 13px;'>I have opened an urgent support ticket for you.</p>
                <div style='font-size: 12px; font-weight: 600;'>Ticket ID: <span style='font-family: monospace;'>{ticket_id}</span></div>
                <div style='font-size: 12px;'>Subject: {subject}</div>
            </div>
            """
            
        except Exception as e:
            await db.rollback()
            print(f"Error creating support ticket: {e}")
            return "I failed to submit your support ticket. Please try again or contact us directly."

async def get_car_reviews(car_id: int):
    """
    Retrieves up to 5 customer reviews for a given vehicle (car_id) from the car_reviews table.
    """
    async with LaravelSessionLocal() as db:
        try:
            # Retrieve car year, make, model for user-friendly display
            car_info_res = await db.execute(text("SELECT year, make, model FROM cars WHERE id = :car_id"), {"car_id": car_id})
            car_row = car_info_res.first()
            car_name = f"{car_row[0]} {car_row[1]} {car_row[2]}" if car_row else f"Vehicle #{car_id}"

            query_str = """
                SELECT r.rating, r.text, r.created_at, u.name AS reviewer_name
                FROM car_reviews r
                LEFT JOIN users u ON r.renter_id = u.id
                WHERE r.car_id = :car_id
                AND r.deleted_at IS NULL
                ORDER BY r.created_at DESC
                LIMIT 5
            """
            result = await db.execute(text(query_str), {"car_id": car_id})
            reviews = result.mappings().all()
            
            if not reviews:
                return f"No reviews found for the {car_name}."
                
            response = f"<p>Here are the reviews for the {car_name}:</p>"
            response += "<div style='display: flex; flex-direction: column; gap: 8px; margin-top: 10px;'>"
            for r in reviews:
                date_str = r['created_at'].strftime('%Y-%m-%d') if r['created_at'] else 'N/A'
                reviewer = r['reviewer_name'] or "Anonymous"
                stars = "★" * int(round(r['rating'])) + "☆" * (5 - int(round(r['rating'])))
                response += f"""
                <div style='background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px;'>
                    <div style='display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 4px;'>
                        <strong style='color: #1E293B;'>{reviewer}</strong>
                        <span style='color: #64748B;'>{date_str}</span>
                    </div>
                    <div style='color: #F59E0B; font-size: 13px; margin-bottom: 6px;'>{stars} ({r['rating']}/5)</div>
                    <p style='margin: 0; font-size: 13px; color: #475569; font-style: italic;'>"{r['text']}"</p>
                </div>
                """
            response += "</div>"
            return response
        except Exception as e:
            print(f"Error fetching reviews: {e}")
            return "I couldn't fetch reviews for this car at this moment. Please try again."

async def get_car_discounts(car_id: int):
    """
    Retrieves active price discounts/rules for a specific vehicle (car_id) from car_price_discounts.
    """
    async with LaravelSessionLocal() as db:
        try:
            # Retrieve car year, make, model for user-friendly display
            car_info_res = await db.execute(text("SELECT year, make, model FROM cars WHERE id = :car_id"), {"car_id": car_id})
            car_row = car_info_res.first()
            car_name = f"{car_row[0]} {car_row[1]} {car_row[2]}" if car_row else f"Vehicle #{car_id}"

            query_str = """
                SELECT discount_name, noOfDays, discount_type, discount_rate
                FROM car_price_discounts
                WHERE car_id = :car_id AND is_active = 1
                ORDER BY noOfDays ASC
            """
            result = await db.execute(text(query_str), {"car_id": car_id})
            discounts = result.mappings().all()
            
            if not discounts:
                return f"No active discounts or promotions are currently registered for the {car_name}."
                
            response = f"<p>Here are the active rental discounts for the {car_name}:</p>"
            response += "<ul style='margin-top: 8px; padding-left: 20px; font-size: 13px; color: #334155; line-height: 1.6;'>"
            for d in discounts:
                rate_val = f"{d['discount_rate']}%" if d['discount_type'] == 'percentage' else f"${d['discount_rate']}"
                name = d['discount_name'] or "Long-term Discount"
                response += f"<li><strong>{name}</strong>: {rate_val} discount for rentals of <strong>{d['noOfDays']} days</strong> or more.</li>"
            response += "</ul>"
            return response
        except Exception as e:
            print(f"Error fetching discounts: {e}")
            return "I had trouble checking the price discounts for this vehicle. Please try again."

async def request_reservation_modification(member_id: int, booking_id_str: str, requested_start_date: str, requested_end_date: str, comment: str = None):
    """
    Submits a reservation modification request for a logged-in user.
    booking_id_str is the public reservation_id (e.g. '2503724608').
    """
    if not member_id or member_id == 0:
        return "You must be logged in to modify your reservation."
        
    async with LaravelSessionLocal() as db:
        try:
            # 1. Look up booking and payment
            query = """
                SELECT b.id AS booking_id, p.id AS payment_id, b.customer_id
                FROM car_bookings b
                LEFT JOIN payments p ON p.car_booking_id = b.id
                WHERE b.reservation_id = :res_id
            """
            result = await db.execute(text(query), {"res_id": booking_id_str})
            row = result.mappings().first()
            
            if not row:
                return f"Could not find any booking with reservation ID '{booking_id_str}'."
                
            if row['customer_id'] != member_id:
                return "Unauthorized: You do not own this reservation."
                
            if not row['payment_id']:
                return "This booking is not confirmed or paid, so it cannot be modified."
                
            # 2. Insert into reservation_modifications
            insert_query = """
                INSERT INTO reservation_modifications (reservation_id, user_id, requested_start_date, requested_end_date, comment, status, created_at, updated_at)
                VALUES (:payment_id, :user_id, :start_date, :end_date, :comment, 'Pending', NOW(), NOW())
            """
            await db.execute(text(insert_query), {
                "payment_id": row['payment_id'],
                "user_id": member_id,
                "start_date": requested_start_date,
                "end_date": requested_end_date,
                "comment": comment
            })
            await db.commit()
            
            return f"""
            <div style='background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 16px; color: #166534; margin-top: 10px;'>
                <h5 style='margin: 0 0 6px 0; font-size: 15px; font-weight: 700;'>Modification Request Submitted!</h5>
                <p style='margin: 0 0 8px 0; font-size: 13px;'>Your request to change trip dates is now pending review.</p>
                <div style='font-size: 12px;'><strong>Reservation ID:</strong> {booking_id_str}</div>
                <div style='font-size: 12px;'><strong>New Dates:</strong> {requested_start_date} to {requested_end_date}</div>
            </div>
            """
        except Exception as e:
            await db.rollback()
            print(f"Error modifying reservation: {e}")
            return "I failed to submit your modification request. Please verify the dates and try again."

async def request_booking_cancellation(member_id: int, booking_id_str: str, cancellation_reason: str = None, comment: str = None):
    """
    Submits a booking cancellation request for a logged-in user.
    booking_id_str is the public reservation_id (e.g. '2503724608').
    """
    if not member_id or member_id == 0:
        return "You must be logged in to cancel a reservation."
        
    async with LaravelSessionLocal() as db:
        try:
            # 1. Look up booking and payment details
            query = """
                SELECT b.id AS booking_id, b.customer_id, p.amount_total, p.sales_tax, p.tax_percent
                FROM car_bookings b
                LEFT JOIN payments p ON p.car_booking_id = b.id
                WHERE b.reservation_id = :res_id
            """
            result = await db.execute(text(query), {"res_id": booking_id_str})
            row = result.mappings().first()
            
            if not row:
                return f"Could not find any booking with reservation ID '{booking_id_str}'."
                
            if row['customer_id'] != member_id:
                return "Unauthorized: You do not own this reservation."
                
            refund_amount = row['amount_total'] or 0.00
            sales_tax = row['sales_tax'] or 0.00
            tax_rate = row['tax_percent'] or 0.00
            
            # 2. Insert into booking_cancellations
            insert_query = """
                INSERT INTO booking_cancellations (booking_id, user_id, cancellation_reason, comment, refund_amount, sales_tax_amount, sales_tax_rate, status, processed_by, created_at, updated_at)
                VALUES (:booking_id, :user_id, :reason, :comment, :refund_amount, :sales_tax, :tax_rate, 'Pending', 'User', NOW(), NOW())
            """
            await db.execute(text(insert_query), {
                "booking_id": row['booking_id'],
                "user_id": member_id,
                "reason": cancellation_reason,
                "comment": comment,
                "refund_amount": refund_amount,
                "sales_tax": sales_tax,
                "tax_rate": tax_rate
            })
            await db.commit()
            
            return f"""
            <div style='background: #FEF2F2; border: 1px solid #FCA5A5; border-radius: 8px; padding: 16px; color: #991B1B; margin-top: 10px;'>
                <h5 style='margin: 0 0 6px 0; font-size: 15px; font-weight: 700;'>Cancellation Request Submitted</h5>
                <p style='margin: 0 0 8px 0; font-size: 13px;'>Your cancellation request is pending host/admin approval.</p>
                <div style='font-size: 12px;'><strong>Reservation ID:</strong> {booking_id_str}</div>
                <div style='font-size: 12px;'><strong>Estimated Refund:</strong> ${float(refund_amount):.2f}</div>
            </div>
            """
        except Exception as e:
            await db.rollback()
            print(f"Error cancelling booking: {e}")
            return "I failed to submit your cancellation request. Please try again later."

async def search_db_faqs(query: str):
    """
    Searches active FAQs from the Laravel FAQs table.
    """
    async with LaravelSessionLocal() as db:
        try:
            query_str = """
                SELECT faq_question, faq_answer
                FROM faqs
                WHERE is_active = 1
                AND (faq_question LIKE :q OR faq_answer LIKE :q)
                LIMIT 3
            """
            result = await db.execute(text(query_str), {"q": f"%{query}%"})
            faqs = result.mappings().all()
            
            if not faqs:
                return ""
                
            response = "<p>Here are some matching FAQs from our help center:</p>"
            for f in faqs:
                response += f"""
                <div style='margin-bottom: 12px; padding: 10px; border-left: 3px solid #ff240d; background: #F8FAFC;'>
                    <strong style='font-size: 13px; color: #1E293B; display: block; margin-bottom: 4px;'>Q: {f['faq_question']}</strong>
                    <span style='font-size: 13px; color: #475569;'>A: {f['faq_answer']}</span>
                </div>
                """
            return response
        except Exception as e:
            print(f"Error querying faqs: {e}")
            return ""

async def lookup_user_by_email(email: str) -> dict:
    """
    Looks up a user's details (ID and Name) by their email address in the users table.
    Returns a dictionary with 'id' and 'name' if found, else None.
    """
    async with LaravelSessionLocal() as db:
        try:
            query = text("SELECT id, name FROM users WHERE email = :email LIMIT 1")
            result = await db.execute(query, {"email": email})
            row = result.first()
            if row:
                return {"id": row[0], "name": row[1]}
            return None
        except Exception as e:
            print(f"Error looking up user by email: {e}")
            return None

async def append_to_latest_support_ticket(member_id: int, text_to_append: str):
    """
    Looks up the latest support ticket for a user and appends new message content to its description.
    """
    if not member_id or member_id == 0:
        return
    async with LaravelSessionLocal() as db:
        try:
            # Find the latest ticket
            find_tkt = text("""
                SELECT ticket_id, description FROM support_tickets
                WHERE customer_id = :member_id
                ORDER BY created_at DESC LIMIT 1
            """)
            res = await db.execute(find_tkt, {"member_id": member_id})
            row = res.mappings().first()
            if row:
                current_desc = row['description'] or ""
                new_desc = f"{current_desc}\n\n[Additional Chat Detail]: {text_to_append}"
                update_tkt = text("""
                    UPDATE support_tickets SET description = :desc, updated_at = NOW()
                    WHERE ticket_id = :ticket_id
                """)
                await db.execute(update_tkt, {"desc": new_desc, "ticket_id": row['ticket_id']})
                await db.commit()
                print(f"Appended detail to ticket {row['ticket_id']} for customer {member_id}")
        except Exception as e:
            await db.rollback()
            print(f"Error appending detail to support ticket: {e}")

async def create_guest_user(email: str) -> dict:
    """
    Creates a new guest user in the users table so they can file support tickets.
    Returns a dictionary with 'id' and 'name' if created/found, else None.
    """
    async with LaravelSessionLocal() as db:
        try:
            # Check if exists (safety check)
            query = text("SELECT id, name FROM users WHERE email = :email LIMIT 1")
            result = await db.execute(query, {"email": email})
            row = result.first()
            if row:
                return {"id": row[0], "name": row[1]}
                
            # Create a new guest user
            insert_user = """
                INSERT INTO users (name, email, password, status, role, notifications_enabled, created_at, updated_at)
                VALUES ('Guest', :email, :password, 'Active', 'user', 1, NOW(), NOW())
            """
            placeholder_password = "$2y$10$GuestUserPlaceholderPasswordHashForRealDealRideChatbot"
            await db.execute(text(insert_user), {
                "email": email,
                "password": placeholder_password
            })
            await db.commit()
            
            # Fetch the newly created user ID
            res = await db.execute(text("SELECT id, name FROM users WHERE email = :email LIMIT 1"), {"email": email})
            new_row = res.first()
            if new_row:
                return {"id": new_row[0], "name": new_row[1]}
            return None
        except Exception as e:
            await db.rollback()
            print(f"Error creating guest user: {e}")
            return None

async def merge_guest_support_tickets(old_member_id: int, new_member_id: int):
    """
    Re-assigns support tickets from a guest member ID to a newly logged-in member ID.
    """
    if not old_member_id or not new_member_id or old_member_id == new_member_id:
        return
    async with LaravelSessionLocal() as db:
        try:
            update_query = text("""
                UPDATE support_tickets 
                SET customer_id = :new_id, updated_at = NOW()
                WHERE customer_id = :old_id
            """)
            await db.execute(update_query, {"new_id": new_member_id, "old_id": old_member_id})
            await db.commit()
            print(f"Merged support tickets from guest user {old_member_id} to logged-in user {new_member_id}")
        except Exception as e:
            await db.rollback()
            print(f"Error merging guest support tickets: {e}")

