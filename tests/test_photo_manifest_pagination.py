import json
import subprocess

from artifact.utils import s3_upload as upload


def test_direct_manifest_scan_reads_all_pages(monkeypatch):
    calls = []
    def get(params, timeout):
        calls.append(params.copy())
        token = "<IsTruncated>true</IsTruncated><NextContinuationToken>next</NextContinuationToken>" if len(calls) == 1 else "<IsTruncated>false</IsTruncated>"
        xml = f"<ListBucketResult><Contents><Key>photo{len(calls)}.png</Key><Size>2000</Size></Contents>{token}</ListBucketResult>"
        return subprocess.CompletedProcess([], 0, xml.encode(), b"")
    monkeypatch.setattr(upload, "_signed_s3_get", get)
    result = upload._list_s3_objects_direct("artifact/photobooth/")
    assert len(json.loads(result.stdout)["Contents"]) == 2
    assert calls[1]["continuation-token"] == "next"


def test_manifest_limits_only_after_sorting(monkeypatch):
    monkeypatch.setattr(upload, "_load_selectel_credentials", lambda: ("unused", "unused"))
    monkeypatch.setattr(upload, "AWS_CLI_AVAILABLE", False)
    rows = [{"Key": f"artifact/photobooth/{i}.png", "Size": 2000, "LastModified": f"2026-09-0{i}"} for i in range(1, 4)]
    monkeypatch.setattr(upload, "_list_s3_objects_direct", lambda prefix: subprocess.CompletedProcess([], 0, json.dumps({"Contents": rows}).encode(), b""))
    captured = {}
    def put(path, *args, **kwargs):
        with open(path) as handle:
            captured.update(json.load(handle))
        return subprocess.CompletedProcess([], 0, b"", b"")
    monkeypatch.setattr(upload, "_upload_local_path_to_s3", put)
    assert upload.refresh_public_photo_manifest(max_items=2)
    assert captured["total"] == 3
    assert [p["key"] for p in captured["photos"]] == [rows[2]["Key"], rows[1]["Key"]]
