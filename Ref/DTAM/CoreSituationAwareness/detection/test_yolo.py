"""
Test YOLO model loading
"""

import os
import sys

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    print("Testing YOLO model loading...")
    
    # Test importing ultralytics
    from ultralytics import YOLO
    print("✓ Ultralytics imported successfully")
    
    # Get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(current_dir, "yolo11n.pt")
    
    print(f"Looking for model at: {model_path}")
    print(f"Model exists: {os.path.exists(model_path)}")
    
    if os.path.exists(model_path):
        print("Loading YOLO model...")
        model = YOLO(model_path)
        print("✓ YOLO model loaded successfully!")
        
        # Test with a dummy frame
        import numpy as np
        test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        print("Testing detection on dummy frame...")
        
        results = model(test_frame, verbose=False)
        print(f"✓ Detection test successful! Found {len(results)} result(s)")
        
    else:
        print("❌ YOLO model file not found")
        print("Available files in detection directory:")
        for file in os.listdir(current_dir):
            print(f"  - {file}")
            
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Install ultralytics with: pip install ultralytics")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("Make sure the YOLO model file is accessible")