from flask import Blueprint
from controllers.video_controller import (
    get_videos,
    download_by_url_api,
    download_by_keyword_api,
    extract_frames,
    extract_frames_result,
    youtube_extract_result
)

video_bp = Blueprint('video', __name__)

video_bp.route('/api/videos', methods=['GET'])(get_videos)
video_bp.route('/api/download/url', methods=['POST'])(download_by_url_api)
video_bp.route('/api/download/keyword', methods=['POST'])(download_by_keyword_api)

# Frames related to video downloads (moved from app.py where they were somewhat scattered)
video_bp.route('/api/frames/extract', methods=['POST'])(extract_frames)
video_bp.route('/api/frames/result', methods=['GET'])(extract_frames_result)
video_bp.route('/api/frames/youtube-result', methods=['GET'])(youtube_extract_result)
