import av
import logging
import time
import m3u8
from multiprocessing import Queue
from typing import Dict, Iterator
from ..stream_analyzer import StreamAnalyzer

logger = logging.getLogger(__name__)

class HLSStreamAnalyzer(StreamAnalyzer):
    def analyze_segment(self, segment_url: str, segment_info: Dict) -> Iterator[Dict]:
        """Analyze a single HLS segment using PyAV"""
        try:
            container = av.open(segment_url)
            video_stream = next((s for s in container.streams if s.type == 'video'), None)
            
            if not video_stream:
                return

            for packet in container.demux(video_stream):
                frame_infos = self.process_video_packet(
                    packet, 'hls', {'segment_info': segment_info}
                )
                for frame_info in frame_infos:
                    yield frame_info

        except Exception as e:
            logger.error(f"Error processing HLS segment {segment_url}: {str(e)}")
        finally:
            if 'container' in locals():
                container.close()

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