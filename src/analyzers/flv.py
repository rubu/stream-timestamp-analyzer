import av
import logging
from multiprocessing import Queue
from ..stream_analyzer import StreamAnalyzer

logger = logging.getLogger(__name__)

class FLVStreamAnalyzer(StreamAnalyzer):
    FLV_HEADER_SIZE = 9
    PREVIOUS_TAG_SIZE = 4
    TAG_HEADER_SIZE = 11
    TAG_TYPE_VIDEO = 9
    TAG_TYPE_SCRIPT = 18

    def process_data_packet(self, packet: av.packet.Packet, video_time_base: float) -> dict:
        """Process FLV data/script packet that might contain SEI/ONFI data"""
        try:
            data = bytes(packet)
            # FLV script data typically starts with a string length
            # We can parse it here if needed, for now just return the raw data
            return {
                'stream_url': self.url,
                'timestamp': packet.pts * video_time_base if packet.pts else 0,
                'dts': packet.dts,
                'pts': packet.pts,
                'stream_type': 'flv_data',
                'data': data.hex()
            }
        except Exception as e:
            logger.error(f"Failed to process data packet: {e}")
            return None

    def analyze_stream(self, queue: Queue):
        try:
            # Open FLV stream directly with PyAV
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
                    frame_infos = self.process_video_packet(packet, 'flv')
                    for frame_info in frame_infos:
                        queue.put(frame_info)
                elif packet.stream == data_stream:
                    data_info = self.process_data_packet(packet, video_time_base)
                    if data_info:
                        queue.put(data_info)

        except Exception as e:
            logger.error(f"Error processing FLV stream {self.url}: {str(e)}")
        finally:
            if 'container' in locals():
                container.close() 