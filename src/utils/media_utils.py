import re
import os

def extract_media_info(file_name: str) -> dict:
    """从文件名提取媒体信息
    
    支持格式:
    - 电影: 电影名 (年份).strm, 电影名.年份.strm
    - 电视剧: 剧名 (年份)/Season 01/剧名 S01E01.strm, 剧名.S01E01.strm
    """
    # 移除扩展名和路径
    name_without_ext = os.path.splitext(os.path.basename(file_name))[0]
    
    info = {
        'title': '',
        'year': None,
        'season': None,
        'episode': None,
        'type': 'movie',  # 默认为电影
        'original_name': name_without_ext
    }
    
    # 电视剧模式匹配
    tv_patterns = [
        # 剧名 S01E01 或 剧名.S01E01
        r'^(?P<title>.+?)[.\s]*[Ss](?P<season>\d+)[Ee](?P<episode>\d+)',
        # 剧名 1x01
        r'^(?P<title>.+?)[.\s]*(?P<season>\d+)x(?P<episode>\d+)',
        # 剧名 第01季 第01集
        r'^(?P<title>.+?)[.\s]*第(?P<season>\d+)[季季][.\s]*第(?P<episode>\d+)[集集]',
    ]
    
    for pattern in tv_patterns:
        match = re.search(pattern, name_without_ext, re.IGNORECASE)
        if match:
            info['type'] = 'tv'
            info['title'] = match.group('title').strip()
            info['season'] = int(match.group('season'))
            info['episode'] = int(match.group('episode'))
            break
    
    # 如果不是电视剧，尝试提取电影信息
    if info['type'] == 'movie':
        movie_patterns = [
            # 标题 (年份)
            r'^(?P<title>.+?)\s*\((?P<year>\d{4})\)',
            # 标题.年份
            r'^(?P<title>.+?)\s*(?P<year>\d{4})',
            # 只有标题
            r'^(?P<title>.+?)$',
        ]
        
        for pattern in movie_patterns:
            match = re.search(pattern, name_without_ext, re.IGNORECASE)
            if match:
                info['title'] = match.group('title').strip()
                if 'year' in match.groupdict():
                    info['year'] = int(match.group('year'))
                break
    
    # 清理标题
    if info['title']:
        # 移除多余空格和特殊字符
        info['title'] = re.sub(r'[._-]+', ' ', info['title']).strip()
    else:
        info['title'] = name_without_ext
    
    return info

def generate_nfo_content(media_info: dict, scraped_data: dict) -> str:
    """生成NFO文件内容"""
    if media_info['type'] == 'movie':
        return generate_movie_nfo(media_info, scraped_data)
    else:
        return generate_tv_nfo(media_info, scraped_data)

def generate_movie_nfo(media_info: dict, scraped_data: dict) -> str:
    """生成电影NFO"""
    nfo_content = f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<movie>
    <title>{media_info['title']}</title>
    <originaltitle>{media_info['title']}</originaltitle>
    <sorttitle>{media_info['title']}</sorttitle>
    <year>{media_info.get('year', '')}</year>
    <outline></outline>
    <plot>{scraped_data.get('overview', '')}</plot>
    <tagline></tagline>
    <runtime></runtime>
    <thumb aspect="poster">{scraped_data.get('poster_path', '')}</thumb>
    <fanart>
        <thumb>{scraped_data.get('backdrop_path', '')}</thumb>
    </fanart>
    <mpaa></mpaa>
    <playcount>0</playcount>
    <lastplayed></lastplayed>
    <id>{scraped_data.get('id', '')}</id>
    <genre></genre>
    <country></country>
    <premiered>{media_info.get('year', '')}</premiered>
    <status></status>
    <code></code>
    <aired></aired>
    <studio></studio>
    <trailer></trailer>
    <fileinfo>
        <streamdetails>
            <video>
                <codec></codec>
                <aspect></aspect>
                <width></width>
                <height></height>
                <durationinseconds></durationinseconds>
                <stereomode></stereomode>
            </video>
            <audio>
                <codec></codec>
                <language></language>
                <channels></channels>
            </audio>
        </streamdetails>
    </fileinfo>
    <path></path>
    <filenameandpath></filenameandpath>
</movie>"""
    
    return nfo_content

def generate_tv_nfo(media_info: dict, scraped_data: dict) -> str:
    """生成电视剧NFO"""
    nfo_content = f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<episodedetails>
    <title>{media_info['title']}</title>
    <showtitle>{media_info['title']}</showtitle>
    <season>{media_info.get('season', 1)}</season>
    <episode>{media_info.get('episode', 1)}</episode>
    <year>{media_info.get('year', '')}</year>
    <outline></outline>
    <plot>{scraped_data.get('overview', '')}</plot>
    <thumb aspect="poster">{scraped_data.get('still_path', '')}</thumb>
    <fanart>
        <thumb>{scraped_data.get('backdrop_path', '')}</thumb>
    </fanart>
    <mpaa></mpaa>
    <playcount>0</playcount>
    <lastplayed></lastplayed>
    <id>{scraped_data.get('id', '')}</id>
    <genre></genre>
    <country></country>
    <premiered>{media_info.get('year', '')}</premiered>
    <status></status>
    <code></code>
    <aired></aired>
    <studio></studio>
    <trailer></trailer>
    <fileinfo>
        <streamdetails>
            <video>
                <codec></codec>
                <aspect></aspect>
                <width></width>
                <height></height>
                <durationinseconds></durationinseconds>
                <stereomode></stereomode>
            </video>
            <audio>
                <codec></codec>
                <language></language>
                <channels></channels>
            </audio>
        </streamdetails>
    </fileinfo>
    <path></path>
    <filenameandpath></filenameandpath>
</episodedetails>"""
    
    return nfo_content

def sanitize_filename(filename: str) -> str:
    """清理文件名，移除不合法字符"""
    # Windows不合法字符
    illegal_chars = r'[<>:"|?*\/]'
    # 替换为空格
    sanitized = re.sub(illegal_chars, ' ', filename)
    # 移除多余空格
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    # 限制长度
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    
    return sanitized