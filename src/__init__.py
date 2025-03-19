"""
Stream Timestamp Analyzer package
""" 

from .stream_analyzer import StreamAnalyzer
from .analyzers import RTMPStreamAnalyzer, FLVStreamAnalyzer, HLSStreamAnalyzer

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