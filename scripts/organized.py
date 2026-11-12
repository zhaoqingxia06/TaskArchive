"""Read-only v1 adapter and semantic v2 projection; leaves every source file intact."""
import hashlib
import json
from pathlib import Path
import re
import tempfile
import archive_v2 as a


def sanitized(text):
    text = a.SECRET.sub('[凭据已隐藏]', text)
    text = re.sub(r'(?i)((?:api[_ ]?key|安全钥匙|token|key)\s*[：:=]\s*)[a-z0-9_-]{20,}', r'\1[凭据已隐藏]', text)
    return text


def build_organized(root, tasks, legacy_html, previous_data=None):
    root = Path(root)
    plan = a.read(root/'data/organized_catalog.json')
    selectors = {t['id']: t for t in tasks}
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        (work/'data/contributions').mkdir(parents=True)
        a.write(work/'archive.config.json', {'title':'TaskArchive','timezone':'Asia/Shanghai'})
        documents = {}
        for task in tasks:
            source = task['source']
            label = '仓库已有会话快照，非全账号实时历史' if source != 'chatgpt' else '历史人工整理稿，非逐字原文；时间未核验'
            doc = documents.setdefault(source, {'schema_version':2,'source':source,'client':'unknown','coverage':{'scope':label},'conversations':[]})
            conv = {'id':task['id'],'messages':[]}
            for index,m in enumerate(task['messages']):
                text = m['text'].strip()
                if text.startswith(('# In app browser:','# Browser comments:','{"WARNING_BANNER"')):
                    continue
                if re.fullmatch(r'(继续|好的?|可以|愿意|认可|已(?:经)?登[录陆](?:了|成功)?|下一步(?:呢)?|再跑一次|1|2|是|[Oo][Kk]|没问题了?)[。！!，, ]*',text):
                    continue
                conv['messages'].append({'id':str(index),'role':'user','text':sanitized(m['text']),
                    'sent_at':m['time'] if source!='chatgpt' else None,
                    'attachments':m.get('attachments',[]),'record_kind':'legacy_summary' if source=='chatgpt' else 'original'})
            if conv['messages']:doc['conversations'].append(conv)
        for source,doc in documents.items():a.write(work/f'data/contributions/{source}.json',doc)
        for source_path in (root/'data/organized_sources').glob('*.json'):
            a.write(work/'data/contributions'/source_path.name,a.read(source_path))
        messages,coverage=a.load_messages(work)
        requirements=[]
        for req in plan['requirements']:
            refs=list(req.get('message_refs',[]))
            for selector in req.get('legacy_selectors',[]):
                t=selectors.get(selector['task_id'])
                if not t:continue
                refs.extend(a.key(t['source'],t['id'],str(j)) for j in selector['indices'])
            refs=list(dict.fromkeys(ref for ref in refs if ref in messages))
            if not refs:continue
            record={k:v for k,v in req.items() if k!='legacy_selectors'}
            record['message_refs']=refs
            # Fingerprints bind the checked-in LLM-authored selectors to the exact reviewed text.
            # A new source message is never silently assigned to an existing demand.
            reviewed=req.get('evidence_sha256')
            actual=a.fingerprint(refs,messages)
            if reviewed and reviewed!=actual:
                raise ValueError('已整理原文变化，需重新复核需求：'+req['id'])
            record['evidence_sha256']=actual
            requirements.append(record)
        catalog={k:plan[k] for k in ('schema_version','categories','projects')}
        catalog['requirements']=requirements
        excluded_tasks=set(plan.get('excluded_task_ids',[]))
        catalog['excluded_messages']=[{'ref':ref,'reason':'原会话缺少可独立识别的目标，暂不进入需求列表'} for ref,m in messages.items() if m['conversation_id'] in excluded_tasks]
        a.write(work/'data/catalog.json',catalog)
        data=a.compile_site(work)
        data['coverage'].append({'source':'说明','scope':f'基于已接入的 {len(tasks)} 个会话；未关联的新消息暂待整理，不假设已完成自动采集'})
        data['stats']['original_messages']=sum(m.get('record_kind')=='original' for m in data['messages'].values())
        data['stats']['legacy_summaries']=sum(m.get('record_kind')=='legacy_summary' for m in data['messages'].values())
        old=previous_data or {}
        if old.get('schema_version')==2 and {k:v for k,v in old.items() if k!='generated_at'}=={k:v for k,v in data.items() if k!='generated_at'}:
            data['generated_at']=old['generated_at']
        page=a.render(data)
        # Full legacy data remains in the existing source files. Do not republish unfiltered
        # legacy HTML as the default page or include excluded text in v2 JSON.
        dist=root/'dist';dist.mkdir(exist_ok=True)
        (root/'index.html').write_text(page)
        (dist/'index.html').write_text(page)
        (dist/'knowledge.html').write_text((root/'assets/knowledge.html').read_text(encoding='utf-8'), encoding='utf-8')
        (dist/'materials.html').write_text((root/'assets/materials.html').read_text(encoding='utf-8'), encoding='utf-8')
        (dist/'materials-ai.js').write_text((root/'assets/materials-ai.js').read_text(encoding='utf-8'), encoding='utf-8')
        a.write(dist/'knowledge.json', a.read(root/'data/knowledge.json'))
        # Source snapshots and Git history retain legacy records without republishing unfiltered HTML.
        a.write(dist/'tasks.json',data)
        a.write(dist/'feed.json',{'schema_version':2,'stats':data['stats'],'data_url':'./tasks.json','sources':[c['source'] for c in coverage]})
        return data
