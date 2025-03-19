import av
import logging
from multiprocessing import Queue
from ..stream_analyzer import StreamAnalyzer

logger = logging.getLogger(__name__)

class RTMPStreamAnalyzer(StreamAnalyzer):
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
                frame_infos = self.process_video_packet(packet, 'rtmp')
                for frame_info in frame_infos:
                    queue.put(frame_info)

        except Exception as e:
            logger.error(f"Error processing RTMP stream {self.url}: {str(e)}")
        finally:
            if 'container' in locals():
                container.close() 