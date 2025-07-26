from flask import Blueprint, jsonify, request, send_file
from flask_cors import cross_origin
import yt_dlp
import os
import tempfile
import re
from urllib.parse import urlparse

video_bp = Blueprint('video', __name__)

def is_valid_url(url):
    """Validate if the provided URL is valid"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def get_video_info(url):
    """Extract video information without downloading"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Extract available formats
            formats = []
            if 'formats' in info:
                for fmt in info['formats']:
                    if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':  # Video with audio
                        quality = fmt.get('height', 'Unknown')
                        filesize = fmt.get('filesize') or fmt.get('filesize_approx', 0)
                        
                        # Convert filesize to MB
                        size_mb = round(filesize / (1024 * 1024), 1) if filesize else 0
                        
                        formats.append({
                            'format_id': fmt['format_id'],
                            'quality': f"{quality}p" if quality != 'Unknown' else 'Unknown',
                            'format': fmt.get('ext', 'mp4').upper(),
                            'size': f"{size_mb} MB" if size_mb > 0 else "Unknown",
                            'url': fmt.get('url', ''),
                            'has_video': fmt.get('vcodec') != 'none',
                            'has_audio': fmt.get('acodec') != 'none'
                        })
            
            # Add audio-only format if available
            for fmt in info.get('formats', []):
                if fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
                    filesize = fmt.get('filesize') or fmt.get('filesize_approx', 0)
                    size_mb = round(filesize / (1024 * 1024), 1) if filesize else 0
                    
                    formats.append({
                        'format_id': fmt['format_id'],
                        'quality': 'Audio Only',
                        'format': 'MP3',
                        'size': f"{size_mb} MB" if size_mb > 0 else "Unknown",
                        'url': fmt.get('url', ''),
                        'has_video': False,
                        'has_audio': True
                    })
                    break
            
            # Sort formats by quality (video first, then audio)
            video_formats = [f for f in formats if f['has_video']]
            audio_formats = [f for f in formats if not f['has_video']]
            
            # Sort video formats by quality (descending)
            video_formats.sort(key=lambda x: int(x['quality'].replace('p', '')) if x['quality'].replace('p', '').isdigit() else 0, reverse=True)
            
            return {
                'title': info.get('title', 'Unknown Title'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'formats': video_formats[:3] + audio_formats[:1]  # Limit to top 3 video + 1 audio
            }
    except Exception as e:
        raise Exception(f"Failed to extract video info: {str(e)}")

@video_bp.route('/analyze', methods=['POST'])
@cross_origin()
def analyze_video():
    """Analyze video URL and return available formats"""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400
        
        url = data['url'].strip()
        if not url:
            return jsonify({'error': 'URL cannot be empty'}), 400
        
        if not is_valid_url(url):
            return jsonify({'error': 'Invalid URL format'}), 400
        
        # Extract video information
        video_info = get_video_info(url)
        
        return jsonify({
            'success': True,
            'data': video_info
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@video_bp.route('/download', methods=['POST'])
@cross_origin()
def download_video():
    """Download video in specified format"""
    try:
        data = request.get_json()
        if not data or 'url' not in data or 'format_id' not in data:
            return jsonify({'error': 'URL and format_id are required'}), 400
        
        url = data['url'].strip()
        format_id = data['format_id']
        
        if not is_valid_url(url):
            return jsonify({'error': 'Invalid URL format'}), 400
        
        # Create temporary directory for downloads
        temp_dir = tempfile.mkdtemp()
        
        # Configure yt-dlp options
        ydl_opts = {
            'format': format_id,
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }
        
        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            if os.path.exists(filename):
                return jsonify({
                    'success': True,
                    'download_url': f'/api/video/file/{os.path.basename(filename)}',
                    'filename': os.path.basename(filename),
                    'title': info.get('title', 'Unknown')
                })
            else:
                return jsonify({'error': 'Download failed'}), 500
                
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@video_bp.route('/supported-sites', methods=['GET'])
@cross_origin()
def get_supported_sites():
    """Get list of supported video platforms"""
    # Common supported sites by yt-dlp
    supported_sites = [
        {'name': 'YouTube', 'domain': 'youtube.com'},
        {'name': 'TikTok', 'domain': 'tiktok.com'},
        {'name': 'Instagram', 'domain': 'instagram.com'},
        {'name': 'Twitter/X', 'domain': 'twitter.com'},
        {'name': 'Facebook', 'domain': 'facebook.com'},
        {'name': 'Douyin', 'domain': 'douyin.com'},
        {'name': 'Vimeo', 'domain': 'vimeo.com'},
        {'name': 'Dailymotion', 'domain': 'dailymotion.com'},
    ]
    
    return jsonify({
        'success': True,
        'sites': supported_sites
    })

@video_bp.route('/health', methods=['GET'])
@cross_origin()
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'video-downloader-api',
        'version': '1.0.0'
    })

