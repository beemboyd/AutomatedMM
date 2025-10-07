# PSAR-specific methods to be integrated into SL_watchdog_PSAR.py

def calculate_psar(self, ticker: str, candles: List[Dict]) -> Optional[Dict]:
    """
    Calculate Parabolic SAR for a list of OHLC candles

    Args:
        ticker: Trading symbol
        candles: List of OHLC dict candles with keys: open, high, low, close

    Returns:
        Dict with 'psar', 'af', 'trend', 'ep' or None if insufficient data
    """
    try:
        if len(candles) < 2:
            self.logger.debug(f"{ticker}: Need at least 2 candles to calculate PSAR")
            return None

        # Initialize or get existing PSAR data
        if ticker not in self.psar_data:
            # First time calculation - start with first two candles
            candle0 = candles[0]
            candle1 = candles[1]

            # Determine initial trend
            if candle1['close'] > candle0['close']:
                trend = 'LONG'
                psar = candle0['low']
                ep = candle1['high']
            else:
                trend = 'SHORT'
                psar = candle0['high']
                ep = candle1['low']

            af = self.psar_start
        else:
            # Continue from existing PSAR
            psar_info = self.psar_data[ticker]
            psar = psar_info['psar']
            af = psar_info['af']
            trend = psar_info['trend']
            ep = psar_info['ep']

        # Process only the latest candle
        current_candle = candles[-1]

        # Calculate new PSAR
        if trend == 'LONG':
            # PSAR for uptrend
            new_psar = psar + af * (ep - psar)

            # PSAR should not be above the prior two lows
            if len(candles) >= 2:
                new_psar = min(new_psar, candles[-2]['low'])
            if len(candles) >= 3:
                new_psar = min(new_psar, candles[-3]['low'])

            # Check for trend reversal
            if current_candle['low'] < new_psar:
                # Reverse to SHORT
                trend = 'SHORT'
                psar = ep  # PSAR becomes the extreme point
                ep = current_candle['low']
                af = self.psar_start
                self.logger.info(f"{ticker}: PSAR TREND REVERSAL - Now SHORT @ ₹{psar:.2f}")
            else:
                # Continue uptrend
                psar = new_psar

                # Update EP if new high
                if current_candle['high'] > ep:
                    ep = current_candle['high']
                    # Increase AF
                    af = min(af + self.psar_increment, self.psar_maximum)

        else:  # SHORT trend
            # PSAR for downtrend
            new_psar = psar + af * (ep - psar)

            # PSAR should not be below the prior two highs
            if len(candles) >= 2:
                new_psar = max(new_psar, candles[-2]['high'])
            if len(candles) >= 3:
                new_psar = max(new_psar, candles[-3]['high'])

            # Check for trend reversal
            if current_candle['high'] > new_psar:
                # Reverse to LONG
                trend = 'LONG'
                psar = ep  # PSAR becomes the extreme point
                ep = current_candle['high']
                af = self.psar_start
                self.logger.info(f"{ticker}: PSAR TREND REVERSAL - Now LONG @ ₹{psar:.2f}")
            else:
                # Continue downtrend
                psar = new_psar

                # Update EP if new low
                if current_candle['low'] < ep:
                    ep = current_candle['low']
                    # Increase AF
                    af = min(af + self.psar_increment, self.psar_maximum)

        result = {
            'psar': psar,
            'af': af,
            'trend': trend,
            'ep': ep,
            'last_updated': datetime.now().isoformat()
        }

        return result

    except Exception as e:
        self.logger.error(f"Error calculating PSAR for {ticker}: {e}")
        return None


def aggregate_ticks_to_candle(self, ticker: str, tick_price: float):
    """
    Aggregate tick prices into OHLC candles based on tick_aggregate_size

    When tick_aggregate_size ticks are accumulated, create a new candle and update PSAR

    Args:
        ticker: Trading symbol
        tick_price: Latest tick price
    """
    try:
        # Initialize tick buffer if not exists
        if ticker not in self.tick_buffers:
            self.tick_buffers[ticker] = deque(maxlen=self.tick_aggregate_size)

        # Add tick to buffer
        self.tick_buffers[ticker].append(tick_price)

        # Check if we have enough ticks to form a candle
        if len(self.tick_buffers[ticker]) == self.tick_aggregate_size:
            # Create OHLC candle from ticks
            ticks = list(self.tick_buffers[ticker])
            candle = {
                'open': ticks[0],
                'high': max(ticks),
                'low': min(ticks),
                'close': ticks[-1],
                'timestamp': datetime.now().isoformat()
            }

            # Initialize tick_candles if not exists
            if ticker not in self.tick_candles:
                self.tick_candles[ticker] = []

            # Add candle to history (keep last 100 candles)
            self.tick_candles[ticker].append(candle)
            if len(self.tick_candles[ticker]) > 100:
                self.tick_candles[ticker].pop(0)

            # Calculate PSAR with updated candles
            psar_result = self.calculate_psar(ticker, self.tick_candles[ticker])
            if psar_result:
                self.psar_data[ticker] = psar_result
                self.logger.debug(f"{ticker}: New {self.tick_aggregate_size}-tick candle - "
                                f"O: ₹{candle['open']:.2f}, H: ₹{candle['high']:.2f}, "
                                f"L: ₹{candle['low']:.2f}, C: ₹{candle['close']:.2f} | "
                                f"PSAR: ₹{psar_result['psar']:.2f} ({psar_result['trend']})")

            # Clear buffer for next candle
            self.tick_buffers[ticker].clear()

    except Exception as e:
        self.logger.error(f"Error aggregating ticks for {ticker}: {e}")


def check_psar_exit(self, ticker: str, current_price: float):
    """
    Check if current price has crossed PSAR, triggering an exit

    For LONG positions: Exit if price closes below PSAR
    For SHORT positions: Exit if price closes above PSAR

    Args:
        ticker: Trading symbol
        current_price: Current market price
    """
    try:
        if not self.psar_watchdog_enabled:
            return

        if ticker not in self.psar_data:
            # No PSAR data yet
            return

        if ticker not in self.tracked_positions:
            return

        # Check if position already has pending order
        if self.tracked_positions[ticker].get("has_pending_order", False):
            return

        # Pre-order validation: Verify position exists
        position_data = self.tracked_positions.get(ticker, {})
        expected_quantity = position_data.get("quantity", 0)

        if not self.verify_position_exists(ticker, expected_quantity):
            self.logger.warning(f"{ticker}: Position not found in broker account. Removing from tracking.")
            self.remove_position_from_tracking(ticker)
            return

        # Get PSAR data
        psar_info = self.psar_data[ticker]
        psar_value = psar_info['psar']
        psar_trend = psar_info['trend']

        # Get position data
        position_type = position_data.get("type", "LONG")
        quantity = position_data["quantity"]

        # Determine if exit is triggered
        exit_triggered = False
        reason = ""

        if position_type == "LONG":
            # For LONG positions, exit if price is below PSAR
            if current_price < psar_value:
                exit_triggered = True
                reason = f"PSAR Exit - LONG position: Price ₹{current_price:.2f} below PSAR ₹{psar_value:.2f}"
        elif position_type == "SHORT":
            # For SHORT positions, exit if price is above PSAR
            if current_price > psar_value:
                exit_triggered = True
                reason = f"PSAR Exit - SHORT position: Price ₹{current_price:.2f} above PSAR ₹{psar_value:.2f}"

        if exit_triggered:
            # Get appropriate tick size
            tick_size = self.get_tick_size(ticker)

            # Determine transaction type
            if position_type == "LONG":
                transaction_type = "SELL"
                # Place order slightly below current price
                raw_price = current_price * 0.995
            else:
                transaction_type = "BUY"
                # Place order slightly above current price
                raw_price = current_price * 1.005

            order_price = self.round_to_tick_size(raw_price, tick_size)

            self.logger.info(f"{ticker}: {reason}")
            self.logger.info(f"Queuing {transaction_type} order for {quantity} shares at ₹{order_price:.2f}")

            # Queue the exit order
            self.queue_order(ticker, quantity, transaction_type, reason, order_price)

    except Exception as e:
        self.logger.error(f"Error checking PSAR exit for {ticker}: {e}")


def on_ticks(self, ws, ticks):
    """
    Websocket callback for tick data

    Processes incoming ticks and aggregates them into candles for PSAR calculation
    """
    try:
        for tick in ticks:
            instrument_token = tick['instrument_token']

            # Find ticker for this instrument token
            ticker = None
            for t, token in self.instrument_tokens.items():
                if token == instrument_token:
                    ticker = t
                    break

            if not ticker:
                continue

            # Get last traded price
            ltp = tick.get('last_price')
            if not ltp or ltp <= 0:
                continue

            # Update current price
            self.current_prices[ticker] = ltp

            # Aggregate tick into candles
            self.aggregate_ticks_to_candle(ticker, ltp)

            # Check PSAR exit condition
            self.check_psar_exit(ticker, ltp)

    except Exception as e:
        self.logger.error(f"Error processing ticks: {e}")


def on_connect(self, ws, response):
    """Websocket connect callback"""
    self.logger.info(f"Websocket connected: {response}")

    # Subscribe to all tracked positions
    if self.instrument_tokens:
        tokens = list(self.instrument_tokens.values())
        ws.subscribe(tokens)
        ws.set_mode(ws.MODE_LTP, tokens)  # Only need LTP mode
        self.logger.info(f"Subscribed to {len(tokens)} instruments for PSAR monitoring")


def on_close(self, ws, code, reason):
    """Websocket close callback"""
    self.logger.warning(f"Websocket closed: {code} - {reason}")

    # Attempt reconnection if still running
    if self.running:
        self.logger.info("Attempting to reconnect websocket in 5 seconds...")
        time.sleep(5)
        if self.running:
            self.start_websocket()


def on_error(self, ws, code, reason):
    """Websocket error callback"""
    self.logger.error(f"Websocket error: {code} - {reason}")


def start_websocket(self):
    """Initialize and start the websocket connection for tick data"""
    try:
        if not self.psar_watchdog_enabled:
            self.logger.info("PSAR watchdog disabled - skipping websocket initialization")
            return

        self.logger.info("Initializing websocket for tick data...")

        # Create KiteTicker instance
        self.kws = KiteTicker(self.api_key, self.access_token)

        # Assign callbacks
        self.kws.on_ticks = self.on_ticks
        self.kws.on_connect = self.on_connect
        self.kws.on_close = self.on_close
        self.kws.on_error = self.on_error

        # Start websocket in separate thread
        self.websocket_thread = threading.Thread(target=self.kws.connect, daemon=True)
        self.websocket_thread.start()

        self.logger.info("Websocket thread started for real-time tick data")

    except Exception as e:
        self.logger.error(f"Error starting websocket: {e}")


def stop_websocket(self):
    """Stop the websocket connection"""
    try:
        if self.kws:
            self.logger.info("Stopping websocket connection...")
            self.kws.close()
            self.kws = None

        if self.websocket_thread and self.websocket_thread.is_alive():
            self.websocket_thread.join(timeout=5)

        self.logger.info("Websocket stopped")

    except Exception as e:
        self.logger.error(f"Error stopping websocket: {e}")


def subscribe_position_to_websocket(self, ticker: str):
    """Subscribe a single position to websocket for tick data"""
    try:
        if not self.psar_watchdog_enabled or not self.kws:
            return

        # Get instrument token
        token = self.get_instrument_token(ticker)
        if not token:
            self.logger.error(f"Cannot subscribe {ticker} - instrument token not found")
            return

        # Store token mapping
        self.instrument_tokens[ticker] = token

        # Subscribe to websocket
        self.kws.subscribe([token])
        self.kws.set_mode(self.kws.MODE_LTP, [token])

        self.logger.info(f"Subscribed {ticker} (token: {token}) to websocket for PSAR monitoring")

    except Exception as e:
        self.logger.error(f"Error subscribing {ticker} to websocket: {e}")
