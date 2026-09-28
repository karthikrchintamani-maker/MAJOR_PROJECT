"""
RoadEye Perception Pipeline
Runs all ONNX / PyTorch models on a single video frame and returns structured results.
Falls back to a high-quality CV simulation when real model weights are unavailable.
"""
import time
import logging
import random
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from config import (
    CONF_THRESH, NMS_THRESH, INPUT_SIZE,
    DETECTION_CLASSES, POTHOLE_CLASSES,
)
from models_loader import (
    ModelInfo, preprocess_frame,
    decode_yolo_detect_output,
)

log = logging.getLogger("roadeye.pipeline")

# ─── Colours ──────────────────────────────────────────────────────────────────
# BGR tuples
CLASS_COLORS = {
    29: (50,  30, 220),   # Person       — vivid red
    47: (50,  30, 220),   # person
    0:  (0,  120, 255),   # Ambulance    — orange
    3:  (0,  165, 255),   # Bike         — amber
    27: (0,  165, 255),   # MotorBike
    7:  (200, 160,  0),   # Bus          — steel blue
    11: (0,  229, 255),   # Car          — cyan
    41: (0,  180,  60),   # Truck        — green
    39: (0,  220,   0),   # Traffic Signal
    1:  (180,  50, 255),  # Autorickshaw — purple
    13: (60,  180, 255),  # Cattle
    17: (80,  180, 200),  # Dog
}
POTHOLE_COLOR  = (0, 130, 255)   # Orange-red
DEFAULT_COLOR  = (0, 229, 255)   # Cyan

# ─── Result dataclasses ───────────────────────────────────────────────────────
@dataclass
class Detection:
    box:   list        # [x1,y1,x2,y2] pixel coords
    conf:  float
    cls:   int
    label: str


@dataclass
class InferenceResult:
    detections:      list[Detection]      = field(default_factory=list)
    potholes:        list[Detection]      = field(default_factory=list)
    seg_mask:        Optional[np.ndarray] = None   # H×W uint8 0/1
    depth_map:       Optional[np.ndarray] = None   # H×W float32
    risk_score:      float                = 0.0
    fps:             float                = 0.0
    mode:            str                  = "simulation"
    warnings:        list[str]            = field(default_factory=list)
    closest_dist_m:  float                = 0.0


# ─── Pipeline ─────────────────────────────────────────────────────────────────
class RoadEyePipeline:

    def __init__(self, models: dict[str, ModelInfo]):
        self.models = models
        self._fc   = 0
        self._t0   = time.perf_counter()
        self._fps  = 0.0
        # Background subtractor for motion-based detection (webcam / video)
        self._mog  = cv2.createBackgroundSubtractorMOG2(
            history=120, varThreshold=50, detectShadows=False)
        log.info("Pipeline ready. Backends: %s",
                 {k: v.backend for k, v in models.items()})

    # ── FPS counter ──────────────────────────────────────────────────────────
    def _tick(self) -> float:
        self._fc += 1
        elapsed = time.perf_counter() - self._t0
        if elapsed >= 1.0:
            self._fps = round(self._fc / elapsed, 1)
            self._fc  = 0
            self._t0  = time.perf_counter()
        return self._fps

    # ── Main entry ───────────────────────────────────────────────────────────
    def run(self, frame_bgr: np.ndarray,
            show_boxes=True, show_seg=True,
            show_depth=False, show_lanes=True
            ) -> tuple[np.ndarray, InferenceResult]:

        h, w   = frame_bgr.shape[:2]
        result = InferenceResult()
        out    = frame_bgr.copy()

        # 1. Object detection
        det_m = self.models.get("detection")
        if det_m and det_m.backend != "simulation":
            result.detections = self._run_detection(frame_bgr, det_m, (h, w))
        elif show_boxes:
            result.detections = self._sim_detection(frame_bgr, (h, w))

        # 2. Pothole detection
        pot_m = self.models.get("pothole")
        if pot_m and pot_m.backend != "simulation":
            result.potholes = self._run_pothole(frame_bgr, pot_m, (h, w))
        elif show_boxes:
            result.potholes = self._sim_pothole(frame_bgr, (h, w))

        # 3. Road segmentation
        seg_m = self.models.get("segmentation")
        if seg_m and seg_m.backend != "simulation":
            result.seg_mask = self._run_segmentation(frame_bgr, seg_m, (h, w))
        elif show_seg:
            result.seg_mask = self._sim_segmentation(frame_bgr, (h, w))

        # 4. Depth
        dep_m = self.models.get("depth")
        if dep_m and dep_m.backend != "simulation":
            result.depth_map = self._run_depth(frame_bgr, dep_m, (h, w))
        elif show_depth:
            result.depth_map = self._sim_depth(frame_bgr, (h, w))

        # Analytics
        result.risk_score     = self._risk(result, (h, w))
        result.closest_dist_m = self._closest(result, (h, w))
        result.warnings       = self._warnings(result)

        # Draw
        self._draw(out, result, show_boxes, show_seg, show_depth, show_lanes)
        self._osd(out, result, (h, w))

        result.fps = self._tick()
        modes = list({m.backend for m in self.models.values()})
        result.mode = modes[0] if len(modes) == 1 else "mixed"
        return out, result

    # ══════════════════════════════════════════════════════════════════════════
    #  REAL INFERENCE
    # ══════════════════════════════════════════════════════════════════════════
    def _run_detection(self, frame, model, orig_hw):
        try:
            tensor = preprocess_frame(frame, INPUT_SIZE)
            outs   = model.session.run(model.output_names, {model.input_name: tensor})
            raw    = decode_yolo_detect_output(outs[0], orig_hw, CONF_THRESH, NMS_THRESH)
            return [Detection(d["box"], d["conf"], d["cls"],
                              DETECTION_CLASSES.get(d["cls"], f"cls{d['cls']}")) for d in raw]
        except Exception as e:
            log.error("Detection error: %s", e)
            return self._sim_detection(frame, orig_hw)

    def _run_pothole(self, frame, model, orig_hw):
        try:
            tensor = preprocess_frame(frame, INPUT_SIZE)
            outs   = model.session.run(model.output_names, {model.input_name: tensor})
            raw    = decode_yolo_detect_output(outs[0], orig_hw, CONF_THRESH, NMS_THRESH)
            return [Detection(d["box"], d["conf"], d["cls"], "Pothole") for d in raw]
        except Exception as e:
            log.error("Pothole error: %s", e)
            return []

    def _run_segmentation(self, frame, model, orig_hw):
        try:
            tensor = preprocess_frame(frame, INPUT_SIZE)
            outs   = model.session.run(model.output_names, {model.input_name: tensor})
            proto  = outs[1][0]   # (32,160,160)
            rough  = proto.mean(axis=0)
            rough  = (rough - rough.min()) / (rough.max() - rough.min() + 1e-6)
            mask160 = (rough > 0.5).astype(np.uint8)
            h, w = orig_hw
            return cv2.resize(mask160, (w, h), interpolation=cv2.INTER_NEAREST)
        except Exception as e:
            log.error("Segmentation error: %s", e)
            return self._sim_segmentation(frame, orig_hw)

    def _run_depth(self, frame, model, orig_hw):
        try:
            tensor = preprocess_frame(frame, orig_hw)
            outs   = model.session.run(model.output_names, {model.input_name: tensor})
            d = outs[0][0, 0]
            return ((d - d.min()) / (d.max() - d.min() + 1e-6)).astype(np.float32)
        except Exception as e:
            log.error("Depth error: %s", e)
            return None

    # ══════════════════════════════════════════════════════════════════════════
    #  IMPROVED SIMULATION — uses actual computer vision on real video frames
    # ══════════════════════════════════════════════════════════════════════════

    # ── Helper: compute road-colour mask ─────────────────────────────────────
    @staticmethod
    def _road_mask(frame: np.ndarray) -> np.ndarray:
        """
        Returns a binary mask of the road surface using colour+position heuristics.
        Road in dashcam footage is typically grey/dark-grey in the lower 2/3.
        """
        h, w = frame.shape[:2]
        hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Road is low-saturation (grey asphalt) OR reddish-brown (brick roads)
        # Mask 1: grey asphalt  — low sat, medium-dark value
        m_asphalt = cv2.inRange(hsv, (0, 0, 30), (180, 60, 180))
        # Mask 2: brownish/red dirt road
        m_dirt    = cv2.inRange(hsv, (5, 20, 60), (30, 120, 200))
        road_colour = cv2.bitwise_or(m_asphalt, m_dirt)

        # Positional mask: road occupies lower portion, perspective trapezoid
        pos_mask = np.zeros((h, w), dtype=np.uint8)
        pts = np.array([
            [int(w * 0.10), h],
            [int(w * 0.32), int(h * 0.50)],
            [int(w * 0.68), int(h * 0.50)],
            [int(w * 0.90), h],
        ], dtype=np.int32)
        cv2.fillPoly(pos_mask, [pts], 255)

        road = cv2.bitwise_and(road_colour, pos_mask)
        # Morphological clean-up
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        road = cv2.morphologyEx(road, cv2.MORPH_CLOSE, k)
        road = cv2.morphologyEx(road, cv2.MORPH_OPEN,  k)
        return road

    # ── Object Detection Simulation ───────────────────────────────────────────
    def _sim_detection(self, frame: np.ndarray, orig_hw: tuple) -> list[Detection]:
        """
        Multi-stage approach:
          1. Motion saliency (MOG2) — picks up moving objects on real video/webcam
          2. Colour saliency — finds regions visually different from road
          3. Merge + NMS + class assignment by shape/position/colour
        """
        h, w = orig_hw
        results: list[Detection] = []
        img_area = h * w

        # ── Stage 1: Motion mask (best for live webcam/video) ────────────────
        fg_mask = self._mog.apply(frame)
        # Remove shadows (value = 127), keep only strong foreground
        _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, k3)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN,  k3)

        # ── Stage 2: Colour-saliency mask (works on static scenes too) ───────
        # Convert to LAB and find regions far from road colour
        road_mask = self._road_mask(frame)
        # Non-road pixels in the upper 80% = likely objects
        non_road  = cv2.bitwise_not(road_mask)
        # Sky region (top 20%) should be excluded
        non_road[:int(h * 0.18), :] = 0
        # Bottom 5% is car bonnet
        non_road[int(h * 0.95):, :] = 0

        # Also look for high-contrast blobs via Laplacian (sharp edges = objects)
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        lap   = cv2.Laplacian(gray, cv2.CV_16S, ksize=3)
        lap_u = cv2.convertScaleAbs(lap)
        _, edge_strong = cv2.threshold(lap_u, 15, 255, cv2.THRESH_BINARY)
        k5 = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        edge_closed = cv2.morphologyEx(edge_strong, cv2.MORPH_CLOSE, k5)

        # Combined saliency = (motion OR non-road) AND has edges
        combined = cv2.bitwise_or(fg_mask, non_road)
        combined = cv2.bitwise_and(combined, edge_closed)

        # Morphological consolidation
        k_big = cv2.getStructuringElement(cv2.MORPH_RECT, (12, 12))
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, k_big)
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN,
                                    cv2.getStructuringElement(cv2.MORPH_RECT, (6, 6)))

        # ── Stage 3: Extract candidate bounding boxes ─────────────────────────
        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)

        # Sort by area descending, take top-N candidates
        candidates = sorted(contours, key=cv2.contourArea, reverse=True)[:12]

        raw_boxes = []   # (x1,y1,x2,y2,score)
        for c in candidates:
            area = cv2.contourArea(c)
            # Size gates: between 0.3% and 25% of frame
            if area < img_area * 0.003 or area > img_area * 0.25:
                continue
            x, y, bw, bh = cv2.boundingRect(c)
            # Must be at least 20px in each direction
            if bw < 20 or bh < 20:
                continue
            # Objects should not start too high (sky) or too low (bonnet)
            if y + bh < h * 0.15 or y > h * 0.92:
                continue
            # Aspect ratio gate: reject pathological shapes
            ar = bw / max(bh, 1)
            if ar > 6.0 or ar < 0.15:
                continue
            # Confidence proxy: how much of the box is in the fg/saliency mask
            roi = combined[y:y+bh, x:x+bw]
            fill_ratio = roi.mean() / 255.0
            if fill_ratio < 0.15:
                continue
            score = min(0.95, 0.50 + fill_ratio * 0.5)
            raw_boxes.append((x, y, x+bw, y+bh, score))

        # ── Stage 4: NMS on raw boxes ─────────────────────────────────────────
        if raw_boxes:
            boxes_np  = np.array([[b[0], b[1], b[2], b[3]] for b in raw_boxes], dtype=float)
            scores_np = np.array([b[4] for b in raw_boxes])
            keep_ids  = _nms(boxes_np, scores_np, iou_thresh=0.40)
            raw_boxes = [raw_boxes[i] for i in keep_ids]

        # ── Stage 5: Classify each surviving box ──────────────────────────────
        for (x1, y1, x2, y2, score) in raw_boxes[:6]:   # max 6 detections
            bw = x2 - x1
            bh = y2 - y1
            ar = bw / max(bh, 1)
            # Centre-Y position (0=top, 1=bottom)
            cy_norm = (y1 + bh / 2) / h
            # Average colour of the box region
            roi_bgr  = frame[y1:y2, x1:x2]
            mean_hsv = cv2.mean(cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2HSV))[:3]
            hue, sat, val = mean_hsv

            # Classification rules (tuned for Indian road dashcam footage):
            if bh > h * 0.35 and ar < 0.65:
                cls, label = 29, "Person"           # Tall & narrow → person
            elif bh > h * 0.30 and ar < 0.55:
                cls, label = 29, "Person"
            elif ar > 2.5 and val > 100:
                cls, label = 7, "Bus"               # Very wide, bright → bus/truck
            elif ar > 1.8 and cy_norm < 0.65:
                cls, label = 41, "Truck"
            elif ar > 1.2 and cy_norm < 0.70:
                cls, label = 11, "Car"              # Wide in middle → car
            elif ar > 0.8 and cy_norm < 0.60 and sat > 30:
                cls, label = 1, "Autorickshaw"      # Compact, mid-frame
            elif ar < 0.7 and bh < h * 0.25 and sat > 20:
                cls, label = 3, "Bike"              # Narrow, small
            elif ar > 0.6 and cy_norm > 0.65:
                cls, label = 11, "Car"              # Low in frame → car
            else:
                cls, label = 27, "MotorBike"

            conf = round(score, 2)
            results.append(Detection(box=[x1, y1, x2, y2], conf=conf,
                                     cls=cls, label=label))

        return results

    # ── Pothole Detection Simulation ──────────────────────────────────────────
    def _sim_pothole(self, frame: np.ndarray, orig_hw: tuple) -> list[Detection]:
        """
        Detect road surface anomalies:
        - Restrict to the confirmed road surface (lower trapezoid, masked by road colour)
        - Find dark patches (potholes/cracks are darker than surrounding road)
        - Find rough-texture patches (cracks produce high Laplacian response)
        - Apply strict size + shape filters to avoid false positives on lane markings
        """
        h, w = orig_hw
        road_mask = self._road_mask(frame)

        # Only look at road surface, bottom 50% of frame
        search_mask = np.zeros((h, w), dtype=np.uint8)
        search_mask[int(h * 0.50):, :] = 255
        search_mask = cv2.bitwise_and(search_mask, road_mask)

        if search_mask.sum() < 1000:   # road surface too small → skip
            return []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # ── Dark-patch detector (potholes are usually darker than road) ──────
        # Compute local mean using a large kernel
        blur = cv2.GaussianBlur(gray, (31, 31), 0)
        dark_diff = blur.astype(np.int16) - gray.astype(np.int16)
        dark_diff = np.clip(dark_diff, 0, 255).astype(np.uint8)
        _, dark_thresh = cv2.threshold(dark_diff, 25, 255, cv2.THRESH_BINARY)
        dark_thresh = cv2.bitwise_and(dark_thresh, search_mask)

        # ── Texture / crack detector ──────────────────────────────────────────
        lap  = cv2.Laplacian(gray, cv2.CV_16S, ksize=5)
        lap_u = cv2.convertScaleAbs(lap)
        _, tex_thresh = cv2.threshold(lap_u, 40, 255, cv2.THRESH_BINARY)
        tex_thresh = cv2.bitwise_and(tex_thresh, search_mask)

        # Combine: dark patches that also have high texture
        combined = cv2.bitwise_and(dark_thresh, tex_thresh)
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, k)
        combined = cv2.morphologyEx(combined, cv2.MORPH_OPEN,
                                    cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))

        contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)

        results: list[Detection] = []
        img_area = h * w
        raw_boxes = []

        for c in sorted(contours, key=cv2.contourArea, reverse=True):
            area = cv2.contourArea(c)
            # Pothole size: between 0.15% and 8% of frame
            if area < img_area * 0.0015 or area > img_area * 0.08:
                continue
            x, y, bw, bh = cv2.boundingRect(c)
            # Must be reasonably compact (not a long thin line = lane marking)
            ar = bw / max(bh, 1)
            if ar > 5.0 or ar < 0.2:
                continue
            # Min physical size in pixels
            if bw < 15 or bh < 10:
                continue
            # Solidity check: pothole fills most of its bounding box
            hull_area = cv2.contourArea(cv2.convexHull(c))
            solidity = area / max(hull_area, 1)
            if solidity < 0.35:
                continue
            # Must be mostly on road mask
            roi_road = road_mask[y:y+bh, x:x+bw]
            road_fill = roi_road.mean() / 255.0
            if road_fill < 0.30:
                continue

            score = min(0.92, 0.55 + road_fill * 0.35 + solidity * 0.10)
            raw_boxes.append((x, y, x+bw, y+bh, score))

        # NMS on pothole candidates
        if raw_boxes:
            boxes_np  = np.array([[b[0],b[1],b[2],b[3]] for b in raw_boxes], dtype=float)
            scores_np = np.array([b[4] for b in raw_boxes])
            keep_ids  = _nms(boxes_np, scores_np, iou_thresh=0.30)
            raw_boxes = [raw_boxes[i] for i in keep_ids]

        for (x1, y1, x2, y2, score) in raw_boxes[:3]:   # max 3 potholes
            cls_id = 3   # Pothole
            results.append(Detection(
                box=[x1, y1, x2, y2],
                conf=round(score, 2),
                cls=cls_id,
                label="Pothole"
            ))

        return results

    # ── Road Segmentation Simulation ──────────────────────────────────────────
    def _sim_segmentation(self, frame: np.ndarray, orig_hw: tuple) -> np.ndarray:
        """High-quality road mask via colour + perspective + edge refinement."""
        h, w = orig_hw
        road = self._road_mask(frame)
        # Normalize to 0/1
        return (road > 0).astype(np.uint8)

    # ── Depth Simulation ─────────────────────────────────────────────────────
    def _sim_depth(self, frame: np.ndarray, orig_hw: tuple) -> np.ndarray:
        """Monocular depth proxy: combine vertical position + local contrast."""
        h, w = orig_hw
        # Objects at top are far; objects at bottom are close
        vert = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, np.newaxis]
        vert = np.tile(vert, (1, w))
        # High contrast = close object (edges are sharper when close)
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        lap   = cv2.Laplacian(gray, cv2.CV_32F, ksize=3)
        lap_n = np.abs(lap)
        lap_n = (lap_n - lap_n.min()) / (lap_n.max() - lap_n.min() + 1e-6)
        depth = 0.65 * vert + 0.35 * (1.0 - gray)
        depth = np.clip(depth, 0.0, 1.0)
        return depth.astype(np.float32)

    # ══════════════════════════════════════════════════════════════════════════
    #  ANALYTICS
    # ══════════════════════════════════════════════════════════════════════════
    def _risk(self, r: InferenceResult, orig_hw: tuple) -> float:
        h, w = orig_hw
        img_area = max(h * w, 1)
        HIGH_RISK = {29, 47, 0}
        risk = 0.0

        for d in r.detections:
            x1, y1, x2, y2 = d.box
            area_frac = (x2 - x1) * (y2 - y1) / img_area
            # Objects lower in frame → closer → higher risk
            cy_norm = (y1 + (y2 - y1) / 2) / h
            base = (area_frac * 60.0 + cy_norm * 20.0) * (1.4 if d.cls in HIGH_RISK else 1.0)
            risk = max(risk, min(base, 85.0))

        for p in r.potholes:
            x1, y1, x2, y2 = p.box
            area_frac = (x2 - x1) * (y2 - y1) / img_area
            cy_norm = (y1 + (y2 - y1) / 2) / h
            base = area_frac * 50.0 + cy_norm * 15.0
            risk = max(risk, min(base, 70.0))

        return round(min(risk, 100.0), 1)

    def _closest(self, r: InferenceResult, orig_hw: tuple) -> float:
        h = orig_hw[0]
        closest = 99.9
        for d in r.detections + r.potholes:
            x1, y1, x2, y2 = d.box
            box_h = max(y2 - y1, 1)
            # Perspective heuristic: taller box → closer
            dist = max(0.4, round(h * 1.6 / box_h - 0.5, 1))
            closest = min(closest, dist)
        return closest if closest < 99.9 else 0.0

    def _warnings(self, r: InferenceResult) -> list[str]:
        w = []
        HIGH_RISK = {29, 47}
        for d in r.detections:
            if d.cls in HIGH_RISK and d.conf > 0.5:
                w.append(f"PEDESTRIAN_AHEAD:{d.label}:{d.conf:.2f}")
        for p in r.potholes:
            if p.conf > 0.5:
                w.append(f"POTHOLE_AHEAD:{p.label}:{p.conf:.2f}")
        if r.risk_score > 70:
            w.append(f"HIGH_RISK:{r.risk_score:.0f}")
        return w

    # ══════════════════════════════════════════════════════════════════════════
    #  DRAWING
    # ══════════════════════════════════════════════════════════════════════════
    def _draw(self, img, r, show_boxes, show_seg, show_depth, show_lanes):
        h, w = img.shape[:2]

        # Road segmentation overlay
        if show_seg and r.seg_mask is not None:
            overlay = img.copy()
            overlay[r.seg_mask == 1] = (0, 160, 70)   # dark green
            cv2.addWeighted(overlay, 0.15, img, 0.85, 0, img)

        # Lane boundary lines (perspective trapezoid, anti-aliased)
        if show_lanes:
            for pts in [
                [(int(w * 0.10), h), (int(w * 0.34), int(h * 0.52))],
                [(int(w * 0.90), h), (int(w * 0.66), int(h * 0.52))],
            ]:
                cv2.line(img, pts[0], pts[1], (0, 229, 255), 3, cv2.LINE_AA)

        # Depth heatmap
        if show_depth and r.depth_map is not None:
            d8 = (r.depth_map * 255).astype(np.uint8)
            cv2.addWeighted(cv2.applyColorMap(d8, cv2.COLORMAP_MAGMA),
                            0.38, img, 0.62, 0, img)

        # Detections
        if show_boxes:
            for d in r.detections:
                color = CLASS_COLORS.get(d.cls, DEFAULT_COLOR)
                self._box(img, d.box, d.label, d.conf, color)
            for p in r.potholes:
                self._box(img, p.box, p.label, p.conf, POTHOLE_COLOR)

    def _box(self, img, box, label, conf, color):
        """Draw a tight, clean bounding box with filled label chip."""
        ih, iw = img.shape[:2]
        x1, y1, x2, y2 = (
            max(0, int(box[0])), max(0, int(box[1])),
            min(iw - 1, int(box[2])), min(ih - 1, int(box[3])),
        )
        if x2 <= x1 or y2 <= y1:
            return

        # Box — slightly thicker when object is large/close
        thickness = 3 if (x2 - x1) * (y2 - y1) > iw * ih * 0.04 else 2
        cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)

        # Label chip
        txt = f"{label}  {conf:.2f}"
        font_scale = 0.50
        font_thick = 1
        (tw, th), baseline = cv2.getTextSize(
            txt, cv2.FONT_HERSHEY_DUPLEX, font_scale, font_thick)

        pad = 4
        ly1 = max(y1 - th - baseline - pad * 2, 0)
        ly2 = ly1 + th + baseline + pad * 2
        # Darken colour for chip background
        chip_color = tuple(max(0, int(c * 0.65)) for c in color)
        cv2.rectangle(img, (x1, ly1), (x1 + tw + pad * 2, ly2), chip_color, -1)
        cv2.rectangle(img, (x1, ly1), (x1 + tw + pad * 2, ly2), color, 1)
        cv2.putText(img, txt, (x1 + pad, ly2 - baseline - pad // 2),
                    cv2.FONT_HERSHEY_DUPLEX, font_scale,
                    (255, 255, 255), font_thick, cv2.LINE_AA)

    def _osd(self, img, r, orig_hw):
        """On-screen display: risk bar, mode tag, warning flash."""
        h, w = orig_hw

        # Risk bar (top-right)
        bar_total = int(w * 0.28)
        bar_fill  = int(bar_total * r.risk_score / 100)
        bx = w - bar_total - 8
        risk_c = (
            (0, 220, 80) if r.risk_score < 35 else
            (0, 165, 255) if r.risk_score < 65 else
            (0,  40, 220)
        )
        cv2.rectangle(img, (bx, 6), (bx + bar_total, 22), (35, 35, 35), -1)
        if bar_fill > 0:
            cv2.rectangle(img, (bx, 6), (bx + bar_fill, 22), risk_c, -1)
        cv2.rectangle(img, (bx, 6), (bx + bar_total, 22), (80, 80, 80), 1)
        risk_lbl = f"RISK {r.risk_score:.0f}%"
        cv2.putText(img, risk_lbl, (bx + 4, 19),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)

        # Mode tag (bottom-left) — clearly labelled
        mode_short = r.mode.upper()[:10]
        tag = f"MODE:{mode_short}"
        cv2.putText(img, tag, (6, h - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 200, 255), 1, cv2.LINE_AA)

        # Detection count (bottom-right)
        cnt = f"OBJ:{len(r.detections)}  POTHOLE:{len(r.potholes)}"
        (cw, _), _ = cv2.getTextSize(cnt, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
        cv2.putText(img, cnt, (w - cw - 6, h - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 180, 180), 1, cv2.LINE_AA)

        # Warning banner (top-centre) — only for real warnings
        if r.warnings:
            msg = r.warnings[0].split(":")[0].replace("_", " ")
            (tw, th), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.62, 2)
            cx = w // 2
            cv2.rectangle(img, (cx - tw // 2 - 10, 4),
                               (cx + tw // 2 + 10, 30), (0, 0, 180), -1)
            cv2.rectangle(img, (cx - tw // 2 - 10, 4),
                               (cx + tw // 2 + 10, 30), (0, 60, 255), 1)
            cv2.putText(img, msg, (cx - tw // 2, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2, cv2.LINE_AA)


# ─── Standalone NMS (no external dependency) ─────────────────────────────────
def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float = 0.45) -> list[int]:
    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes[:,0], boxes[:,1], boxes[:,2], boxes[:,3]
    areas  = (x2 - x1 + 1) * (y2 - y1 + 1)
    order  = scores.argsort()[::-1]
    keep   = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        if order.size == 1:
            break
        ix1 = np.maximum(x1[i], x1[order[1:]])
        iy1 = np.maximum(y1[i], y1[order[1:]])
        ix2 = np.minimum(x2[i], x2[order[1:]])
        iy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, ix2 - ix1 + 1) * np.maximum(0, iy2 - iy1 + 1)
        iou   = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
        order = order[1:][iou <= iou_thresh]
    return keep
