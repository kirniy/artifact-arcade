#!/usr/bin/env python3
"""Readiness probe. Never issues a student ID, awards a prize or sends Telegram."""
import argparse,asyncio,os
from io import BytesIO
from pathlib import Path
from PIL import Image
from artifact.printing.party_exam_roll import PartyExamRollReceiptGenerator
from artifact.services.vnvnc_kiosk import VNVNCKioskClient,KioskClientError

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--hardware',action='store_true');args=parser.parse_args()
    image=Image.new('RGB',(300,400),'white');buf=BytesIO();image.save(buf,'PNG')
    for night in ('2026-09-18','2026-09-19'):
        result=PartyExamRollReceiptGenerator().generate_receipt('photobooth',{
            'night':night,'student_number':26091841,'caricature':buf.getvalue(),
            'claim_url':'https://t.me/vnvncbattlebot?start=exam_'+'a'*32})
        assert result.raw_commands and result.preview_image
    from artifact.modes.party_exam import PartyExamMode
    assert PartyExamMode.name=='party_exam'
    if args.hardware:
        from dotenv import load_dotenv
        load_dotenv(Path.cwd()/'.env',override=False)
        from artifact.hardware.printer.rp80 import auto_detect_rp80_printer
        assert auto_detect_rp80_printer(),'RP80 is not detected'
        client=VNVNCKioskClient(base_url=os.getenv('VNVNC_KIOSK_API_BASE_URL','https://api.vnvnc.ru'),
            device_id=os.getenv('ARTIFACT_KIOSK_DEVICE_ID',''),device_secret=os.getenv('ARTIFACT_KIOSK_DEVICE_SECRET',''))
        try:
            await client._request('POST','/api/party-exam/issue',{'issue_id':'0'*32,'portrait':''})
        except KioskClientError as exc:
            assert exc.code=='INVALID_PORTRAIT',f'Signed backend probe failed: {exc.code}'
        else:raise AssertionError('Backend unexpectedly accepted an empty portrait')
    print('PASS: Friday/Saturday raster, generated assets, mode import'+(', RP80 detection and signed backend authentication' if args.hardware else ''))
asyncio.run(main())
