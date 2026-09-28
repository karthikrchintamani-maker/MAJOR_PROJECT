import os
import sys
import yaml
import time
import argparse
import datetime
import urllib.request
import cv2
import numpy as np
import pandas as pd
import torch
from ultralytics import YOLO
import onnxruntime as ort
import queue
import threading

class RoadEyePipeline:
    def __init__(self, calibration_path, classes_path, inference_path, obd_csv_path=None):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Initializing RoadEye Pipeline on device: {self.device}")
        
        # Load YAML configs
        self.calib_config = self._load_yaml(calibration_path)
        self.classes_config = self._load_yaml(classes_path)
        self.inf_config = self._load_yaml(inference_path)
        
        # Set paths resolving package locations
        self.base_path = self._detect_base_path()
        print(f"Resolved base path: {self.base_path}")
        
        # Initialize models
        self._init_models()
        
        # Load OBD2 Telemetry data if provided
        self.telemetry_df = None
        if obd_csv_path and os.path.exists(obd_csv_path):
            self._load_telemetry(obd_csv_path)
        elif obd_csv_path:
            print(f"Warning: Telemetry CSV file not found at: {obd_csv_path}")

    def _detect_base_path(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if os.path.exists(os.path.join(script_dir, "models")):
            return script_dir
        if os.path.exists(os.path.join(".", "models")):
            return os.path.abspath(".")
        if os.path.exists(os.path.join(".", "RoadEye")):
            return os.path.abspath(os.path.join(".", "RoadEye"))
        return script_dir

    def _load_yaml(self, path):
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    def _init_models(self):
        # Resolve weights paths dynamically
        det_pt = os.path.join(self.base_path, "models", "detection", "yolo26n_indian_road_best.pt")
        seg_pt = os.path.join(self.base_path, "models", "segmentation", "yolo11m-road-seg.pt")
        pot_pt = os.path.join(self.base_path, "models", "pothole", "pothole-detection-yolov8.pt")
        depth_onnx = os.path.join(self.base_path, "models", "depth", "unet_depthwise_nano_best.onnx")
        
        print("Loading YOLO models...")
        self.det_model = YOLO(det_pt).to(self.device)
        self.seg_model = YOLO(seg_pt).to(self.device)
        self.pot_model = YOLO(pot_pt).to(self.device)
        
        print("Loading Depth ONNX Runtime session...")
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if self.device == 'cuda' else ['CPUExecutionProvider']
        
        # Optimize ONNX runtime options for Raspberry Pi 5 quad-core ARM layout
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 4
        sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        self.depth_session = ort.InferenceSession(depth_onnx, sess_options=sess_options, providers=providers)
        
        # Cache class names and configurations
        self.det_names = self.classes_config['detection']['names']
        self.seg_names = self.classes_config['segmentation']['names']
        self.pot_names = self.classes_config['pothole']['names']
        
        # Depth scale and shift settings
        self.depth_scale = self.calib_config['depth_model_scale']['scale']
        self.depth_shift = self.calib_config['depth_model_scale']['shift']
        
        # Camera calibration intrinsics
        self.camera_matrix = None
        self.dist_coeffs = None
        cam_cfg = self.calib_config.get('camera', {})
        fx, fy = cam_cfg.get('fx', 0.0), cam_cfg.get('fy', 0.0)
        if fx > 0 and fy > 0:
            self.camera_matrix = np.array([
                [fx, 0, cam_cfg.get('cx', 0.0)],
                [0, fy, cam_cfg.get('cy', 0.0)],
                [0, 0, 1]
            ], dtype=np.float32)
            self.dist_coeffs = np.array(cam_cfg.get('distortion_coefficients', [0.0]*5), dtype=np.float32)
            print("Loaded camera calibration matrix.")
        else:
            print("No valid camera calibration found. Skipping frame undistortion.")

    def _load_telemetry(self, csv_path):
        print(f"Loading OBD2 telemetry from: {csv_path}")
        self.telemetry_df = pd.read_csv(csv_path)
        self.telemetry_df['datetime'] = pd.to_datetime(self.telemetry_df['timestamp'])
        print(f"Loaded {len(self.telemetry_df)} telemetry entries.")

    def get_telemetry_at_time(self, query_time):
        if self.telemetry_df is None:
            return None
        # Find closest timestamp row
        closest_idx = (self.telemetry_df['datetime'] - query_time).abs().idxmin()
        return self.telemetry_df.loc[closest_idx]

    def undistort_frame(self, frame):
        if self.camera_matrix is not None and self.dist_coeffs is not None:
            return cv2.undistort(frame, self.camera_matrix, self.dist_coeffs)
        return frame

    def run_depth_inference(self, frame):
        # Preprocess: resize to a dynamic multiple of 32 for stability
        h, w = frame.shape[:2]
        depth_h = (h // 32) * 32
        depth_w = (w // 32) * 32
        
        blob = cv2.resize(frame, (depth_w, depth_h))
        blob = blob.astype(np.float32) / 255.0
        # Transpose to NCHW
        blob = np.transpose(blob, (2, 0, 1))
        blob = np.expand_dims(blob, axis=0)
        
        # Run inference
        input_name = self.depth_session.get_inputs()[0].name
        output_name = self.depth_session.get_outputs()[0].name
        raw_depth = self.depth_session.run([output_name], {input_name: blob})[0]
        
        # Postprocess: scale + shift + resize back
        depth_map = raw_depth[0, 0] * self.depth_scale + self.depth_shift
        depth_resized = cv2.resize(depth_map, (w, h))
        return depth_resized

    def process_frame(self, frame, telemetry_data=None):
        # 1. Camera Undistortion
        undistorted = self.undistort_frame(frame)
        overlay_frame = undistorted.copy()
        
        # 2. Road Segmentation Model
        seg_results = self.seg_model(undistorted, verbose=False)[0]
        if seg_results.masks is not None:
            # Create overlay road layer
            mask_layer = np.zeros_like(undistorted)
            for seg in seg_results.masks.xy:
                pts = seg.astype(np.int32)
                cv2.fillPoly(mask_layer, [pts], (0, 180, 0)) # Green overlay for road
            # Overlay semi-transparent mask
            cv2.addWeighted(mask_layer, 0.4, overlay_frame, 0.6, 0, overlay_frame)
            
        # 3. Object Detection Model
        det_results = self.det_model(undistorted, verbose=False)[0]
        for box in det_results.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            conf = float(box.conf[0])
            if conf < 0.25:
                continue
            cls = int(box.cls[0])
            class_name = self.det_names.get(cls, f"Class {cls}")
            
            # Simple color assignment (vehicles blue, pedestrians yellow, signs/etc red/gray)
            color = (255, 120, 0) # Default cyan-ish/blue (BGR)
            if "person" in class_name.lower():
                color = (0, 255, 255) # Yellow
            elif "traffic" in class_name.lower() or "barricade" in class_name.lower():
                color = (0, 0, 255) # Red
                
            cv2.rectangle(overlay_frame, (x1, y1), (x2, y2), color, 2)
            label = f"{class_name} {conf:.2f}"
            cv2.putText(overlay_frame, label, (x1, max(y1 - 7, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

        # 4. Pothole / Defect Detection Model
        pot_results = self.pot_model(undistorted, verbose=False)[0]
        for box in pot_results.boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
            conf = float(box.conf[0])
            if conf < 0.25:
                continue
            cls = int(box.cls[0])
            class_name = self.pot_names.get(cls, f"Defect {cls}")
            
            color = (0, 69, 255) # Orange-red for road defects
            cv2.rectangle(overlay_frame, (x1, y1), (x2, y2), color, 2)
            label = f"{class_name} {conf:.2f}"
            cv2.putText(overlay_frame, label, (x1, max(y1 - 7, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)

        # 5. Depth Model
        depth_map = self.run_depth_inference(undistorted)
        # Normalize and colormap depth map
        depth_min, depth_max = depth_map.min(), depth_map.max()
        if depth_max - depth_min > 1e-5:
            depth_norm = ((depth_map - depth_min) / (depth_max - depth_min) * 255.0).astype(np.uint8)
        else:
            depth_norm = np.zeros_like(depth_map, dtype=np.uint8)
        depth_colored = cv2.applyColorMap(depth_norm, cv2.COLORMAP_VIRIDIS)

        # 6. Render OBD2 HUD overlay
        if telemetry_data is not None:
            self._render_hud(overlay_frame, telemetry_data)

        # 7. Merge Side-by-Side (Combined Visual overlays + Color-mapped depth map)
        merged = np.hstack((overlay_frame, depth_colored))
        return merged

    def _render_hud(self, frame, row):
        # Create a semi-transparent panel for telemetry HUD
        h, w = frame.shape[:2]
        hud_w = int(w * 0.28)
        hud_h = int(h * 0.32)
        hud_x = 15
        hud_y = 15
        
        # Sub-pixel blend for overlay background
        sub_img = frame[hud_y:hud_y+hud_h, hud_x:hud_x+hud_w]
        black_rect = np.zeros_like(sub_img)
        # Bins: Speed, RPM, Throttle, Gear, Fuel Usage, Load
        cv2.addWeighted(black_rect, 0.7, sub_img, 0.3, 0, sub_img)
        frame[hud_y:hud_y+hud_h, hud_x:hud_x+hud_w] = sub_img
        
        # Draw borders
        cv2.rectangle(frame, (hud_x, hud_y), (hud_x + hud_w, hud_y + hud_h), (0, 255, 0), 1)
        
        # Add telemetry text
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 0.45
        color = (255, 255, 255)
        thickness = 1
        
        labels = [
            f"SPEED: {row.get('SPEED', 0.0):.1f} km/h",
            f"RPM: {row.get('RPM', 0.0):.0f}",
            f"GEAR: {row.get('GEAR') if pd.notna(row.get('GEAR')) else 'N/A'}",
            f"THROTTLE: {row.get('THROTTLE_POS', 0.0):.1f}%",
            f"LOAD: {row.get('ENGINE_LOAD', 0.0):.1f}%",
            f"FUEL: {row.get('REAL_FUEL_USAGE_ML_MIN', 0.0):.1f} ml/min",
            f"TIME: {str(row.get('timestamp', '')).split(' ')[1][:11]}",
            f"SEGMENT: {row.get('segment_file', 'N/A')}"
        ]
        
        y_offset = hud_y + 20
        cv2.putText(frame, "RoadEye Vehicle Telemetry", (hud_x + 10, y_offset), font, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
        cv2.line(frame, (hud_x + 10, y_offset + 5), (hud_x + hud_w - 10, y_offset + 5), (0, 255, 0), 1)
        
        y_offset += 25
        for label in labels:
            cv2.putText(frame, label, (hud_x + 15, y_offset), font, scale, color, thickness, cv2.LINE_AA)
            y_offset += 18

    def process_image(self, img_path, output_path, timestamp_str=None):
        frame = cv2.imread(img_path)
        if frame is None:
            raise FileNotFoundError(f"Failed to read image at: {img_path}")
            
        telemetry = None
        if self.telemetry_df is not None:
            if timestamp_str:
                query_time = pd.to_datetime(timestamp_str)
            else:
                query_time = self.telemetry_df['datetime'].iloc[0]
            telemetry = self.get_telemetry_at_time(query_time)
            
        result = self.process_frame(frame, telemetry)
        cv2.imwrite(output_path, result)
        print(f"Processed frame saved to: {output_path}")

    def process_video(self, video_path, output_path, start_time_str=None, max_frames=150):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Failed to open video file at: {video_path}")
            
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0:
            fps = 30.0
            
        print(f"Processing video (Asynchronous Multi-threaded): {video_path} ({width}x{height} @ {fps} FPS, {total_frames} frames)")
        
        # Calculate video starting time
        if start_time_str:
            start_time = pd.to_datetime(start_time_str)
        elif self.telemetry_df is not None:
            start_time = self.telemetry_df['datetime'].iloc[0]
        else:
            start_time = datetime.datetime.now()
            
        # Video writer for side-by-side output: twice the width
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width * 2, height))
        
        # Thread-safe queue of capacity 1 for frame handoffs to inference worker
        frame_queue = queue.Queue(maxsize=1)
        result_lock = threading.Lock()
        stop_event = threading.Event()
        
        # Dictionary caching the latest results from inference background worker thread
        latest_inference = {
            "seg_results": None,
            "det_results": None,
            "pot_results": None,
            "depth_colored": None,
            "telemetry": None
        }
        
        # Worker thread loop for non-blocking model inferences
        def inference_worker():
            while not stop_event.is_set():
                try:
                    # Timeout checks stop_event regularly
                    task = frame_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                in_frame, telemetry_data = task
                try:
                    # Run perception model pipeline on the background thread
                    undistorted = self.undistort_frame(in_frame)
                    
                    # 1. Road Segmentation
                    seg_res = self.seg_model(undistorted, verbose=False)[0]
                    
                    # 2. Object Detection
                    det_res = self.det_model(undistorted, verbose=False)[0]
                    
                    # 3. Pothole Detection
                    pot_res = self.pot_model(undistorted, verbose=False)[0]
                    
                    # 4. Depth Estimation (resizing / preprocessing inside this function)
                    depth_map = self.run_depth_inference(undistorted)
                    depth_min, depth_max = depth_map.min(), depth_map.max()
                    if depth_max - depth_min > 1e-5:
                        depth_norm = ((depth_map - depth_min) / (depth_max - depth_min) * 255.0).astype(np.uint8)
                    else:
                        depth_norm = np.zeros_like(depth_map, dtype=np.uint8)
                    depth_col = cv2.applyColorMap(depth_norm, cv2.COLORMAP_VIRIDIS)
                    
                    # Update thread-safe shared state
                    with result_lock:
                        latest_inference["seg_results"] = seg_res
                        latest_inference["det_results"] = det_res
                        latest_inference["pot_results"] = pot_res
                        latest_inference["depth_colored"] = depth_col
                        latest_inference["telemetry"] = telemetry_data
                        
                except Exception as e:
                    print(f"Error in backend inference worker thread: {e}")
                finally:
                    frame_queue.task_done()
                    
        # Start the daemon background worker
        worker = threading.Thread(target=inference_worker, daemon=True)
        worker.start()
        
        frame_idx = 0
        start_processing_time = time.time()
        
        # Configurable skipping interval (e.g. inference runs on every 3rd frame)
        skip_interval = 3
        
        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                    
                if max_frames and frame_idx >= max_frames:
                    print(f"Reached limit of {max_frames} frames. Stopping video processing early.")
                    break
                
                # Retrieve telemetry for current timestamp
                frame_time = start_time + datetime.timedelta(seconds=frame_idx / fps)
                telemetry_data = self.get_telemetry_at_time(frame_time)
                
                # Drop queue contents if a new target frame matches interval and queue is full
                if frame_idx % skip_interval == 0:
                    if frame_queue.full():
                        try:
                            frame_queue.get_nowait()
                            frame_queue.task_done()
                        except queue.Empty:
                            pass
                    try:
                        frame_queue.put_nowait((frame.copy(), telemetry_data))
                    except queue.Full:
                        pass
                
                # Fetch latest thread-safe inference state
                with result_lock:
                    cached_seg = latest_inference["seg_results"]
                    cached_det = latest_inference["det_results"]
                    cached_pot = latest_inference["pot_results"]
                    cached_depth = latest_inference["depth_colored"]
                    cached_telemetry = latest_inference["telemetry"]
                
                # Draw visual layers on the main thread (using undistorted frame)
                undistorted = self.undistort_frame(frame)
                overlay_frame = undistorted.copy()
                
                # Render cached segmentation
                if cached_seg is not None and cached_seg.masks is not None:
                    mask_layer = np.zeros_like(undistorted)
                    for seg in cached_seg.masks.xy:
                        pts = seg.astype(np.int32)
                        cv2.fillPoly(mask_layer, [pts], (0, 180, 0))
                    cv2.addWeighted(mask_layer, 0.4, overlay_frame, 0.6, 0, overlay_frame)
                    
                # Render cached object detection boxes
                if cached_det is not None:
                    for box in cached_det.boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                        conf = float(box.conf[0])
                        if conf >= 0.25:
                            cls = int(box.cls[0])
                            class_name = self.det_names.get(cls, f"Class {cls}")
                            color = (255, 120, 0)
                            if "person" in class_name.lower():
                                color = (0, 255, 255)
                            elif "traffic" in class_name.lower() or "barricade" in class_name.lower():
                                color = (0, 0, 255)
                            cv2.rectangle(overlay_frame, (x1, y1), (x2, y2), color, 2)
                            label = f"{class_name} {conf:.2f}"
                            cv2.putText(overlay_frame, label, (x1, max(y1 - 7, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
                            
                # Render cached pothole detection boxes (always mapped as "Pothole")
                if cached_pot is not None:
                    for box in cached_pot.boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                        conf = float(box.conf[0])
                        if conf >= 0.25:
                            color = (0, 69, 255)
                            cv2.rectangle(overlay_frame, (x1, y1), (x2, y2), color, 2)
                            label = f"Pothole {conf:.2f}"
                            cv2.putText(overlay_frame, label, (x1, max(y1 - 7, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
                
                # Check depth map cache
                depth_representation = cached_depth if cached_depth is not None else np.zeros_like(undistorted)
                
                # Draw HUD
                if cached_telemetry is not None:
                    self._render_hud(overlay_frame, cached_telemetry)
                    
                # Merge Side-by-Side and write out
                merged = np.hstack((overlay_frame, depth_representation))
                out.write(merged)
                
                frame_idx += 1
                if frame_idx % 30 == 0:
                    elapsed = time.time() - start_processing_time
                    fps_processing = frame_idx / elapsed
                    print(f"Frame {frame_idx}/{total_frames} ({frame_idx/total_frames*100:.1f}%) | processing speed: {fps_processing:.1f} fps")
        finally:
            stop_event.set()
            cap.release()
            out.release()
            print(f"Output video successfully written to: {output_path}")

def generate_synthetic_road_scene():
    """Generates a high-quality synthetic road scene for testing the pipeline."""
    # 720p base canvas
    h, w = 720, 1280
    img = np.zeros((h, w, 3), dtype=np.uint8)
    
    # Sky (gradient blue)
    for y in range(360):
        c = int(255 - (y / 360) * 150)
        img[y, :] = (c, 160 + int(y/360*50), 100) # light blue/cyan gradient
        
    # Grass/sides (green)
    img[360:, :] = (50, 150, 50)
    
    # Road lanes (polygon)
    road_pts = np.array([
        [int(w*0.42), 360],
        [int(w*0.58), 360],
        [w - 100, h],
        [100, h]
    ], dtype=np.int32)
    cv2.fillPoly(img, [road_pts], (90, 90, 90)) # Asphalt gray
    
    # Lane divider lines (white dashes)
    cv2.line(img, (int(w*0.5), 360), (int(w*0.5), h), (255, 255, 255), 5)
    
    # Add a mock vehicle box (simulating a car in the lane)
    cv2.rectangle(img, (int(w*0.48), 380), (int(w*0.58), 480), (120, 80, 80), -1) # Dark grey car body
    cv2.rectangle(img, (int(w*0.50), 400), (int(w*0.56), 460), (0, 0, 255), -1) # Red taillights/window
    
    # Add a mock pothole circle
    cv2.circle(img, (int(w*0.35), h - 150), 30, (30, 30, 30), -1) # Dark patch
    cv2.circle(img, (int(w*0.35), h - 150), 20, (10, 10, 10), -1) # Inner pit
    
    return img

def download_test_image(target_path):
    print("Downloading a sample road scene image for testing...")
    url = "https://images.unsplash.com/photo-1519074002996-a69e7ac46a42?w=1280&q=80"
    try:
        # User-agent header to avoid getting blocked
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response, open(target_path, 'wb') as out_file:
            out_file.write(response.read())
        print(f"Downloaded test image to: {target_path}")
        return True
    except Exception as e:
        print(f"Failed to download image from unsplash: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RoadEye — Unified Perception and OBD2 Telemetry Pipeline")
    parser.add_argument("--input", type=str, default="dummy", help="Path to input image/video, folder path, or 'dummy' for synthetic frame")
    parser.add_argument("--obd-csv", type=str, default=None, help="Path to OBD2 CSV data file")
    parser.add_argument("--timestamp", type=str, default=None, help="Specific telemetry timestamp to use (format: YYYY-MM-DD HH:MM:SS.ffffff)")
    parser.add_argument("--output-dir", type=str, default="output", help="Directory where processed files are saved")
    
    args = parser.parse_args()
    
    # Determine base configurations path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(script_dir, "RoadEye")):
        configs_dir = os.path.join(script_dir, "RoadEye", "models", "configs")
    else:
        configs_dir = os.path.join(script_dir, "models", "configs")
        
    calibration_path = os.path.join(configs_dir, "calibration.yaml")
    classes_path = os.path.join(configs_dir, "classes.yaml")
    inference_path = os.path.join(configs_dir, "inference.yaml")
    
    obd_csv = args.obd_csv
    if not obd_csv:
        default_csv = os.path.join(script_dir, "vehicle_data", "OBD2_panel_opel_2012.csv")
        if os.path.exists(default_csv):
            obd_csv = default_csv

    # Initialize the pipeline
    pipeline = RoadEyePipeline(
        calibration_path=calibration_path,
        classes_path=classes_path,
        inference_path=inference_path,
        obd_csv_path=obd_csv
    )
    
    # Ensure output directory exists
    output_dir = os.path.join(pipeline.base_path, "..", args.output_dir) if os.path.exists(os.path.join(script_dir, "RoadEye")) else args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    print(f"Saving output files to: {os.path.abspath(output_dir)}")
    
    # Process inputs
    if args.input.lower() == "dummy":
        print("Generating a synthetic road scene frame...")
        dummy_frame = generate_synthetic_road_scene()
        
        # Load a default timestamp row from the CSV if present
        telemetry = None
        if pipeline.telemetry_df is not None:
            telemetry = pipeline.telemetry_df.iloc[0]
            
        print("Processing synthetic frame...")
        result = pipeline.process_frame(dummy_frame, telemetry)
        
        output_file = os.path.join(output_dir, "dummy_processed.jpg")
        cv2.imwrite(output_file, result)
        print(f"Synthetic frame successfully processed and saved to: {output_file}")
        
    elif args.input.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
        output_file = os.path.join(output_dir, f"processed_{os.path.basename(args.input)}")
        pipeline.process_video(args.input, output_file, start_time_str=args.timestamp)
        
    else:
        # Check if file exists, if not try downloading if it's a test trigger
        if not os.path.exists(args.input) and args.input == "test_road.jpg":
            success = download_test_image(args.input)
            if not success:
                print(f"Error: Could not retrieve '{args.input}' for processing.")
                sys.exit(1)
                
        output_file = os.path.join(output_dir, f"processed_{os.path.basename(args.input)}")
        pipeline.process_image(args.input, output_file, timestamp_str=args.timestamp)
