from typing import Dict

class NALUnit:
    """Helper class to parse NAL units from AnnexB format"""
    NAL_UNIT_TYPE_SEI = 6

    def __init__(self, data: bytes):
        self.data = data
        # First byte: forbidden_zero_bit(1) | nal_ref_idc(2) | nal_unit_type(5)
        self.forbidden_zero_bit = (data[0] & 0x80) >> 7
        self.nal_ref_idc = (data[0] & 0x60) >> 5
        self.nal_unit_type = data[0] & 0x1F

    @property
    def is_sei(self) -> bool:
        return self.nal_unit_type == self.NAL_UNIT_TYPE_SEI

    def parse_sei(self) -> Dict:
        """Parse SEI message according to H.264/AVC spec"""
        if not self.is_sei or len(self.data) < 2:
            return {}

        result = {'payloads': []}
        pos = 1  # Skip NAL header

        while pos < len(self.data):
            # Parse payload type
            payload_type = 0
            while pos < len(self.data) and self.data[pos] == 0xFF:
                payload_type += 0xFF
                pos += 1
            if pos < len(self.data):
                payload_type += self.data[pos]
                pos += 1

            # Parse payload size
            payload_size = 0
            while pos < len(self.data) and self.data[pos] == 0xFF:
                payload_size += 0xFF
                pos += 1
            if pos < len(self.data):
                payload_size += self.data[pos]
                pos += 1

            # Extract payload data
            if pos + payload_size <= len(self.data):
                payload = self.data[pos:pos + payload_size]
                result['payloads'].append({
                    'type': payload_type,
                    'size': payload_size,
                    'data': payload.hex()
                })
                pos += payload_size
            else:
                break

        return result 