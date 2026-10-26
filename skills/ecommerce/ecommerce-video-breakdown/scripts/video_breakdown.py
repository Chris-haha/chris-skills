#!/usr/bin/env python3
"""Public CLI for the ecommerce evidence workflow (Python 3.9+ standard library)."""
import argparse
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from archive import Archive, identity, read_json, write_json
from analysis import prepare, validate_workspace
from reports import render
from upstream import parse_input_text, extract_url
from portable import file_lock, resolve_runtime, setup_runtime
from excel_export import export_excel


def emit(value):
    print(json.dumps(value,ensure_ascii=False,indent=2))


@contextlib.contextmanager
def workspace_lock(root):
    root.mkdir(parents=True, exist_ok=True)
    with file_lock(root / '.workflow.lock', message='该工作区已有任务运行，请等待完成后重试'):
        yield


def skill_root():
    return Path(__file__).resolve().parents[1]


def doctor(workspace=None, config_path=None):
    runtime = resolve_runtime(workspace, config_path)
    bundled = skill_root() / 'scripts/public_media.py'
    exists = lambda key: bool(runtime.get(key) and shutil.which(str(runtime[key])))
    def runnable(key, arguments, signature):
        if not exists(key):
            return False
        try:
            check = subprocess.run([str(runtime[key]), *arguments], capture_output=True,
                                   text=True, encoding='utf-8', errors='replace', timeout=15)
            return check.returncode == 0 and signature in (check.stdout + check.stderr).lower()
        except (OSError, subprocess.SubprocessError):
            return False
    python_ok = runnable('python', ['--version'], 'python')
    ffmpeg_ok = runnable('ffmpeg', ['-version'], 'ffmpeg version')
    ffprobe_ok = runnable('ffprobe', ['-version'], 'ffprobe version')
    cpp_model = Path(runtime['whisperModel']) if runtime.get('whisperModel') else None
    faster_model = runtime.get('fasterWhisperModel')
    transcription = bool((exists('whisperCli') and cpp_model and cpp_model.is_file()) or
                         (faster_model and Path(faster_model).is_dir() and runtime.get('transcriptionBackend') == 'faster-whisper'))
    if transcription and runtime.get('transcriptionBackend') == 'faster-whisper':
        env = {**os.environ, 'PYTHONPATH':os.pathsep.join(runtime.get('packagePaths') or []),
               'PYTHONUTF8':'1', 'PYTHONIOENCODING':'utf-8'}
        try:
            check = subprocess.run([str(runtime['python']), '-c',
                                    'from faster_whisper import WhisperModel; import sys; '
                                    'WhisperModel(sys.argv[1], device="cpu", compute_type="int8", local_files_only=True)',
                                    str(faster_model)],
                                   capture_output=True, text=True, encoding='utf-8', env=env, timeout=30)
            transcription = check.returncode == 0
        except (OSError, subprocess.SubprocessError):
            transcription = False
    capabilities = {'archive': True, 'html': True, 'excel': True, 'anonymous_parser': bundled.is_file(),
                    'video_frames': ffmpeg_ok and ffprobe_ok, 'local_transcription': transcription}
    return {'ok': bundled.is_file(), 'skill_root': str(skill_root()), 'capabilities': capabilities,
            'checks': {'python': python_ok, 'ffmpeg': ffmpeg_ok, 'ffprobe': ffprobe_ok,
                       'anonymous_only': True, 'repository_dependency': False},
            'runtime': runtime, 'parser_sha256': hashlib.sha256(bundled.read_bytes()).hexdigest() if bundled.is_file() else None,
            'next': '缺少视频工具时运行 setup --workspace <工作区>；需要本地转录时再加 --with-transcription。',
            'note': '环境检查不访问平台。解析代码和Excel基础写入器随Skill提供，平台是否允许匿名访问需单独验证。'}


def distributable_files(source):
    excluded = {'__pycache__', 'node_modules', '.venv', 'workspace', 'cache', 'models', 'reports', 'runtime'}
    for path in sorted(source.rglob('*')):
        relative = path.relative_to(source)
        if not path.is_file() or (relative.parts[0] not in ('scripts', 'references', 'assets', 'agents') and
                                  relative.as_posix() not in ('SKILL.md', 'LICENSE', 'COMMERCIAL-LICENSE.md', 'THIRD_PARTY_NOTICES.md')):
            continue
        if any(part in excluded for part in relative.parts) or path.suffix in ('.pyc', '.pyo', '.log', '.tmp'):
            continue
        if path.name in ('runtime.local.json', 'config.json', '.DS_Store') or 'cookie' in path.name.lower() or path.name.startswith('.env'):
            continue
        if path.is_symlink():
            raise ValueError('Skill分发文件不能依赖外部符号链接：' + str(relative))
        yield path, relative


def default_install_target():
    for parent in (Path.cwd(), *Path.cwd().parents):
        if (parent / '.git').exists() or (parent / 'AGENTS.md').is_file():
            return parent / '.agents/skills/ecommerce-video-breakdown'
    home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    return home / 'skills/ecommerce-video-breakdown'


def install_project(target=None):
    source = skill_root()
    target = Path(target).expanduser().absolute() if target else default_install_target()
    if target.is_symlink():
        raise ValueError('安装目标是符号链接，请先核对，避免覆盖其他源码')
    if target.resolve() == source:
        return {'ok': True, 'source': str(source), 'installed': str(target), 'already_installed': True}
    if target.resolve().is_relative_to(source):
        raise ValueError('安装目标不能位于Skill源码内部')
    previous=read_json(target/'.installed-manifest.json',{}).get('files',[])
    files=[]
    for p, relative in distributable_files(source):
        dest=target/relative
        if dest.is_symlink() or not dest.resolve().is_relative_to(target.resolve()):
            raise ValueError('安装副本中存在符号链接，停止更新：'+str(relative))
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,dest)
        files.append(relative.as_posix())
    for obsolete in set(previous)-set(files):
        candidate=(target/obsolete).resolve()
        if candidate.is_relative_to(target.resolve()) and candidate.is_file():
            candidate.unlink()
    write_json(target/'.installed-manifest.json',{'name':'ecommerce-video-breakdown','version':'2.1.0','files':sorted(files)})
    return {'ok':True,'source':str(source),'installed':str(target),'files':len(files)}


def pack(output):
    source = skill_root()
    output = Path(output).expanduser().absolute()
    if output.suffix.lower() != '.zip':
        raise ValueError('Skill分发包需要.zip扩展名')
    files = list(distributable_files(source))
    manifest = {'name':'ecommerce-video-breakdown','version':'2.1.0',
                'files':[{'path':rel.as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p,rel in files]}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + '.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            for p, relative in files:
                archive.write(p, 'ecommerce-video-breakdown/' + relative.as_posix())
            archive.writestr('ecommerce-video-breakdown/package-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return {'ok': True, 'output':str(output), 'version':'2.1.0', 'files':len(files),
            'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='电商视频证据归档、拆解任务与博主蒸馏报告；内容分析由Codex完成。')
    commands=parser.add_subparsers(dest='command',required=True)
    for name,help_text in [('doctor','检查本机可用能力，不访问平台'),('setup','在工作区准备缺少的运行依赖'),
                          ('ingest','使用Skill内置解析器处理链接清单'),
                          ('import','直接导入已有解析产物'),('confirm','核对后人工确认博主身份'),
                          ('review','复核口播质量并选择口播或画面分析，不重新转录'),
                          ('attach-media','关联已有本地原视频，不下载或转录'),
                          ('index','查看归档与失败记录'),('prepare','准备全文逐条与全量蒸馏任务'),
                          ('validate','校验分析证据、版本与覆盖'),('render','更新Excel总表及图文报告'),
                          ('export-excel','追加或更新同一份Excel，保留备注和自建列'),
                          ('install','将完整Skill安装到指定位置'),('pack','打包独立Skill，不含本机数据')]:
        sub=commands.add_parser(name,help=help_text)
        if name not in ('doctor','install','pack'):
            sub.add_argument('--workspace',required=True,type=Path,help='新项目独立工作区')
        if name == 'doctor':
            sub.add_argument('--workspace',type=Path,help='读取该工作区的运行配置，可省略')
        if name in ('doctor','ingest','setup'):
            sub.add_argument('--config',type=Path,help='本机配置文件，默认使用工作区runtime.local.json')
        if name == 'setup':
            sub.add_argument('--with-transcription',action='store_true',help='同时准备本地Whisper及模型，首次需要联网下载')
        if name == 'install':
            sub.add_argument('--target',type=Path,help='目标Skill文件夹，默认当前项目.agents/skills或个人技能目录')
        if name == 'pack':
            sub.add_argument('--output',required=True,type=Path,help='独立Skill的ZIP分发包')
        if name in ('ingest','import'):
            sub.add_argument('--creator-id',default='',help='已核对的平台账号ID；省略时来源缺ID则待确认')
            sub.add_argument('--creator-name',default='',help='已核对的博主昵称')
            sub.add_argument('--refresh',action='store_true',help='明确重取已存在视频，保留旧稿修订和人工分析')
        if name=='ingest':
            sub.add_argument('--input',required=True,help='TXT/Markdown分享文本或JSON清单；- 为标准输入')
            sub.add_argument('--retry-failed',action='store_true',help='仅处理当前工作区中已有的失败链接')
        if name=='import':
            sub.add_argument('--source',required=True,type=Path,help='含metadata.json与transcript.txt的目录或批量归档根目录')
        if name=='confirm':
            sub.add_argument('--video-key',required=True)
            sub.add_argument('--creator-id',required=True)
            sub.add_argument('--creator-name',required=True)
        if name=='prepare':
            sub.add_argument('--group-size',type=int,default=10)
        if name=='review':
            sub.add_argument('--video-key',required=True)
            sub.add_argument('--narration',required=True,choices=('usable','unusable','missing'))
            sub.add_argument('--mode',required=True,choices=('speech','visual','mixed'))
            sub.add_argument('--reason',required=True)
            sub.add_argument('--basis',required=True,choices=('text_review','audio_review'))
        if name=='attach-media':
            sub.add_argument('--video-key',required=True)
            sub.add_argument('--source',required=True,type=Path)
            sub.add_argument('--duration',required=True,type=float,help='FFprobe核对的实际原媒体秒数')
        if name in ('render','export-excel'):
            sub.add_argument('--output' if name=='export-excel' else '--excel-output',dest='excel_output',type=Path,
                             help='指定已有总表或新建路径；以后更新沿用此路径')
            sub.add_argument('--previews',type=Path,help='可选：将各工作表预览保存到指定目录供验收')
        if name=='render':
            sub.add_argument('--html-only',action='store_true',help='仅刷新图文资料页，不作为Excel最终交付')
    args=parser.parse_args(argv)
    try:
        if args.command=='doctor':
            result=doctor(args.workspace,args.config);emit(result);return 0 if result['ok'] else 1
        if args.command=='install':
            emit(install_project(args.target));return 0
        if args.command=='pack':
            emit(pack(args.output));return 0
        root=args.workspace.resolve()
        with workspace_lock(root):
            if args.command=='setup':
                result=setup_runtime(root,with_transcription=args.with_transcription,config_path=args.config)
                emit(result);return 0 if result.get('ok') else 1
            archive=Archive(root)
            if args.command=='index':
                emit(archive.index())
            elif args.command=='confirm':
                emit(archive.confirm_creator(args.video_key,args.creator_id,args.creator_name))
            elif args.command=='review':
                emit(archive.review_narration(args.video_key,args.narration,args.mode,args.reason,args.basis))
            elif args.command=='attach-media':
                emit(archive.attach_media(args.video_key,args.source,args.duration))
            elif args.command=='import':
                if not args.source.is_dir():
                    raise ValueError('导入源目录不存在')
                if args.source.resolve()==root or root.is_relative_to(args.source.resolve()):
                    raise ValueError('导入源不能包含目标工作区，避免把新归档再次递归导入')
                records=archive.import_directory(args.source,{'creator_id':args.creator_id,'creator_name':args.creator_name},args.refresh)
                emit({'imported':len(records),'records':[{'video_key':r['video_key'],'status':r['status']} for r in records], 'failures':archive.index()['failures']})
                return 0 if records and not archive.index()['failures'] else 1
            elif args.command=='ingest':
                text=sys.stdin.read() if args.input=='-' else Path(args.input).read_text(encoding='utf-8')
                rows=parse_input_text(text)
                if not rows:
                    raise ValueError('清单中没有找到链接')
                if args.retry_failed:
                    failed={f['url'] for f in archive.index()['failures']}
                    rows=[r for r in rows if r['url'] in failed]
                outcomes=[]
                for row in rows:
                    url=row['url']
                    try:
                        key=identity(url)['video_key']
                        old=next((r for r in archive.records() if r['video_key']==key or url in r.get('source_urls',[])),None)
                        if old and not args.refresh:
                            outcomes.append({'video_key':old['video_key'],'status':'skipped_existing','url':url});continue
                        print(f'处理链接 {len(outcomes)+1}/{len(rows)}',file=sys.stderr)
                        result=extract_url(url,root,config_path=args.config)
                        result.update({k:row[k] for k in ('metrics','comments','performance_label') if k in row})
                        record=archive.add(result,requested_url=url,creator_override={
                            'creator_id':row.get('creator_id') or args.creator_id,
                            'creator_name':row.get('creator_name') or args.creator_name},refresh=args.refresh)
                        if result.get('media_file') and result.get('media_duration'):
                            media_path=Path(result['media_file']).resolve()
                            if not media_path.is_relative_to(root):
                                raise ValueError('解析器返回的媒体不在当前工作区内')
                            record=archive.attach_media(record['video_key'],media_path,float(result['media_duration']))
                        outcomes.append({'video_key':record['video_key'],'status':record['status'],'url':url})
                    except (ValueError,RuntimeError,OSError,json.JSONDecodeError) as exc:
                        archive.failure(url,str(exc));outcomes.append({'url':url,'status':'failed','reason':str(exc)})
                emit({'outcomes':outcomes,'failures':archive.index()['failures']})
                return 1 if any(r['status']=='failed' for r in outcomes) else 0
            elif args.command=='prepare':
                result=prepare(root,args.group_size)
                emit({'videos':len(result['videos']),'groups':len(result['groups']),'creators':len(result['creators']),
                      'excluded':len(result['excluded']),'tasks':str(root/'analysis/tasks.json'),
                      'next':'Codex应完整阅读任务原文和图片后填写analyses，不是空模板生成即分析完成。'})
            elif args.command=='validate':
                result=validate_workspace(root);emit(result);return 0 if result['ok'] else 1
            elif args.command=='render':
                if args.html_only:
                    output=render(root);emit({'reports':str(output),'entry':str(output/'index.html')})
                else:
                    result=export_excel(root,args.excel_output,args.previews)
                    emit({'entry':str(root/'reports/index.html'),'excel':result})
            elif args.command=='export-excel':
                emit(export_excel(root,args.excel_output,args.previews))
        return 0
    except (ValueError,OSError,StopIteration,TypeError,KeyError) as exc:
        emit({'error':str(exc) or '找不到指定记录'});return 1


if __name__=='__main__':
    raise SystemExit(main())
