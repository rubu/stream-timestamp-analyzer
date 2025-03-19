from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any

class TimingSource(Enum):
    """Source of timing information"""
    AMF_ONFI = "amf_onfi"
    H264_SEI = "h264_sei"

@dataclass
class TimingInfo:
    """Structured timing information from stream"""
    stream_url: str
    timestamp: float  # System timestamp when packet was processed
    stream_time: float  # Stream time in seconds
    pts: Optional[int] = None  # Presentation timestamp
    dts: Optional[int] = None  # Decoding timestamp
    duration: Optional[int] = None  # Packet duration
    source: TimingSource = TimingSource.H264_SEI  # Default to H264_SEI
    extra_data: Optional[Dict[str, Any]] = None  # For source-specific data (SEI payload, onFI data) 