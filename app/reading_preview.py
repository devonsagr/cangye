"""Local extractive reading aid, excluded from processing, export and AI prompts."""
from functools import lru_cache
import re

def plain(text):
    text=re.sub(r'!\[[^\]]*\]\([^)]*\)','',text or '')
    text=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',text)
    return re.sub(r'(?m)^\s*[#>*-]+\s*','',text).strip()

FRAGMENT=re.compile(r'^(?:也将|同时也|此外|其中|与此同时|该作|该游戏|这款|其(?:中|将|在)|而且|以及|also\b|it\b|they\b)',re.I)
NOISE=re.compile(r'^(?:点赞|收藏|关注|评论|举报|分享|返回顶部|展开全文|加载更多|登录后查看|相关阅读|相关推荐)(?:[\s\d:：·|]*)$')

def opening(block):
    if len(block)<=360:return block
    sentences=re.findall(r'.+?[。！？!?](?:\s|$)|.+$',block)
    chosen=[]
    for sentence in sentences:
        if sum(map(len,chosen))+len(sentence)>360:break
        chosen.append(sentence)
    return ''.join(chosen).strip() or None

@lru_cache(maxsize=1024)
def extract(text):
    # Keep the first substantive paragraph and its adjacent context together.
    # Repeated dates/platform names must not replace the subject with two scattered lines.
    blocks=[b.strip() for b in re.split(r'\n\s*\n',text) if b.strip()]
    if len(blocks)==1:blocks=[b.strip() for b in text.splitlines() if b.strip()]
    blocks=[b for b in blocks if not NOISE.fullmatch(b)]
    first=next((i for i,b in enumerate(blocks) if not FRAGMENT.search(b) and opening(b)),None)
    if first is None:return None
    selected=[opening(blocks[first])]
    for block in blocks[first+1:first+3]:
        piece=opening(block)
        if not piece or piece in selected or sum(map(len,selected))+len(piece)>480:break
        selected.append(piece)
    return '\n'.join(selected)

def make(item):
    content=item.get('content',{})
    if content.get('media_kind')=='video_reference':return None
    if content.get('segments') and item.get('platform') in ('bilibili','youtube','douyin'):
        text='\n'.join(s['text'] for s in content['segments']);source='字幕'
    else:text=plain(item.get('body',''));source='原文'
    result=local_summary(text)
    if not result:return None
    return {'text':result,'method':'extractive','source':source,'reading_only':True,'model_used':False,
            'basis':'已取得的部分文字' if item.get('collection') in ('partial','failed','queued','running','paused') else '已取得的文字'}

@lru_cache(maxsize=512)
def local_summary(text):
    """Extract complete source sentences in order; no network or invented wording."""
    sentences=[s.strip() for s in re.findall(r'[^。！？!?\n]+[。！？!?]+|[^。！？!?\n]+(?:\n|$)',text)]
    sentences=[s for s in sentences if s and not NOISE.fullmatch(s)]
    # Keep the subject at the start, then choose key statements across the source.
    first=next((i for i,s in enumerate(sentences) if not FRAGMENT.search(s)),None)
    if first is None:return None
    if len(text)<=480:return '\n'.join(sentences[first:])
    chosen={first}
    if first+1<len(sentences):chosen.add(first+1)
    conclusion=re.compile(r'结论|总结|因此|所以|最终|建议|关键|核心|结果|需要|必须|conclusion|therefore|recommend|important',re.I)
    remaining=list(range(first+2,len(sentences)))
    if remaining:
        # Include middle and ending evidence, even after a long transcript's first 24k.
        for start,end in ((first+2,(first+len(sentences))//2),((first+len(sentences))//2,len(sentences))):
            candidates=[i for i in range(max(first+2,start),end) if not FRAGMENT.search(sentences[i])]
            if candidates:chosen.add(max(candidates,key=lambda i:(bool(conclusion.search(sentences[i])),i if end==len(sentences) else -i)))
    output=[];size=0
    for i in sorted(chosen):
        sentence=sentences[i]
        if size+len(sentence)>640:
            if not output:output.append(sentence[:480]+'…')
            continue
        output.append(sentence);size+=len(sentence)
    return '\n'.join(output) or None

def excerpt(item):
    preview=make(item)
    if preview:return preview['text'].replace('\n',' ')[:240]
    content=item.get('content',{})
    if content.get('media_kind')=='video_reference':return '原视频链接与封面已保留，尚未转写'
    text=plain(item.get('body',''))
    if not text and content.get('gallery_count'):text=f"图片帖 · {content['gallery_count']} 张图片"
    if not text and content.get('segments'):text=content['segments'][0]['text']
    return text[:240]
