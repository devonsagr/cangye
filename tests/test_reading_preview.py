from app import reading_preview,store
from test_automatic_collection import local

TEXT='工具把原文和用户批注分开保存，避免混淆作者的说法与个人理解。\n\n图片按原文位置保存，顶部的五张图片也是同一条材料的一部分。\n\n后来再次导入时，只给新材料排队，已有材料的原文、批注和处理状态保持。\n\n来源指纹可以阻止已经彻底删除的帖子再次被误当成新材料。\n\n真正整理材料时，应依据原文和用户自己的批注，不把速览当成结论。'

def test_preview_uses_original_sentences_without_model_or_notes():
    item={'body':TEXT,'notes':'仅在我的备注中的秘密目的','summary':'AI编出的不同看法','content':{},'platform':'heybox'}
    r=reading_preview.make(item)
    assert r and r['method']=='extractive' and not r['model_used'] and r['reading_only']
    assert '秘密目的' not in r['text'] and 'AI编出的' not in r['text']
    assert all(sentence in TEXT for sentence in r['text'].splitlines())

def test_short_posts_and_video_references_do_not_get_fake_summaries():
    assert reading_preview.make({'body':'短帖直接阅读原文。','content':{}})['text']=='短帖直接阅读原文。'
    assert reading_preview.make({'body':TEXT,'content':{'media_kind':'video_reference'}}) is None

def test_gallery_does_not_hide_the_list_excerpt():
    body='\n\n'.join(f'![图片](capture-id/images/{i}.png)' for i in range(5))+'\n\n这是图片后面的作者原文。'
    assert reading_preview.excerpt({'body':body,'content':{}})=='这是图片后面的作者原文。'

def test_reading_preview_is_not_saved_or_exported(local):
    client,_=local
    mid=client.post('/api/materials',json={'url':'https://x.com/i/status/76001','text':TEXT}).json()['id']
    before=store.get(mid)
    detail=client.get('/api/materials/'+mid).json()
    assert detail['reading_preview']['reading_only']
    assert store.get(mid)==before and 'reading_preview' not in store.markdown(before)
    payload=client.post('/api/materials/'+mid+'/push-preview',json={'destination':'markdown'}).json()['payload']
    assert 'reading_preview' not in payload and '原文摘录' not in payload['markdown']


def test_context_is_kept_instead_of_picking_repeated_dates_and_platform_fragments():
    text='《合成冒险》是一款多人协作游戏，这篇报道介绍了开发团队宣布的主机发行计划。\n\n也将会登陆Switch 2平台\n\n游戏将在10月16号在Switch发售，新增的协作模式允许四名玩家共同挑战关卡。\n\nSwitch平台支持跨平台存档。'*2
    result=reading_preview.make({'body':text,'content':{}})
    assert result['text'].startswith('《合成冒险》')
    assert '发行计划' in result['text'] and '协作模式' in result['text']
    assert result['source']=='原文' and not result['model_used']

def test_fragments_and_ui_noise_do_not_become_a_fake_subject():
    text='收藏 123\n\n也将登陆Switch平台，发布日期会稍后公布。\n\n此外会推出新的音乐版本，更多信息将在后续公布。'*3
    assert reading_preview.make({'body':text,'content':{}}) is None

def test_default_summary_covers_long_transcript_tail_without_network(monkeypatch):
    import socket
    monkeypatch.setattr(socket,'create_connection',lambda *a,**k:(_ for _ in ()).throw(AssertionError('local summary must not connect')))
    lines=['这段视频介绍怎样保护材料原文和自己的备注。','首先需要保存对应来源，防止后续处理丢失依据。']
    lines+=['中间展示一个完整的保存步骤，并说明文档的组织方式。']*1600
    lines+=['最终结论是整理必须以原文和本人备注为依据，不用自动摘要代替理解。']
    item={'platform':'bilibili','body':'仅有的视频简介，不是字幕。','notes':'我的秘密批注','content':{'segments':[{'text':t,'start':i,'end':i+1} for i,t in enumerate(lines)]},'collection':'partial'}
    result=reading_preview.make(item)
    assert '最终结论' in result['text'] and result['text'].startswith(lines[0])
    assert all(s in lines for s in result['text'].splitlines())
    assert '秘密批注' not in result['text'] and '视频简介' not in result['text']
    assert result['model_used'] is False and '部分' in result['basis'] and result['source']=='字幕'

def test_image_only_and_title_only_cannot_invent_a_default_summary():
    assert reading_preview.make({'title':'只有标题','body':'![图片](images/a.png)','content':{}}) is None
