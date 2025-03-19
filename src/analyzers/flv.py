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
                frame_infos = self.process_video_packet(packet, 'flv')
                for frame_info in frame_infos:
                    queue.put(frame_info)

        except Exception as e:
            logger.error(f"Error processing FLV stream {self.url}: {str(e)}")
        finally:
            if 'container' in locals():
                container.close() 