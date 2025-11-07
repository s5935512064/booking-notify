import requests
from datetime import datetime, timedelta
import json
import time
import os

# --- ⬇️ ฟังก์ชันใหม่สำหรับส่ง Discord Webhook ⬇️ ---
def send_discord_webhook(message, webhook_url):
    """
    Sends a message to a Discord channel using a Webhook.
    """
    # Discord รับข้อมูลเป็น JSON payload
    # "content" คือข้อความ
    # "username" คือชื่อบอทที่จะแสดง
    data = {
        "content": message,
        "username": "Slot Bot 🤖"
    }
    
    try:
        # ใช้ json=data เพื่อให้ requests ส่ง Content-Type: application/json
        response = requests.post(webhook_url, json=data)
        response.raise_for_status()
        print(f"    🔔 Discord: Message sent successfully!")
    except requests.exceptions.RequestException as e:
        print(f"    🔥 Discord Webhook Error: {e}")
        if hasattr(e, 'response') and e.response is not None and e.response.status_code == 404:
            print("    🔥 HINT: Webhook URL อาจจะไม่ถูกต้องหรือถูกลบไปแล้ว")
# --- ⬆️ สิ้นสุดฟังก์ชัน Discord ⬆️ ---

def load_notified_dates(filename="notified_dates.json"):
    """
    โหลดรายการวันที่ที่แจ้งเตือนแล้วจากไฟล์ JSON
    """
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data.get('notified_dates', []))
        return set()
    except Exception as e:
        print(f"⚠️ Error loading notified dates: {e}")
        return set()

def save_notified_dates(notified_dates, filename="notified_dates.json"):
    """
    บันทึกรายการวันที่ที่แจ้งเตือนแล้วลงไฟล์ JSON
    """
    try:
        data = {
            "last_updated": datetime.now().isoformat(),
            "notified_dates": list(notified_dates)
        }
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"💾 Notified dates saved to {filename}")
    except Exception as e:
        print(f"⚠️ Error saving notified dates: {e}")

def check_availability(start_date, end_date, discord_webhook_url, notified_dates, skip_dates=None):
    """
    Check availability from API for date range and send Discord notification
    if a new available date is found.
    
    Args:
        start_date: Starting date (YYYY-MM-DD)
        end_date: Ending date (YYYY-MM-DD)
        discord_webhook_url: Discord Webhook URL
        notified_dates: A set of dates that have already been notified. 
                        This set will be modified in-place.
        skip_dates: A set of dates to skip checking (YYYY-MM-DD format)
    
    Returns:
        A list of all currently available dates (for saving to JSON).
    """
    if skip_dates is None:
        skip_dates = set()
    
    base_url = "https://q.wildlifesanctuaryfca16.com/api/v1/bookings/availability"
    
    current_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔍 Checking from {start_date} to {end_date}...")
    if skip_dates:
        print(f"    ⏭️ Skipping dates: {sorted(skip_dates)}")
    
    all_available_dates_this_run = []
    new_dates_found_count = 0
    
    while current_date <= end_date_obj:
        date_str = current_date.strftime("%Y-%m-%d")
        
        # ข้ามวันที่ที่ระบุไว้ใน skip_dates
        if date_str in skip_dates:
            print(f"    ⏭️ {date_str} - SKIPPED (in skip list)")
            current_date += timedelta(days=1)
            continue
        
        try:
            response = requests.get(f"{base_url}?date={date_str}")
            response.raise_for_status()
            data = response.json()
            
            if data.get("success") and data.get("data"):
                booking_data = data["data"]
                available = booking_data.get("available", 0)
                capacity = booking_data.get("capacity", 0)
                
                if available > 0:
                    all_available_dates_this_run.append({
                        "date": date_str,
                        "available": available,
                        "capacity": capacity,
                    })

                    if date_str not in notified_dates:
                        print(f"    🎉 NEW SLOT FOUND! {date_str} - {available} slots")
                        
                        # สร้างข้อความสำหรับ Discord (รองรับ Markdown)
                        message = (
                            f"## 🚨 พบช่องว่างใหม่! 🚨\n"
                            f"> **วันที่: {date_str}**\n"
                            f"> **จำนวนที่ว่าง: {available} / {capacity}**\n\n"
                            f"รีบไปจองเลย! https://q.wildlifesanctuaryfca16.com/"
                        )
                        
                        # ส่ง Discord
                        send_discord_webhook(message, discord_webhook_url)
                        
                        notified_dates.add(date_str)
                        new_dates_found_count += 1
                    else:
                        print(f"    ✅ {date_str} - Still available: {available} (Already notified)")

                else:
                    print(f"    ❌ {date_str} - FULL ({booking_data.get('used', 0)}/{capacity})")
                    if date_str in notified_dates:
                        notified_dates.remove(date_str)
                        print(f"    ℹ️ {date_str} is now full. Removed from notified list.")

            else:
                print(f"    ⚠️  {date_str} - No data available")
                
        except requests.exceptions.RequestException as e:
            print(f"    ❌ {date_str} - Error: {e}")
        
        current_date += timedelta(days=1)
        time.sleep(0.5)
    
    if new_dates_found_count > 0:
        print(f"✨ Found and notified {new_dates_found_count} new dates in this run.")
    else:
        print("😔 No *new* available dates found in this run.")
    
    return all_available_dates_this_run

# --- ⬇️ ส่วนหลักของการรัน ⬇️ ---
if __name__ == "__main__":
    
    # ==========================================================
    # 🔐 ใช้ Environment Variable สำหรับ Webhook URL (สำหรับ GitHub Actions)
    # ใน GitHub Actions จะตั้งค่าเป็น Secret
    DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', 'https://discord.com/api/webhooks/1436424986675122298/wJpkFF-6Wve2Awut51sFL7XmFqY0vTmIiHRjQ1PgJ9ZDrEhWat1RK8F78EfQuKEzNZKN')
    # ==========================================================
    
    # ==========================================================
    # 📅 วันที่ที่ต้องการข้าม (ไม่ต้องการตรวจสอบ)
    # เพิ่มวันที่ในรูปแบบ "YYYY-MM-DD" ลงในลิสต์นี้
    SKIP_DATES = {
        "2025-11-19",  # วันที่ไม่สะดวก
        "2025-11-26",
        "2025-12-03",
        "2025-12-10",
        "2025-12-17",
        "2025-12-24",
        "2025-12-31",
        "2026-01-07",
        "2026-01-14",
        "2026-01-21",
        "2026-01-28",
        "2026-02-04",
        "2026-02-11",
        "2026-02-13",
        "2026-02-14",
        "2026-02-15"
    }
    # ==========================================================
    
    if DISCORD_WEBHOOK_URL == "YOUR_WEBHOOK_URL_HERE" or not DISCORD_WEBHOOK_URL.startswith("https://discord.com/api/webhooks/"):
        print("="*80)
        print("🔥🔥🔥 ข้อผิดพลาด: กรุณาใส่ DISCORD_WEBHOOK_URL ของคุณในโค้ดก่อนรันสคริปต์")
        print("="*80)
        exit(1)
    
    # โหลดรายการวันที่ที่แจ้งเตือนแล้ว
    notified_dates = load_notified_dates()
    
    print("🚀 Starting availability check...")
    print(f"Webhook URL: ...{DISCORD_WEBHOOK_URL[-20:]}")
    if SKIP_DATES:
        print(f"📅 Will skip these dates: {sorted(SKIP_DATES)}")
    
    try:
        start_date = "2025-11-15"
        end_date = "2026-02-15"
        
        available = check_availability(
            start_date, 
            end_date, 
            DISCORD_WEBHOOK_URL, 
            notified_dates,
            SKIP_DATES
        )
        
        # บันทึกรายการวันที่แจ้งเตือนแล้ว
        save_notified_dates(notified_dates)
        
        # บันทึกผลลัพธ์การตรวจสอบ
        with open("available_dates.json", "w", encoding="utf-8") as f:
            json.dump({
                "checked_at": datetime.now().isoformat(),
                "date_range": {
                    "start": start_date,
                    "end": end_date
                },
                "skip_dates": list(SKIP_DATES),
                "available_dates_now": available,
                "total_notified_dates": len(notified_dates)
            }, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Results updated to available_dates.json")
        print("✅ Check completed successfully!")
        
    except Exception as e:
        print(f"😱 An unexpected error occurred: {e}")
        exit(1)