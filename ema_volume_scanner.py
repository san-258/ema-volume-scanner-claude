#!/usr/bin/env python3
"""
EMA + Volume Strategy Scanner
Identifies high-probability setups based on 10, 21, 50 EMA reclaim patterns with volume confirmation.

Strategy Rules:
1. Main Setup: Price pulls back below all 3 EMAs, then reclaims all 3
2. Secondary Setup: Price dips below 10 & 21 EMA but holds 50 EMA, then reclaims
3. Volume Confirmation: High-volume candle during pullback that never closes below its low
4. Reclaim Validation: Reclaim candle closes above high-volume bearish candle's high
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class EMAVolumeScanner:
    def __init__(self, period="6mo", lookback_bars=20):
        """
        Initialize the scanner.
        
        Args:
            period: Data period to fetch (3mo, 6mo, 1y, etc.)
            lookback_bars: Number of bars to look back for high-volume analysis
        """
        self.period = period
        self.lookback_bars = lookback_bars
        
    def calculate_emas(self, df):
        """Calculate 10, 21, and 50 period EMAs."""
        df['EMA_10'] = df['Close'].ewm(span=10, adjust=False).mean()
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        return df
    
    def calculate_volume_metrics(self, df, lookback=20):
        """Calculate volume averages and identify high-volume bars."""
        df['Volume_Avg'] = df['Volume'].rolling(window=lookback).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_Avg']
        df['High_Volume'] = df['Volume_Ratio'] > 1.5  # 50% above average
        return df
    
    def identify_ema_position(self, row):
        """Determine price position relative to EMAs."""
        close = row['Close']
        ema10 = row['EMA_10']
        ema21 = row['EMA_21']
        ema50 = row['EMA_50']
        
        if close > ema10 and close > ema21 and close > ema50:
            return "ABOVE_ALL"
        elif close < ema10 and close < ema21 and close < ema50:
            return "BELOW_ALL"
        elif close < ema10 and close < ema21 and close > ema50:
            return "BELOW_10_21_ABOVE_50"
        elif close > ema10 and close > ema21 and close < ema50:
            return "ABOVE_10_21_BELOW_50"
        else:
            return "MIXED"
    
    def find_high_volume_support(self, df, current_idx, lookback=20):
        """
        Find the most recent high-volume candle that could serve as support.
        Returns: (index, low_price, high_price, volume_ratio, is_bearish)
        """
        if current_idx < lookback:
            lookback = current_idx
            
        search_range = df.iloc[max(0, current_idx - lookback):current_idx]
        
        # Find high-volume bars
        high_vol_bars = search_range[search_range['High_Volume'] == True]
        
        if len(high_vol_bars) == 0:
            return None
        
        # Get the most recent high-volume bar
        most_recent_hv = high_vol_bars.iloc[-1]
        hv_idx = high_vol_bars.index[-1]
        
        # Check if it's bearish (close < open)
        is_bearish = most_recent_hv['Close'] < most_recent_hv['Open']
        
        # Check if price never closed below this candle's low after it formed
        subsequent_bars = df.loc[hv_idx:current_idx]
        never_closed_below = (subsequent_bars['Close'] >= most_recent_hv['Low']).all()
        
        return {
            'index': hv_idx,
            'date': most_recent_hv.name,
            'low': most_recent_hv['Low'],
            'high': most_recent_hv['High'],
            'close': most_recent_hv['Close'],
            'volume_ratio': most_recent_hv['Volume_Ratio'],
            'is_bearish': is_bearish,
            'never_closed_below': never_closed_below
        }
    
    def detect_main_setup(self, df, current_idx, lookback=10):
        """
        Detect Main Bullish Setup:
        - Was above all 3 EMAs
        - Pulled back below all 3 EMAs
        - Now reclaimed and closed above all 3 EMAs
        """
        if current_idx < lookback + 5:
            return None
        
        current_bar = df.iloc[current_idx]
        current_position = self.identify_ema_position(current_bar)
        
        # Must be above all EMAs now
        if current_position != "ABOVE_ALL":
            return None
        
        # Look back to find if we were below all EMAs recently
        lookback_window = df.iloc[max(0, current_idx - lookback):current_idx]
        
        was_below_all = False
        was_above_all_before = False
        below_all_idx = None
        
        for idx in range(len(lookback_window) - 1, -1, -1):
            bar = lookback_window.iloc[idx]
            position = self.identify_ema_position(bar)
            
            if position == "BELOW_ALL" and not was_below_all:
                was_below_all = True
                below_all_idx = lookback_window.index[idx]
            
            # Check if we were above all before the dip
            if was_below_all and position == "ABOVE_ALL":
                was_above_all_before = True
                break
        
        if was_below_all and was_above_all_before:
            # Find high-volume support during the pullback
            hv_support = self.find_high_volume_support(df, current_idx, lookback)
            
            # Check if current close is above high-volume candle's high
            reclaim_confirmation = False
            if hv_support and hv_support['never_closed_below']:
                reclaim_confirmation = current_bar['Close'] > hv_support['high']
            
            return {
                'setup_type': 'MAIN_BULLISH',
                'reclaim_bar_date': current_bar.name,
                'below_all_date': below_all_idx,
                'hv_support': hv_support,
                'reclaim_confirmation': reclaim_confirmation,
                'current_close': current_bar['Close'],
                'distance_from_50ema': ((current_bar['Close'] - current_bar['EMA_50']) / current_bar['EMA_50']) * 100
            }
        
        return None
    
    def detect_secondary_setup(self, df, current_idx, lookback=10):
        """
        Detect Secondary Bullish Setup:
        - Was above all EMAs
        - Dipped below 10 & 21 EMA but held above 50 EMA
        - Now reclaimed above all 3 EMAs
        """
        if current_idx < lookback + 5:
            return None
        
        current_bar = df.iloc[current_idx]
        current_position = self.identify_ema_position(current_bar)
        
        # Must be above all EMAs now
        if current_position != "ABOVE_ALL":
            return None
        
        lookback_window = df.iloc[max(0, current_idx - lookback):current_idx]
        
        was_below_10_21_above_50 = False
        was_above_all_before = False
        pullback_idx = None
        
        for idx in range(len(lookback_window) - 1, -1, -1):
            bar = lookback_window.iloc[idx]
            position = self.identify_ema_position(bar)
            
            if position == "BELOW_10_21_ABOVE_50" and not was_below_10_21_above_50:
                was_below_10_21_above_50 = True
                pullback_idx = lookback_window.index[idx]
            
            if was_below_10_21_above_50 and position == "ABOVE_ALL":
                was_above_all_before = True
                break
        
        if was_below_10_21_above_50 and was_above_all_before:
            hv_support = self.find_high_volume_support(df, current_idx, lookback)
            
            reclaim_confirmation = False
            if hv_support and hv_support['never_closed_below']:
                reclaim_confirmation = current_bar['Close'] > hv_support['high']
            
            return {
                'setup_type': 'SECONDARY_BULLISH',
                'reclaim_bar_date': current_bar.name,
                'pullback_date': pullback_idx,
                'hv_support': hv_support,
                'reclaim_confirmation': reclaim_confirmation,
                'current_close': current_bar['Close'],
                'distance_from_50ema': ((current_bar['Close'] - current_bar['EMA_50']) / current_bar['EMA_50']) * 100
            }
        
        return None
    
    def detect_forming_setup(self, df, current_idx):
        """
        Detect setups that are currently forming (price in pullback phase).
        """
        if current_idx < 10:
            return None
        
        current_bar = df.iloc[current_idx]
        current_position = self.identify_ema_position(current_bar)
        
        # Check if we were recently above all EMAs
        lookback = 10
        lookback_window = df.iloc[max(0, current_idx - lookback):current_idx]
        
        was_above_all_recently = False
        for idx in range(len(lookback_window) - 1, -1, -1):
            bar = lookback_window.iloc[idx]
            position = self.identify_ema_position(bar)
            if position == "ABOVE_ALL":
                was_above_all_recently = True
                break
        
        if not was_above_all_recently:
            return None
        
        # Forming Main Setup (below all EMAs after being above)
        if current_position == "BELOW_ALL":
            hv_support = self.find_high_volume_support(df, current_idx, lookback)
            return {
                'setup_type': 'FORMING_MAIN',
                'current_position': current_position,
                'hv_support': hv_support,
                'watch_for': 'Reclaim above all 3 EMAs'
            }
        
        # Forming Secondary Setup (below 10 & 21, above 50)
        if current_position == "BELOW_10_21_ABOVE_50":
            hv_support = self.find_high_volume_support(df, current_idx, lookback)
            return {
                'setup_type': 'FORMING_SECONDARY',
                'current_position': current_position,
                'hv_support': hv_support,
                'watch_for': 'Reclaim above 10 & 21 EMAs'
            }
        
        return None
    
    def calculate_confidence_score(self, setup_data, df, current_idx):
        """
        Calculate confidence score (1-10) based on multiple factors.
        """
        if setup_data is None:
            return 0
        
        score = 5.0  # Base score
        
        # Volume confirmation adds significant confidence
        if setup_data.get('hv_support'):
            hv = setup_data['hv_support']
            if hv['never_closed_below']:
                score += 2.0
            if hv['volume_ratio'] > 2.0:  # 2x average volume
                score += 1.0
            if hv['is_bearish']:  # Bearish high-volume bar = absorption
                score += 0.5
        
        # Reclaim confirmation
        if setup_data.get('reclaim_confirmation'):
            score += 1.5
        
        # Distance from 50 EMA (not too extended)
        distance = setup_data.get('distance_from_50ema', 0)
        if 0 < distance < 5:  # Close to 50 EMA = healthier
            score += 0.5
        elif distance > 15:  # Too extended
            score -= 1.0
        
        # Check for declining volume on recent upside (bearish divergence)
        current_bar = df.iloc[current_idx]
        if current_idx >= 5:
            recent_bars = df.iloc[current_idx-5:current_idx+1]
            recent_highs = recent_bars[recent_bars['Close'] > recent_bars['Open']]
            if len(recent_highs) > 2:
                volume_trend = recent_highs['Volume'].diff().mean()
                if volume_trend < 0:  # Declining volume on upside
                    score -= 1.0
        
        # EMA alignment (10 > 21 > 50 for bullish)
        if current_idx > 0:
            ema_aligned = (df.iloc[current_idx]['EMA_10'] > df.iloc[current_idx]['EMA_21'] and 
                          df.iloc[current_idx]['EMA_21'] > df.iloc[current_idx]['EMA_50'])
            if ema_aligned:
                score += 0.5
        
        return min(10.0, max(1.0, score))  # Clamp between 1 and 10
    
    def scan_symbol(self, symbol, verbose=False):
        """Scan a single symbol for setups."""
        try:
            # Fetch data
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=self.period)
            
            if len(df) < 60:  # Need enough data for 50 EMA
                return None
            
            # Calculate indicators
            df = self.calculate_emas(df)
            df = self.calculate_volume_metrics(df)
            df['Position'] = df.apply(self.identify_ema_position, axis=1)
            
            # Scan the most recent bar
            current_idx = len(df) - 1
            
            # Check for completed setups
            main_setup = self.detect_main_setup(df, current_idx)
            secondary_setup = self.detect_secondary_setup(df, current_idx)
            forming_setup = self.detect_forming_setup(df, current_idx)
            
            # Determine which setup is present
            active_setup = main_setup or secondary_setup or forming_setup
            
            if active_setup:
                confidence = self.calculate_confidence_score(active_setup, df, current_idx)
                
                result = {
                    'symbol': symbol,
                    'date': df.index[-1].strftime('%Y-%m-%d'),
                    'close': round(df.iloc[-1]['Close'], 2),
                    'setup_type': active_setup['setup_type'],
                    'confidence': round(confidence, 1),
                    'ema_10': round(df.iloc[-1]['EMA_10'], 2),
                    'ema_21': round(df.iloc[-1]['EMA_21'], 2),
                    'ema_50': round(df.iloc[-1]['EMA_50'], 2),
                    'volume_ratio': round(df.iloc[-1]['Volume_Ratio'], 2),
                    'current_position': df.iloc[-1]['Position']
                }
                
                # Add high-volume support details if present
                if active_setup.get('hv_support'):
                    hv = active_setup['hv_support']
                    result['hv_support_level'] = round(hv['low'], 2)
                    result['hv_volume_ratio'] = round(hv['volume_ratio'], 2)
                    result['hv_never_closed_below'] = hv['never_closed_below']
                
                if active_setup.get('reclaim_confirmation') is not None:
                    result['reclaim_confirmed'] = active_setup['reclaim_confirmation']
                
                if verbose:
                    print(f"✓ {symbol}: {active_setup['setup_type']} - Confidence: {confidence:.1f}/10")
                
                return result
            
            return None
            
        except Exception as e:
            if verbose:
                print(f"✗ {symbol}: Error - {str(e)}")
            return None
    
    def scan_multiple(self, symbols, verbose=True):
        """
        Scan multiple symbols.
        
        Args:
            symbols: List of ticker symbols
            verbose: Print progress
            
        Returns:
            DataFrame with results
        """
        results = []
        
        if verbose:
            print(f"\n{'='*80}")
            print(f"EMA + VOLUME SCANNER - Scanning {len(symbols)} symbols")
            print(f"{'='*80}\n")
        
        for i, symbol in enumerate(symbols, 1):
            if verbose:
                print(f"[{i}/{len(symbols)}] Scanning {symbol}...", end=" ")
            
            result = self.scan_symbol(symbol, verbose=False)
            
            if result:
                results.append(result)
                if verbose:
                    print(f"✓ {result['setup_type']} (Confidence: {result['confidence']}/10)")
            else:
                if verbose:
                    print("✗ No setup found")
        
        if verbose:
            print(f"\n{'='*80}")
            print(f"Scan Complete: Found {len(results)} setups")
            print(f"{'='*80}\n")
        
        if results:
            return pd.DataFrame(results).sort_values('confidence', ascending=False)
        else:
            return pd.DataFrame()


def main():
    """Example usage"""
    
    # Popular stocks to scan (you can customize this list)
    symbols = [
        # Tech
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD', 'INTC', 'CRM',
        # Finance
        'JPM', 'BAC', 'WFC', 'GS', 'MS', 'V', 'MA',
        # Healthcare
        'JNJ', 'UNH', 'PFE', 'ABBV', 'TMO', 'MRK',
        # Consumer
        'WMT', 'HD', 'NKE', 'SBUX', 'MCD', 'DIS',
        # Energy
        'XOM', 'CVX', 'COP', 'SLB',
        # Industrial
        'BA', 'CAT', 'GE', 'UPS'
    ]
    
    # Initialize scanner
    scanner = EMAVolumeScanner(period="6mo", lookback_bars=20)
    
    # Scan all symbols
    results_df = scanner.scan_multiple(symbols, verbose=True)
    
    if len(results_df) > 0:
        # Display results
        print("\n" + "="*100)
        print("SCAN RESULTS - HIGH PROBABILITY SETUPS")
        print("="*100 + "\n")
        
        # Completed setups
        completed = results_df[results_df['setup_type'].isin(['MAIN_BULLISH', 'SECONDARY_BULLISH'])]
        if len(completed) > 0:
            print("🎯 COMPLETED SETUPS (Ready to Trade):")
            print("-" * 100)
            for _, row in completed.iterrows():
                print(f"\n{row['symbol']:6s} | {row['setup_type']:20s} | Confidence: {row['confidence']}/10")
                print(f"  Price: ${row['close']:.2f}")
                print(f"  EMAs: 10=${row['ema_10']:.2f} | 21=${row['ema_21']:.2f} | 50=${row['ema_50']:.2f}")
                if 'hv_support_level' in row:
                    print(f"  High-Volume Support: ${row['hv_support_level']:.2f} " + 
                          f"(Volume: {row['hv_volume_ratio']:.1f}x avg)")
                if 'reclaim_confirmed' in row:
                    print(f"  Reclaim Confirmed: {'✓ YES' if row['reclaim_confirmed'] else '✗ NO'}")
        
        # Forming setups
        forming = results_df[results_df['setup_type'].str.contains('FORMING')]
        if len(forming) > 0:
            print("\n\n⏳ FORMING SETUPS (Watch List):")
            print("-" * 100)
            for _, row in forming.iterrows():
                print(f"\n{row['symbol']:6s} | {row['setup_type']:20s}")
                print(f"  Price: ${row['close']:.2f} | Current Position: {row['current_position']}")
                print(f"  EMAs: 10=${row['ema_10']:.2f} | 21=${row['ema_21']:.2f} | 50=${row['ema_50']:.2f}")
                if 'hv_support_level' in row:
                    print(f"  High-Volume Support: ${row['hv_support_level']:.2f}")
        
        # Save to CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ema_volume_scan_{timestamp}.csv"
        results_df.to_csv(filename, index=False)
        print(f"\n\n💾 Results saved to: {filename}")
        
    else:
        print("\n⚠️  No setups found in the scanned symbols.")
        print("Try scanning more symbols or adjusting the lookback period.")


if __name__ == "__main__":
    main()
