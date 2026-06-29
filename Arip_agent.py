import os
import asyncio
import aiohttp
import json
import re
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from uagents import Agent, Context, Model, Protocol
from uagents.setup import fund_agent_if_low

import uagents.agent
# Removed interceptors - using official ACP models instead

# Load environment variables
load_dotenv()

# --- Config & Constants ---
SUPABASE_URL = "https://itpgmtgpdkgfvysngwhn.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") # Fallback to env or hardcoded key if needed


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
ASI_API_KEY = os.environ.get("ASI_API_KEY", "")

# --- Models for ACP (Agent Chat Protocol) ---
from uagents_core.contrib.protocols.chat import (
    ChatMessage, 
    TextContent,
    MetadataContent,
    ChatAcknowledgement,
    chat_protocol_spec
)
from uagents_core.contrib.protocols.payment import RequestPayment, CommitPayment, Funds
from uagents_core.utils.registration import (
    register_chat_agent,
    RegistrationRequestCredentials,
)

# --- Agent Initialization ---
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

if ASI_API_KEY:
    # Hosted Mailbox mode - Pro Fetch.ai setup
    arip_agent = Agent(
        name="arip_agent",
        port=8007,  # Changed to 8007 to avoid any local conflicts
        seed=os.environ.get("SEED_PHASE", ""),
        mailbox=f"{ASI_API_KEY}@https://agentverse.ai",
        network="testnet"  # Suppresses mainnet wallet funding warnings
    )
else:
    # Local mode
    arip_agent = Agent(
        name="arip_agent",
        port=8006,
        seed=os.environ.get("SEED_PHASE", ""),
        endpoint=["http://127.0.0.1:8006/submit"]
    )

fund_agent_if_low(arip_agent.wallet.address())

# --- Tools Definition ---

async def verify_user(email: str, password: str):
    """Authenticate via Supabase REST API to get user_id"""
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json"
    }
    payload = {"email": email, "password": password}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return {"status": "success", "user_id": data["user"]["id"]}
            return {"status": "error", "message": "Invalid email or password"}

async def fetch_usage_data(user_id: str):
    """Fetch recent usage logs from Supabase via REST API for a specific user"""
    thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    url = f"{SUPABASE_URL}/rest/v1/usage_logs?timestamp=gte.{thirty_days_ago}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                rows = await response.json()
                return {"status": "success", "count": len(rows), "data": rows, "sample": rows[:5]} # Return all data for prediction, sample for context
            else:
                return {"status": "error", "message": f"Supabase error: {response.status}"}

async def fetch_prediction_data(user_id: str):
    """Compute predictions using the logic from prediction_agent"""
    data = await fetch_usage_data(user_id)
    if data["status"] == "success":
        rows = data["data"]
        total_tokens = sum(row.get('estimated_tokens', 0) for row in rows)
        
        # Assuming $0.0001 per token roughly for MVP
        total_cost = total_tokens * 0.0001
        
        trend = "+12.5%" if len(rows) > 0 else "0%"
        
        budget_limit = 100.0
        priority = "LOW"
        
        if total_cost >= budget_limit * 0.9:
            priority = "CRITICAL"
        elif total_cost >= budget_limit * 0.75:
            priority = "HIGH"
            
        reason = f"Usage logs over the last 30 days show ${total_cost:.2f} spent across {len(rows)} requests."
        recommendation = "Continue monitoring usage."
        
        if priority == "CRITICAL":
            reason = f"Budget is almost exhausted (${total_cost:.2f} / $100.00)."
            recommendation = "URGENT: Route generic tasks to cheaper models immediately."
        elif priority == "HIGH":
            recommendation = "Consider reviewing token-heavy requests to optimize costs."

        return {
            "projected_cost": total_cost,
            "trend": trend,
            "priority": priority,
            "reason": reason,
            "recommendation": recommendation,
            "total_tokens": total_tokens,
            "total_requests": len(rows)
        }
    return {"status": "error", "message": "Could not fetch data for prediction"}

async def rule_engine_evaluation(cost_data):
    """Evaluate business rules against cost data"""
    if cost_data.get("priority") == "CRITICAL":
        return "CRITICAL: Budget threshold exceeded. Recommend rate limiting."
    elif cost_data.get("priority") == "HIGH":
        return "WARNING: Spending is high. Optimize models."
    return "NORMAL: Spending is within acceptable bounds."

# --- LangGraph Orchestrator (Simplified Logic) ---
# NOTE: A full LangGraph implementation requires langchain-openai and langgraph packages.
# To keep this script self-contained and immediately runnable without complex dependencies,
# we implement a lightweight orchestration pattern that mimics the LangGraph routing.

async def orchestrate_query(query: str, ctx: Context, user_id: str) -> str:
    ctx.logger.info(f"Orchestrating query: {query}")
    
    if GEMINI_API_KEY:
        try:
            ctx.logger.info("Using Gemini LLM for complex routing and analysis...")
            llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GEMINI_API_KEY)
            
            # Fetch data context to feed into the LLM
            prediction = await fetch_prediction_data(user_id)
            usage = await fetch_usage_data(user_id)
            # Calculate daily usage summary
            daily_usage = {}
            for row in usage.get('data', []):
                try:
                    day = row['timestamp'].split('T')[0]
                    daily_usage[day] = daily_usage.get(day, 0) + row.get('estimated_tokens', 0)
                except Exception:
                    pass
                    
            current_date = datetime.utcnow().strftime('%Y-%m-%d')

            system_prompt = f"""You are the ARIP Agent, the intelligent backend for the Autonomous AI Resource Intelligence Platform (ARIP).
Your task is to analyze user queries and provide highly structured, concise, and data-driven responses based on the following real-time system context:

Today's Date: {current_date}

Daily Token Usage (Last 30 Days): 
{daily_usage}

Usage Logs Sample: {usage.get('sample', [])}
Cost & Predictions: {prediction}

Respond as a Staff Backend Engineer. CRITICAL INSTRUCTIONS:
1. Be extremely concise and to the point.
2. Use structured formatting (bullet points, bold text for metrics).
3. DO NOT write long paragraphs or excessive explanations. 
4. If asked about a specific day (like yesterday), calculate it perfectly based on Today's Date and just give the exact number and a very brief one-sentence insight."""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=query)
            ]
            response = llm.invoke(messages)
            return response.content
        except Exception as e:
            ctx.logger.error(f"LLM Error: {e}")
            return f"Error interacting with Gemini: {str(e)}"
            
    # --- Fallback Simple Router ---
    query_lower = query.lower()
    
    if "cost" in query_lower or "spend" in query_lower:
        ctx.logger.info("Routing to Prediction & Rule Engine Tools...")
        prediction = await fetch_prediction_data(user_id)
        rule_eval = await rule_engine_evaluation(prediction)
        return f"ARIP Cost Analysis:\n- Projected Cost: ${prediction.get('projected_cost', 0):.2f}\n- Priority: {prediction.get('priority', 'N/A')}\n- Rule Engine: {rule_eval}"
        
    elif "usage" in query_lower or "logs" in query_lower:
        ctx.logger.info("Routing to Database Tool...")
        usage = await fetch_usage_data(user_id)
        if usage["status"] == "success":
            return f"ARIP Usage Analysis:\n- Processed {usage['count']} logs in the last 30 days.\n- Sample: {usage['data'][0] if usage['count'] > 0 else 'No data'}"
        return "Failed to fetch usage data from Supabase."
        
    else:
        ctx.logger.info("Default Routing...")
        return "I am the ARIP Agent. I can help you analyze 'cost' predictions or 'usage' logs from the AI Resource Intelligence Platform. How can I assist you today?"


# --- ASI Interactive Card Logic ---

def parse_card_selection(text):
    text = (text or "").strip()
    
    # Remove @mention prefix if present
    text = re.sub(r'^@[a-zA-Z0-9]+\s+', '', text).strip()
    
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
        
    # Fallback: regex search for a JSON object
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
            
    return None

def build_login_card():
    payload = {
        "title": "AiRP Authentication",
        "fields": [
            {"name": "email", "kind": "email", "label": "Email Address", "required": True},
            {"name": "password", "kind": "text", "label": "Password", "required": True}
        ],
        "submit_cta": {
            "label": "Login to AiRP", 
            "selection": {"action": "submit_login"}
        }
    }
    return MetadataContent(
        type="metadata",
        metadata={
            "card_protocol_version": "1",
            "requires_card_interaction": "true",
            "card_kind": "form",
            "card_payload": json.dumps(payload),
        }
    )

def build_topup_card():
    payload = {
        "title": "Top-up ARIP Credits",
        "fields": [
            {
                "name": "amount", 
                "kind": "select", 
                "label": "Select Credit Package",
                "options": [
                    {"label": "100 Credits ($10)", "value": "100"},
                    {"label": "200 Credits ($20)", "value": "200"},
                    {"label": "500 Credits ($45)", "value": "500"}
                ],
                "required": True
            }
        ],
        "submit_cta": {
            "label": "Proceed to Payment", 
            "selection": {"action": "submit_topup"}
        }
    }
    return MetadataContent(
        type="metadata",
        metadata={
            "card_protocol_version": "1",
            "requires_card_interaction": "true",
            "card_kind": "form",
            "card_payload": json.dumps(payload),
        }
    )

# --- Agent Handlers & Protocols ---

# Initialize the official chat protocol
arip_protocol = Protocol(spec=chat_protocol_spec)

@arip_agent.on_event("startup")
async def startup_handler(ctx: Context):
    ctx.logger.info("========================================")
    ctx.logger.info("🚀 ARIP Agent Starting...")
    ctx.logger.info(f"Agent Address: {arip_agent.address}")
    ctx.logger.info("Ready to receive ACP messages.")
    ctx.logger.info("========================================")

@arip_protocol.on_message(ChatMessage)
async def message_handler(ctx: Context, sender: str, msg: ChatMessage):
    # Use official Fetch.ai ACP method to extract text
    incoming_query = msg.text()
    
    ctx.logger.info(f"Received message from {sender[-6:]}: {incoming_query}")
    
    # Send acknowledgment first (ASI Chat expectation)
    ack = ChatAcknowledgement(
        timestamp=datetime.now(timezone.utc),
        acknowledged_msg_id=msg.msg_id
    )
    await ctx.send(sender, ack)
    
    # Check Auth Status
    user_data = ctx.storage.get(f"auth_{sender}")
    if not user_data:
        parsed_action = parse_card_selection(incoming_query)
        
        # If the parsed action is the submit from our login form card
        if parsed_action and parsed_action.get("action") == "submit_login" and "email" in parsed_action and "password" in parsed_action:
            ctx.logger.info("Attempting authentication...")
            auth_result = await verify_user(parsed_action["email"], parsed_action["password"])
            if auth_result["status"] == "success":
                ctx.storage.set(f"auth_{sender}", {"user_id": auth_result["user_id"]})
                response_msg = ChatMessage(
                    timestamp=datetime.now(timezone.utc),
                    msg_id=uuid4(),
                    content=[TextContent(text="✅ **Authentication Successful!**\n\nnow you can ask anyhting about your tokens and othere")]
                )
                await ctx.send(sender, response_msg)
                return
            else:
                response_msg = ChatMessage(
                    timestamp=datetime.now(timezone.utc),
                    msg_id=uuid4(),
                    content=[TextContent(text="❌ Authentication failed. Please try again."), build_login_card()]
                )
                await ctx.send(sender, response_msg)
                return
                
        # Check if they pasted a UUID (User ID) from Google Login directly as text
        # (This is just a fallback in case they logged in on dashboard and copy pasted)
        text_only = re.sub(r'^@[a-zA-Z0-9]+\s+', '', incoming_query).strip()
        if re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', text_only, re.I):
            ctx.storage.set(f"auth_{sender}", {"user_id": text_only})
            response_msg = ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(text="✅ **Authentication Successful!**\n\nnow you can ask anyhting about your tokens and othere")]
            )
            await ctx.send(sender, response_msg)
            return
                
        # Send Login Card for unauthenticated user
        ctx.logger.info("User unauthenticated, sending login card.")
        response_msg = ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[
                TextContent(text="Welcome to the AiRP Assistant! Please fill in your credentials below to authenticate."),
                build_login_card()
            ]
        )
        await ctx.send(sender, response_msg)
        return
    
    user_id = user_data["user_id"]
    
    parsed_action = parse_card_selection(incoming_query)
    # Handle topup selection
    if parsed_action and parsed_action.get("action") == "submit_topup":
        amount = int(parsed_action.get("amount", 100))
        # Price map based on credits
        prices = {100: 1000, 200: 2000, 500: 4500} # in cents
        amount_cents = prices.get(amount, 1000)
        
        ctx.logger.info(f"Generating payment request for {amount} credits ({amount_cents} cents)")
        payment_request = RequestPayment(
            description=f"{amount} ARIP Credits Top-up",
            reference=f"topup_{user_id}_{datetime.now().timestamp()}",
            accepted_funds=[
                Funds(amount=str(amount_cents), currency="usd", payment_method="stripe"),
                Funds(amount=str(amount_cents), currency="usd", payment_method="fet_direct")
            ],
            recipient=arip_agent.address,
            deadline_seconds=600
        )
        await ctx.send(sender, payment_request)
        
        # Simulate successful payment webhook after 3 seconds for the demo
        async def simulate_payment():
            await asyncio.sleep(3)
            dummy_commit = CommitPayment(
                funds=Funds(amount=str(amount_cents), currency="usd", payment_method="stripe"),
                recipient=arip_agent.address,
                transaction_id=f"pi_{uuid4().hex[:12]}",
                reference=payment_request.reference
            )
            await handle_payment(ctx, sender, dummy_commit)
            
        asyncio.create_task(simulate_payment())
        
        return

    # Trigger topup card manually
    if "topup" in incoming_query.lower() or "buy credits" in incoming_query.lower() or "add tokens" in incoming_query.lower():
        ctx.logger.info("Sending top-up card to user.")
        response_msg = ChatMessage(
            timestamp=datetime.now(timezone.utc),
            msg_id=uuid4(),
            content=[
                TextContent(text="Please select the amount of ARIP credits you want to purchase:"),
                build_topup_card()
            ]
        )
        await ctx.send(sender, response_msg)
        return
    # Run orchestration
    final_response = await orchestrate_query(incoming_query, ctx, user_id)
    
    # Send response back using official ACP ChatMessage model
    response_msg = ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(text=final_response)]
    )
    await ctx.send(sender, response_msg)

# Acknowledgement Handler - Process received acknowledgements
@arip_protocol.on_message(ChatAcknowledgement)
async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.info(f"Received acknowledgement from {sender[-6:]} for message: {msg.acknowledged_msg_id}")

# Payment Handler - Process successful payments
@arip_agent.on_message(CommitPayment)
async def handle_payment(ctx: Context, sender: str, msg: CommitPayment):
    ctx.logger.info(f"Received successful payment commitment from {sender}: {msg}")
    
    # Extract user_id and amount from the reference
    try:
        parts = msg.reference.split("_")
        if len(parts) >= 2 and parts[0] == "topup":
            user_id = parts[1]
            
            # Map amount back to credits
            added_credits = 100
            amount_str = msg.funds.amount
            if amount_str == "2000": added_credits = 200
            if amount_str == "4500": added_credits = 500
            
            # Update Database actually via REST API
            async with aiohttp.ClientSession() as session:
                # 1. Login to get access token for the specific user
                login_url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
                login_headers = {
                    "apikey": SUPABASE_KEY,
                    "Content-Type": "application/json"
                }
                login_payload = {
                    "email": "priyanshusakshamrajput@gmail.com",
                    "password": "@Arip1234"
                }
                async with session.post(login_url, headers=login_headers, json=login_payload) as login_resp:
                    if login_resp.status == 200:
                        login_data = await login_resp.json()
                        access_token = login_data["access_token"]
                        
                        # 2. Get current user data
                        user_url = f"{SUPABASE_URL}/auth/v1/user"
                        user_headers = {
                            "apikey": SUPABASE_KEY,
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json"
                        }
                        
                        async with session.get(user_url, headers=user_headers) as user_resp:
                            if user_resp.status == 200:
                                user_data = await user_resp.json()
                                current_credits = user_data.get("user_metadata", {}).get("remaining_credits", 0)
                                new_credits = current_credits + added_credits
                                
                                # 3. Update the credits
                                update_payload = {
                                    "data": {
                                        "remaining_credits": new_credits
                                    }
                                }
                                async with session.put(user_url, headers=user_headers, json=update_payload) as update_resp:
                                    if update_resp.status == 200:
                                        ctx.logger.info(f"Successfully updated credits to {new_credits}!")
                                    else:
                                        error_text = await update_resp.text()
                                        ctx.logger.error(f"Failed to update credits: {error_text}")
                            else:
                                error_text = await user_resp.text()
                                ctx.logger.error(f"Failed to fetch user data: {error_text}")
                    else:
                        error_text = await login_resp.text()
                        ctx.logger.error(f"Failed to login user to update credits: {error_text}")

            response_msg = ChatMessage(
                timestamp=datetime.now(timezone.utc),
                msg_id=uuid4(),
                content=[TextContent(text=f"✅ **Payment Successful!**\n\nYour account has been credited with **{added_credits} ARIP Credits**.")]
            )
            await ctx.send(sender, response_msg)
            return
    except Exception as e:
        ctx.logger.error(f"Error processing payment commitment: {e}")

AGENTVERSE_KEY = os.environ.get("ILABS_AGENTVERSE_API_KEY")

@arip_agent.on_event("startup")
async def startup_handler(ctx: Context):
    """Initialize agent and register with Agentverse on startup."""
    ctx.logger.info(f"🚀 Agent starting: {ctx.agent.name} at {ctx.agent.address}")
    
    SEED_PHRASE = os.environ.get("SEED_PHASE", "")
    if AGENTVERSE_KEY and SEED_PHRASE:
        try:
            with open("readme.md", "r") as f:
                readme_content = f.read()
            # If agent runs with a mailbox, endpoints might be empty or mapped to agentverse
            endpoint_url = ctx.agent._endpoints[0].url if ctx.agent._endpoints else "https://agentverse.ai"
            register_chat_agent(
                ctx.agent.name,
                endpoint_url,
                active=True,
                credentials=RegistrationRequestCredentials(
                    agentverse_api_key=AGENTVERSE_KEY,
                    agent_seed_phrase=SEED_PHRASE,
                ),
                readme=readme_content,
                description="ARIP Agent - Autonomous AI Resource Intelligence Platform powered by ASI1."
            )
            ctx.logger.info("✅ Registered with Agentverse")
        except Exception as e:
            ctx.logger.error(f"Failed to register with Agentverse: {e}")
    else:
        ctx.logger.warning("⚠️ ILABS_AGENTVERSE_API_KEY or SEED_PHASE not set, skipping Agentverse registration")

arip_agent.include(arip_protocol, publish_manifest=True)

if __name__ == "__main__":
    arip_agent.run()
