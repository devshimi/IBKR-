# ---------------------------
# 1) Custom Exceptions
# ---------------------------
class ConfigError(Exception):
    """Raised when there's a critical configuration issue."""
    pass

class AuthenticationError(Exception):
    """Raised when user authentication fails."""
    pass

class IBKRConnectionError(Exception):
    """Raised when connecting to IBKR fails."""
    pass

class DatabaseError(Exception):
    """Raised for critical DB issues."""
    pass


# ---------------------------
# 2) Logger Setup (Rotating + Console)
# ---------------------------
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

def setup_logger(logger_name: str = "UltimateTradingApp",
                 log_file: str = "ultimate_app.log",
                 level: int = logging.DEBUG) -> logging.Logger:
    """
    Creates a rotating file logger plus console stream handler.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # Prevent double handlers if called multiple times
    if logger.handlers:
        return logger

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch_format = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    ch.setFormatter(ch_format)

    # Rotating File Handler
    fh = RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=2)
    fh.setLevel(level)
    fh_format = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    fh.setFormatter(fh_format)

    logger.addHandler(ch)
    logger.addHandler(fh)
    logger.debug("Logger initialized with rotating file handler.")
    return logger

logger = setup_logger()


# ---------------------------
# 3) Encryption (Fernet)
# ---------------------------
from cryptography.fernet import Fernet

SECRET_KEY_FILE = "secret.key"

def load_or_create_key(key_file: str = SECRET_KEY_FILE) -> bytes:
    """
    Loads the encryption key from SECRET_KEY_FILE or creates a new one
    if not present.
    """
    if not os.path.exists(key_file):
        key = Fernet.generate_key()
        with open(key_file, 'wb') as f:
            f.write(key)
        logger.info(f"Generated new encryption key ({key_file}).")
        return key
    else:
        with open(key_file, 'rb') as f:
            return f.read()

FERNET_KEY: bytes = load_or_create_key(SECRET_KEY_FILE)
fernet: Fernet = Fernet(FERNET_KEY)


# ---------------------------
# 4) Configuration
# ---------------------------
import json

CONFIG_FILE = "config.json"

def recreate_default_config() -> dict:
    """
    Creates and saves a default config dict to disk (encrypted).
    """
    default_cfg = {
        "ibkr": {"host": "127.0.0.1", "port": 7497, "clientId": 1},
        "api_keys": {"finnhub": "", "polygon": ""},
        "database": {"use_db": False}
    }
    save_config(default_cfg)
    return default_cfg

def load_config() -> dict:
    """
    Loads and decrypts the config.json file. Recreates a default if missing.
    """
    if not os.path.exists(CONFIG_FILE):
        logger.warning("No config.json found. Creating a default.")
        return recreate_default_config()
    
    with open(CONFIG_FILE, 'rb') as f:
        data = f.read()
        if not data:
            logger.error("config.json is empty! Recreating default config.")
            return recreate_default_config()
        try:
            decrypted = fernet.decrypt(data)
            return json.loads(decrypted.decode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to decrypt config.json: {e}. Recreating default.")
            return recreate_default_config()

def save_config(cfg: dict) -> None:
    """
    Encrypts and saves the config dict to config.json.
    """
    data_str = json.dumps(cfg, indent=4)
    encrypted = fernet.encrypt(data_str.encode('utf-8'))
    with open(CONFIG_FILE, 'wb') as f:
        f.write(encrypted)
    logger.debug("Config saved (encrypted).")

config: dict = load_config()


# ---------------------------
# 5) Authentication
# ---------------------------
import bcrypt
from typing import List, Optional

USERSTORE_FILE = "users.json"

def recreate_default_users() -> List[dict]:
    """
    Creates a default admin user with username=admin / password=admin.
    """
    default_admin = {"username": "admin", "password_hash": ""}
    hashed_pw = bcrypt.hashpw("admin".encode('utf-8'), bcrypt.gensalt())
    default_admin["password_hash"] = hashed_pw.decode('utf-8')
    save_users([default_admin])
    return [default_admin]

def load_users() -> List[dict]:
    """
    Loads and decrypts the users.json file. Recreates a default admin if missing.
    """
    if not os.path.exists(USERSTORE_FILE):
        logger.warning("No users.json found. Creating a default admin user.")
        return recreate_default_users()
    
    with open(USERSTORE_FILE, 'rb') as f:
        data = f.read()
        if not data:
            logger.error("users.json is empty! Recreating default user file.")
            return recreate_default_users()
        try:
            decrypted = fernet.decrypt(data)
            return json.loads(decrypted.decode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to decrypt users.json: {e}. Recreating default user file.")
            return recreate_default_users()

def save_users(user_list: List[dict]) -> None:
    """
    Encrypts and saves the user list to users.json.
    """
    data_str = json.dumps(user_list, indent=4)
    encrypted = fernet.encrypt(data_str.encode('utf-8'))
    with open(USERSTORE_FILE, 'wb') as f:
        f.write(encrypted)
    logger.debug("Users saved (encrypted).")

users_db: List[dict] = load_users()

def find_user(username: str) -> Optional[dict]:
    """
    Finds a user dict by username (case-insensitive).
    """
    for u in users_db:
        if u["username"].lower() == username.lower():
            return u
    return None

def verify_password(user: dict, password: str) -> bool:
    """
    Verifies a plaintext password against a stored bcrypt hash.
    """
    stored_hash = user["password_hash"].encode('utf-8')
    return bcrypt.checkpw(password.encode('utf-8'), stored_hash)


# ---------------------------
# 6) Database
# ---------------------------
import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
SessionLocal = None

class TradeRecord(Base):
    __tablename__ = 'trades'
    id = Column(Integer, primary_key=True)
    symbol = Column(String)
    action = Column(String)
    quantity = Column(Integer)
    price = Column(Float)
    timestamp = Column(DateTime)

class PositionRecord(Base):
    __tablename__ = 'positions'
    id = Column(Integer, primary_key=True)
    symbol = Column(String)
    quantity = Column(Integer)
    avg_cost = Column(Float)
    realized_pnl = Column(Float)

def init_db() -> Optional[sessionmaker]:
    """
    Initializes and returns the SQLAlchemy session if `use_db` is True.
    Otherwise returns None.
    """
    use_db = config.get("database", {}).get("use_db", False)
    if not use_db:
        logger.info("Database usage is disabled in config.")
        return None
    try:
        engine = create_engine("sqlite:///trades.db")
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        logger.info("SQLAlchemy DB logging enabled. Using trades.db")
        return session_factory
    except Exception as e:
        logger.error(f"Could not initialize DB: {e}")
        raise DatabaseError("Failed to init DB") from e

SessionLocal = init_db()


# ---------------------------
# 7) Positions
# ---------------------------
from sqlalchemy.orm.exc import NoResultFound

class PositionsManager:
    """
    Tracks open positions (symbol -> dict), average cost, realized PnL,
    can optionally log to DB if session is available.
    
    positions[symbol] = {
      "quantity": int,
      "avg_cost": float,
      "realized_pnl": float
    }
    """
    def __init__(self) -> None:
        self.positions: dict = {}
        self.db_session = SessionLocal() if SessionLocal else None

    def on_fill(self, symbol: str, action: str, fill_price: float, fill_qty: int) -> None:
        """
        Called on every execution fill from IBKR. Updates the position's
        quantity, average cost, and realized PnL.
        """
        pos = self.positions.get(symbol, {"quantity": 0, "avg_cost": 0.0, "realized_pnl": 0.0})
        old_qty = pos["quantity"]
        old_avg = pos["avg_cost"]
        old_real = pos["realized_pnl"]

        if action.upper() == "BUY":
            new_qty = old_qty + fill_qty
            if new_qty == 0:
                pos["quantity"] = 0
                pos["avg_cost"] = 0.0
            else:
                total_cost_old = old_qty * old_avg
                total_cost_new = total_cost_old + (fill_qty * fill_price)
                pos["avg_cost"] = total_cost_new / new_qty
                pos["quantity"] = new_qty

        elif action.upper() == "SELL":
            # For a basic long strategy
            if old_qty > 0:
                shares_closed = min(old_qty, fill_qty)
                realized = (fill_price - old_avg) * shares_closed
                pos["realized_pnl"] = old_real + realized
                pos["quantity"] = old_qty - fill_qty
                if pos["quantity"] <= 0:
                    pos["avg_cost"] = 0.0
            else:
                # short logic is simplified, but could be extended
                new_qty = old_qty - fill_qty
                pos["quantity"] = new_qty
        else:
            logger.warning(f"PositionsManager: Unknown action={action}")

        self.positions[symbol] = pos
        logger.info(f"PositionsManager: Updated {symbol} => {self.positions[symbol]}")
        if self.db_session:
            self.save_position_to_db(symbol)

    def save_position_to_db(self, symbol: str) -> None:
        """
        Upserts the position into the 'positions' table via SQLAlchemy.
        """
        rec = self.positions[symbol]
        if not self.db_session:
            return
        try:
            position_obj = self.db_session.query(PositionRecord).filter_by(symbol=symbol).one()
            position_obj.quantity = rec["quantity"]
            position_obj.avg_cost = rec["avg_cost"]
            position_obj.realized_pnl = rec["realized_pnl"]
        except NoResultFound:
            position_obj = PositionRecord(
                symbol=symbol,
                quantity=rec["quantity"],
                avg_cost=rec["avg_cost"],
                realized_pnl=rec["realized_pnl"]
            )
            self.db_session.add(position_obj)
        self.db_session.commit()

    def get_unrealized_pnl(self, symbol: str, last_price: float) -> float:
        """
        Calculates unrealized PnL for a given symbol's position.
        """
        pos = self.positions.get(symbol)
        if not pos or pos["quantity"] == 0:
            return 0.0
        return (last_price - pos["avg_cost"]) * pos["quantity"]


# ---------------------------
# 8) Market Data 
# ---------------------------
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime

class MarketDataInterface:
    """
    Abstract-like interface for fetching market data.
    Could be extended or replaced by real feeds.
    """
    def get_live_price(self, symbol: str) -> Optional[float]:
        raise NotImplementedError("Override me with real data feed logic.")

class MarketDataManager:
    """
    Fetches data from Yahoo (historical) and SEC Filings (via requests).
    For real-time, use IBKR or an internal worker.
    """
    def __init__(self, finnhub_key: str = "", polygon_key: str = "") -> None:
        self.finnhub_key = finnhub_key
        self.polygon_key = polygon_key

    def fetch_yahoo_ohlc(self, symbol: str, period: str = "1mo", interval: str = "1d") -> pd.DataFrame:
        try:
            df = yf.download(symbol, period=period, interval=interval, progress=False)
            logger.debug(f"Fetched {len(df)} rows from yfinance for {symbol}.")
            return df
        except Exception as e:
            logger.error(f"Failed yfinance fetch for {symbol}: {e}")
            return pd.DataFrame()

    def fetch_sec_filings(self, symbol: str) -> Optional[str]:
        """
        Fetches latest SEC Filings from sec.gov for a given symbol or CIK.
        """
        try:
            url = "https://www.sec.gov/cgi-bin/browse-edgar"
            params = {
                "action": "getcompany",
                "CIK": symbol,
                "owner": "exclude",
                "count": "40"
            }
            headers = {"User-Agent": "UltimateApp/1.0"}
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code == 200:
                logger.debug(f"SEC filings fetched for {symbol}")
                return resp.text
            logger.warning(f"SEC request status: {resp.status_code}")
        except Exception as e:
            logger.error(f"SEC Filings fetch error: {e}")
        return None

    def fetch_option_chain_data(self, symbol: str) -> Optional[dict]:
        """
        Fetches option chain data from yfinance for a given symbol.
        """
        try:
            ticker = yf.Ticker(symbol)
            expiries = ticker.options
            if not expiries:
                return None
            chain = ticker.option_chain(expiries[0])
            return {
                "expiries": expiries,
                "calls": chain.calls,
                "puts": chain.puts
            }
        except Exception as e:
            logger.error(f"Failed to fetch option chain for {symbol}: {e}")
        return None


# ---------------------------
# 9) IBKR Integration
# ---------------------------
from ib_insync import IB, Stock, MarketOrder, LimitOrder
import time

class IBKRManager(MarketDataInterface):
    """
    Manages the IBKR connection for live market data, placing/canceling orders,
    DOM, T&S, etc. Integrates with PositionsManager.
    """
    def __init__(self, host: str, port: int, client_id: int,
                 positions_manager: Optional[PositionsManager] = None) -> None:
        super().__init__()
        self.ib = IB()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connected = False
        self.order_event_callback: Optional[callable] = None
        self.positions_manager = positions_manager

    def connect(self) -> None:
        """
        Connects to IBKR TWS/Gateway.
        """
        try:
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            self.connected = True
            logger.info(f"Connected to IBKR {self.host}:{self.port} (clientId={self.client_id}).")

            # Listen for events
            self.ib.orderStatusEvent += self.onOrderStatus
            self.ib.execDetailsEvent += self.onExecDetails
            self.ib.errorEvent += self.onErrorEvent

        except Exception as e:
            self.connected = False
            logger.warning(f"Failed to connect to IBKR: {e}")
            raise IBKRConnectionError from e

    def disconnect(self) -> None:
        """
        Disconnect from IBKR.
        """
        self.ib.disconnect()
        self.connected = False
        logger.info("Disconnected from IBKR.")

    def get_live_price(self, symbol: str) -> Optional[float]:
        """
        Fetches the last trade price from IBKR for a given symbol.
        """
        if not self.connected:
            return None
        contract = Stock(symbol, 'SMART', 'USD')
        ticker = self.ib.reqMktData(contract, "", False, False)
        for _ in range(50):
            if ticker.last is not None:
                return ticker.last
            time.sleep(0.1)
        return None

    def place_limit_order(self, symbol: str, price: float, quantity: int, is_buy: bool = True):
        if not self.connected:
            logger.warning("Not connected to IBKR, can't place order.")
            return None
        contract = Stock(symbol, 'SMART', 'USD')
        action = "BUY" if is_buy else "SELL"
        order = LimitOrder(action, quantity, price)
        trade = self.ib.placeOrder(contract, order)
        logger.info(f"Placed {action} Limit Order on {symbol} at {price}, qty={quantity}")
        return trade

    def place_market_order(self, symbol: str, quantity: int, is_buy: bool = True):
        if not self.connected:
            logger.warning("Not connected to IBKR, can't place order.")
            return None
        contract = Stock(symbol, 'SMART', 'USD')
        action = "BUY" if is_buy else "SELL"
        order = MarketOrder(action, quantity)
        trade = self.ib.placeOrder(contract, order)
        logger.info(f"Placed {action} Market Order on {symbol}, qty={quantity}")
        return trade

    def cancel_order(self, trade):
        if not self.connected:
            logger.warning("Not connected to IBKR, can't cancel order.")
            return
        self.ib.cancelOrder(trade.order)
        logger.info(f"Cancel requested for orderId={trade.order.orderId}")

    def onOrderStatus(self, trade):
        if self.order_event_callback:
            self.order_event_callback("orderStatus", trade)

    def onExecDetails(self, trade, fill):
        if self.order_event_callback:
            self.order_event_callback("execDetails", trade, fill)

        if self.positions_manager and fill:
            self.positions_manager.on_fill(
                trade.contract.symbol,
                trade.order.action,
                float(fill.price),
                int(fill.shares)
            )

    def onErrorEvent(self, reqId: int, errorCode: int, errorMsg: str, contract):
        if self.order_event_callback:
            self.order_event_callback("error", (reqId, errorCode, errorMsg))

    def subscribe_dom(self, symbol: str, depth_handler: callable) -> None:
        if not self.connected:
            logger.warning("Can't subscribe DOM. IBKR not connected.")
            return
        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.reqMktDepth(contract, rows=10, isSmartDepth=False)

        def dom_callback(diffs):
            levels = self.ib.domTicks(contract)
            bids, asks = [], []
            for lvl in levels:
                if lvl.side == 1:
                    bids.append((lvl.price, lvl.size))
                else:
                    asks.append((lvl.price, lvl.size))
            depth_handler(bids, asks)

        self.ib.updateMktDepth += dom_callback
        logger.info(f"Subscribed to DOM for {symbol}.")

    def subscribe_tas(self, symbol: str, tas_handler: callable) -> None:
        if not self.connected:
            logger.warning("Can't subscribe T&S. IBKR not connected.")
            return
        contract = Stock(symbol, 'SMART', 'USD')

        def onTickByTick(ticks, done: bool = False):
            for t in ticks:
                if hasattr(t, 'price'):
                    tas_handler(t.price, t.size, t.time)

        self.ib.reqTickByTickData(contract, "AllLast", 0, True)
        self.ib.tickByTickEvent += onTickByTick
        logger.info(f"Subscribed to T&S for {symbol}.")


# ---------------------------
# 10) Alert System
# ---------------------------
class AlertEngine:
    """
    Manages technical or price-based alerts and triggers user-defined callbacks
    when conditions are met.
    """
    def __init__(self) -> None:
        # (type, symbol, condition_func, callback)
        self.alerts = []

    def add_technical_alert(self, symbol: str, condition_func, callback) -> None:
        """
        Registers an alert that triggers if condition_func(price)==True
        """
        self.alerts.append(("technical", symbol, condition_func, callback))
        logger.debug(f"Added alert on {symbol}")

    def check_alerts(self, price_dict: dict) -> None:
        """
        Checks all known alerts against the latest price dictionary.
        """
        triggered = []
        for (atype, sym, cond, cb) in self.alerts:
            if atype == "technical":
                px = price_dict.get(sym)
                if px is not None and cond(px):
                    triggered.append((sym, cb))

        for (sym, handler) in triggered:
            logger.info(f"Alert triggered for {sym}")
            handler(sym)


# ---------------------------
# 11) Backtester
# ---------------------------
import numpy as np

class Backtester:
    """
    Demonstrates a simple SMA-based backtest with a buy/sell cross strategy.
    """
    def __init__(self, df_ohlc: pd.DataFrame, initial_capital: float = 100_000) -> None:
        self.df = df_ohlc
        self.initial_capital = initial_capital

    def sma_strategy(self, short_win: int = 20, long_win: int = 50):
        """
        Simple moving average cross strategy with long-only logic.
        
        Returns:
            - DataFrame with columns (signal, positions, portfolio_value)
            - final portfolio value
            - % return from initial capital
        """
        df = self.df.copy()
        if df.empty:
            return df, self.initial_capital, 0
        
        df["SMA_short"] = df["Close"].rolling(short_win).mean()
        df["SMA_long"] = df["Close"].rolling(long_win).mean()

        df["signal"] = 0
        df.loc[df.index[long_win:], "signal"] = np.where(
            df["SMA_short"][long_win:] > df["SMA_long"][long_win:], 1, 0
        )
        df["positions"] = df["signal"].diff()

        capital = self.initial_capital
        shares = 0
        portfolio_vals = []

        for _, row in df.iterrows():
            if row["positions"] == 1:  # Buy signal
                if row["Close"] > 0:
                    can_buy = int(capital // row["Close"])
                    cost = can_buy * row["Close"]
                    shares += can_buy
                    capital -= cost
            elif row["positions"] == -1:  # Sell signal
                capital += shares * row["Close"]
                shares = 0
            portfolio_vals.append(capital + shares * row["Close"])

        df["portfolio_value"] = portfolio_vals
        final_val = portfolio_vals[-1] if portfolio_vals else self.initial_capital
        ret_pct = (final_val - self.initial_capital) / self.initial_capital * 100
        logger.debug(f"Backtest final={final_val:.2f}, ret={ret_pct:.2f}%")
        return df, final_val, ret_pct


# ---------------------------
# 12) Candlesticks
# ---------------------------
from pyqtgraph import GraphicsObject, mkPen, mkBrush, QtGui, QtCore
from PyQt5.QtCore import QRectF

class CandlestickItem(GraphicsObject):
    """
    Custom candlestick item for PyQtGraph that renders the candle
    as a rectangle plus a wick line.
    Data format: list of tuples (timestamp, open, close, low, high).
    """
    def __init__(self, data=None) -> None:
        super().__init__()
        self.data = data if data else []
        self.picture = None
        self.generatePicture()

    def setData(self, data) -> None:
        self.data = data
        self.generatePicture()
        self.update()

    def generatePicture(self) -> None:
        self.picture = QtGui.QPicture()
        painter = QtGui.QPainter(self.picture)
        pen = mkPen('w', width=1)

        for (t, op, cl, lo, hi) in self.data:
            painter.setPen(pen)
            # wick
            painter.drawLine(QtCore.QPointF(t, lo), QtCore.QPointF(t, hi))
            # body
            if cl >= op:
                painter.setBrush(mkBrush('g'))  # bullish
            else:
                painter.setBrush(mkBrush('r'))  # bearish
            candleRect = QtCore.QRectF(t - 0.3, op, 0.6, cl - op)
            painter.drawRect(candleRect)

        painter.end()

    def paint(self, p: QtGui.QPainter, *args) -> None:
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self) -> QRectF:
        if not self.data:
            return QRectF()
        xs = [d[0] for d in self.data]
        lows = [d[3] for d in self.data]
        highs = [d[4] for d in self.data]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(lows), max(highs)
        return QRectF(xmin - 1, ymin - 1, (xmax - xmin) + 2, (ymax - ymin) + 2)


# ---------------------------
# 13) Chart Data
# ---------------------------
from datetime import datetime

class ChartDataManager:
    """
    Maintains rolling candlestick data for real-time updates (1-minute candle).
    
    symbol_candles[symbol] = list of (timestamp, open, close, low, high)
    """
    def __init__(self) -> None:
        self.symbol_candles = {}
        self.current_bar_time = {}

    def update_price(self, symbol: str, price: float) -> None:
        ts = datetime.utcnow()
        minute_stamp = ts.replace(second=0, microsecond=0)

        if symbol not in self.symbol_candles:
            self.symbol_candles[symbol] = []
            self.current_bar_time[symbol] = minute_stamp
            self.symbol_candles[symbol].append(
                (minute_stamp.timestamp(), price, price, price, price)
            )
            return

        candles = self.symbol_candles[symbol]
        last_bar = candles[-1]
        last_bar_time = datetime.utcfromtimestamp(last_bar[0])

        if minute_stamp == last_bar_time:
            # same minute, update
            op, cl, lo, hi = last_bar[1], last_bar[2], last_bar[3], last_bar[4]
            cl = price
            lo = min(lo, price)
            hi = max(hi, price)
            candles[-1] = (last_bar[0], op, cl, lo, hi)
        else:
            # new candle
            candles.append(
                (minute_stamp.timestamp(), price, price, price, price)
            )
            self.current_bar_time[symbol] = minute_stamp

    def get_candles(self, symbol: str):
        return self.symbol_candles.get(symbol, [])


# ---------------------------
# 14) Login Dialog
# ---------------------------
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QHBoxLayout
from PyQt5.QtWidgets import QLineEdit, QPushButton, QMessageBox

class LoginDialog(QDialog):
    """
    Shows a login dialog for username/password, plus a 'Skip IBKR' option for offline mode.
    """
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ultimate Trading - Login")
        self.resize(300, 150)

        layout = QVBoxLayout()
        form_layout = QFormLayout()

        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)

        form_layout.addRow("Username:", self.username_input)
        form_layout.addRow("Password:", self.password_input)

        layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        self.btn_login = QPushButton("Login (IBKR)")
        self.btn_skip = QPushButton("Skip IBKR")

        self.btn_login.clicked.connect(self.do_login)
        self.btn_skip.clicked.connect(self.do_skip)

        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(self.btn_skip)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self.authenticated: bool = False
        self.skip: bool = False

    def do_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        user = find_user(username)
        if not user:
            QMessageBox.warning(self, "Error", "User not found.")
            logger.warning(f"User not found: {username}")
            return

        if not verify_password(user, password):
            QMessageBox.warning(self, "Error", "Invalid password.")
            logger.warning(f"Invalid password for user: {username}")
            return

        self.authenticated = True
        logger.info(f"User {username} authenticated.")
        self.accept()

    def do_skip(self) -> None:
        self.skip = True
        logger.info("Skipping IBKR, offline mode.")
        self.accept()


# ---------------------------
# 15) Strategy Engine
# ---------------------------
class StrategyEngine:
    """
    Placeholder for advanced strategies. Tied to "Run Autotrader" in MainWindow.
    """
    def __init__(self, ibkr_manager: Optional[IBKRManager]) -> None:
        self.ibkr_manager = ibkr_manager
        self.running = False

    def start(self) -> None:
        """Starts all configured strategies."""
        logger.info("[StrategyEngine] Starting strategies.")
        self.running = True

    def stop(self) -> None:
        """Stops all configured strategies."""
        logger.info("[StrategyEngine] Stopping strategies.")
        self.running = False


# ---------------------------
# 16) UI Tabs
# ---------------------------
# 16.1) OrdersTab
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QLabel

class OrdersTab(QWidget):
    """
    Displays current IBKR orders in a table, allows canceling them.
    """
    def __init__(self, ibkr_manager=None):
        super().__init__()
        self.ibkr_manager = ibkr_manager
        layout = QVBoxLayout()

        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(6)
        self.orders_table.setHorizontalHeaderLabels([
            "Order ID", "Symbol", "Action", "Qty", "Status", "Cancel?"
        ])
        self.orders_table.cellClicked.connect(self.on_table_click)

        layout.addWidget(QLabel("Live Orders"))
        layout.addWidget(self.orders_table)
        self.setLayout(layout)

        self.order_map = {}

    def update_order(self, trade) -> None:
        """
        Updates or inserts an order row in the QTableWidget.
        """
        oid = trade.order.orderId
        symbol = getattr(trade.contract, "symbol", "???")
        action = trade.order.action
        qty = trade.order.totalQuantity
        status = trade.orderStatus.status

        row = self.find_order_row(oid)
        if row < 0:
            row = self.orders_table.rowCount()
            self.orders_table.insertRow(row)

        self.order_map[oid] = trade

        self.orders_table.setItem(row, 0, QTableWidgetItem(str(oid)))
        self.orders_table.setItem(row, 1, QTableWidgetItem(symbol))
        self.orders_table.setItem(row, 2, QTableWidgetItem(action))
        self.orders_table.setItem(row, 3, QTableWidgetItem(str(qty)))
        self.orders_table.setItem(row, 4, QTableWidgetItem(status))
        self.orders_table.setItem(row, 5, QTableWidgetItem("Cancel"))

        # Gray out if filled/cancelled
        if status in ["Filled", "Cancelled", "ApiCancelled"]:
            for c in range(self.orders_table.columnCount()):
                item = self.orders_table.item(row, c)
                if item:
                    item.setForeground(Qt.gray)

    def find_order_row(self, order_id: int) -> int:
        for r in range(self.orders_table.rowCount()):
            cell = self.orders_table.item(r, 0)
            if cell and cell.text() == str(order_id):
                return r
        return -1

    def on_table_click(self, row: int, col: int) -> None:
        if col == 5:  # Cancel? column
            oid_item = self.orders_table.item(row, 0)
            if oid_item:
                oid = int(oid_item.text())
                trade = self.order_map.get(oid)
                if trade and self.ibkr_manager:
                    self.ibkr_manager.cancel_order(trade)
                    QMessageBox.information(self, "Order", f"Cancel requested for OrderId={oid}")


# 16.2) BotManagementTab
from PyQt5.QtWidgets import QHBoxLayout, QTextEdit, QLineEdit, QPushButton

class Bot:
    """
    Placeholder for an algorithmic bot or strategy.
    """
    def __init__(self, name: str, symbol: str) -> None:
        self.name = name
        self.symbol = symbol
        self.active = False

    def start(self) -> None:
        self.active = True

    def stop(self) -> None:
        self.active = False

class BotManagementTab(QWidget):
    """
    Allows creating and stopping placeholder algo bots, logs output in a QTextEdit.
    """
    def __init__(self, ibkr_manager=None):
        super().__init__()
        self.ibkr_manager = ibkr_manager
        layout = QVBoxLayout()

        self.bots: List[Bot] = []
        self.text_log = QTextEdit()

        input_layout = QHBoxLayout()
        self.bot_symbol_edit = QLineEdit()
        self.bot_symbol_edit.setPlaceholderText("Symbol for new Bot (e.g. AAPL)")
        self.btn_add_bot = QPushButton("Add Bot")
        self.btn_add_bot.clicked.connect(self.add_bot)
        input_layout.addWidget(self.bot_symbol_edit)
        input_layout.addWidget(self.btn_add_bot)

        self.btn_stop_all = QPushButton("Stop All Bots")
        self.btn_stop_all.clicked.connect(self.stop_all)

        layout.addWidget(QLabel("Algorithmic Bot Manager (placeholder)"))
        layout.addLayout(input_layout)
        layout.addWidget(self.btn_stop_all)
        layout.addWidget(self.text_log)
        self.setLayout(layout)

    def add_bot(self) -> None:
        sym = self.bot_symbol_edit.text().strip()
        if not sym:
            return
        bot_name = f"Bot_{len(self.bots)+1}"
        bot = Bot(bot_name, sym)
        bot.start()
        self.bots.append(bot)
        self.text_log.append(f"[{bot_name}] started on {sym}")

    def stop_all(self) -> None:
        for b in self.bots:
            b.stop()
        self.text_log.append(f"Stopped all {len(self.bots)} bots")


# 16.3) PositionsTab
from PyQt5.QtCore import QTimer

class PositionsTab(QWidget):
    """
    Displays open positions and their PnL in a QTableWidget, refreshing periodically.
    """
    def __init__(self, positions_manager: PositionsManager,
                 price_getter: callable) -> None:
        super().__init__()
        self.positions_manager = positions_manager
        self.get_last_price = price_getter

        layout = QVBoxLayout()
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Symbol", "Quantity", "Avg Cost", "Realized PnL", "Unrealized PnL"
        ])
        layout.addWidget(QLabel("Open Positions & PnL"))
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_positions)
        self.timer.start(3000)

    def refresh_positions(self) -> None:
        positions = self.positions_manager.positions
        self.table.setRowCount(len(positions))
        row = 0
        for sym, data in positions.items():
            qty = data["quantity"]
            avg_cost = data["avg_cost"]
            realized = data["realized_pnl"]
            last_px = self.get_last_price(sym) or avg_cost
            unreal = self.positions_manager.get_unrealized_pnl(sym, last_px)

            self.table.setItem(row, 0, QTableWidgetItem(sym))
            self.table.setItem(row, 1, QTableWidgetItem(str(qty)))
            self.table.setItem(row, 2, QTableWidgetItem(f"{avg_cost:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{realized:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{unreal:.2f}"))
            row += 1


# 16.4) OptionChainTab
class OptionChainTab(QWidget):
    """
    Displays an option chain for a specified symbol using yfinance.
    """
    def __init__(self, market_data_manager: MarketDataManager):
        super().__init__()
        self.mdm = market_data_manager

        layout = QVBoxLayout()

        self.oc_symbol_edit = QLineEdit()
        self.oc_symbol_edit.setPlaceholderText("Symbol (e.g. AAPL)")
        self.btn_oc_fetch = QPushButton("Fetch Option Chain")
        self.btn_oc_fetch.clicked.connect(self.on_fetch_option_chain)

        self.oc_expiry_combo = QComboBox()
        self.oc_expiry_combo.currentIndexChanged.connect(self.on_expiry_changed)

        self.oc_calls_table = QTableWidget()
        self.oc_calls_table.setColumnCount(4)
        self.oc_calls_table.setHorizontalHeaderLabels(["Strike", "LastPrice", "Volume", "OpenInt"])

        self.oc_puts_table = QTableWidget()
        self.oc_puts_table.setColumnCount(4)
        self.oc_puts_table.setHorizontalHeaderLabels(["Strike", "LastPrice", "Volume", "OpenInt"])

        layout.addWidget(QLabel("OPTION CHAIN (yfinance)"))
        layout.addWidget(self.oc_symbol_edit)
        layout.addWidget(self.btn_oc_fetch)
        layout.addWidget(QLabel("Expiry:"))
        layout.addWidget(self.oc_expiry_combo)
        layout.addWidget(QLabel("Calls"))
        layout.addWidget(self.oc_calls_table)
        layout.addWidget(QLabel("Puts"))
        layout.addWidget(self.oc_puts_table)

        self.setLayout(layout)
        self._option_chain_data = None

    def on_fetch_option_chain(self) -> None:
        sym = self.oc_symbol_edit.text().strip()
        if not sym:
            return
        data = self.mdm.fetch_option_chain_data(sym)
        if not data:
            QMessageBox.warning(self, "OptionChain", "No option chain data found.")
            return
        self._option_chain_data = data
        self.oc_expiry_combo.clear()
        for expiry in data["expiries"]:
            self.oc_expiry_combo.addItem(expiry)
        self.load_chain_tables(data["calls"], data["puts"])

    def on_expiry_changed(self, idx: int) -> None:
        if not self._option_chain_data:
            return
        sym = self.oc_symbol_edit.text().strip()
        if not sym:
            return
        expiry = self.oc_expiry_combo.currentText()
        try:
            ticker = yf.Ticker(sym)
            chain = ticker.option_chain(expiry)
            calls, puts = chain.calls, chain.puts
            self.load_chain_tables(calls, puts)
        except Exception as e:
            logger.error(f"Chain fetch error for {sym} expiry {expiry}: {e}")

    def load_chain_tables(self, calls_df: pd.DataFrame, puts_df: pd.DataFrame) -> None:
        self.oc_calls_table.setRowCount(len(calls_df))
        for r, row in enumerate(calls_df.itertuples()):
            self.oc_calls_table.setItem(r, 0, QTableWidgetItem(str(row.strike)))
            self.oc_calls_table.setItem(r, 1, QTableWidgetItem(str(row.lastPrice)))
            self.oc_calls_table.setItem(r, 2, QTableWidgetItem(str(row.volume)))
            self.oc_calls_table.setItem(r, 3, QTableWidgetItem(str(row.openInterest)))

        self.oc_puts_table.setRowCount(len(puts_df))
        for r, row in enumerate(puts_df.itertuples()):
            self.oc_puts_table.setItem(r, 0, QTableWidgetItem(str(row.strike)))
            self.oc_puts_table.setItem(r, 1, QTableWidgetItem(str(row.lastPrice)))
            self.oc_puts_table.setItem(r, 2, QTableWidgetItem(str(row.volume)))
            self.oc_puts_table.setItem(r, 3, QTableWidgetItem(str(row.openInterest)))


# 16.5) SecFilingsTab
class SecFilingsTab(QWidget):
    def __init__(self, market_data_manager: MarketDataManager):
        super().__init__()
        self.mdm = market_data_manager

        layout = QVBoxLayout()

        self.sec_symbol_edit = QLineEdit()
        self.sec_symbol_edit.setPlaceholderText("Symbol (e.g. AAPL)")
        
        self.btn_sec_fetch = QPushButton("Fetch SEC Filings")
        self.btn_sec_fetch.clicked.connect(self.on_fetch_filings)
        
        self.sec_text_area = QTextEdit()
        
        layout.addWidget(self.sec_symbol_edit)
        layout.addWidget(self.btn_sec_fetch)
        layout.addWidget(self.sec_text_area)
        
        self.setLayout(layout)

    def on_fetch_filings(self) -> None:
        sym = self.sec_symbol_edit.text().strip()
        if sym:
            text = self.mdm.fetch_sec_filings(sym)
            if text:
                self.sec_text_area.setPlainText(text)
            else:
                self.sec_text_area.setPlainText("Failed to retrieve SEC filings.")


# 16.6) AlertsTab
class AlertsTab(QWidget):
    """
    Simple UI for adding a price-based alert.
    """
    def __init__(self, alert_engine: AlertEngine):
        super().__init__()
        self.alert_engine = alert_engine

        layout = QVBoxLayout()

        self.alert_symbol_input = QLineEdit()
        self.alert_symbol_input.setPlaceholderText("Symbol (e.g. AAPL)")
        self.alert_price_input = QLineEdit()
        self.alert_price_input.setPlaceholderText("Price threshold")

        self.btn_add_alert = QPushButton("Add Alert")
        self.btn_add_alert.clicked.connect(self.on_add_alert)

        layout.addWidget(QLabel("Price-based alert - triggers if current price >= threshold"))
        layout.addWidget(self.alert_symbol_input)
        layout.addWidget(self.alert_price_input)
        layout.addWidget(self.btn_add_alert)

        self.setLayout(layout)

    def on_add_alert(self) -> None:
        sym = self.alert_symbol_input.text().strip()
        if not sym:
            return
        try:
            thresh = float(self.alert_price_input.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Alert Error", "Invalid number.")
            return
        
        def cond_func(px: float) -> bool:
            return px >= thresh
        
        def callback(symbol: str) -> None:
            QMessageBox.information(self, "ALERT", f"{symbol} reached {thresh}!")
        
        self.alert_engine.add_technical_alert(sym, cond_func, callback)
        QMessageBox.information(self, "Success", f"Alert added on {sym} at {thresh}.")


# 16.7) BacktestTab
class BacktestTab(QWidget):
    """
    Simple tab that runs a 20/50 SMA strategy on 1 year of daily data.
    """
    def __init__(self, market_data_manager: MarketDataManager):
        super().__init__()
        self.mdm = market_data_manager

        layout = QVBoxLayout()
        
        self.backtest_symbol_input = QLineEdit()
        self.backtest_symbol_input.setPlaceholderText("Symbol (e.g. AAPL)")
        
        self.btn_run_backtest = QPushButton("Run SMA Backtest (20/50)")
        self.btn_run_backtest.clicked.connect(self.on_run_backtest)
        
        self.backtest_text_area = QTextEdit()
        
        layout.addWidget(QLabel("Simple SMA Backtest over 1y of daily data."))
        layout.addWidget(self.backtest_symbol_input)
        layout.addWidget(self.btn_run_backtest)
        layout.addWidget(self.backtest_text_area)
        
        self.setLayout(layout)

    def on_run_backtest(self) -> None:
        sym = self.backtest_symbol_input.text().strip()
        if not sym:
            return
        df = self.mdm.fetch_yahoo_ohlc(sym, period="1y", interval="1d")
        if df.empty:
            self.backtest_text_area.setPlainText("No data for that symbol.")
            return
        
        bt = Backtester(df)
        _, final_val, ret_pct = bt.sma_strategy()
        
        result_str = f"Final Value: {final_val:.2f}\nReturn: {ret_pct:.2f}%"
        self.backtest_text_area.setPlainText(result_str)


# 16.8) DomTsTab
class DomTsTab(QWidget):
    """
    Displays DOM and T&S for a chosen symbol via IBKR.
    """
    def __init__(self, ibkr_manager: IBKRManager):
        super().__init__()
        self.ibkr_manager = ibkr_manager

        layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        self.dom_table = QTableWidget(10, 2)
        self.dom_table.setHorizontalHeaderLabels(["Bid Price", "Size"])
        self.tas_text_area = QTextEdit()

        left_layout.addWidget(QLabel("Depth of Market (bids)"))
        left_layout.addWidget(self.dom_table)

        right_layout.addWidget(QLabel("Time & Sales"))
        right_layout.addWidget(self.tas_text_area)

        layout.addLayout(left_layout)
        layout.addLayout(right_layout)

        self.dom_symbol_edit = QLineEdit()
        self.dom_symbol_edit.setPlaceholderText("Symbol for DOM & T&S")
        self.btn_subscribe_dom = QPushButton("Subscribe DOM & T&S")
        self.btn_subscribe_dom.clicked.connect(self.on_subscribe_dom_ts)

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.dom_symbol_edit)
        bottom_layout.addWidget(self.btn_subscribe_dom)

        main_vlayout = QVBoxLayout()
        main_vlayout.addLayout(layout)
        main_vlayout.addLayout(bottom_layout)

        self.setLayout(main_vlayout)

    def on_subscribe_dom_ts(self) -> None:
        if not self.ibkr_manager or not self.ibkr_manager.connected:
            QMessageBox.warning(self, "IBKR", "Not connected. Can't subscribe DOM/T&S.")
            return
        sym = self.dom_symbol_edit.text().strip()
        if not sym:
            return

        def dom_handler(bids, asks):
            self.dom_table.clearContents()
            row = 0
            sorted_bids = sorted(bids, key=lambda x: x[0], reverse=True)[:10]
            for (price, size) in sorted_bids:
                if row < 10:
                    self.dom_table.setItem(row, 0, QTableWidgetItem(f"{price:.2f}"))
                    self.dom_table.setItem(row, 1, QTableWidgetItem(str(int(size))))
                    row += 1

        def tas_handler(price: float, size: float, ts):
            timestr = ts.strftime("%H:%M:%S")
            self.tas_text_area.append(f"{timestr}  {price:.2f} x {size}")

        self.ibkr_manager.subscribe_dom(sym, dom_handler)
        self.ibkr_manager.subscribe_tas(sym, tas_handler)
        QMessageBox.information(self, "DOM & T&S", f"Subscribed to {sym} successfully.")


# ---------------------------
# 17) Main Window
# ---------------------------
from PyQt5.QtWidgets import QMainWindow, QTabWidget
from PyQt5.QtCore import QThread, pyqtSignal

class MarketDataWorker(QThread):
    dataSignal = pyqtSignal(dict)  # symbol->price

    def __init__(self, symbols: List[str], ibkr_manager: Optional[IBKRManager] = None,
                 interval: int = 5, parent=None):
        super().__init__(parent)
        self.symbols = symbols
        self.ibkr = ibkr_manager
        self.interval = interval
        self.running = True

    def run(self) -> None:
        import time
        import yfinance as yf

        while self.running:
            prices: dict = {}
            if self.ibkr and self.ibkr.connected:
                # Use IBKR
                for sym in self.symbols:
                    px = self.ibkr.get_live_price(sym)
                    if px is not None:
                        prices[sym] = px
            else:
                # Yahoo fallback (faking near real-time by using '1m' data)
                for sym in self.symbols:
                    df = yf.download(sym, period="1d", interval="1m", progress=False)
                    if not df.empty:
                        last_close = float(df["Close"][-1])
                        prices[sym] = last_close
            
            if prices:
                self.dataSignal.emit(prices)
                logger.debug(f"[MarketDataWorker] Emitted prices: {prices}")
            time.sleep(self.interval)

    def stop(self) -> None:
        self.running = False
        logger.info("[MarketDataWorker] Stopping thread.")


import pyqtgraph as pg

class MainWindow(QMainWindow):
    def __init__(self, use_ibkr: bool = False) -> None:
        super().__init__()
        self.setWindowTitle("Ultimate Enterprise Trading (Real-Time Chart + PnL) - Pro Edition")
        self.resize(1400, 900)

        self.autotrader_running = False
        self.btn_autotrader = QPushButton("Run Autotrader")
        self.btn_autotrader.clicked.connect(self.toggle_autotrader)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.btn_autotrader)

        # PositionsManager
        self.positions_manager = PositionsManager()

        # IBKR Manager
        self.ibkr_manager = None
        if use_ibkr:
            ib_cfg = config.get("ibkr", {})
            host = ib_cfg.get("host", "127.0.0.1")
            port = ib_cfg.get("port", 7497)
            cid = ib_cfg.get("clientId", 1)
            
            self.ibkr_manager = IBKRManager(host, port, cid, positions_manager=self.positions_manager)
            try:
                self.ibkr_manager.connect()
            except:
                QMessageBox.warning(self, "IBKR Error", "Failed to connect. Offline features only.")
        else:
            logger.info("Running in offline mode (no IBKR).")

        # StrategyEngine
        self.strategy_engine = StrategyEngine(self.ibkr_manager) if self.ibkr_manager else None

        # If IBKR manager is valid, wire up event callback
        if self.ibkr_manager:
            self.ibkr_manager.order_event_callback = self.on_ibkr_order_event

        # Market data + alerts
        api_keys = config.get("api_keys", {})
        self.market_data_manager = MarketDataManager(
            finnhub_key=api_keys.get("finnhub", ""),
            polygon_key=api_keys.get("polygon", "")
        )
        self.alert_engine = AlertEngine()

        # Real-time chart manager
        self.chart_data_manager = ChartDataManager()

        # TABS
        self.tab_dashboard = self.create_dashboard_tab()
        self.tab_option_chain = OptionChainTab(self.market_data_manager)
        self.tab_sec_filings = SecFilingsTab(self.market_data_manager)
        self.tab_alerts = AlertsTab(self.alert_engine)
        self.tab_backtest = BacktestTab(self.market_data_manager)

        self.tab_dom_ts = DomTsTab(self.ibkr_manager) if self.ibkr_manager else QWidget()
        self.tab_orders = OrdersTab(self.ibkr_manager) if self.ibkr_manager else QWidget()
        self.tab_bots = BotManagementTab(self.ibkr_manager)
        self.tab_positions = PositionsTab(self.positions_manager, self.get_last_price)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.tab_dashboard, "Market Dashboard")
        self.tabs.addTab(self.tab_option_chain, "Option Chain")
        self.tabs.addTab(self.tab_sec_filings, "SEC Filings")
        self.tabs.addTab(self.tab_alerts, "Alerts")
        self.tabs.addTab(self.tab_backtest, "Backtest")
        self.tabs.addTab(self.tab_dom_ts, "DOM & T&S")
        self.tabs.addTab(self.tab_orders, "Orders")
        self.tabs.addTab(self.tab_bots, "Bots")
        self.tabs.addTab(self.tab_positions, "Positions")

        # MarketDataWorker
        self.symbols_to_watch = ["AAPL", "TSLA", "MSFT"]
        self.data_worker = MarketDataWorker(self.symbols_to_watch, self.ibkr_manager, interval=5)
        self.data_worker.dataSignal.connect(self.on_market_data_update)
        self.data_worker.start()

        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.tabs)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Timer to refresh the chart
        self.chart_timer = QTimer()
        self.chart_timer.timeout.connect(self.refresh_chart)
        self.chart_timer.start(5000)

        self._last_prices = {}

    def toggle_autotrader(self) -> None:
        if not self.autotrader_running:
            self.autotrader_running = True
            self.btn_autotrader.setText("Stop Autotrader")
            logger.info("[AUTOTRADER] Started (placeholder).")
            if self.strategy_engine:
                self.strategy_engine.start()
        else:
            self.autotrader_running = False
            self.btn_autotrader.setText("Run Autotrader")
            logger.info("[AUTOTRADER] Stopped (placeholder).")
            if self.strategy_engine:
                self.strategy_engine.stop()

    def get_last_price(self, symbol: str) -> Optional[float]:
        return self._last_prices.get(symbol, None)

    def on_ibkr_order_event(self, event_type: str, *args) -> None:
        if event_type == "orderStatus":
            trade = args[0]
            self.tab_orders.update_order(trade)
        elif event_type == "execDetails":
            trade, fill = args
            self.tab_orders.update_order(trade)
        elif event_type == "error":
            reqId, errorCode, errorMsg = args[0]
            logger.warning(f"Order error {errorCode}: {errorMsg}")

    def create_dashboard_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout()

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setLabel("bottom", "Time")
        self.plot_widget.setLabel("left", "Price")
        self.plot_widget.showGrid(x=True, y=True)

        self.candle_item = CandlestickItem()
        self.plot_widget.addItem(self.candle_item)

        layout.addWidget(QLabel("Real-Time Candlestick Chart"))
        layout.addWidget(self.plot_widget)

        widget.setLayout(layout)
        return widget

    def refresh_chart(self) -> None:
        if not self.symbols_to_watch:
            return
        symbol = self.symbols_to_watch[0]
        candles = self.chart_data_manager.get_candles(symbol)
        self.candle_item.setData(candles)
        self.plot_widget.enableAutoRange()

    def on_market_data_update(self, price_dict: dict) -> None:
        self._last_prices = price_dict
        self.alert_engine.check_alerts(price_dict)

        for sym, px in price_dict.items():
            self.chart_data_manager.update_price(sym, px)

    def closeEvent(self, event) -> None:
        reply = QMessageBox.question(
            self, "Exit",
            "Are you sure you want to exit?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self.data_worker:
                self.data_worker.stop()
                self.data_worker.wait()
            if self.ibkr_manager and self.ibkr_manager.connected:
                self.ibkr_manager.disconnect()
            logger.info("Application closed.")
            event.accept()
        else:
            event.ignore()


# ---------------------------
# 18) main () – Entry Point
# ---------------------------
def main() -> None:
    """
    Entry point of the entire application. Launches the login dialog,
    then the main window in IBKR or offline mode.
    """
    from PyQt5.QtWidgets import QApplication
    import sys

    logger.info("Starting Ultimate Trading App (Real-Time Chart + PnL) - Pro Edition.")
    
    app = QApplication(sys.argv)
    login_dialog = LoginDialog()
    login_dialog.exec_()
    
    if login_dialog.skip:
        window = MainWindow(use_ibkr=False)
        window.show()
        sys.exit(app.exec_())
    else:
        if login_dialog.authenticated:
            window = MainWindow(use_ibkr=True)
            window.show()
            sys.exit(app.exec_())
        else:
            logger.warning("Login canceled or invalid. Exiting.")
            sys.exit(0)


if __name__ == "__main__":
    main()
#---------------------------------------------------------------------------------------------------------------------------------------
#Disclaimer
#This project is provided for educational and research purposes only. It is not financial advice, nor an invitation to trade or invest.
#The author does not guarantee the accuracy, completeness, or profitability of this trading software. Use of this code in live or paper trading environments is at your own risk.
#Trading financial instruments such as stocks, options, or derivatives involves significant risk of loss and may not be suitable for all investors. You are solely responsible for any decisions or trades you make.
#Before using this system, consult with a qualified financial advisor and ensure compliance with your local regulations and your broker’s terms of service.
#The author is not liable for any damages, financial losses, or legal issues resulting from the use of this codebase.
#--------------------------------------------------------------------------------------------------------------------------------------
