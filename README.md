# Stream Timestamp Analyzer

A Python tool for analyzing timing information from various types of media streams (RTMP, HLS, etc.).

## Features

- Support for multiple stream types (RTMP, HLS)
- Concurrent stream analysis using multiprocessing
- Extensible architecture for adding new stream types
- Real-time PTS (Presentation Timestamp) extraction
- Timestamp correlation between streams

## Requirements

- Python 3.7+
- FFmpeg installed on your system

## Installation

1. Clone this repository
2. Install the required Python packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Modify the stream URLs in `src/main.py`:
```python
streams = [
    "rtmp://your-rtmp-server/live/stream1",
    "http://your-hls-server/stream/playlist.m3u8"
]
```

2. Run the analyzer:
```bash
python src/main.py
```

The program will create a separate process for each stream and continuously log timing information.

## Adding New Stream Types

1. Create a new class that inherits from `StreamAnalyzer`
2. Implement the `analyze_stream` method
3. Add detection logic to the `create_analyzer` factory function

## Output Format

The timing information is output in the following format:
```python
{
    'stream_url': 'url of the stream',
    'timestamp': 'current system timestamp',
    'pts': 'presentation timestamp',
    'stream_type': 'type of stream (rtmp/hls)',
    # Additional stream-specific information
}
```

## License

MIT 