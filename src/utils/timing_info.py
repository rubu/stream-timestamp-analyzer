from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

class TimingSource(Enum):
    """Source of timing information"""
    AMF_ONFI = "amf_onfi"
    H264_SEI = "h264_sei"
    BURNED_TIMECODE = "burned_timecode"  # OCR'd timecode from video frames

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

    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS.mmm"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds_float = seconds % 60
        seconds_int = int(seconds_float)
        milliseconds = int((seconds_float - seconds_int) * 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds_int:02d}.{milliseconds:03d}"

    def __str__(self) -> str:
        """Concise string representation focusing on timing info"""
        # Build base timing string
        pts_str = f"pts={self.pts}" if self.pts is not None else "pts=None"
        dts_str = f"dts={self.dts}" if self.dts is not None else ""
        timing_str = f"{pts_str} {dts_str}".strip()

        # For ONFI, show st and sd directly from the data
        if self.source == TimingSource.AMF_ONFI:
            if not (self.extra_data and 'data' in self.extra_data):
                return ""
            onfi_data = self.extra_data['data']
            if not isinstance(onfi_data, dict):
                return ""
            # Just display st and sd if they exist
            if 'st' in onfi_data:
                return f"[{self.source.value}] {timing_str} st={onfi_data['st']}"
            return ""

        # For SEI, add wallclock if available
        if self.source == TimingSource.H264_SEI and self.extra_data and 'sei_payload' in self.extra_data:
            payload = self.extra_data['sei_payload']
            if all(k in payload for k in ['hours', 'minutes', 'seconds']):
                ms = int((payload.get('time_offset', 0) / 1000) % 1000) if 'time_offset' in payload else 0
                wallclock = f"{payload['hours']:02d}:{payload['minutes']:02d}:{payload['seconds']:02d}.{ms:03d}"
                if 'n_frames' in payload:
                    wallclock += f"+{payload['n_frames']}f"
                return f"[{self.source.value}] {timing_str} {wallclock}"

        # For burned timecode, show the OCR'd time
        if self.source == TimingSource.BURNED_TIMECODE and self.extra_data and 'timecode' in self.extra_data:
            timecode = self.extra_data['timecode']
            return f"[{self.source.value}] {timing_str} {timecode['text']}"

        # Default output with just timing info
        return f"[{self.source.value}] {timing_str}" 