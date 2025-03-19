from .rtmp import RTMPStreamAnalyzer
from .flv import FLVStreamAnalyzer
from .hls import HLSStreamAnalyzer
from ..stream_analyzer import StreamAnalyzer

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