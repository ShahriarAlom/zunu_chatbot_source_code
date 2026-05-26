import os
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

# Initialize the Gemini Flash Lite Model
llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

from sqlalchemy.ext.asyncio import AsyncSession
from retrieval import retrieve_context
from operational_api import (
    search_available_cars,
    check_user_reservations,
    create_support_ticket,
    get_car_reviews,
    get_car_discounts,
    request_reservation_modification,
    request_booking_cancellation,
    search_db_faqs,
    lookup_user_by_email,
    create_guest_user
)
from langchain_core.tools import tool
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

async def generate_bot_response(user_message: str, db: AsyncSession, history: list = None, member_id: int = 0, session_id: str = None) -> str:
    """
    Intelligent Agent Pipeline.
    Uses tools and conversation memory to dynamically fulfill user requests.
    """
    if history is None:
        history = []

    # 1. Query database ChatSession to get the persisted member_id for this session
    db_member_id = 0
    if session_id:
        from sqlalchemy import select
        from database import ChatSession
        try:
            result = await db.execute(select(ChatSession.member_id).where(ChatSession.session_id == session_id))
            db_member_id = result.scalar() or 0
        except Exception as e:
            print(f"Error querying ChatSession member_id: {e}")

    # Use db_member_id if found, otherwise fallback to the passed member_id
    current_member_id = db_member_id if db_member_id > 0 else member_id

    # A user is securely logged in ONLY if the initial connect had member_id > 0.
    # If member_id was 0, they are a guest (even if they dynamically verified their email).
    is_securely_logged_in = (member_id > 0)

    # Mutable user context to allow dynamic authentication of guest sessions via email lookup
    user_context = {
        "member_id": current_member_id,
        "name": None,
        "is_securely_logged_in": is_securely_logged_in
    }
        
    @tool(return_direct=True)
    async def search_car_inventory_tool(city: str, vehicle_type: str = None, min_price: int = None, max_price: int = None, start_date: str = None, end_date: str = None) -> str:
        """
        Searches the RealDealRide live database for available cars to rent.
        Use this tool whenever the user wants to find a car, check inventory, filter by price, or book a car.
        Args:
            city: The city name (e.g. 'Germantown', 'Gainesville').
            vehicle_type: Optional. e.g. 'SUV', 'Van', 'Sedan'.
            min_price: Optional minimum price per day.
            max_price: Optional maximum price per day.
            start_date: Optional rental start date in YYYY-MM-DD format.
            end_date: Optional rental end date in YYYY-MM-DD format.
        """
        return await search_available_cars(city=city, vehicle_type=vehicle_type, min_price=min_price, max_price=max_price, start_date=start_date, end_date=end_date)

    @tool
    async def search_company_policies_tool(query: str) -> str:
        """
        Searches the RealDealRide knowledge base and dynamic website FAQs for company rules, policies, fees, contact info, privacy policies, office locations, and general FAQ.
        Use this tool whenever the user asks a question about how the service works, rules, or general company information.
        """
        # Search Vector DB
        context = await retrieve_context(query, db)
        # Search Dynamic DB FAQs
        faq_context = await search_db_faqs(query)
        
        combined = ""
        if context:
            combined += f"### Policy Documents:\n{context}\n\n"
        if faq_context:
            combined += f"### Dynamic FAQs:\n{faq_context}\n\n"
            
        if not combined:
            return "No specific policies or FAQs found. Proceed to answer based on general knowledge or politely offer human support."
        return combined

    @tool
    async def lookup_user_by_email_tool(email: str) -> str:
        """
        Looks up a registered user by their email address to authenticate them for account-specific queries.
        Use this tool when a guest user (who is not logged in) wants to check their reservations, file a ticket, cancel or modify a booking, and provides their email.
        Args:
            email: The email address to look up.
        """
        user_info = await lookup_user_by_email(email)
        is_new_guest = False
        if not user_info:
            user_info = await create_guest_user(email)
            is_new_guest = True
            
        if user_info:
            user_context["member_id"] = user_info["id"]
            user_context["name"] = user_info["name"]
            
            # Update ChatSession in database so that it persists for this session
            if session_id:
                from sqlalchemy import update
                from database import ChatSession
                try:
                    await db.execute(
                        update(ChatSession)
                        .where(ChatSession.session_id == session_id)
                        .values(member_id=user_info["id"])
                    )
                    await db.commit()
                except Exception as e:
                    await db.rollback()
                    print(f"Error updating ChatSession with retrieved member_id: {e}")
                    
            if is_new_guest:
                return f"Success: Registered and authenticated new guest user {user_info['name']} (ID: {user_info['id']}) for email {email}. They are now authenticated for this session. You can now use tools on their behalf."
            else:
                return f"Success: Found user {user_info['name']} (ID: {user_info['id']}) for email {email}. They are now authenticated for this session. You can now use tools on their behalf."
        else:
            return f"Error: Unable to authenticate or create guest user for email address '{email}'."

    @tool(return_direct=True)
    async def check_reservation_status_tool() -> str:
        """
        Retrieves all active or past car reservations and bookings for the logged-in user.
        Use this tool whenever the user asks about the status of their reservation, booking, or trip.
        """
        if not user_context["member_id"] or user_context["member_id"] == 0:
            return "I'd be happy to check your reservation status! Could you please tell me the email address associated with your RealDealRide account?"
            
        if not user_context["is_securely_logged_in"]:
            return "For security reasons, you must be logged in to your RealDealRide account to view reservation details. Please log in to the website and try again."
            
        return await check_user_reservations(member_id=user_context["member_id"])

    @tool(return_direct=True)
    async def create_support_ticket_tool(subject: str, description: str, priority: str = "medium") -> str:
        """
        Creates a new support ticket in the database for the logged-in user.
        Use this tool whenever the user has an issue, complaint, or wants to contact support, open a ticket, or file a complaint.
        Args:
            subject: The short summary/title of the issue.
            description: The detailed explanation of the user's issue.
            priority: The priority of the issue. Allowed values: 'low', 'medium', 'high', 'urgent'. Default is 'medium'.
        """
        if not user_context["member_id"] or user_context["member_id"] == 0:
            return "I can help you file a support ticket! Could you please provide the email address associated with your RealDealRide account?"
        
        ticket_res = await create_support_ticket(member_id=user_context["member_id"], subject=subject, description=description, priority=priority)
        
        # Mark session as escalated in the DB and update socket manager state
        if session_id:
            from sqlalchemy import update
            from database import ChatSession
            try:
                await db.execute(
                    update(ChatSession)
                    .where(ChatSession.session_id == session_id)
                    .values(was_escalated=True)
                )
                await db.commit()
            except Exception as e:
                await db.rollback()
                print(f"Error marking ChatSession as escalated: {e}")
                
            from socket_manager import manager
            await manager.set_session_state_pending(session_id, db, user_context["member_id"])
            
        return ticket_res

    @tool(return_direct=True)
    async def get_car_reviews_tool(car_id: int) -> str:
        """
        Retrieves up to 5 customer reviews and star ratings for a specific vehicle.
        Use this tool whenever the user asks about the rating, reviews, customer feedback, or experiences with a specific car (using its car_id).
        """
        return await get_car_reviews(car_id=car_id)

    @tool(return_direct=True)
    async def get_car_discounts_tool(car_id: int) -> str:
        """
        Retrieves active promotional discounts and duration rules (e.g. 7+ day or weekly discounts) for a specific vehicle.
        Use this tool whenever the user asks about discounts, special prices, promotions, long-term deals, or weekly rates for a specific car (using its car_id).
        """
        return await get_car_discounts(car_id=car_id)

    @tool(return_direct=True)
    async def request_reservation_modification_tool(booking_id: str, requested_start_date: str, requested_end_date: str, comment: str = None) -> str:
        """
        Submits a pending request to change the start/end dates of an active reservation.
        Use this tool when a logged-in user wants to modify their reservation dates, extend their trip, or shift their booking schedule.
        Args:
            booking_id: The public reservation ID string (e.g., '2503724608').
            requested_start_date: The requested new start date in YYYY-MM-DD format.
            requested_end_date: The requested new end date in YYYY-MM-DD format.
            comment: Optional reason or comments for the host/administrator.
        """
        if not user_context["member_id"] or user_context["member_id"] == 0:
            return "I can help you modify your reservation! Could you please tell me the email address associated with your RealDealRide account first?"
            
        if not user_context["is_securely_logged_in"]:
            return "For security reasons, you must be logged in to your RealDealRide account to request reservation modifications. Please log in to the website and try again."
            
        return await request_reservation_modification(
            member_id=user_context["member_id"],
            booking_id_str=booking_id,
            requested_start_date=requested_start_date,
            requested_end_date=requested_end_date,
            comment=comment
        )

    @tool(return_direct=True)
    async def request_booking_cancellation_tool(booking_id: str, cancellation_reason: str = None, comment: str = None) -> str:
        """
        Submits a pending request to cancel a confirmed booking/reservation.
        Use this tool when a logged-in user wants to cancel their reservation or booking.
        Args:
            booking_id: The public reservation ID string (e.g., '2503724608').
            cancellation_reason: Optional short explanation of why the user is cancelling.
            comment: Optional extra comments.
        """
        if not user_context["member_id"] or user_context["member_id"] == 0:
            return "I can help you cancel your reservation! Could you please tell me the email address associated with your RealDealRide account first?"
            
        if not user_context["is_securely_logged_in"]:
            return "For security reasons, you must be logged in to your RealDealRide account to request a booking cancellation. Please log in to the website and try again."
            
        return await request_booking_cancellation(
            member_id=user_context["member_id"],
            booking_id_str=booking_id,
            cancellation_reason=cancellation_reason,
            comment=comment
        )

    tools = [
        search_car_inventory_tool,
        search_company_policies_tool,
        lookup_user_by_email_tool,
        check_reservation_status_tool,
        create_support_ticket_tool,
        get_car_reviews_tool,
        get_car_discounts_tool,
        request_reservation_modification_tool,
        request_booking_cancellation_tool
    ]
    
    # Dynamically inject the user's login state into the prompt to guide the LLM agent
    if user_context["member_id"] > 0:
        if user_context["is_securely_logged_in"]:
            user_status = f"Current User: Logged-in Member (ID: {user_context['member_id']}, Securely Authenticated)"
        else:
            user_status = f"Current User: Guest User (ID: {user_context['member_id']}, Dynamically Verified Email)"
    else:
        user_status = "Current User: Anonymous Guest (Not Authenticated)"
    
    system_prompt = f"""You are Junu, the RealDealRide AI Assistant.
You help users book cars, check their reservation status, create support tickets, modify or cancel bookings, look up car reviews/discounts, and answer questions about RealDealRide policies.

{user_status}

Security & Authentication Policy:
- Logged-in members (Securely Authenticated) have full access to view, modify, cancel reservations, and submit support tickets.
- Anonymous Guests must be authenticated via email before performing account-specific actions. Prompt: "I'd be happy to help with that! Could you please tell me the email address associated with your account?"
- Guests who have verified their email (Dynamically Verified Email) are only allowed to submit support tickets. They are strictly blocked from checking reservation details, modifying reservations, or cancelling reservations due to lack of a secure session token. If they attempt these, the system tool will return a security blocking message. You should explain that they need to log in to the website securely first to perform reservation modifications/viewing.

Core Capabilities:
- Search and book cars: You can search our live car inventory by city, type (SUV, Sedan, Van, etc.), and price.
- Check reservation status: You can look up active and past bookings for securely logged-in users.
- Support tickets: You can open official support tickets directly in our system if a user has an issue.
- Modify/Cancel Reservations: You can file pending reservation modification requests or cancellation requests for securely logged-in users.
- Car Reviews & Discounts: You can fetch customer feedback, ratings, and active promotional discounts for specific vehicles.
- Policy knowledge: You can answer questions about rental rules, age limits, deposits, cancellation policies, etc.

Behavior Guidelines:
- Be friendly, helpful, clear, and concise.
- Never invent policies, procedures, reviews, or discounts.
- When you use the search_car_inventory_tool, check_reservation_status_tool, create_support_ticket_tool, request_reservation_modification_tool, or request_booking_cancellation_tool, the tool will return HTML code for the UI. You MUST return this HTML code EXACTLY as provided without altering it or wrapping it in Markdown blocks. Do not add ```html blocks around the output.
- If the user asks a conversational question that doesn't require a tool, just answer it directly.
"""

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
    )
    
    # Format history for LangChain
    messages = []
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
            
    # Append current user message
    messages.append(HumanMessage(content=user_message))
            
    try:
        response = await agent.ainvoke({
            "messages": messages
        })
        last_message = response["messages"][-1]
        content = last_message.content
        if isinstance(content, list):
            text_blocks = []
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    text_blocks.append(block["text"])
                elif isinstance(block, str):
                    text_blocks.append(block)
            return "".join(text_blocks)
        elif isinstance(content, str):
            return content
        return str(content)
    except Exception as e:
        print(f"Agent Error: {e}")
        return "I am experiencing technical difficulties. Please wait while I connect you to a human agent."
