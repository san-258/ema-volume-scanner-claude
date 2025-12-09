#!/bin/bash
# EMA Volume Scanner - Mac/Linux Launcher

echo "============================================"
echo "   EMA + VOLUME STRATEGY SCANNER"
echo "============================================"
echo ""
echo "Choose your scan type:"
echo ""
echo "1. Default Scan (50+ popular stocks)"
echo "2. Custom Watchlist Scanner"
echo "3. Quick Single Symbol Check"
echo "4. Install/Update Dependencies"
echo "5. Exit"
echo ""
read -p "Enter your choice (1-5): " choice

case $choice in
    1)
        echo ""
        echo "Starting default scanner..."
        python3 ema_volume_scanner.py
        ;;
    2)
        echo ""
        echo "Starting custom watchlist scanner..."
        python3 custom_scanner.py
        ;;
    3)
        echo ""
        read -p "Enter symbol (e.g., AAPL): " symbol
        python3 quick_scan.py "$symbol"
        ;;
    4)
        echo ""
        echo "Installing dependencies..."
        pip3 install -r requirements.txt
        echo ""
        echo "Done!"
        ;;
    5)
        exit 0
        ;;
    *)
        echo "Invalid choice. Please run again."
        ;;
esac
