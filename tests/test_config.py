import os
from pathlib import Path
import pytest
from config import get_cv_path, SHEET_NAME

def test_get_cv_path_env_override(tmp_path, monkeypatch):
    custom_cv = tmp_path / "custom_cv.pdf"
    custom_cv.write_text("dummy cv content")
    monkeypatch.setenv("CV_PATH", str(custom_cv))
    
    resolved = get_cv_path()
    assert resolved == custom_cv.resolve()

def test_get_cv_path_scans_cvs_directory(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_PATH", raising=False)
    
    cvs_dir = tmp_path / "CVs"
    cvs_dir.mkdir()
    cv_file = cvs_dir / "my_resume.pdf"
    cv_file.write_text("resume pdf")
    
    monkeypatch.setattr("config.BASE_DIR", tmp_path)
    
    resolved = get_cv_path()
    assert resolved == cv_file

def test_get_cv_path_fallback_to_sample(tmp_path, monkeypatch):
    monkeypatch.delenv("CV_PATH", raising=False)
    
    # Empty CVs dir
    cvs_dir = tmp_path / "CVs"
    cvs_dir.mkdir()
    
    sample_dir = tmp_path / "CVs_sample"
    sample_dir.mkdir()
    sample_cv = sample_dir / "sample_cv.txt"
    sample_cv.write_text("sample content")
    
    monkeypatch.setattr("config.BASE_DIR", tmp_path)
    
    resolved = get_cv_path()
    assert resolved == sample_cv

def test_sheet_name_default():
    assert isinstance(SHEET_NAME, str)
