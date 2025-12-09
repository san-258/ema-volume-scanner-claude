#!/usr/bin/env python3
"""
Scanner Alert System
Runs scanner and sends alerts via Discord, Telegram, or Email
"""

import os
import sys
from datetime import datetime
from ema_volume_scanner import EMAVolumeScanner
import pandas as pd

# Alert method imports (install as needed)
try:
    import requests
except ImportError:
    requests = None

try:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
except ImportError:
    smtplib = None


class AlertSystem:
    def __init__(self):
        self.alert_method = os.getenv('ALERT_METHOD', 'discord').lower()
        self.discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.email_recipient = os.getenv('EMAIL_RECIPIENT')
        self.email_sender = os.getenv('EMAIL_SENDER')
        self.email_password = os.getenv('EMAIL_PASSWORD')
    
    def send_discord_alert(self, message, embeds=None):
        """Send alert to Discord via webhook."""
        if not self.discord_webhook or not requests:
            print("❌ Discord webhook not configured or requests not installed")
            return False
        
        try:
            data = {"content": message}
            if embeds:
                data["embeds"] = embeds
            
            response = requests.post(self.discord_webhook, json=data)
            if response.status_code == 204:
                print("✅ Discord alert sent successfully")
                return True
            else:
                print(f"❌ Discord alert failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Discord error: {str(e)}")
            return False
    
    def send_telegram_alert(self, message):
        """Send alert to Telegram."""
        if not self.telegram_token or not self.telegram_chat_id or not requests:
            print("❌ Telegram not configured or requests not installed")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            response = requests.post(url, data=data)
            if response.status_code == 200:
                print("✅ Telegram alert sent successfully")
                return True
            else:
                print(f"❌ Telegram alert failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Telegram error: {str(e)}")
            return False
    
    def send_email_alert(self, subject, body):
        """Send alert via email."""
        if not all([self.email_sender, self.email_password, self.email_recipient, smtplib]):
            print("❌ Email not configured or smtplib not available")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_sender
            msg['To'] = self.email_recipient
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Gmail SMTP
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(self.email_sender, self.email_password)
            server.send_message(msg)
            server.quit()
            
            print("✅ Email alert sent successfully")
            return True
        except Exception as e:
            print(f"❌ Email error: {str(e)}")
            return False
    
    def format_discord_embed(self, setup):
        """Format setup data as Discord embed."""
        color = 0x00ff00 if setup['confidence'] >= 8.0 else 0xffa500 if setup['confidence'] >= 6.0 else 0xff0000
        
        embed = {
            "title": f"🎯 {setup['symbol']} - {setup['setup_type']}",
            "color": color,
            "fields": [
                {"name": "⭐ Confidence", "value": f"{setup['confidence']}/10", "inline": True},
                {"name": "💰 Price", "value": f"${setup['close']:.2f}", "inline": True},
                {"name": "📊 Position", "value": setup['current_position'], "inline": True},
            ],
            "footer": {"text": f"Scanned on {setup['date']}"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add EMAs
        ema_text = f"10: ${setup['ema_10']:.2f} | 21: ${setup['ema_21']:.2f} | 50: ${setup['ema_50']:.2f}"
        embed["fields"].append({"name": "📈 EMAs", "value": ema_text, "inline": False})
        
        # Add support level if available
        if 'hv_support_level' in setup and pd.notna(setup['hv_support_level']):
            distance = ((setup['close'] - setup['hv_support_level']) / setup['close']) * 100
            support_text = f"${setup['hv_support_level']:.2f} ({distance:.1f}% below)"
            if 'hv_volume_ratio' in setup:
                support_text += f"\nVolume: {setup['hv_volume_ratio']:.1f}x average"
            embed["fields"].append({"name": "🛡️ Support", "value": support_text, "inline": False})
        
        # Add reclaim status
        if 'reclaim_confirmed' in setup:
            status = "✅ Confirmed" if setup['reclaim_confirmed'] else "⏳ Pending"
            embed["fields"].append({"name": "🎯 Reclaim", "value": status, "inline": True})
        
        return embed
    
    def format_telegram_message(self, setups):
        """Format setups as Telegram message."""
        message = f"*🎯 EMA + VOLUME SCANNER ALERT*\n"
        message += f"_{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n\n"
        
        for setup in setups:
            confidence_emoji = "🔥" if setup['confidence'] >= 8.0 else "📊" if setup['confidence'] >= 6.0 else "⚠️"
            
            message += f"{confidence_emoji} *{setup['symbol']}* - {setup['setup_type']}\n"
            message += f"⭐ Confidence: *{setup['confidence']:.1f}/10*\n"
            message += f"💰 Price: ${setup['close']:.2f}\n"
            
            if 'hv_support_level' in setup and pd.notna(setup['hv_support_level']):
                distance = ((setup['close'] - setup['hv_support_level']) / setup['close']) * 100
                message += f"🛡️ Support: ${setup['hv_support_level']:.2f} ({distance:.1f}% below)\n"
            
            if 'reclaim_confirmed' in setup:
                status = "✅" if setup['reclaim_confirmed'] else "⏳"
                message += f"🎯 Reclaim: {status}\n"
            
            message += "\n"
        
        return message
    
    def format_email_body(self, setups):
        """Format setups as email body."""
        body = f"EMA + VOLUME SCANNER ALERT\n"
        body += f"Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        body += f"{'='*80}\n\n"
        
        for setup in setups:
            body += f"SYMBOL: {setup['symbol']}\n"
            body += f"Setup Type: {setup['setup_type']}\n"
            body += f"Confidence: {setup['confidence']:.1f}/10\n"
            body += f"Price: ${setup['close']:.2f}\n"
            body += f"EMAs: 10=${setup['ema_10']:.2f} | 21=${setup['ema_21']:.2f} | 50=${setup['ema_50']:.2f}\n"
            
            if 'hv_support_level' in setup and pd.notna(setup['hv_support_level']):
                distance = ((setup['close'] - setup['hv_support_level']) / setup['close']) * 100
                body += f"Support: ${setup['hv_support_level']:.2f} ({distance:.1f}% below)\n"
            
            if 'reclaim_confirmed' in setup:
                status = "YES" if setup['reclaim_confirmed'] else "PENDING"
                body += f"Reclaim Confirmed: {status}\n"
            
            body += f"\n{'-'*80}\n\n"
        
        return body


def load_watchlist():
    """Load watchlist from file or use defaults."""
    watchlist_file = os.getenv('WATCHLIST_FILE', 'my_watchlist.txt')
    
    if os.path.exists(watchlist_file):
        print(f"📋 Loading watchlist from {watchlist_file}")
        with open(watchlist_file, 'r') as f:
            symbols = [line.strip().upper() for line in f 
                      if line.strip() and not line.startswith('#')]
        return symbols
    
    # Default watchlist
    print("📋 Using default watchlist")
    return [
        # Tech
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD',
        # Finance
        'JPM', 'BAC', 'GS', 'V', 'MA',
        # Other
        'SPY', 'QQQ'
    ]


def main():
    """Main scanner alert function."""
    print("\n" + "="*80)
    print("EMA + VOLUME SCANNER - AUTOMATED ALERT SYSTEM")
    print("="*80 + "\n")
    
    # Load watchlist
    symbols = load_watchlist()
    print(f"Scanning {len(symbols)} symbols...\n")
    
    # Initialize scanner
    scanner = EMAVolumeScanner(period="6mo", lookback_bars=20)
    
    # Scan
    results_df = scanner.scan_multiple(symbols, verbose=True)
    
    if len(results_df) == 0:
        print("\n⚠️  No setups found. No alerts sent.\n")
        return
    
    # Filter for high-confidence setups only (≥6.0)
    min_confidence = float(os.getenv('MIN_CONFIDENCE', '6.0'))
    high_conf = results_df[results_df['confidence'] >= min_confidence]
    
    if len(high_conf) == 0:
        print(f"\n⚠️  No setups with confidence ≥{min_confidence}. No alerts sent.\n")
        # Still save all results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"automated_scan_{timestamp}.csv"
        results_df.to_csv(filename, index=False)
        print(f"💾 All results saved to: {filename}\n")
        return
    
    print(f"\n{'='*80}")
    print(f"🔥 FOUND {len(high_conf)} HIGH-CONFIDENCE SETUPS!")
    print(f"{'='*80}\n")
    
    # Display results
    for _, row in high_conf.iterrows():
        print(f"{row['symbol']:6s} | {row['setup_type']:20s} | Confidence: {row['confidence']:.1f}/10")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"automated_scan_{timestamp}.csv"
    results_df.to_csv(filename, index=False)
    print(f"\n💾 Results saved to: {filename}")
    
    # Send alerts
    alert_system = AlertSystem()
    setups_list = high_conf.to_dict('records')
    
    print(f"\n{'='*80}")
    print("SENDING ALERTS...")
    print(f"{'='*80}\n")
    
    if alert_system.alert_method == 'discord':
        # Send summary message
        summary = f"🎯 **EMA Volume Scanner Alert**\nFound **{len(high_conf)} setups** with confidence ≥{min_confidence}"
        alert_system.send_discord_alert(summary)
        
        # Send individual embeds (max 10 to avoid spam)
        for setup in setups_list[:10]:
            embed = alert_system.format_discord_embed(setup)
            alert_system.send_discord_alert("", embeds=[embed])
    
    elif alert_system.alert_method == 'telegram':
        message = alert_system.format_telegram_message(setups_list)
        alert_system.send_telegram_alert(message)
    
    elif alert_system.alert_method == 'email':
        subject = f"🎯 Scanner Alert: {len(high_conf)} High-Confidence Setups Found"
        body = alert_system.format_email_body(setups_list)
        alert_system.send_email_alert(subject, body)
    
    else:
        print(f"⚠️  Unknown alert method: {alert_system.alert_method}")
        print("Available methods: discord, telegram, email")
    
    print(f"\n{'='*80}")
    print("SCAN COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
