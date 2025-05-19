from enum import Enum

class MediaType(Enum):
    IMAGE = 'image'
    VIDEO = 'video'

class DiscountType(Enum):
    PERCENTAGE = 'percentage'
    FIXED = 'fixed'

class AttributeInputType(Enum):
    TEXT = 'text'
    NUMBER = 'number'
    SELECT = 'select'
    MULTISELECT = 'multiselect'
    BOOLEAN = 'boolean'

class BrandRequestStatus(Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'

class PlacementTypeEnum(Enum):
    FEATURED = "featured"
    PROMOTED = "promoted"