import os
import shutil
import uuid
import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
import cv2

# Import pipeline components
from run_pipeline import RoadEyePipeline, generate_synthetic_road_scene

app = FastAPI(title="RoadEye AI Perception & Telemetry Server")

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve paths
script_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(script_dir, "RoadEye")):
    base_dir = os.path.join(script_dir, "RoadEye")
else:
    base_dir = script_dir

configs_dir = os.path.join(base_dir, "models", "configs")
calibration_path = os.path.join(configs_dir, "calibration.yaml")
classes_path = os.path.join(configs_dir, "classes.yaml")
inference_path = os.path.join(configs_dir, "inference.yaml")
obd_csv_path = os.path.join(base_dir, "vehicle_data", "OBD2_panel_opel_2012.csv")

# Ensure static directories exist
static_dir = os.path.join(script_dir, "static")
uploads_dir = os.path.join(static_dir, "uploads")
outputs_dir = os.path.join(static_dir, "outputs")
os.makedirs(uploads_dir, exist_ok=True)
os.makedirs(outputs_dir, exist_ok=True)

# Initialize perception pipeline
pipeline = RoadEyePipeline(
    calibration_path=calibration_path,
    classes_path=classes_path,
    inference_path=inference_path,
    obd_csv_path=obd_csv_path
)

@app.get("/api/segments")
def get_segments():
    if pipeline.telemetry_df is None:
        raise HTTPException(status_code=404, detail="OBD2 telemetry dataset not loaded on server.")
    
    # Get unique segment file list
    segments = pipeline.telemetry_df['segment_file'].dropna().unique().tolist()
    segments = sorted([str(s) for s in segments])
    return {"segments": segments}

@app.get("/api/telemetry")
def get_telemetry(segment: str):
    if pipeline.telemetry_df is None:
        raise HTTPException(status_code=404, detail="OBD2 telemetry dataset not loaded on server.")
    
    # Filter by segment
    df_seg = pipeline.telemetry_df[pipeline.telemetry_df['segment_file'] == segment]
    if df_seg.empty:
        raise HTTPException(status_code=404, detail=f"No telemetry found for segment: {segment}")
        
    # Extract only visual HUD-relevant parameters to optimize payload size
    cols = ['timestamp', 'SPEED', 'RPM', 'THROTTLE_POS', 'GEAR', 'ENGINE_LOAD', 'REAL_FUEL_USAGE_ML_MIN']
    records = df_seg[cols].to_dict(orient="records")
    
    # Clean NaN values for JSON compatibility
    for r in records:
        for k, v in r.items():
            if pd.isna(v):
                r[k] = None
                
    return {"telemetry": records}

def _clean_telemetry_dict(telemetry):
    if telemetry is None:
        return None
    d = telemetry.to_dict()
    return {k: (None if pd.isna(v) else v) for k, v in d.items()}

@app.post("/api/process")
async def process_media(
    file: UploadFile = File(None),
    use_dummy: bool = Form(False),
    segment: str = Form(None),
    timestamp: str = Form(None),
    conf_threshold: float = Form(0.25)
):
    # Set model confidence thresholds dynamically
    pipeline.det_model.conf = conf_threshold
    pipeline.pot_model.conf = conf_threshold
    
    # Resolve telemetry row
    telemetry = None
    if pipeline.telemetry_df is not None:
        if timestamp:
            query_time = pd.to_datetime(timestamp)
        elif segment:
            df_seg = pipeline.telemetry_df[pipeline.telemetry_df['segment_file'] == segment]
            query_time = df_seg['datetime'].iloc[0] if not df_seg.empty else pipeline.telemetry_df['datetime'].iloc[0]
        else:
            query_time = pipeline.telemetry_df['datetime'].iloc[0]
        telemetry = pipeline.get_telemetry_at_time(query_time)

    # Process based on input mode
    if use_dummy:
        print("API: Processing dummy synthetic road scene...")
        frame = generate_synthetic_road_scene()
        result = pipeline.process_frame(frame, telemetry)
        
        filename = f"dummy_{uuid.uuid4().hex[:8]}.jpg"
        out_path = os.path.join(outputs_dir, filename)
        cv2.imwrite(out_path, result)
        return {"url": f"/static/outputs/{filename}", "telemetry": _clean_telemetry_dict(telemetry)}
        
    if not file:
        raise HTTPException(status_code=400, detail="Missing file parameter. Upload an image or check use_dummy.")
        
    # Save uploaded file
    file_ext = os.path.splitext(file.filename)[1].lower()
    unique_name = f"{uuid.uuid4().hex}{file_ext}"
    in_path = os.path.join(uploads_dir, unique_name)
    
    with open(in_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    out_filename = f"processed_{uuid.uuid4().hex[:12]}{file_ext}"
    out_path = os.path.join(outputs_dir, out_filename)
    
    try:
        if file_ext in ['.mp4', '.avi', '.mov', '.mkv']:
            print(f"API: Processing video {file.filename}...")
            pipeline.process_video(in_path, out_path, start_time_str=timestamp)
            # Cleanup input
            os.remove(in_path)
            return {"url": f"/static/outputs/{out_filename}", "type": "video"}
        else:
            print(f"API: Processing image {file.filename}...")
            frame = cv2.imread(in_path)
            if frame is None:
                raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")
                
            result = pipeline.process_frame(frame, telemetry)
            cv2.imwrite(out_path, result)
            
            # Cleanup input
            os.remove(in_path)
            
            return {
                "url": f"/static/outputs/{out_filename}", 
                "type": "image",
                "telemetry": _clean_telemetry_dict(telemetry)
            }
    except Exception as e:
        if os.path.exists(in_path):
            os.remove(in_path)
        raise HTTPException(status_code=500, detail=f"Pipeline processing failed: {str(e)}")

# Mount static files server
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_root():
    # Redirect base URL to index.html dashboard
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")

if __name__ == "__main__":
    import uvicorn
    import argparse
    
    parser = argparse.ArgumentParser(description="Start the RoadEye Web Server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to run server on")
    
    args = parser.parse_args()
    print(f"Starting RoadEye Web Dashboard at http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)
