"""Enum definitions for the application."""
from enum import Enum


class Marketplace(str, Enum):
    """Marketplace options."""
    AMAZON = "AMAZON"
    FLIPKART = "FLIPKART"
    MYNTRA = "MYNTRA"
    JIOMART = "JIOMART"
    MEESHO = "MEESHO"
    AJIO = "AJIO"


class Carrier(str, Enum):
    """Carrier options."""
    DELHIVERY = "DELHIVERY"
    EKART = "EKART"
    SHADOWFAX = "SHADOWFAX"
    BLUEDART = "BLUEDART"
    AMAZON_SHIPPING = "AMAZON_SHIPPING"


class FlowType(str, Enum):
    """Flow type options."""
    DISPATCH = "DISPATCH"
    RETURN = "RETURN"


class Shift(str, Enum):
    """Shift options."""
    MORNING = "MORNING"
    EVENING = "EVENING"
    NIGHT = "NIGHT"


class ManifestStatus(str, Enum):
    """Manifest status options."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class UserRole(str, Enum):
    """User role options."""
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    OPERATOR = "OPERATOR"


class SyncStatus(str, Enum):
    """Sync status for scan events."""
    PENDING = "PENDING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"


class BarcodeType(str, Enum):
    """Barcode type options."""
    QR = "QR"
    CODE128 = "CODE128"
    CODE39 = "CODE39"
    EAN13 = "EAN13"
    UNKNOWN = "UNKNOWN"


class TenantPlan(str, Enum):
    """Tenant subscription plan options."""
    FREE = "FREE"
    BASIC = "BASIC"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"
