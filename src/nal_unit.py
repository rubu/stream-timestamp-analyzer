from typing import Dict, Optional, Tuple, List
import struct
import logging
from dataclasses import dataclass
from bitstring import BitStream, ReadError

logger = logging.getLogger(__name__)

@dataclass
class ClockTimestamp:
    ct_type: Optional[int] = None
    nuit_field_based_flag: Optional[bool] = None
    counting_type: Optional[int] = None
    full_timestamp_flag: Optional[bool] = None
    discontinuity_flag: Optional[bool] = None
    cnt_dropped_flag: Optional[bool] = None
    n_frames: Optional[int] = None
    seconds_value: Optional[int] = None
    minutes_value: Optional[int] = None
    hours_value: Optional[int] = None
    time_offset: Optional[int] = None

class NALUnit:
    """Helper class to parse NAL units from AnnexB format"""
    NAL_UNIT_TYPE_SEI = 6
    SEI_PAYLOAD_TYPE_PIC_TIMING = 1
    SEI_PAYLOAD_TYPE_USER_DATA_UNREGISTERED = 5

    def __init__(self, data: bytes):
        self.data = data
        # First byte: forbidden_zero_bit(1) | nal_ref_idc(2) | nal_unit_type(5)
        self.forbidden_zero_bit = (data[0] & 0x80) >> 7
        self.nal_ref_idc = (data[0] & 0x60) >> 5
        self.nal_unit_type = data[0] & 0x1F

    @property
    def is_sei(self) -> bool:
        return self.nal_unit_type == self.NAL_UNIT_TYPE_SEI

    def _parse_clock_timestamp(self, bits: BitStream, time_offset_length: int) -> Optional[ClockTimestamp]:
        """Parse a single clock timestamp according to H.264 spec"""
        try:
            ct = ClockTimestamp()
            ct.ct_type = bits.read('uint:2')
            ct.nuit_field_based_flag = bits.read('bool')
            ct.counting_type = bits.read('uint:5')
            ct.full_timestamp_flag = bits.read('bool')
            ct.discontinuity_flag = bits.read('bool')
            ct.cnt_dropped_flag = bits.read('bool')
            ct.n_frames = bits.read('uint:8')

            if ct.full_timestamp_flag:
                ct.seconds_value = bits.read('uint:6')  # 0-59
                ct.minutes_value = bits.read('uint:6')  # 0-59
                ct.hours_value = bits.read('uint:5')    # 0-23
            else:
                seconds_flag = bits.read('bool')
                if seconds_flag:
                    ct.seconds_value = bits.read('uint:6')
                    minutes_flag = bits.read('bool')
                    if minutes_flag:
                        ct.minutes_value = bits.read('uint:6')
                        hours_flag = bits.read('bool')
                        if hours_flag:
                            ct.hours_value = bits.read('uint:5')

            if time_offset_length > 0:
                ct.time_offset = bits.read(f'int:{time_offset_length}')

            return ct
        except ReadError as e:
            logger.error(f"Failed to parse clock timestamp: {e}")
            return None

    def _parse_pic_timing(self, data: bytes, cpb_dpb_delays_present_flag: bool = False,
                         pic_struct_present_flag: bool = True,
                         time_offset_length: int = 24) -> Optional[Dict]:
        """Parse picture timing SEI according to H.264 spec"""
        try:
            bits = BitStream(data)
            result = {'type': 'pic_timing'}

            if cpb_dpb_delays_present_flag:
                # Note: 'v' in u(v) means variable length, would need additional context
                # Using reasonable defaults for now
                result['cpb_removal_delay'] = bits.read('uint:32')
                result['dpb_output_delay'] = bits.read('uint:32')

            if pic_struct_present_flag:
                pic_struct = bits.read('uint:4')
                result['pic_struct'] = pic_struct

                # Determine NumClockTS based on pic_struct
                num_clock_ts = {
                    0: 1,  # (progressive) frame
                    1: 1,  # top field
                    2: 1,  # bottom field
                    3: 2,  # top field, bottom field
                    4: 2,  # bottom field, top field
                    5: 3,  # top field, bottom field, top field
                    6: 3,  # bottom field, top field, bottom field
                    7: 2,  # frame doubling
                    8: 3,  # frame tripling
                }.get(pic_struct, 1)

                clock_timestamps = []
                for i in range(num_clock_ts):
                    clock_timestamp_flag = bits.read('bool')
                    if clock_timestamp_flag:
                        ct = self._parse_clock_timestamp(bits, time_offset_length)
                        if ct:
                            ct_dict = {
                                'ct_type': ct.ct_type,
                                'counting_type': ct.counting_type,
                                'n_frames': ct.n_frames,
                                'time_offset': ct.time_offset
                            }
                            
                            # Add timestamp if available
                            if ct.hours_value is not None:
                                ct_dict.update({
                                    'hours': ct.hours_value,
                                    'minutes': ct.minutes_value or 0,
                                    'seconds': ct.seconds_value or 0,
                                    'text': f"{ct.hours_value:02d}:{ct.minutes_value or 0:02d}:{ct.seconds_value or 0:02d}"
                                })
                                
                            clock_timestamps.append(ct_dict)

                if clock_timestamps:
                    result['clock_timestamps'] = clock_timestamps

            return result

        except Exception as e:
            logger.error(f"Failed to parse picture timing SEI: {e}")
            return None

    def _parse_sei_payload(self, data: bytes, payload_type: int) -> Optional[Dict]:
        """Parse specific SEI payload types"""
        if payload_type == self.SEI_PAYLOAD_TYPE_PIC_TIMING:
            return self._parse_pic_timing(data)
        elif payload_type == self.SEI_PAYLOAD_TYPE_USER_DATA_UNREGISTERED:
            try:
                if len(data) >= 16:  # UUID size
                    uuid = data[0:16].hex()
                    user_data = data[16:].hex() if len(data) > 16 else None
                    return {
                        'type': 'user_data_unregistered',
                        'uuid': uuid,
                        'data': user_data
                    }
            except Exception as e:
                logger.error(f"Failed to parse user data SEI: {e}")
                return None
        return None

    def _read_sei_payload(self, data: bytes, start_pos: int) -> Tuple[Optional[Dict], int]:
        """Read a single SEI payload and return (payload_data, new_position)"""
        pos = start_pos
        
        # Parse payload type
        payload_type = 0
        while pos < len(data) and data[pos] == 0xFF:
            payload_type += 0xFF
            pos += 1
        if pos < len(data):
            payload_type += data[pos]
            pos += 1

        # Parse payload size
        payload_size = 0
        while pos < len(data) and data[pos] == 0xFF:
            payload_size += 0xFF
            pos += 1
        if pos < len(data):
            payload_size += data[pos]
            pos += 1

        # Extract and parse payload data
        if pos + payload_size <= len(data):
            payload_data = data[pos:pos + payload_size]
            parsed_payload = self._parse_sei_payload(payload_data, payload_type)
            if parsed_payload:
                parsed_payload.update({
                    'payload_type': payload_type,
                    'payload_size': payload_size
                })
            return parsed_payload, pos + payload_size
        
        return None, pos

    def parse_sei(self) -> Dict:
        """Parse SEI message according to H.264/AVC spec, focusing on timing info"""
        if not self.is_sei or len(self.data) < 2:
            return {}

        result = {'payloads': []}
        pos = 1  # Skip NAL header

        while pos < len(self.data):
            payload, new_pos = self._read_sei_payload(self.data, pos)
            if payload:
                result['payloads'].append(payload)
            pos = new_pos
            
            # Break if we've reached the end or rbsp_trailing_bits
            if pos >= len(self.data) or self.data[pos] == 0x80:
                break

        return result 