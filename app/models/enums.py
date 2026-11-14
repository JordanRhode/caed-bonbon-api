import enum


class ShellType(str, enum.Enum):
    DARK = "dark"
    MILK = "milk"
    WHITE = "white"
    RUBY = "ruby"


class FlavorCategory(str, enum.Enum):
    SIGNATURE = "signature"
    SEASONAL = "seasonal"
    ARCHIVED = "archived"


class ImageProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
