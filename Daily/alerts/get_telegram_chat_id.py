#!/usr/bin/env python3
"""
Helper script to get your Telegram Chat ID
"""

import requests
import sys
import json

def get_chat_id(bot_token):
    """Get chat ID from Telegram bot updates"""
    try:
        # Get updates from bot
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        response = requests.get(url)
        
        if response.status_code != 200:
            print(f"Error: Failed to get updates. Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return None
        
        data = response.json()
        
        if not data.get('ok'):
            print(f"Error: {data.get('description', 'Unknown error')}")
            return None
        
        updates = data.get('result', [])
        
        if not updates:
            print("No messages found. Please:")
            print("1. Start a chat with your bot")
            print("2. Send any message to the bot")
            print("3. Run this script again")
            return None
        
        # Get the most recent update
        latest_update = updates[-1]
        
        # Extract chat information
        if 'message' in latest_update:
            chat = latest_update['message']['chat']
            chat_id = chat['id']
            chat_type = chat.get('type', 'private')
            
            if chat_type == 'private':
                first_name = chat.get('first_name', 'Unknown')
                last_name = chat.get('last_name', '')
                username = chat.get('username', 'No username')
                
                print(f"\n✅ Found Chat ID: {chat_id}")
                print(f"Chat Type: {chat_type}")
                print(f"User: {first_name} {last_name}")
                print(f"Username: @{username}")
            else:
                title = chat.get('title', 'Unknown')
                print(f"\n✅ Found Chat ID: {chat_id}")
                print(f"Chat Type: {chat_type}")
                print(f"Group Name: {title}")
            
            print(f"\n📋 Add this to your environment variables:")
            print(f"export TELEGRAM_CHAT_ID='{chat_id}'")
            
            return chat_id
        
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    """Main function"""
    print("Telegram Chat ID Finder")
    print("=" * 40)
    
    # Check if token provided as argument
    if len(sys.argv) > 1:
        bot_token = sys.argv[1]
    else:
        # Use the token you provided (be careful with this!)
        bot_token = input("Enter your bot token (or press Enter to use default): ").strip()
        if not bot_token:
            # You can set a default here for testing, but remove it later
            bot_token = None
    
    if not bot_token:
        print("\nError: Bot token required!")
        print("Usage: python get_telegram_chat_id.py YOUR_BOT_TOKEN")
        sys.exit(1)
    
    print(f"\nUsing bot token: {bot_token[:10]}...{bot_token[-5:]}")
    print("\nFetching updates...")
    
    chat_id = get_chat_id(bot_token)
    
    if chat_id:
        print("\n✅ Success! You can now use this chat ID for alerts.")
    else:
        print("\n❌ Failed to get chat ID.")

if __name__ == "__main__":
    main()