# Stream Timestamp Analyzer

A Python tool for analyzing video streams (RTMP, HLS, FLV) and extracting timing information from H.264 SEI messages and AMF metadata.

## Features

- Support for multiple stream types:
  - RTMP streams
  - HLS streams (m3u8)
  - FLV over HTTP
- Extracts timing information from:
  - H.264 SEI messages in video frames
  - AMF onFI messages in data streams
- Multi-process architecture for parallel stream analysis
- Debug mode support with remote debugging capabilities
- Structured timing information output with source tracking

## Requirements

- Python 3.8+
- PyAV (for video stream handling)
- m3u8 (for HLS playlist parsing)
- debugpy (for remote debugging support)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/stream-timestamp-analyzer.git
cd stream-timestamp-analyzer
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

Run the analyzer with one or more stream URLs:

```bash
python -m src.main rtmp://example.com/live/stream1 http://example.com/stream2.flv
```

### Debug Mode

Run with debugging enabled:

```bash
python -m src.main --debug rtmp://example.com/live/stream
```

Each analyzer process will wait for a debugger to attach on a unique port starting from 5678.

### VS Code Debugging

1. Create a `.vscode/launch.json` configuration:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Attach to Stream Analyzer",
            "type": "python",
            "request": "attach",
            "connect": {
                "host": "localhost",
                "port": 5678
            },
            "pathMappings": [
                {
                    "localRoot": "${workspaceFolder}",
                    "remoteRoot": "."
                }
            ],
            "justMyCode": false
        }
    ]
}
```

2. Run the script with `--debug`
3. Use the VS Code debugger to attach to the process

## Architecture

The analyzer uses a multi-process architecture where each stream is analyzed in a separate process:

- `StreamManager`: Manages multiple stream analyzers
- `StreamAnalyzer`: Base class for stream analysis
  - `RTMPStreamAnalyzer`: Handles RTMP streams
  - `HLSStreamAnalyzer`: Handles HLS streams
  - `FLVStreamAnalyzer`: Handles FLV streams

### Timing Information

Timing data is extracted from two sources:
1. H.264 SEI messages in video frames
2. AMF onFI messages in data streams

The `TimingInfo` class provides a structured format for timing data:
```python
@dataclass
class TimingInfo:
    stream_url: str
    timestamp: float    # System timestamp
    stream_time: float  # Stream time in seconds
    pts: Optional[int]  # Presentation timestamp
    dts: Optional[int]  # Decoding timestamp
    duration: Optional[int]
    source: TimingSource
    extra_data: Optional[Dict[str, Any]]
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

[Your License Here] 