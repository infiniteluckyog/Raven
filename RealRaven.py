import telebot
import asyncio
import aiohttp
import time
import re
import threading
import json
import random

# Update the bot token
BOT_TOKEN = "7294739772:AAHRDxPnLz57Jacnejn_AVrqKMT3kbJSbIo"
bot = telebot.TeleBot(BOT_TOKEN)  

with open("country_map.json", encoding="utf-8") as f:
    COUNTRY_MAP = json.load(f)

try:
    with open("country_code.txt", encoding="utf-8") as f:
        VALID_COUNTRY_CODES = {line.split(':')[0].strip(): line.split(':')[1].strip() for line in f}
except FileNotFoundError:
    print("country_code.txt file not found. Please ensure it exists in the same directory as this script.")
    VALID_COUNTRY_CODES = {}

vbv_antispam = {}
mass_vbv_antispam = {}

def extract_bin(bin_input):
    parts = bin_input.strip().split('|')
    bin_number = parts[0]
    month = parts[1] if len(parts) > 1 and parts[1].lower() != "xx" else None
    year = parts[2] if len(parts) > 2 else None
    return bin_number, month, year

async def lookup_bin(bin_number):
    url = f"https://bins.antipublic.cc/bins/{bin_number[:6]}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                bin_data = await response.json()
                country_code = bin_data.get('country', 'XX')
                if country_code:
                    country_code = country_code.upper()
                country_name, flag = COUNTRY_MAP.get(country_code, ("NOT FOUND", "🏳️"))
                return {
                    "bin": bin_number[:6],  
                    "bank": bin_data.get('bank', 'NOT FOUND').upper() if bin_data.get('bank') else 'NOT FOUND',
                    "card_type": bin_data.get('type', 'NOT FOUND').upper() if bin_data.get('type') else 'NOT FOUND',
                    "network": bin_data.get('brand', 'NOT FOUND').upper() if bin_data.get('brand') else 'NOT FOUND',
                    "tier": bin_data.get('level', 'NOT FOUND').upper() if bin_data.get('level') else 'NOT FOUND',
                    "country": country_name,
                    "flag": flag
                }
            else:
                return {"error": f"API error: {response.status}"}

async def check_vbv(cc):
    card_number = ''.join(filter(str.isdigit, cc.split('|')[0]))  # Strip non-numeric characters
    url = f"https://api.voidapi.xyz/v2/vbv?card={card_number}&key=VDX-SHA2X-NZ0RS-O7HAM"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as response:
            try:
                if response.status != 200:
                    return {"error": f"Failed to fetch data. Status: {response.status}"}
                data = await response.json()

                # Ensure the vbv_status is returned
                if "vbv_status" not in data:
                    return {"error": "VBV status not found in response"}
                
                return data
            except Exception as e:
                return {"error": f"An error occurred: {str(e)}"}


async def generate_cc_async(bin_number, month=None, year=None, cvv=None, quantity=10, session=None):
    url = "http://api.asheo.dev/asheogen"
    params = {
        "bin": bin_number,
        "quantity": quantity
    }
    if month:
        params["month"] = month
    if year:
        params["year"] = year
    if cvv:
        params["cvv"] = cvv

    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        async with session.get(url, params=params, timeout=10) as response:
            if response.status == 200:
                text = await response.text()
                return text.strip().split("\n")
            else:
                return {"error": f"API error: {response.status}"}
    finally:
        if close_session:
            await session.close()

def format_cc_response(data, bin_number, bin_info, month=None, year=None):
    if isinstance(data, dict) and "error" in data:
        return f"❌ ERROR: {data['error']}"
    if not data:
        return "❌ NO CARDS GENERATED."

    formatted_text = f"𝗕𝗜𝗡: <code>{bin_number[:6]}</code>\n"
    formatted_text += f"𝗔𝗺𝗼𝘂𝗻𝘁: <code>{len(data)}</code>\n\n"
    for card in data:
        card_parts = card.split('|')
        if month and year:
            card_parts[1] = month
            card_parts[2] = year
        formatted_text += f"<code>{'|'.join(card_parts)}</code>\n"
    formatted_text += f"\n𝐈𝐧𝐟𝐨: {bin_info.get('card_type', 'NOT FOUND')} - {bin_info.get('network', 'NOT FOUND')} ({bin_info.get('tier', 'NOT FOUND')})\n"
    formatted_text += f"𝐈𝐬𝐬𝐮𝐞𝐫: {bin_info.get('bank', 'NOT FOUND')}\n"
    formatted_text += f"𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {bin_info.get('country', 'NOT FOUND')} {bin_info.get('flag', '🏳️')}"
    return formatted_text

async def generate_cc_async(bin_number, month=None, year=None, cvv=None, quantity=10, session=None):
    url = "http://api.asheo.dev/asheogen"
    params = {
        "bin": bin_number,
        "quantity": quantity
    }
    if month:
        params["month"] = month
    if year:
        params["year"] = year
    if cvv:
        params["cvv"] = cvv

    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    try:
        async with session.get(url, params=params, timeout=10) as response:
            if response.status == 200:
                text = await response.text()
                return text.strip().split("\n")
            else:
                return {"error": f"API error: {response.status}"}
    finally:
        if close_session:
            await session.close()



@bot.message_handler(func=lambda message: message.text.startswith(("/gen", ".gen")))
def gen_command(message):
    import threading

    command_parts = message.text.split(' ', 1)
    if len(command_parts) < 2:
        bot.reply_to(message, "❌ PLEASE PROVIDE A BIN.")
        return

    args = command_parts[1].split()
    bin_input = args[0]
    bin_number, month, year = extract_bin(bin_input)

    cvv = None
    quantity = 10
    for arg in args[1:]:
        if arg.startswith("cvv="):
            cvv = arg.split("=", 1)[1]
        elif arg.startswith("quantity="):
            quantity = int(arg.split("=", 1)[1])

    def run_async():
        async def async_gen():
            async with aiohttp.ClientSession() as session:
                cc_data = await generate_cc_async(bin_number, month, year, cvv, quantity, session)
                bin_info = await lookup_bin(bin_number)
                response = format_cc_response(cc_data, bin_number, bin_info, month, year)
                bot.reply_to(message, response, parse_mode="HTML")

        asyncio.run(async_gen())

    threading.Thread(target=run_async).start()

    

async def generate_fake_address(country_code):
    url = "https://randomuser.me/api/"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as response:
            print(f"FAKE API STATUS: {response.status}")
            if response.status != 200:
                raise Exception(f"Failed to fetch fake address. Status: {response.status}")
            data = await response.json()
            ...

            full_name = f"{result['name']['first']} {result['name']['last']}"
            street = result['location']['street']
            street_address = f"{street['number']} {street['name']}"
            city = result['location']['city']
            state = result['location']['state']
            postal_code = result['location']['postcode']
            phone_number = result['phone']
            country = result['location']['country']

            return {
                "full_name": full_name,
                "street_address": street_address,
                "city": city,
                "state": state,
                "postal_code": postal_code,
                "phone_number": phone_number,
                "country": country
            }


    return {
        "full_name": f"{first_name} {last_name}",
        "street_address": street_address,
        "city": city,
        "state": state,
        "postal_code": postal_code,
        "phone_number": phone_number,
        "country": country
    }

@bot.message_handler(func=lambda message: message.text.startswith(("/fake", ".fake")))
def fake_command(message):
    try:
        command_parts = message.text.split(' ', 1)
        if len(command_parts) < 2:
            bot.reply_to(message, "❌ PLEASE PROVIDE A COUNTRY CODE.")
            return

        country_code = command_parts[1].lower()
        if country_code not in VALID_COUNTRY_CODES:
            bot.reply_to(message, f"❌ INVALID COUNTRY CODE. Valid codes: {', '.join(VALID_COUNTRY_CODES.keys())}")
            return

        address = asyncio.run(generate_fake_address(country_code))
        response = (
            f"📍{address['country']} 𝗔𝗱𝗱𝗿𝗲𝘀𝘀 𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲𝗱\n\n"
            f"𝗙𝘂𝗹𝗹 𝗡𝗮𝗺𝗲: <code>{address['full_name']}</code>\n"
            f"𝗦𝘁𝗿𝗲𝗲𝘁: <code>{address['street_address']}</code>\n"
            f"𝗖𝗶𝘁𝘆: <code>{address['city']}</code>\n"
            f"𝗦𝘁𝗮𝘁𝗲: <code>{address['state']}</code>\n"
            f"𝗭𝗶𝗽 𝗖𝗼𝗱𝗲: <code>{address['postal_code']}</code>\n"
            f"𝗣𝗵𝗼𝗻𝗲 𝗡𝘂𝗺𝗯𝗲𝗿: <code>{address['phone_number']}</code>\n"
            f"𝗖𝗼𝘂𝗻𝘁𝗿𝘆: <code>{address['country']}</code>"
        )
        bot.reply_to(message, response, parse_mode="HTML")

    except Exception as e:
        bot.reply_to(message, f"❌ ERROR: {e}")

def format_bin_lookup_response(bin_info):
    return (
        f"𝗕𝗜𝗡 𝗟𝗼𝗼𝗸𝘂𝗽 𝗥𝗲𝘀𝘂𝗹𝘁 🔍\n\n"
        f"𝗕𝗶𝗻 ⇾ <code>{bin_info.get('bin', 'NOT FOUND')}</code>\n\n"
        f"𝐈𝐧𝐟𝐨 ⇾ <code>{bin_info.get('card_type', 'NOT FOUND')} - {bin_info.get('network', 'NOT FOUND')} ({bin_info.get('tier', 'NOT FOUND')})</code>\n"
        f"𝐈𝐬𝐬𝐮𝐞𝐫 ⇾ <code>{bin_info.get('bank', 'NOT FOUND')}</code>\n"
        f"𝐂𝐨𝐮𝐧𝐭𝐫𝐲 ⇾ <code>{bin_info.get('country', 'NOT FOUND')} {bin_info.get('flag', '🏳️')}</code>"
    )

@bot.message_handler(func=lambda message: message.text.startswith(("/bin", ".bin")))
def bin_command(message):
    try:
        command_parts = message.text.split(' ', 1)
        if len(command_parts) < 2:
            bot.reply_to(message, "❌ PLEASE PROVIDE A BIN.")
            return

        bin_number = command_parts[1]
        if not re.match(r'^\d{6,16}$', bin_number):
            bot.reply_to(message, "❌ INVALID BIN FORMAT.")
            return

        bin_info = asyncio.run(lookup_bin(bin_number))
        if "error" in bin_info:
            bot.reply_to(message, f"❌ ERROR: {bin_info['error']}")
        else:
            bot.reply_to(message, format_bin_lookup_response(bin_info), parse_mode="HTML")

    except Exception as e:
        bot.reply_to(message, f"❌ ERROR: {e}")


import pycountry

def get_country_name_and_flag(country_code):
    try:
        country = pycountry.countries.get(alpha_2=country_code)
        if country:
            flag = f"🇳🇬"  # Default flag for unknown countries (adjust as necessary)
            # Find flag emoji using country alpha-2 code
            return country.name, flag
        return "N/A", "🏳️"
    except:
        return "Unknown", "🏳️"

import time

@bot.message_handler(func=lambda message: message.text.startswith(("/vbv", ".vbv")))
def vbv_command(message):
    import threading

    command_parts = message.text.split(' ', 1)
    if len(command_parts) < 2:
        bot.reply_to(message, "❌ PLEASE PROVIDE A CREDIT CARD.")
        return

    cc = command_parts[1].strip()
    bin_number = cc.split('|')[0][:6]  # Get the BIN (first 6 digits)

    def run_async():
        async def async_vbv():
            start_time = time.time()  # Record start time

            try:
                result = await check_vbv(cc)  # Check the VBV status for the card
                if "error" in result:
                    bot.reply_to(message, f"❌ {result['error']}")
                    return
                    
                    # Fetch the bin info using the lookup_bin function
                bin_info = await lookup_bin(bin_number)

                # Extract the necessary data
                vbv_status = result.get("vbv_status", "N/A")
                gateway = result.get("scheme", "N/A")
                card_type = result.get("type", "N/A")
                bank = result.get("bank", "N/A")
                country_code = result.get("country", "N/A")

               # Get full country name and flag using the BIN Lookup API
                country_name = bin_info.get("country", "N/A")
                country_flag = bin_info.get("flag", "🏳️")

                   # Generate response based on VBV status
                if vbv_status == "authenticate_successful":
                    verdict = "𝗣𝗮𝘀𝘀𝗲𝗱 ✅"
                elif vbv_status == "authenticate_failed":
                    verdict = "𝗥𝗲𝗷𝗲𝗰𝘁𝗲𝗱 ❌"
                else:
                    verdict = "𝗥𝗲𝗷𝗲𝗰𝘁𝗲𝗱 ❌"
                    
                # Calculate the time taken
                end_time = time.time()
                time_taken = round(end_time - start_time, 2)  # Time in seconds

      
# Build the formatted response
                response = (
                    f"{verdict}\n\n"
                    f"𝗖𝗮𝗿𝗱: <code>{cc}</code>\n"
 f"𝐆𝐚𝐭𝐞𝐰𝐚𝐲: 3DS Lookup\n" 
                                   f"𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: {vbv_status}\n\n"
                    
                    f"𝗜𝗻𝗳𝗼: {card_type}\n"
                    f"𝐈𝐬𝐬𝐮𝐞𝐫: {bank}\n"
                    f"𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {country_name} {country_flag}\n\n"
                    f"𝗧𝗶𝗺𝗲: {time_taken} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀"
                )

                bot.reply_to(message, response, parse_mode="HTML")

            except Exception as e:
                bot.reply_to(message, f"❌ ERROR: {e}")

        asyncio.run(async_vbv())

    threading.Thread(target=run_async).start()



@bot.message_handler(func=lambda message: message.text.startswith(("/chk", ".chk")))
def chk_command(message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ PLEASE PROVIDE A CARD.")
            return

        cc = parts[1].strip()
        bin_number = cc.split('|')[0][:6]
        proxy = "http://PP_1D1E5YMPFG-country-US:5vl30ay0@evo-pro.porterproxies.com:61236"
        start_time = time.time()

# Send an initial "Please wait..." message
        waiting_message = bot.reply_to(message, "⏳ Please wait...")
        
        async def check_card_luckyxd():
            import httpx
            url = "http://luckyxd.biz/str"
            params = {
                "cc": cc,
                "proxy": "PP_1D1E5YMPFG-country-US:5vl30ay0@evo-pro.porterproxies.com:61236"
            }
            async with httpx.AsyncClient(proxy=proxy, timeout=15) as client:
                r = await client.get(url, params=params)
                try:
                    return r.json()
                except:
                    return {"message": r.text.strip(), "status": "fail"}

        async def run_checks():
            return await asyncio.gather(check_card_luckyxd(), lookup_bin(bin_number))

        result, bin_info = asyncio.run(run_checks())
        elapsed = round(time.time() - start_time, 2)

        info = f"{bin_info.get('network', 'N/A')} - {bin_info.get('card_type', 'N/A')} - {bin_info.get('tier', 'N/A')}"
        issuer = bin_info.get("bank", "N/A")
        country = bin_info.get("country", "N/A")
        flag = bin_info.get("flag", "")

        message_clean = result.get("message", "No Response").replace("✅", "").strip()
        status = result.get("status", "").lower()
        verdict = "𝐀𝐩𝐩𝐫𝐨𝐯𝐞𝐝 ✅" if "success" in status or "approved" in message_clean.lower() else "𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝 ❌"

        msg = (
            f"{verdict}\n\n"
            f"𝗖𝗮𝗿𝗱: <code>{cc}</code>\n"
            f"𝐆𝐚𝐭𝐞𝐰𝐚𝐲: Stripe Auth\n"
            f"𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: {message_clean}\n\n"
            f"𝗜𝗻𝗳𝗼: {info}\n"
            f"𝐈𝐬𝐬𝐮𝐞𝐫: {issuer}\n"
            f"𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {country} {flag}\n\n"
            f"𝗧𝗶𝗺𝗲: {elapsed} 𝐬𝐞𝐜𝐨𝐧𝐝𝐬"
        )

        bot.edit_message_text(msg, chat_id=message.chat.id, message_id=waiting_message.message_id, parse_mode="HTML")

    except Exception as e:
        bot.reply_to(message, f"❌ ERROR: {e}")

        

@bot.message_handler(commands=['start'])
def start_command(message):
    welcome_message = (
        f"𝐖𝐞𝐥𝐜𝐨𝐦𝐞 {message.from_user.first_name} 𝐭𝐨 𝐭𝐡𝐞 𝐁𝐨𝐭\n\n"
        "/fake :- 𝐆𝐞𝐧𝐞𝐫𝐚𝐭𝐞 𝐅𝐚𝐤𝐞 𝐀𝐝𝐝𝐫𝐞𝐬𝐬\n"
        "/bin :- 𝐁𝐢𝐧 𝐋𝐨𝐨𝐤𝐮𝐩\n"
        "/gen :- 𝐆𝐞𝐧𝐞𝐫𝐚𝐭𝐞 𝐂𝐂\n"
        "/vbv :- 𝐒𝐢𝐧𝐠𝐥𝐞 𝐕𝐁𝐕\n"

        "/chk :- 𝐒𝐭𝐫𝐢𝐩𝐞 𝐀𝐮𝐭𝐡\n\n"
        "Bᴏᴛ Bʏ @Newlester "
    )
    bot.reply_to(message, welcome_message, parse_mode="HTML")

if __name__ == "__main__":
    print("BOT IS RUNNING...")
    bot.delete_webhook()
    bot.skip_pending = True
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"BOT POLLING ERROR: {e}")
            time.sleep(3)
