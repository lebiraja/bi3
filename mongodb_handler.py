"""
MongoDB Handler Module.
Handles storage and retrieval of frames, YOLO detections, and analysis results.
"""

from datetime import datetime
from typing import List, Dict, Optional, Any
from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from pymongo.database import Database

from config import Config


class MongoDBHandler:
    """
    MongoDB handler for video analysis pipeline.
    
    Collections:
    - frames: Stores extracted frame data and metadata
    - detections: Stores YOLO detection results
    - analyses: Stores VLM behavioral analysis results
    """
    
    def __init__(
        self,
        uri: str = None,
        database: str = None,
        collection: str = None
    ):
        """
        Initialize MongoDB connection.
        
        Args:
            uri: MongoDB connection URI
            database: Database name
            collection: Base collection name for frames
        """
        self.uri = uri or Config.MONGODB_URI
        self.database_name = database or Config.MONGODB_DATABASE
        self.collection_name = collection or Config.MONGODB_COLLECTION
        
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        self.frames_collection: Optional[Collection] = None
        self.detections_collection: Optional[Collection] = None
        self.analyses_collection: Optional[Collection] = None
    
    def connect(self):
        """Establish MongoDB connection and setup collections."""
        self.client = MongoClient(self.uri)
        self.db = self.client[self.database_name]
        
        # Setup collections
        self.frames_collection = self.db[self.collection_name]
        self.detections_collection = self.db["detections"]
        self.analyses_collection = self.db["analyses"]
        
        # Create indexes
        self._create_indexes()
        
        return self
    
    def _create_indexes(self):
        """Create indexes for efficient querying."""
        # Frames collection indexes
        self.frames_collection.create_index([
            ("video_id", ASCENDING),
            ("frame_number", ASCENDING)
        ], unique=True)
        self.frames_collection.create_index("timestamp_ms")
        
        # Detections collection indexes
        self.detections_collection.create_index([
            ("video_id", ASCENDING),
            ("frame_number", ASCENDING)
        ])
        self.detections_collection.create_index("track_id")
        
        # Analyses collection indexes
        self.analyses_collection.create_index([
            ("video_id", ASCENDING),
            ("second_index", ASCENDING)
        ])
        self.analyses_collection.create_index("risk_score")
    
    # ============ Frame Operations ============
    
    def store_frame(self, video_id: str, frame_data: dict) -> str:
        """
        Store a single frame with metadata.
        
        Args:
            video_id: Unique identifier for the video
            frame_data: Frame data dictionary from FrameData.to_dict()
        
        Returns:
            Inserted document ID
        """
        document = {
            "video_id": video_id,
            **frame_data,
            "stored_at": datetime.utcnow()
        }
        result = self.frames_collection.insert_one(document)
        return str(result.inserted_id)
    
    def store_frames_batch(self, video_id: str, frames: List[dict]) -> List[str]:
        """
        Store multiple frames in batch.
        
        Args:
            video_id: Unique identifier for the video
            frames: List of frame data dictionaries
        
        Returns:
            List of inserted document IDs
        """
        documents = [
            {"video_id": video_id, **frame, "stored_at": datetime.utcnow()}
            for frame in frames
        ]
        result = self.frames_collection.insert_many(documents)
        return [str(id) for id in result.inserted_ids]
    
    def get_frames_by_second(self, video_id: str, second: int) -> List[dict]:
        """
        Retrieve frames for a specific second of video.
        
        Args:
            video_id: Unique identifier for the video
            second: Second index (0-indexed)
        
        Returns:
            List of frame documents
        """
        min_ms = second * 1000
        max_ms = (second + 1) * 1000
        
        return list(self.frames_collection.find({
            "video_id": video_id,
            "timestamp_ms": {"$gte": min_ms, "$lt": max_ms}
        }).sort("timestamp_ms", ASCENDING))
    
    # ============ Detection Operations ============
    
    def store_detection(
        self,
        video_id: str,
        frame_number: int,
        detections: List[dict]
    ) -> str:
        """
        Store YOLO detection results for a frame.
        
        Args:
            video_id: Unique identifier for the video
            frame_number: Frame index
            detections: List of detection dictionaries with bbox, class, track_id
        
        Returns:
            Inserted document ID
        """
        document = {
            "video_id": video_id,
            "frame_number": frame_number,
            "detections": detections,
            "detection_count": len(detections),
            "stored_at": datetime.utcnow()
        }
        result = self.detections_collection.insert_one(document)
        return str(result.inserted_id)
    
    def get_detections_for_frames(
        self,
        video_id: str,
        frame_numbers: List[int]
    ) -> Dict[int, List[dict]]:
        """
        Get detections for multiple frames.
        
        Args:
            video_id: Unique identifier for the video
            frame_numbers: List of frame indices
        
        Returns:
            Dictionary mapping frame_number to list of detections
        """
        results = self.detections_collection.find({
            "video_id": video_id,
            "frame_number": {"$in": frame_numbers}
        })
        
        detections_map = {fn: [] for fn in frame_numbers}
        for doc in results:
            detections_map[doc["frame_number"]] = doc.get("detections", [])
        
        return detections_map
    
    # ============ Analysis Operations ============
    
    def store_analysis(
        self,
        video_id: str,
        second_index: int,
        analysis_result: dict,
        frame_numbers: List[int]
    ) -> str:
        """
        Store VLM behavioral analysis result.
        
        Args:
            video_id: Unique identifier for the video
            second_index: Second of video analyzed
            analysis_result: VLM analysis output
            frame_numbers: Frame numbers used in analysis
        
        Returns:
            Inserted document ID
        """
        document = {
            "video_id": video_id,
            "second_index": second_index,
            "frame_numbers": frame_numbers,
            "analysis": analysis_result,
            "risk_score": analysis_result.get("overall_assessment", {}).get("risk_score", 0),
            "analyzed_at": datetime.utcnow()
        }
        result = self.analyses_collection.insert_one(document)
        return str(result.inserted_id)
    
    def get_high_risk_analyses(
        self,
        video_id: str,
        min_risk_score: int = 7
    ) -> List[dict]:
        """
        Get analyses with risk score above threshold.
        
        Args:
            video_id: Unique identifier for the video
            min_risk_score: Minimum risk score to filter (1-10)
        
        Returns:
            List of high-risk analysis documents
        """
        return list(self.analyses_collection.find({
            "video_id": video_id,
            "risk_score": {"$gte": min_risk_score}
        }).sort("second_index", ASCENDING))
    
    def get_video_summary(self, video_id: str) -> dict:
        """
        Get summary of all analyses for a video.
        
        Args:
            video_id: Unique identifier for the video
        
        Returns:
            Summary dictionary with stats and highlights
        """
        pipeline = [
            {"$match": {"video_id": video_id}},
            {"$group": {
                "_id": "$video_id",
                "total_seconds_analyzed": {"$sum": 1},
                "avg_risk_score": {"$avg": "$risk_score"},
                "max_risk_score": {"$max": "$risk_score"},
                "critical_count": {
                    "$sum": {"$cond": [{"$gte": ["$risk_score", 7]}, 1, 0]}
                }
            }}
        ]
        
        results = list(self.analyses_collection.aggregate(pipeline))
        if results:
            return results[0]
        return {
            "video_id": video_id,
            "total_seconds_analyzed": 0,
            "avg_risk_score": 0,
            "max_risk_score": 0,
            "critical_count": 0
        }
    
    # ============ Enhanced Report Operations ============
    
    def _ensure_enhanced_reports_collection(self):
        """Ensure enhanced_reports collection exists with indexes."""
        if not hasattr(self, 'enhanced_reports_collection') or self.enhanced_reports_collection is None:
            self.enhanced_reports_collection = self.db["enhanced_reports"]
            try:
                self.enhanced_reports_collection.create_index("video_id", unique=True)
                self.enhanced_reports_collection.create_index("generated_at")
            except Exception:
                # Index may already exist with different specs, ignore
                pass
    
    def store_enhanced_report(
        self,
        video_id: str,
        enhanced_report: dict
    ) -> str:
        """
        Store enhanced report for a video.
        
        Args:
            video_id: Unique identifier for the video
            enhanced_report: Enhanced report data dictionary
        
        Returns:
            Inserted document ID
        """
        self._ensure_enhanced_reports_collection()
        
        document = {
            "video_id": video_id,
            **enhanced_report,
            "stored_at": datetime.utcnow()
        }
        
        try:
            # Upsert to allow updating existing reports
            result = self.enhanced_reports_collection.update_one(
                {"video_id": video_id},
                {"$set": document},
                upsert=True
            )
            return str(result.upserted_id) if result.upserted_id else video_id
            
        except Exception as e:
            # Handle legacy index conflicts by dropping problematic indexes
            if "duplicate key error" in str(e) or "E11000" in str(e):
                try:
                    # Drop all indexes except _id and recreate
                    self.enhanced_reports_collection.drop_indexes()
                    self.enhanced_reports_collection.create_index("video_id", unique=True)
                    
                    # Retry the upsert
                    result = self.enhanced_reports_collection.update_one(
                        {"video_id": video_id},
                        {"$set": document},
                        upsert=True
                    )
                    return str(result.upserted_id) if result.upserted_id else video_id
                except Exception:
                    pass
            raise
    
    def get_enhanced_report(self, video_id: str) -> Optional[dict]:
        """
        Get enhanced report for a video.
        
        Args:
            video_id: Unique identifier for the video
        
        Returns:
            Enhanced report document or None
        """
        self._ensure_enhanced_reports_collection()
        
        result = self.enhanced_reports_collection.find_one({"video_id": video_id})
        if result:
            result.pop("_id", None)  # Remove MongoDB ID
        return result
    
    def get_historical_reports(
        self,
        exclude_video_id: str = None,
        limit: int = 5
    ) -> List[dict]:
        """
        Get historical VLM analysis summaries for context.
        
        Args:
            exclude_video_id: Video ID to exclude from results
            limit: Maximum number of reports to return
        
        Returns:
            List of historical report summaries
        """
        query = {}
        if exclude_video_id:
            query["video_id"] = {"$ne": exclude_video_id}
        
        # Aggregate to get summary per video
        pipeline = [
            {"$match": query},
            {"$sort": {"analyzed_at": -1}},
            {"$group": {
                "_id": "$video_id",
                "video_id": {"$first": "$video_id"},
                "analyzed_at": {"$first": "$analyzed_at"},
                "avg_risk_score": {"$avg": "$risk_score"},
                "max_risk_score": {"$max": "$risk_score"},
                "total_analyses": {"$sum": 1},
                "sample_analysis": {"$first": "$analysis"}
            }},
            {"$sort": {"analyzed_at": -1}},
            {"$limit": limit}
        ]
        
        results = list(self.analyses_collection.aggregate(pipeline))
        
        # Format results
        historical = []
        for r in results:
            # Extract critical observations from sample analysis
            sample = r.get("sample_analysis", {})
            observations = sample.get("observations", [])
            critical_obs = [
                obs for obs in observations
                if obs.get("risk_level") in ["critical", "warning", "high"]
            ]
            
            historical.append({
                "video_id": r.get("video_id", ""),
                "analyzed_at": r.get("analyzed_at", "").isoformat() if r.get("analyzed_at") else "",
                "avg_risk_score": round(r.get("avg_risk_score", 0), 2),
                "max_risk_score": r.get("max_risk_score", 0),
                "critical_observations": critical_obs[:3]  # Limit to top 3
            })
        
        return historical
    
    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
    
    def __enter__(self):
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

