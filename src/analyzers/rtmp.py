import av
import logging
from multiprocessing import Queue
from ..stream_analyzer import StreamAnalyzer
from ..utils.amf_analyzer import AMFAnalyzer
from ..utils.timing_info import TimingInfo, TimingSource
from typing import Optional

logger = logging.getLogger(__name__)

class RTMPStreamAnalyzer(StreamAnalyzer):
    def __init__(self, url: str):
        super().__init__(url)
        self.amf_analyzer = AMFAnalyzer()

    def process_data_packet(self, packet: av.packet.Packet, video_time_base: float) -> Optional[TimingInfo]:
        """Process RTMP data packet that might contain SEI/ONFI data"""
        try:
            data = bytes(packet)
            # Try to extract onFI data from AMF packet
            onfi_data = self.amf_analyzer.extract_onfi_data(data)
            
            if onfi_data:
                return TimingInfo(
                    stream_url=self.url,
                    timestamp=packet.pts * video_time_base if packet.pts else 0,
                    stream_time=packet.pts * video_time_base if packet.pts else 0,
                    dts=packet.dts,
                    pts=packet.pts,
                    source=TimingSource.AMF_ONFI,
                    extra_data=onfi_data
                )
            
            return None  # Skip non-onFI packets

        except Exception as e:
            logger.error(f"Failed to process data packet: {e}")
            return None

    def analyze_stream(self, queue: Queue):
        try:
            # Open RTMP stream directly with PyAV
            container = av.open(self.url)
            video_stream = None
            data_stream = None
            
            # Find video and data streams
            for stream in container.streams:
                if stream.type == 'video':
                    video_stream = stream
                elif stream.type == 'data':
                    data_stream = stream
            
            if not video_stream:
                raise ValueError("No video stream found")

            # Configure video stream to not drop packets
            video_stream.codec_context.skip_frame = 'NONE'

            # Store video time base for data packet timestamps
            video_time_base = float(video_stream.time_base)

            # Demux both video and data streams if data stream exists
            streams_to_demux = [video_stream]
            if data_stream:
                streams_to_demux.append(data_stream)
                logger.info("Found data stream, will process for SEI/ONFI data")

            for packet in container.demux(*streams_to_demux):
                if packet.stream == video_stream:
                    timing_infos = self.process_video_packet(packet, 'rtmp')
                    for timing_info in timing_infos:
                        queue.put(timing_info)
                elif packet.stream == data_stream:
                    timing_info = self.process_data_packet(packet, video_time_base)
                    if timing_info:
                        queue.put(timing_info)

        except Exception as e:
            logger.error(f"Error processing RTMP stream {self.url}: {str(e)}")
        finally:
            if 'container' in locals():
                container.close() 