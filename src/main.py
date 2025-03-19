import logging
import sys
import time
from typing import List, Dict
from multiprocessing import Queue
from .stream_analyzer import create_analyzer, StreamAnalyzer
import argparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StreamManager:
    """Manage multiple stream analyzers"""
    
    def __init__(self):
        self.analyzers: Dict[str, StreamAnalyzer] = {}
        self.queues: Dict[str, Queue] = {}

    def add_stream(self, url: str, ocr_enabled: bool = False):
        """Add a new stream to analyze"""
        try:
            # Create analyzer for the stream
            analyzer = create_analyzer(url, ocr_enabled)
            
            # Start the analyzer and get its queue
            queue = analyzer.start()
            
            # Store analyzer and queue
            self.analyzers[url] = analyzer
            self.queues[url] = queue
            
            logger.info(f"Added stream: {url}")
        except Exception as e:
            logger.error(f"Failed to add stream {url}: {e}")

    def remove_stream(self, url: str):
        """Stop analyzing a stream"""
        if url in self.analyzers:
            self.analyzers[url].stop()
            del self.analyzers[url]
            del self.queues[url]
            logger.info(f"Stopped analyzing stream: {url}")

    def process_timing_info(self):
        """Process timing information from all streams"""
        while True:
            for url, queue in self.queues.items():
                try:
                    # Non-blocking queue check
                    while not queue.empty():
                        timing_info = queue.get_nowait()
                        logger.info(f"Stream {url}: {timing_info}")
                except Exception as e:
                    logger.error(f"Error processing queue for {url}: {str(e)}")
            
            time.sleep(0.1)  # Prevent CPU overload

    def stop_all(self):
        """Stop all analyzers"""
        for analyzer in self.analyzers.values():
            analyzer.stop()
        self.analyzers.clear()
        self.queues.clear()

def main():
    parser = argparse.ArgumentParser(description='Stream timestamp analyzer')
    parser.add_argument('url', help='Stream URL to analyze')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--ocr', action='store_true', help='Enable OCR for burned-in timecodes')
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    manager = StreamManager()
    manager.add_stream(args.url, ocr_enabled=args.ocr)

    try:
        # Process timing information from all streams
        manager.process_timing_info()
    except KeyboardInterrupt:
        manager.stop_all()

if __name__ == '__main__':
    main() 