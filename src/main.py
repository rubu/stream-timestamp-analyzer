import logging
import sys
import time
from typing import List, Dict
from stream_analyzer import create_analyzer, StreamAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StreamManager:
    def __init__(self, debug: bool = False):
        self.analyzers: Dict[str, StreamAnalyzer] = {}
        self.queues = {}
        self.debug = debug

    def add_stream(self, url: str):
        """Add a new stream to analyze"""
        try:
            analyzer = create_analyzer(url)
            analyzer.debug = self.debug  # Enable debugging if manager is in debug mode
            queue = analyzer.start()
            self.analyzers[url] = analyzer
            self.queues[url] = queue
            logger.info(f"Started analyzing stream: {url}")
        except Exception as e:
            logger.error(f"Failed to add stream {url}: {str(e)}")

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
                        logger.info(f"Stream timing info: {timing_info}")
                except Exception as e:
                    logger.error(f"Error processing queue for {url}: {str(e)}")
            
            time.sleep(0.1)  # Prevent CPU overload

    def stop_all(self):
        """Stop all stream analyzers"""
        for url in list(self.analyzers.keys()):
            self.remove_stream(url)

def main():
    # Check if debug mode is enabled
    debug_mode = '--debug' in sys.argv
    if debug_mode:
        sys.argv.remove('--debug')
    
    manager = StreamManager(debug=debug_mode)
    
    # Add your stream URLs here
    streams = sys.argv[1:]  # Take all command line arguments after the script name
    
    try:
        # Add all streams
        for stream_url in streams:
            manager.add_stream(stream_url)
        
        # Process timing information
        manager.process_timing_info()
    
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        manager.stop_all()

if __name__ == "__main__":
    main() 