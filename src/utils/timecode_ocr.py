import cv2
import numpy as np
import pytesseract
import re
from typing import Optional, Tuple, Dict
import logging

logger = logging.getLogger(__name__)

class TimecodeOCR:
    """Extract burned-in timecode from video frames using OCR"""
    
    def __init__(self):
        self.last_timecode_box: Optional[Tuple[int, int, int, int]] = None  # x, y, w, h
        self.timecode_pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2})[.,](\d{3})')
        self.debug_frames = False  # Flag to control frame saving
    
    def get_ocr_config(self) -> str:
        """Get OCR configuration for timecode recognition"""
        config = '--psm 7'  # Treat image as a single line of text
        config += ' -c tessedit_char_whitelist="-0123456789:.\n "'  # Allow only timecode characters
        return config
    
    def preprocess_frame(self, frame: np.ndarray, roi: Optional[Tuple[int, int, int, int]] = None) -> np.ndarray:
        """Preprocess frame for better OCR results"""
        if roi:
            # Extract region of interest if specified
            x, y, w, h = roi
            frame = frame[y:y+h, x:x+w]
            
        # Save original frame/ROI if debug enabled
        if self.debug_frames:
            cv2.imwrite('/tmp/frame_original.png', frame)
        
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self.debug_frames:
            cv2.imwrite('/tmp/frame_gray.png', gray)
        
        # Increase contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        contrast = clahe.apply(gray)
        if self.debug_frames:
            cv2.imwrite('/tmp/frame_contrast.png', contrast)
        
        # Threshold
        _, binary = cv2.threshold(contrast, 127, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if self.debug_frames:
            cv2.imwrite('/tmp/frame_binary.png', binary)
        
        return binary

    def find_timecode_region(self, frame: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Find the region containing the timecode"""
        # If we have a previous location, check if it still contains timecode
        if self.last_timecode_box:
            x, y, w, h = self.last_timecode_box
            roi = self.preprocess_frame(frame, (x, y, w, h))
            text = pytesseract.image_to_string(roi, config=self.get_ocr_config())
            if self.timecode_pattern.search(text):
                return self.last_timecode_box
        
        height, width = frame.shape[:2]
        regions = [
            (0, 0, 680, 45),  # top left
        ]
        
        for region in regions:
            roi = self.preprocess_frame(frame, region)
            text = pytesseract.image_to_string(roi, config=self.get_ocr_config())
            if self.timecode_pattern.search(text):
                self.last_timecode_box = region
                return region
        
        return None

    def extract_timecode(self, frame: np.ndarray) -> Optional[Dict]:
        """Extract timecode from video frame"""
        try:
            # Find region containing timecode
            region = self.find_timecode_region(frame)
            if not region:
                return None
            
            # Preprocess and OCR the region
            roi = self.preprocess_frame(frame, region)
            text = pytesseract.image_to_string(roi, config=self.get_ocr_config())
            
            # Extract timecode using regex
            match = self.timecode_pattern.search(text)
            if match:
                hours, minutes, seconds, ms = map(int, match.groups())
                return {
                    'hours': hours,
                    'minutes': minutes,
                    'seconds': seconds,
                    'milliseconds': ms,
                    'text': f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"
                }
            
            return None

        except Exception as e:
            logger.error(f"Failed to extract timecode: {e}")
            return None 