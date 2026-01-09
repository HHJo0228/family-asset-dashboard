from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Date, ForeignKey, Index
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Account(Base):
    __tablename__ = 'account_master'
    
    account_number = Column(String, primary_key=True)
    owner = Column(String, nullable=False)
    account_name = Column(String, nullable=False)
    broker = Column(String)
    type = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_account_lookup', 'owner', 'account_name'),
    )

    def __repr__(self):
        return f"<Account(owner={self.owner}, name={self.account_name})>"

class Asset(Base):
    __tablename__ = 'asset_master'
    
    asset_name = Column(String, primary_key=True) # Assuming unique asset names for now
    ticker = Column(String)
    currency = Column(String, default='KRW')
    asset_class = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_asset_ticker', 'ticker'),
    )

    def __repr__(self):
        return f"<Asset(name={self.asset_name}, ticker={self.ticker})>"

class Transaction(Base):
    __tablename__ = 'transaction_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    owner = Column(String, nullable=False)
    account_name = Column(String, nullable=False)
    asset_name = Column(String, nullable=False) # FK logically to Asset.asset_name
    type = Column(String, nullable=False) # Buy, Sell, Deposit, etc.
    
    amount = Column(Float, default=0.0)
    qty = Column(Float, default=0.0)
    price = Column(Float, default=0.0)
    fee = Column(Float, default=0.0) # New: Fee field
    currency = Column(String)
    
    status = Column(String, default='Settled') # Pending vs Settled (미결제/완료)
    note = Column(String)
    
    # Sync Meta
    sync_hash = Column(String, unique=True)
    source_row_index = Column(Integer)
    synced_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_txn_date', 'date'),
        Index('idx_txn_owner_asset', 'owner', 'asset_name'),
    )

    def __repr__(self):
        return f"<Transaction(date={self.date}, asset={self.asset_name}, type={self.type})>"

class HistorySnapshot(Base):
    __tablename__ = 'history_snapshot'
    
    # Composite PK or just ID? Let's use ID for simplicity, but enforce uniqueness via Index
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    key = Column(String, nullable=False) # e.g., 'Total', 'OwnerA_Stock', etc.
    value = Column(Float, default=0.0)
    
    # Metadata to track when this snapshot was taken
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_hist_date', 'date'),
        Index('idx_hist_key', 'key'),
        # Ensure one value per key per date
        Index('idx_hist_unique', 'date', 'key', unique=True),
    )

class InventorySnapshot(Base):
    __tablename__ = 'inventory_snapshot'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    owner = Column(String)
    account_name = Column(String)
    asset_name = Column(String)
    ticker = Column(String)
    
    qty = Column(Float, default=0.0)
    price = Column(Float, default=0.0) # Avg Price
    amount = Column(Float, default=0.0) # Invested Amount (Book Value)
    
    # Aggregated from transactions
    dividend = Column(Float, default=0.0) # Total dividends
    realized = Column(Float, default=0.0) # Total realized gains
    
    # Extra metadata from GSheet
    currency = Column(String)
    asset_class = Column(String)
    
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_inv_owner', 'owner'),
    )

class SyncMetadata(Base):
    __tablename__ = 'sync_metadata'
    
    key = Column(String, primary_key=True)
    value = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow)
