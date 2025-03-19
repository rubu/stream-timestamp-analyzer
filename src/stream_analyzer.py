import abc
import av
import logging
import time
from datetime import datetime
from multiprocessing import Queue, get_context, Value
from typing import Optional, Dict, Iterator, List
from .nal_unit import NALUnit
from .utils.timing_info import TimingInfo, TimingSource

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_analyzer(url: str) -> 'StreamAnalyzer':
    """Create appropriate analyzer based on stream URL"""
    # Import analyzers here to avoid circular imports
    from .analyzers.rtmp import RTMPStreamAnalyzer
    from .analyzers.flv import FLVStreamAnalyzer
    from .analyzers.hls import HLSStreamAnalyzer
    
    if url.startswith('rtmp://'):
        return RTMPStreamAnalyzer(url)
    elif url.endswith('.flv') or ('flv?' in url and url.startswith('http')):
        return FLVStreamAnalyzer(url)
    elif url.endswith('.m3u8') or ('m3u8?' in url and url.startswith('http')):
        return HLSStreamAnalyzer(url)
    else:
        raise ValueError(f"Unsupported stream URL format: {url}")

class StreamAnalyzer(abc.ABC):
    def __init__(self, url: str):
        self.url = url
        self.process = None
        self.queue = None
        self.mp_context = get_context('spawn')

    @abc.abstractmethod
    def analyze_stream(self, queue: Queue):
        """Abstract method to analyze stream and send timing info to queue"""
        pass

    def _run_process(self, queue: Queue):
        """Process entry point with optional debugging"""
        self.analyze_stream(queue)

    def start(self):
        """Start the analysis process"""
        self.queue = self.mp_context.Queue()
        self.process = self.mp_context.Process(target=self._run_process, args=(self.queue,))
        self.process.start()
        return self.queue

    def stop(self):
        """Stop the analysis process"""
        if self.process and self.process.is_alive():
            self.process.terminate()
            self.process.join()

    def extract_nals_from_packet(self, packet: av.packet.Packet) -> Iterator[NALUnit]:
        """Extract NAL units from AVC/H.264 packet - common for all analyzers"""
        # Get raw packet data - we need to handle this differently based on the packet format
        try:
            # Try to get AVCC format data (length-prefixed NAL units)
            data = bytes(packet)
            pos = 0
            while pos < len(data):
                # AVCC format: 4-byte length prefix followed by NAL unit
                if pos + 4 > len(data):
                    break
                nal_length = int.from_bytes(data[pos:pos+4], byteorder='big')
                pos += 4
                if pos + nal_length > len(data):
                    break
                nal_data = data[pos:pos+nal_length]
                if nal_data:
                    yield NALUnit(nal_data)
                pos += nal_length
        except Exception as e:
            # Fallback to Annex-B format (start code prefixed)
            try:
                data = bytes(packet)
                i = 0
                while i < len(data):
                    # Look for start code
                    start = data.find(b'\x00\x00\x01', i)
                    if start == -1:
                        # Try 4-byte start code
                        start = data.find(b'\x00\x00\x00\x01', i)
                        if start == -1:
                            break
                        start += 4
                    else:
                        start += 3

                    # Find next start code
                    next_start = data.find(b'\x00\x00\x01', start)
                    if next_start == -1:
                        next_start = data.find(b'\x00\x00\x00\x01', start)

                    if next_start == -1:
                        # Last NAL unit
                        nal_data = data[start:]
                        if nal_data:
                            yield NALUnit(nal_data)
                        break
                    else:
                        nal_data = data[start:next_start]
                        if nal_data:
                            yield NALUnit(nal_data)
                        i = next_start
            except Exception as e2:
                logger.error(f"Failed to extract NAL units: {e2}")

    def process_video_packet(self, packet: av.packet.Packet, stream_type: str) -> List[TimingInfo]:
        """Common video packet processing for all analyzers"""
        if not packet.dts:
            return []

        results = []
        current_time = datetime.now().timestamp()
        stream_time = float(packet.dts * packet.time_base)

        # Process NAL units in packet
        for nal_unit in self.extract_nals_from_packet(packet):
            if nal_unit.is_sei:
                sei_data = nal_unit.parse_sei()
                
                # Extract timing info from SEI payloads
                for payload in sei_data.get('payloads', []):
                    if payload.get('type') == 'pic_timing' and 'clock_timestamps' in payload:
                        # Get first clock timestamp that has timing data
                        for cts in payload['clock_timestamps']:
                            if 'hours' in cts:
                                timing_info = TimingInfo(
                                    stream_url=self.url,
                                    timestamp=current_time,
                                    stream_time=stream_time,
                                    dts=packet.dts,
                                    pts=packet.pts,
                                    duration=packet.duration,
                                    source=TimingSource.H264_SEI,
                                    extra_data={'sei_payload': cts}
                                )
                                results.append(timing_info)
                                break

        return results
