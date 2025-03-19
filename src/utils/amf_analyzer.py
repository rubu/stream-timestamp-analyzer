import logging
import struct
from typing import Optional, Dict, Tuple, Any

logger = logging.getLogger(__name__)

class AMFAnalyzer:
    """Helper class to parse AMF data and extract onFI messages from RTMP and FLV streams"""
    
    # AMF0 type markers
    AMF0_NUMBER = 0x00
    AMF0_BOOLEAN = 0x01
    AMF0_STRING = 0x02
    AMF0_OBJECT = 0x03
    AMF0_NULL = 0x05
    AMF0_UNDEFINED = 0x06
    AMF0_ECMA_ARRAY = 0x08
    AMF0_OBJECT_END = 0x09
    AMF0_STRICT_ARRAY = 0x0A
    AMF0_DATE = 0x0B
    AMF0_LONG_STRING = 0x0C

    @staticmethod
    def read_u8(data: bytes, offset: int) -> Tuple[int, int]:
        """Read unsigned 8-bit integer"""
        return data[offset], offset + 1

    @staticmethod
    def read_u16(data: bytes, offset: int) -> Tuple[int, int]:
        """Read unsigned 16-bit integer"""
        return struct.unpack('>H', data[offset:offset+2])[0], offset + 2

    @staticmethod
    def read_u32(data: bytes, offset: int) -> Tuple[int, int]:
        """Read unsigned 32-bit integer"""
        return struct.unpack('>I', data[offset:offset+4])[0], offset + 4

    @staticmethod
    def read_double(data: bytes, offset: int) -> Tuple[float, int]:
        """Read 64-bit double"""
        return struct.unpack('>d', data[offset:offset+8])[0], offset + 8

    def read_string(self, data: bytes, offset: int, is_long: bool = False) -> Tuple[str, int]:
        """Read AMF string (short or long)"""
        if is_long:
            length, offset = self.read_u32(data, offset)
        else:
            length, offset = self.read_u16(data, offset)
        return data[offset:offset+length].decode('utf-8'), offset + length

    def parse_ecma_array(self, data: bytes, offset: int) -> Tuple[Dict[str, Any], int]:
        """Parse an AMF0 ECMA array (associative array / object with length prefix)"""
        # Skip array length (we'll read until object end marker)
        array_length, offset = self.read_u32(data, offset)
        
        # Parse as regular object
        obj = {}
        while True:
            # Read property name
            key, offset = self.read_string(data, offset)
            
            # Check for object end marker
            if not key and data[offset] == self.AMF0_OBJECT_END:
                return obj, offset + 1
                
            # Parse and store property value
            value, offset = self.parse_amf0_value(data, offset)
            obj[key] = value
        
        return obj, offset

    def parse_amf0_value(self, data: bytes, offset: int) -> Tuple[Any, int]:
        """Parse an AMF0 value based on its type marker"""
        type_marker, offset = self.read_u8(data, offset)

        if type_marker == self.AMF0_NUMBER:
            return self.read_double(data, offset)
        elif type_marker == self.AMF0_BOOLEAN:
            val, offset = self.read_u8(data, offset)
            return bool(val), offset
        elif type_marker == self.AMF0_STRING:
            return self.read_string(data, offset)
        elif type_marker == self.AMF0_LONG_STRING:
            return self.read_string(data, offset, True)
        elif type_marker == self.AMF0_OBJECT:
            obj = {}
            while True:
                key, offset = self.read_string(data, offset)
                if not key and data[offset] == self.AMF0_OBJECT_END:
                    return obj, offset + 1
                value, offset = self.parse_amf0_value(data, offset)
                obj[key] = value
            return obj, offset
        elif type_marker == self.AMF0_ECMA_ARRAY:
            return self.parse_ecma_array(data, offset)
        elif type_marker in (self.AMF0_NULL, self.AMF0_UNDEFINED):
            return None, offset
        else:
            logger.warning(f"Unsupported AMF0 type marker: 0x{type_marker:02x}")
            return None, offset

    def extract_onfi_data(self, data: bytes) -> Optional[Dict]:
        """
        Extract onFI message from AMF data if present.
        Returns None if no onFI message is found or if parsing fails.
        """
        try:
            offset = 0
            while offset < len(data):
                # Try to find onFI command name
                type_marker, new_offset = self.read_u8(data, offset)
                if type_marker == self.AMF0_STRING:
                    command, new_offset = self.read_string(data, new_offset)
                    if command == 'onFI':
                        # Parse the onFI data object
                        onfi_data, _ = self.parse_amf0_value(data, new_offset)
                        return {
                            'type': 'onfi',
                            'data': onfi_data
                        }
                    offset = new_offset
                else:
                    # Skip other types
                    _, offset = self.parse_amf0_value(data, offset)

        except Exception as e:
            logger.error(f"Failed to parse AMF data: {e}")
            return None

        return None 