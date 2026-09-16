#!/usr/bin/env python3
"""Apply a verified additive PARTY EXAM package on an idle booth; retain a rollback."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,time
parser=argparse.ArgumentParser();parser.add_argument('--repo',default='/home/kirniy/modular-arcade');args=parser.parse_args()
root=Path(args.repo).resolve();package=Path(__file__).resolve().parent
manifest=json.loads((package/'manifest.json').read_text())
for name,digest in manifest.items():
    assert hashlib.sha256((package/name).read_bytes()).hexdigest()==digest,'Package mismatch: '+name
status=subprocess.run(['systemctl','is-active','--quiet','artifact.service']).returncode==0
if status:
    snapshot=json.loads((root/'data/status.json').read_text())
    if time.time()-float(snapshot['timestamp'])>30 or str(snapshot.get('mode','')).lower() not in ('','idle','none'):
        raise SystemExit('Booth is active or idle state is stale; defer installation')
patch=package/'integration.patch'
check=subprocess.run(['git','apply','--check',str(patch)],cwd=root,capture_output=True)
already=check.returncode!=0 and subprocess.run(['git','apply','--reverse','--check',str(patch)],cwd=root,capture_output=True).returncode==0
assert check.returncode==0 or already,'Integration patch conflicts with live booth; review the live diff, do not overwrite'
payload=[n for n in manifest if n!='integration.patch']
for name in payload:
    if (root/name).exists():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==manifest[name],'Existing file differs: '+name
changed=['src/artifact/modes/manager.py','src/artifact/printing/manager.py','src/artifact/printing/photobooth_roll.py',*payload,'.env']
backup=root/'.deploy'/('party-exam-backup-'+time.strftime('%Y%m%d-%H%M%S'));backup.mkdir(parents=True,mode=0o700)
for name in changed:
    if (root/name).exists():
        dest=backup/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/name,dest)
(backup/'paths.json').write_text(json.dumps(changed))
python=root/'.venv/bin/python';assert python.exists(),'Booth virtual environment missing'
timer_active=subprocess.run(['systemctl','is-active','--quiet','artifact-update.timer']).returncode==0
if timer_active:subprocess.run(['sudo','-n','systemctl','stop','artifact-update.timer'],check=True)
try:
    if not already:subprocess.run(['git','apply',str(patch)],cwd=root,check=True)
    for name in payload:
        dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(package/name,dest)
    envfile=root/'.env';lines=envfile.read_text().splitlines() if envfile.exists() else []
    values={'ARTIFACT_QUEST_PROFILE':'party_exam','ARTIFACT_SPIDERVERSE_QUEST_ENABLED':'true'}
    lines=[line for line in lines if not any(line.startswith(k+'=') for k in values)]
    envfile.write_text('\n'.join(lines+[k+'='+v for k,v in values.items()])+'\n')
    envfile.chmod(0o600)
    env=dict(os.environ,PYTHONPATH=str(root/'src'))
    subprocess.run([str(python),'scripts/check-party-exam.py','--hardware'],cwd=root,env=env,check=True)
    subprocess.run(['sudo','-n','systemctl','restart','artifact.service'],check=True)
    time.sleep(5)
    subprocess.run(['systemctl','is-active','--quiet','artifact.service'],check=True)
    (root/'.deploy/party-exam-ready.json').write_text(json.dumps({'installed_at':time.time(),'backup':str(backup),'manifest':manifest,'physical_print_verified':False},indent=2))
    print('Installed. Physical camera/AI/print canary still required. Backup:',backup)
except Exception:
    for name in changed:
        if (backup/name).exists():shutil.copy2(backup/name,root/name)
        elif (root/name).exists():(root/name).unlink()
    subprocess.run(['sudo','-n','systemctl','restart','artifact.service'],check=False)
    print('Installation failed; original files and environment restored:',backup)
    raise
finally:
    if timer_active:subprocess.run(['sudo','-n','systemctl','start','artifact-update.timer'],check=True)
