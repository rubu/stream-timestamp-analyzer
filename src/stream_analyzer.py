import abc
import av
import logging
import time
from datetime import datetime
from multiprocessing import Queue, get_context, Value
import m3u8
from typing import Optional, Dict, Iterator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

class NALUnit:
    """Helper class to parse NAL units from AnnexB format"""
    NAL_UNIT_TYPE_SEI = 6

    def __init__(self, data: bytes):
        self.data = data
        # First byte: forbidden_zero_bit(1) | nal_ref_idc(2) | nal_unit_type(5)
        self.forbidden_zero_bit = (data[0] & 0x80) >> 7
        self.nal_ref_idc = (data[0] & 0x60) >> 5
        self.nal_unit_type = data[0] & 0x1F

    @property
    def is_sei(self) -> bool:
        return self.nal_unit_type == self.NAL_UNIT_TYPE_SEI

    def parse_sei(self) -> Dict:
        """Parse SEI message according to H.264/AVC spec"""
        if not self.is_sei or len(self.data) < 2:
            return {}

        result = {'payloads': []}
        pos = 1  # Skip NAL header

        while pos < len(self.data):
            # Parse payload type
            payload_type = 0
            while pos < len(self.data) and self.data[pos] == 0xFF:
                payload_type += 0xFF
                pos += 1
            if pos < len(self.data):
                payload_type += self.data[pos]
                pos += 1

            # Parse payload size
            payload_size = 0
            while pos < len(self.data) and self.data[pos] == 0xFF:
                payload_size += 0xFF
                pos += 1
            if pos < len(self.data):
                payload_size += self.data[pos]
                pos += 1

            # Extract payload data
            if pos + payload_size <= len(self.data):
                payload = self.data[pos:pos + payload_size]
                result['payloads'].append({
                    'type': payload_type,
                    'size': payload_size,
                    'data': payload.hex()
                })
                pos += payload_size
            else:
                break

        return result

class RTMPStreamAnalyzer(StreamAnalyzer):
    def extract_nals_from_packet(self, packet: av.packet.Packet) -> Iterator[NALUnit]:
        """Extract NAL units from AVC/H.264 packet"""
        data = packet.to_bytes()
        
        # Look for NAL unit start codes (0x000001 or 0x00000001)
        i = 0
        while i < len(data):
            # Find start code
            start = data.find(b'\x00\x00\x01', i)
            if start == -1:
                break
            
            # Skip start code
            start += 3
            
            # Find next start code
            next_start = data.find(b'\x00\x00\x01', start)
            if next_start == -1:
                # Last NAL unit in packet
                nal_data = data[start:]
                if nal_data:
                    yield NALUnit(nal_data)
                break
            else:
                nal_data = data[start:next_start]
                if nal_data:
                    yield NALUnit(nal_data)
                i = next_start

    def analyze_stream(self, queue: Queue):
        try:
            # Open RTMP stream directly with PyAV
            container = av.open(self.url)
            video_stream = None
            
            # Find video stream
            for stream in container.streams:
                if stream.type == 'video':
                    video_stream = stream
                    break
            
            if not video_stream:
                raise ValueError("No video stream found")

            for packet in container.demux(video_stream):
                if not packet.dts:
                    continue

                current_time = datetime.now().timestamp()
                stream_time = float(packet.dts * packet.time_base)
                
                # Process NAL units in packet
                for nal_unit in self.extract_nals_from_packet(packet):
                    if nal_unit.is_sei:
                        sei_data = nal_unit.parse_sei()
                        
                        frame_info = {
                            'stream_url': self.url,
                            'timestamp': current_time,
                            'stream_time': stream_time,
                            'dts': packet.dts,
                            'pts': packet.pts,
                            'duration': packet.duration,
                            'stream_type': 'rtmp',
                            'sei_data': sei_data
                        }
                        
                        queue.put(frame_info)

        except Exception as e:
            logger.error(f"Error processing RTMP stream {self.url}: {str(e)}")
        finally:
            if 'container' in locals():
                container.close()

class FLVStreamAnalyzer(StreamAnalyzer):
    FLV_HEADER_SIZE = 9
    PREVIOUS_TAG_SIZE = 4
    TAG_HEADER_SIZE = 11
    TAG_TYPE_VIDEO = 9

    def extract_nals_from_packet(self, packet: av.packet.Packet) -> Iterator[NALUnit]:
        """Extract NAL units from AVC/H.264 packet"""
        data = packet.to_bytes()
        
        # Look for NAL unit start codes (0x000001 or 0x00000001)
        i = 0
        while i < len(data):
            # Find start code
            start = data.find(b'\x00\x00\x01', i)
            if start == -1:
                break
            
            # Skip start code
            start += 3
            
            # Find next start code
            next_start = data.find(b'\x00\x00\x01', start)
            if next_start == -1:
                # Last NAL unit in packet
                nal_data = data[start:]
                if nal_data:
                    yield NALUnit(nal_data)
                break
            else:
                nal_data = data[start:next_start]
                if nal_data:
                    yield NALUnit(nal_data)
                i = next_start

    def analyze_stream(self, queue: Queue):
        try:
            # Open FLV stream directly with PyAV
            container = av.open(self.url)
            video_stream = None
            
            # Find video stream
            for stream in container.streams:
                if stream.type == 'video':
                    video_stream = stream
                    break
            
            if not video_stream:
                raise ValueError("No video stream found")

            # Configure video stream to not drop packets
            video_stream.codec_context.skip_frame = 'NONE'

            for packet in container.demux(video_stream):
                if not packet.dts:
                    continue

                current_time = datetime.now().timestamp()
                stream_time = float(packet.dts * packet.time_base)
                
                # Process NAL units in packet
                for nal_unit in self.extract_nals_from_packet(packet):
                    if nal_unit.is_sei:
                        sei_data = nal_unit.parse_sei()
                        
                        frame_info = {
                            'stream_url': self.url,
                            'timestamp': current_time,
                            'stream_time': stream_time,
                            'dts': packet.dts,
                            'pts': packet.pts,
                            'duration': packet.duration,
                            'stream_type': 'flv',
                            'sei_data': sei_data
                        }
                        
                        queue.put(frame_info)

        except Exception as e:
            logger.error(f"Error processing FLV stream {self.url}: {str(e)}")
        finally:
            if 'container' in locals():
                container.close()

class HLSStreamAnalyzer(StreamAnalyzer):
    def analyze_segment(self, segment_url: str, segment_info: Dict) -> Iterator[Dict]:
        """Analyze a single HLS segment using PyAV"""
        try:
            container = av.open(segment_url)
            video_stream = next((s for s in container.streams if s.type == 'video'), None)
            
            if not video_stream:
                return

            for packet in container.demux(video_stream):
                if not packet.dts:
                    continue

                current_time = datetime.now().timestamp()
                stream_time = float(packet.dts * packet.time_base)

                # Process NAL units in packet
                for nal_unit in self.extract_nals_from_packet(packet):
                    if nal_unit.is_sei:
                        sei_data = nal_unit.parse_sei()
                        
                        frame_info = {
                            'stream_url': self.url,
                            'timestamp': current_time,
                            'stream_time': stream_time,
                            'dts': packet.dts,
                            'pts': packet.pts,
                            'duration': packet.duration,
                            'stream_type': 'hls',
                            'segment_info': segment_info,
                            'sei_data': sei_data
                        }
                        
                        yield frame_info

        except Exception as e:
            logger.error(f"Error processing HLS segment {segment_url}: {str(e)}")
        finally:
            if 'container' in locals():
                container.close()

    def extract_nals_from_packet(self, packet: av.packet.Packet) -> Iterator[NALUnit]:
        """Extract NAL units from AVC/H.264 packet"""
        data = packet.to_bytes()
        
        # Look for NAL unit start codes
        i = 0
        while i < len(data):
            start = data.find(b'\x00\x00\x01', i)
            if start == -1:
                break
            
            start += 3
            next_start = data.find(b'\x00\x00\x01', start)
            
            if next_start == -1:
                nal_data = data[start:]
                if nal_data:
                    yield NALUnit(nal_data)
                break
            else:
                nal_data = data[start:next_start]
                if nal_data:
                    yield NALUnit(nal_data)
                i = next_start

    def analyze_stream(self, queue: Queue):
        try:
            while True:
                # Get the M3U8 playlist
                playlist = m3u8.load(self.url)
                
                if playlist.is_endlist:
                    logger.info(f"HLS stream {self.url} has ended")
                    break

                for segment in playlist.segments:
                    segment_info = {
                        'duration': segment.duration,
                        'uri': segment.uri,
                        'program_date_time': segment.program_date_time.timestamp() if segment.program_date_time else None
                    }

                    # Analyze segment with PyAV
                    for frame_info in self.analyze_segment(segment.uri, segment_info):
                        queue.put(frame_info)
                
                time.sleep(playlist.target_duration or 1)

        except Exception as e:
            logger.error(f"Error processing HLS stream {self.url}: {str(e)}")

def create_analyzer(url: str) -> StreamAnalyzer:
    """Factory function to create appropriate stream analyzer based on URL"""
    if url.startswith('rtmp://'):
        return RTMPStreamAnalyzer(url)
    elif url.endswith('.flv') or ('flv?' in url and url.startswith('http')):
        return FLVStreamAnalyzer(url)
    elif '.m3u8' in url or url.startswith('http'):  # Simple HLS detection
        return HLSStreamAnalyzer(url)
    else:
        raise ValueError(f"Unsupported stream type for URL: {url}") 